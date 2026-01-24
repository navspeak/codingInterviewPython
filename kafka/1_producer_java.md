1. `pom.xml`
Includes Web, Kafka, AOP (for Retry), and Actuator (for Metrics).
```xml
<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.kafka</groupId>
        <artifactId>spring-kafka</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-aop</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.retry</groupId>
        <artifactId>spring-retry</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-actuator</artifactId>
    </dependency>
    <dependency>
        <groupId>io.micrometer</groupId>
        <artifactId>micrometer-registry-prometheus</artifactId>
    </dependency>
</dependencies>
```

2. `application.yml` Configured for idempotence, fail-fast behavior, and metrics exposure.
```yml
spring:
  kafka:
    bootstrap-servers: localhost:9092
    admin:
      auto-create: false # Restricted env: don't try to create topics on startup
    producer:
      acks: all
      enable.idempotence: true
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.apache.kafka.common.serialization.StringSerializer
      properties:
        max.block.ms: 5000 # Don't hang if topic is missing, timeout in 5s
        delivery.timeout.ms: 30000 #time betweensend and get ack which if exceeded marked message for failure no retry
        max.in.flight.requests.per.connection: 5

management:
  endpoints:
    web:
      exposure:
        include: health, prometheus
  endpoint:
    health:
      show-details: always
```
3. `TopicBuilder` - not needed here, but if we wanted to create topic

```java
import org.apache.kafka.clients.admin.NewTopic;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.TopicBuilder;

@Configuration
public class KafkaConfig {
    @Bean
    public NewTopic orderTopic() {
        return TopicBuilder.name("orders-topic")
                .partitions(3)
                .replicas(1)
                .build();
    }
}
```
```bash
kafka-topics.sh --bootstrap-server localhost:9092 --create \
--topic orders-topic \
--partitions 3 \
--replication-factor 1
```
-  Does the Producer create the topic?
    - Default Behavior (`auto.create.topics.enable=true`): If the broker is configured to allow it, the producer will trigger topic creation the moment it tries to send the first message to a non-existent topic.
    - In Spring Boot, the `KafkaAdmin` bean (which is auto-configured) looks for any NewTopic beans in your application context. On startup, it compares those beans against the topics existing in the cluster and sends a request to the broker to create any that are missing.
    - Note: These "auto-created" topics usually have default settings (often 1 partition, 1 replica), which might not match what you want, so we use TopicBuilder to override defualy.
    - Production Environment (`auto.create.topics.enable=false`): In most professional environments, this is disabled. If the topic doesn't exist, the Producer will throw a `TimeoutException` or `UnknownTopicOrPartitionException`.

3. Producer Service with Retry & Recovery: 
Handles the business logic, retries on failure, and moves "dead" messages to a DLT.
```java
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Recover;
import org.springframework.retry.annotation.Retryable;
import org.springframework.stereotype.Service;

@Service
public class OrderProducer {
    private static final Logger log = LoggerFactory.getLogger(OrderProducer.class);
    private final KafkaTemplate<String, String> kafkaTemplate;
    private final Counter successCounter;
    private final Counter failureCounter;

    public OrderProducer(KafkaTemplate<String, String> kafkaTemplate/*, MeterRegistry registry*/) {
        this.kafkaTemplate = kafkaTemplate;
        // this.successCounter = Counter.builder("orders.sent.success").register(registry);
        // this.failureCounter = Counter.builder("orders.sent.failure").register(registry);
    }

    @Retryable(
        retryFor = { Exception.class },
        maxAttempts = 3,
        backoff = @Backoff(delay = 2000, multiplier = 2)
    )
    public void sendMessage(String message) {
        // .get() makes it synchronous so @Retryable can catch the exception
        kafkaTemplate.send("orders-topic", message).get();
        // successCounter.increment();
    }

/*
     Improving Reliability without the DLT
    - If you want to avoid the "DLT may fail too" headache entirely, you can use the Local Database Pattern (Outbox Pattern):
    - Save to DB: First, save the order to your Postgres/MySQL database in an OUTBOX table.
    - Send to Kafka: Try to send to Kafka.
    - Update DB: If Kafka acknowledges, mark the DB record as SENT.
    - Background Retry: A scheduled task looks for any record in the DB that is still PENDING after 5 minutes and tries to resend it.
*/
    @Recover
    public void recover(Exception e, String message) {
        log.error("All retries failed. Sending to DLT: {}", message);
        // failureCounter.increment();
        kafkaTemplate.send("orders-topic.DLT", message);
    }

    // Fast and informative, but NO automatic @Retryable support
    public void sendMessageAsync(String message) {
    kafkaTemplate.send("orders-topic", message)
        .whenComplete((result, ex) -> {
            if (ex != null) {
                // You'd have to handle retry logic manually here
                log.error("Background failure: " + ex.getMessage());
            }
        });
}
}

// Note: Instead of manual Counter, we can have use Spring Kafka provided a MicrometerProducerListener 
// that automatically hooks into the KafkaTemplate to track successes and failures (see below)
```

```java
/*
Once this listener is attached, Micrometer will automatically generate these tags for every send attempt:
    - kafka.producer.record.send.total (Counter)
    - kafka.producer.record.errors.total (Counter)
Tags: It will automatically include tags like topic, so you can filter your Grafana dashboard by topic="orders-topic" 
without writing a single line of business logic for it.
*/
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.MicrometerProducerListener;
import org.springframework.kafka.core.ProducerFactory;

@Configuration
public class KafkaMetricsConfig {

    @Bean
    public ProducerFactory<String, String> producerFactory(
            MeterRegistry meterRegistry, 
            DefaultKafkaProducerFactory<String, String> factory) {
        
        // This line automates the success/failure tracking
        factory.addListener(new MicrometerProducerListener<>(meterRegistry));
        return factory;
    }
}
```
4. Custom Health Indicator: 
Since auto-create is false, this component checks if the topic exists so your app status reflects reality.

```java
import org.apache.kafka.clients.admin.AdminClient;
import org.apache.kafka.clients.admin.ListTopicsOptions;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.kafka.core.KafkaAdmin;
import org.springframework.stereotype.Component;
import java.util.concurrent.TimeUnit;

@Component
public class KafkaTopicHealthIndicator implements HealthIndicator {
    private final KafkaAdmin kafkaAdmin;

    public KafkaTopicHealthIndicator(KafkaAdmin kafkaAdmin) {
        this.kafkaAdmin = kafkaAdmin;
    }

    @Override
    public Health health() {
        try (AdminClient client = AdminClient.create(kafkaAdmin.getConfigurationProperties())) {
            var topics = client.listTopics(new ListTopicsOptions().timeoutMs(2000))
                               .names().get(2, TimeUnit.SECONDS);
            
            if (topics.contains("orders-topic")) {
                return Health.up().withDetail("topic", "orders-topic").build();
            }
            return Health.down().withDetail("error", "Topic 'orders-topic' missing").build();
        } catch (Exception e) {
            return Health.down(e).build();
        }
    }
}
```

5. REST Controller & Config: 
The entry point and the required annotation to enable the retry logic.

```java
import org.springframework.context.annotation.Configuration;
import org.springframework.retry.annotation.EnableRetry;
import org.springframework.web.bind.annotation.*;

@Configuration
@EnableRetry
class AppConfig {}

@RestController
@RequestMapping("/api/orders")
public class OrderController {
    private final OrderProducer orderProducer;

    public OrderController(OrderProducer orderProducer) {
        this.orderProducer = orderProducer;
    }

    @PostMapping
    public String placeOrder(@RequestBody String order) {
        orderProducer.sendMessage(order);
        return "Order received";
    }
}
```
---

### Async + DLT
- Removing blocking .get() call to gain a massive boost in throughput.
- However, you still have to decide how to handle retries. 
- Without .get(), the standard Spring `@Retryable` won't work because the exception happens on a background thread. You have two options for handling this:

#### 1. The "High Throughput" Way (Pure Async)
In this scenario, you trust the Kafka Native Retries (configured in your yml) to handle transient network issues. You lose the ability to use `@Recover` for business logic, but your API becomes lightning-fast.
```Java
public void sendMessage(String message) {
    // Fire and forget (mostly). 
    // Kafka's internal 'retries' config in yml still works here.
    kafkaTemplate.send("orders-topic", message); 
    
    // REST Controller returns immediately while Kafka handles the send in the background.
}
```
#### 2. The "Reliable Async" Way (Callbacks)
If you want the speed of async but still need to log failures or move messages to a DLT if Kafka's internal retries fail, use whenComplete.

```Java
public void sendMessage(String message) {
    kafkaTemplate.send("orders-topic", message)
        .whenComplete((result, ex) -> {
            if (ex != null) {
                // This runs on a Kafka IO thread when all native retries are exhausted
                log.error("Failed to send message after native retries", ex);
                // Manual DLT send since @Recover won't trigger
                kafkaTemplate.send("orders-topic.DLT", message);
            } else {
                log.info("Sent to partition: {}", result.getRecordMetadata().partition());
            }
        });
}
```
---
#### Outbox pattern:
- Transactional Producer (that saves the order and the message in one hit) and 
- a Message Relay (that polls the DB and sends to Kafka).

```Java
// 1. The Database Entity
// You need a table to store the messages that are "waiting" to be sent.
@Entity
@Table(name = "outbox")
public class OutboxMessage {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String topic;
    private String payload;
    private LocalDateTime createdAt;
    private boolean processed = false; // Flag to track status
}
// 2. The Service (Atomic Transaction)
// This is where you solve the "Dual Write" problem. By using @Transactional, both the order and the outbox entry succeed or fail together.

@Service
public class OrderService {
    private final OrderRepository orderRepository;
    private final OutboxRepository outboxRepository;

    public OrderService(OrderRepository orderRepository, OutboxRepository outboxRepository) {
        this.orderRepository = orderRepository;
        this.outboxRepository = outboxRepository;
    }

    @Transactional
    public void placeOrder(OrderRequest request) {
        // 1. Save the actual business data
        Order order = new Order(request.getItem(), request.getAmount());
        orderRepository.save(order);

        // 2. Save the message to the Outbox table instead of calling Kafka
        OutboxMessage outboxMessage = new OutboxMessage();
        outboxMessage.setTopic("orders-topic");
        outboxMessage.setPayload(serialize(order)); 
        outboxMessage.setCreatedAt(LocalDateTime.now());
        
        outboxRepository.save(outboxMessage);
        
        // At this point, even if the app crashes, the data is safe in the DB.
    }
}
// 3. The Message Relay (The Poller)
// This background task acts as your "internal producer." It picks up pending messages and pushes them to Kafka.

@Component
public class OutboxRelay {
    private final OutboxRepository outboxRepository;
    private final KafkaTemplate<String, String> kafkaTemplate;

    public OutboxRelay(OutboxRepository outboxRepository, KafkaTemplate<String, String> kafkaTemplate) {
        this.outboxRepository = outboxRepository;
        this.kafkaTemplate = kafkaTemplate;
    }

    @Scheduled(fixedDelay = 5000) // Poll every 5 seconds
    @Transactional
    public void publishMessages() {
        List<OutboxMessage> pendingMessages = outboxRepository.findByProcessedFalse();

        for (OutboxMessage message : pendingMessages) {
            try {
                // Send to Kafka and wait for ACK
                kafkaTemplate.send(message.getTopic(), message.getPayload()).get();
                
                // Mark as processed so it's not sent again
                message.setProcessed(true);
                outboxRepository.save(message);
            } catch (Exception e) {
                log.error("Failed to relay message {}: {}", message.getId(), e.getMessage());
                // If it fails, we don't mark as processed; it will be retried next cycle.
            }
        }
    }
}
```
#### "Latency" follow-up:
- User Latency: The user only waits for a local DB write (the placeOrder method). They do not wait for Kafka. This makes the UI feel faster.

- System Latency: The "End-to-End" latency (from order placement to Kafka) is now determined by your @Scheduled interval.

- "The Polling Drawback": downside of the code above => Polling Overhead. Polling the DB every few seconds can be intensive.

- To scale this, you would use CDC (Change Data Capture) like Debezium. Debezium watches the Postgres/MySQL transaction logs (WAL/Binlog) and streams the outbox entries to Kafka automatically with sub-millisecond latency and zero impact on the database's query performance.

- In the previous design, Application Code was the producer. In the Outbox design, the Database becomes the source of truth, and a Background Process (the Relay) becomes the actual Kafka producer.

#### The Mental Shift
1. Old Way (Direct):  User → App → Kafka (Wait for Ack) → User.
    - Problem: If Kafka is slow or down, the User waits or fails.
2. New Way (Outbox):  User → App → Database (Commit) → User.
    - Relay (Background): Database → Kafka.

**Benefit**:
- The User is "done" as soon as the DB saves. The message "eventually" arrives in Kafka a few milliseconds later.

**Does this mean you deleted the DLT?**
- Not necessarily. You just moved where it happens.

__In the Outbox Relay (the code that reads from the DB), you still have to decide what happens if Kafka rejects the message repeatedly. You have two choices:__

1. Option A: The "Retry Forever" (Strict Ordering): The relay keeps trying to send that specific outbox entry until Kafka accepts it. This ensures perfect ordering but "clogs" the relay if one message is "poison" (invalid).

2. Option B: The "Relay DLT": If the relay fails to send an outbox entry 5 times, it moves that entry to a failed_outbox table or sends it to a Kafka DLT and moves on to the next message.

** How to Answer the "Latency" Question in the Interview **
- Since you aren't sending to Kafka during the request, the User-Facing Latency is actually lower. However, the End-to-End Latency (Time from Order → Consumer) is slightly higher because of the polling interval.
- "By moving the Kafka send out of the request path and into an Outbox, I traded a small amount of end-to-end latency for guaranteed delivery. Even if Kafka is down for an hour, my users can keep placing orders, and the system will automatically drain the 'debt' in the Outbox table once Kafka returns."

Why this is safer for your "Restricted Environment"
Remember your restricted environment where you couldn't create topics?

**"What happens if the Outbox Relay sends the message but crashes before updating the DB to processed = true?"**

    - Answer: "The relay will restart, see the message as unprocessed, and send it again. This is why the Consumer must be Idempotent. The Outbox pattern guarantees at-least-once delivery, not exactly-once."

```sql
-- PRODUCER SIDE: Outbox Table
CREATE TABLE outbox (
    id UUID PRIMARY KEY,            -- Unique ID generated by the app
    topic VARCHAR(255) NOT NULL,    -- Where the message is going
    payload JSONB NOT NULL,         -- The actual order data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'PENDING' -- PENDING, SENT, FAILED
);

-- CONSUMER SIDE: Processed Messages Table
CREATE TABLE processed_messages (
    message_id UUID PRIMARY KEY,    -- Matches the ID from the outbox
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```