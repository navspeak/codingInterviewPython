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
</dependencies>
```

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