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

    public OrderProducer(KafkaTemplate<String, String> kafkaTemplate, MeterRegistry registry) {
        this.kafkaTemplate = kafkaTemplate;
        this.successCounter = Counter.builder("orders.sent.success").register(registry);
        this.failureCounter = Counter.builder("orders.sent.failure").register(registry);
    }

    @Retryable(
        retryFor = { Exception.class },
        maxAttempts = 3,
        backoff = @Backoff(delay = 2000, multiplier = 2)
    )
    public void sendMessage(String message) {
        // .get() makes it synchronous so @Retryable can catch the exception
        try {
            kafkaTemplate.send("orders-topic", message).get();
            successCounter.increment();
            log.info("Message sent successfully");
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    @Recover
    public void recover(Exception e, String message) {
        log.error("All retries failed. Sending to DLT: {}", message);
        failureCounter.increment();
        kafkaTemplate.send("orders-topic.DLT", message);
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
Here is the consolidated, production-ready Spring Boot Producer. This setup accounts for your restricted environment (no auto-create permissions), incorporates retries with recovery, and includes health monitoring.

1. pom.xml
Includes Web, Kafka, AOP (for Retry), and Actuator (for Metrics).

XML
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
2. application.yml
Configured for idempotence, fail-fast behavior, and metrics exposure.

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
        max.block.ms: 5000 # Don't hang if topic is missing
        delivery.timeout.ms: 30000
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
3. Producer Service with Retry & Recovery
Handles the business logic, retries on failure, and moves "dead" messages to a DLT.

```Java
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

    public OrderProducer(KafkaTemplate<String, String> kafkaTemplate, MeterRegistry registry) {
        this.kafkaTemplate = kafkaTemplate;
        this.successCounter = Counter.builder("orders.sent.success").register(registry);
        this.failureCounter = Counter.builder("orders.sent.failure").register(registry);
    }

    @Retryable(
        retryFor = { Exception.class },
        maxAttempts = 3,
        backoff = @Backoff(delay = 2000, multiplier = 2)
    )
    public void sendMessage(String message) {
        // .get() makes it synchronous so @Retryable can catch the exception
        try {
            kafkaTemplate.send("orders-topic", message).get();
            successCounter.increment();
            log.info("Message sent successfully");
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    @Recover
    public void recover(Exception e, String message) {
        log.error("All retries failed. Sending to DLT: {}", message);
        failureCounter.increment();
        kafkaTemplate.send("orders-topic.DLT", message);
    }
}
```
4. Custom Health Indicator
Since auto-create is false, this component checks if the topic exists so your app status reflects reality.

Java
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