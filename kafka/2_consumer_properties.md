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
``

