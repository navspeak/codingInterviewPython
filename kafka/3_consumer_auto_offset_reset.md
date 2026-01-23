### The exact rule for auto.offset.reset 
If a consumer group has never committed offsets before, Kafka has no offsets for that group.
1. Producer produces messages
2. New consumer group joins later
3. Kafka checks (`__consumer_offsets` which an internal topic)
    - Finds no offsets for that group
    - __consumer_offsets stores:
```
Key (group, topic, partition)  → Value             Earliest           Latest            None
-------------------------------------------------------------------------------------------
(G1, orders, P0)               → 128               NA                 NA                NA
(G1, orders, P1)               → 130               NA                 NA                NA
(G2, orders, P1)               → NOT PRESENT       0                 log-end offset     NoOffsetForPartitionException
(G2, orders, P0)               → NOT PRESENT       0                 log-end offset     NoOffsetForPartitionException

Partition P0 log:  offsets: 0,1,2,3,4

__consumer_offsets:
(G1, orders, P0) → 3
(G2, orders, P0) → ❌ 

G1 resumes at offset 3
G2 must use earliest / latest / none 
```


👉 auto.offset.reset will be consulted

### Real production example (very common incident) Scenario
- Consumer group orders-svc
```
auto.offset.reset=earliest
Offsets stored in Kafka
Offset retention = 7 days
```
- What happened: Consumer was down for >7 days
- Kafka deleted offsets
- Consumer restarts
- Kafka finds no offsets 
- auto.offset.reset=earliest kicks in
-Entire topic reprocessed

Downstream systems got duplicate orders 😬 This is one of the most expensive Kafka mistakes.

### The most important nuance (this trips people up)
`auto.offset.reset` does NOT override committed offsets.
Example:
- Consumer group G1 has committed offset 500
- You restart consumer with: `auto.offset.reset=latest`
👉 Consumer will resume at 500, not jump to latest.

`auto.offset.reset` is only used when Kafka says: “I have no idea where you were.”

### Recommended defaults (battle-tested)
- Event-driven microservices
    ```
    auto.offset.reset=latest
    enable.auto.commit=false
    #Plus: Manual commits + Idempotent processing
    ```
- Batch / analytics: `auto.offset.reset=earliest`
- Financial / critical systems (strongly recommended): `auto.offset.reset=none`

Fail fast → human decision → no surprises.