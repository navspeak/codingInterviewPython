### Common configurations
```java
Properties props = new Properties();
// comman separted list
props.setProperty(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
props.setProperty(ConsumerConfig.GROUP_ID_CONFIG, "data-archival-app");
```

### Offset management
```java

    props.setProperty(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, "true");
    props.setProperty(ConsumerConfig.AUTO_COMMIT_INTERVAL_MS_CONFIG, "5000"); 
    /* 1.  applicable when ENABLE_AUTO_COMMIT_CONFIG = true
       2.  auto commits at 5 secs | enabling auto-commit can result in data loss if the consumer dies before the commit. 
       3.  Additionally, if we set the auto.commit.interval.ms configuration to a very low value, the consumer may spend too much time committing offsets and not enough time processing messages, leading to a decrease in overall throughput.
     */

    props.setProperty(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "latest");
```

### Fetching configurations
```java
props.setProperty(ConsumerConfig.MAX_POLL_RECORDS_CONFIG, "10");
props.setProperty(ConsumerConfig.FETCH_MIN_BYTES_CONFIG, "1024");
props.setProperty(ConsumerConfig.FETCH_MAX_BYTES_CONFIG, "4096");
props.setProperty(ConsumerConfig.FETCH_MAX_WAIT_MS_CONFIG, "5000");
```

### Session management
```java
//heartbeat.interval.ms  < session.timeout.ms value to ensure that the consumer sends heartbeats to the broker at a sufficient rate to keep the session alive.
props.setProperty(ConsumerConfig.HEARTBEAT_INTERVAL_MS_CONFIG, "1000");
//session.timeout.ms =  maximum time (in milliseconds) that the broker waits for a heartbeat from the consumer before considering it dead and initiating a rebalance. This value should be set higher than the heartbeat.interval.ms value to avoid false rebalances caused by a slow network or high load on the consumer side. However, setting it too high can cause slow rebalances and delays in detecting dead consumers. It’s considered a best practice to set this value to a few times the heartbeat.interval.ms value.
props.setProperty(ConsumerConfig.SESSION_TIMEOUT_MS_CONFIG, "5000");
// max.poll.interval.ms = maximum time in milliseconds that the consumer is allowed to spend processing a single batch of records before a new poll() call is made. If this time is exceeded, the consumer is considered inactive, and its partitions are reassigned to another consumer. We must set this value to a reasonable time that allows the consumer to process a batch of records without causing a rebalance. Setting this value too low can cause frequent rebalances and disrupt the processing flow, whereas setting it too high can cause inactive consumers to remain in the group and consume resources. It is considered a best practice to set this value to a few times the maximum processing time of a batch.
props.setProperty(ConsumerConfig.MAX_POLL_INTERVAL_MS_CONFIG, "3000");

```

### Session management
```java
props.setProperty(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, "org.apache.kafka.common.serialization.StringDeserializer");
props.setProperty(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, "org.apache.kafka.common.serialization.StringDeserializer");
```