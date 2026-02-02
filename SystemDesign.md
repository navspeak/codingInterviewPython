|kafka Cluster|
|-|
|Broker -1 (are just servers)|
|Broker -2 (store data. serves prod/cons)|
|Broker -3 (Participate in replication)

|Topic: Order-events|
|-|
|3 Partition, replication factor 2|

order-events : P0, P1, P2
Partition Layout (with Leaders)

Broker-1:
  - order-events-P0 (Leader)
  - order-events-P2 (Follower)

Broker-2:
  - order-events-P1 (Leader)
  - order-events-P0 (Follower)

Broker-3:
  - order-events-P2 (Leader)
  - order-events-P1 (Follower)

Producer => {
  "orderId": "ORD-101",
  "eventType": "ORDER_CREATED",
  "customerId": "C123"
}

Message (partion Key) = order ID => hash (orderId) % 3 => P1

|Write Flow|
|-|
Only the leader Partition accepts writes. Exactly 1 Leader per partition

* Producer -> Broker-2 Leader of Partition 1 -> Append to log => replicate to follower -> Broker 3
* Inside Partition: P1 (order events)
    * Offset is guaranteed only within a partition
    * offsets are per partition

    | offset| Msg|
    |-|-|
    |0| ORD-100 CREATED
    |1| ORD-101 CREATED
    |2| ORD-101 PAID



