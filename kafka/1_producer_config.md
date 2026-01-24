### common config
1. `bootstrap.servers`
```java
Properties properties = new Properties();
properties.setProperty(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092"); // comma separated kadka brokers
```
2. `acks`
```java
properties.setProperty(ProducerConfig.ACKS_CONFIG, "all"); 
/*
0 => the producer does not wait for any acknowledgment from the broker and assumes the message has been sent successfully.
1 => leader only. Good throughput, less durability on leader failure before replication.
2 => waits for in-sync replicas. Safer, slightly lower throughput / higher latency.
```
3. The `enable.idempotence` configuration
```java
properties.setProperty(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, "true");
/*
When enable.idempotence is set to true, the producer attaches a Producer ID (PID) and a Sequence Number to every batch sent.
= Server-Side Checking: The Kafka broker must check the sequence number of every incoming batch against the last one it committed. This overhead is small but measurable.
= In-Flight Request Limit: Idempotence requires:
    max.in.flight.requests.per.connection to be 5 or less. This limits how much data you can "pipeline" through the network at once, which can lower overall throughput.
    Acks=all: Idempotence forces acks=all. The leader must wait for all in-sync replicas (ISRs) to acknowledge the write before telling the producer "I got it." This is the biggest contributor to latency.
*/
```
The Performance vs. Safety Trade-off
| Feature | Idempotent (Safe) | Non-Idempotent (Fast)|
|-|-|-|
|acks| all (High Latency) |1 or 0 (Low Latency)
|Duplicates|Zero (guaranteed)| Possible on retries|
|Ordering|Guaranteed|Risk of out-of-order messages|
|Use Case| Payments, Order Processing| Metrics, Logs, IoT sensor data|
### Serialization configurations
```java
properties.setProperty(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, "org.apache.kafka.common.serialization.StringSerializer");
properties.setProperty(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, "org.apache.kafka.common.serialization.StringSerializer");
```
### Performance tuning configurations
1. Batching:
    - `batch.size` - bytes per partition  
        - Bigger batch ⇒ fewer requests ⇒ higher throughput.
        - Too big ⇒ more memory + can increase latency if traffic is low (batch takes longer to fill).
    - `linger.ms` -time to wait to build a batch (gentle deadline to ensure nothing linges too long, even if batch isnt full)
        - Even 5–20ms can drastically increase batching (and throughput) under moderate load.
        - Tradeoff: adds up to that much extra latency.

> Rule of thumb: If you care about throughput: increase linger.ms + batch.size together. If linger size is 5 ms, it will at least wait for 5 ms before sending the batch. It can send before 5 ms if batch size fills before ms

```java
properties.setProperty(ProducerConfig.LINGER_MS_CONFIG, "10");
properties.setProperty(ProducerConfig.BATCH_SIZE_CONFIG, "100");
```
2. Buffering on the producer    
    - `buffer.memory`
        - Total memory the producer can use to buffer unsent records.
        - If too small under load, producer blocks (or times out).
    - `max.block.ms`
        - Max time send() can block when buffer is full / metadata unavailable.
        - Tune this based on how you want your app to behave under backpressure.
3. Compression
    - `compression.type` = lz4 or zstd (usually best)
        - Compression reduces bytes on wire + broker disk IO.
        - Tradeoff: CPU on producer (and consumer).
    - Practical picks:
        - lz4: very fast, great default.
        - zstd: better compression ratio; good when network is the bottleneck and you have CPU headroom.
4. In-flight requests & ordering
    -  `max.in.flight.requests.per.connection`
        - Higher can increase throughput.
        - With idempotence enabled, Kafka constrains this safely (ordering + exactly-once-ish per partition).
    - Good default: Leave it unless you’re diagnosing ordering/latency edge cases.

### Timeout configurations
```java
properties.setProperty(ProducerConfig.REQUEST_TIMEOUT_MS_CONFIG, "10");
properties.setProperty(ProducerConfig.DELIVERY_TIMEOUT_MS_CONFIG, "100");
```
### Retry configuration
```java
properties.setProperty(ProducerConfig.RETRIES_CONFIG, "3");
properties.setProperty(ProducerConfig.RETRY_BACKOFF_MS_CONFIG, "5");
```
### Others
1.  `partitioner.class`
```java
properties.setProperty(ProducerConfig.PARTITIONER_CLASS_CONFIG, UniformStickyPartitioner.class.getName());
```
- The partitioner.class configuration determines how messages are partitioned among the available partitions in a Kafka topic. 
- By default, Kafka uses a hash-based partitioner that assigns messages to partitions based on their key.
- Some examples of built-in partitioner classes in Kafka include:
    - `org.apache.kafka.clients.producer.RoundRobinPartitioner`: This partitioner assigns messages to partitions in a round-robin fashion, cycling through all available partitions. This partitioning strategy can be used when users want to distribute the writes to all partitions equally (regardless of the record key hash).
    - `org.apache.kafka.clients.producer.UniformStickyPartitioner`: This partitioner assigns messages to partitions based on a sticky algorithm that tries to maintain affinity between a producer and a particular partition. If a partition is specified in the record, it is used. Otherwise, we choose the sticky partition that changes when the batch is full.

2. `security.protocol` 
- The security protocol is used for communication with the Kafka brokers, such as PLAINTEXT, SSL, or SASL.

3. `ssl.truststore.location` and `ssl.truststore.password` 

- These are the location and password of the trust store file containing the CA certificates for SSL encryption.

----
### Latency vs throughput vs safety: profiles you can start with
#### High-throughput (still safe)
```
acks=all
enable.idempotence=true
compression.type=lz4
linger.ms=10
batch.size=131072
buffer.memory=67108864
delivery.timeout.ms=120000
request.timeout.ms=30000
```

#### Lower latency (interactive APIs)
```
acks=1
compression.type=lz4
linger.ms=0
batch.size=16384
# it means if all messages arrive at same time it will form batch of upto 16384 byte. But if messages dont arrive fast it will send whatever is there immediately
buffer.memory=33554432
```

#### Maximum throughput (analytics/firehose; accept more latency)
acks=1
compression.type=zstd
linger.ms=20
batch.size=262144
buffer.memory=134217728


### Reliability configs that affect performance indirectly
- Retries / timeouts (avoid “false failures”)
- delivery.timeout.ms (upper bound for delivery incl retries)
- request.timeout.ms (per request)
- retries (modern clients handle this; with idempotence it’s safer)
- If timeouts are too aggressive, you get unnecessary retries, which kills throughput.

#### How to know what to tune (quick diagnostic checklist)
- Are requests small and frequent? → Increase linger.ms and batch.size.
- Is network the bottleneck? → Turn on compression.type (lz4/zstd).
- Is producer CPU pegged after enabling compression? → Switch zstd → lz4 or reduce compression.
- Are you seeing buffer exhaustion / blocking? → Increase buffer.memory or reduce send rate; check `max.block.ms`.
- Are you producing to many partitions/topics? → Batching gets harder; linger.ms helps a lot.

---

`max.block.ms` : when producer calls send(), the first think it does is ask the broker for metadata - `which broker is leader for my topic?`
    - If a topic does not exist and `auto.create` is off, the producer will block and keep asking for metadata until it hits `max.block.ms.

---