# Getting Started
* Distributed system : components are located on different netweork computers that coordinate their action by passing message to one another
    * Performance
    * Scalabilty
    * Availability
* 8 Fallacies of a distributed system:
    * 1. Network is Reliable   2. Network is Secure    3. Network is Homogenous    4. Network Topology don't change  
    * 5.  Latency is zero    6. Bandwidth is infinite    7. There is one admin   8. Transport cost is zero (* also The global clock fallacy not included but real) 
* Challenges:
    * n/w asynchrony (unpredictable, causing delays and messages arriving out of order). 
    * Partial Failures (it’s difficult to ensure all parts of the system stay consistent when some components fail). 
    * Concurrency: Interleaved execution, Race Condition, Deadlocks
* Correctness of a Distributed System has two properties: 
    * Safety – nothing bad ever happens
    * Liveness – something good eventually happens
* System Models: Async or Sync
* Types of failures
    * Fail-stop: A node halts and remains halted permanently. Other nodes can detect that the node has failed (i.e., by communicating with it).
    * Crash: A node halts, but silently. So, other nodes may not be able to detect this state. They can only assume its failure when they are unable to communicate with it.
    * Omission: A node fails to respond to incoming requests.
    * Byzantine: A node exhibits arbitrary behavior: it may transmit arbitrary messages at arbitrary times, take incorrect steps, or stop. Byzantine failures occur when a node does not behave according to its specific protocol or algorithm. This usually happens when a malicious actor or a software bug compromises the node. To cope with these failures, we need complex solutions. However, most companies deploy distributed systems in environments that they assume to be private and secure.
* Multiple delivery of messages: Idempotent or De-duplication approach (each message unique id - can be retried):
    * It's impossible to have `exactly-once` delivery in a distributed system. However, it's still sometimes possible to have exactly-once processing.
    * We can easily implement at-most-once delivery semantics and at-least-once delivery semantics. We can achieve the at-most-once delivery when we send every message only one time, no matter what happens. Meanwhile, we can achieve the at-least-once delivery when we send a message continuously until we get an acknowledgment from the recipient.
* Detect Failures : Large vs small timeouts
* You are designing a distributed online store where multiple servers handle orders. Sometimes servers crash, messages are delayed, or requests are duplicated. How can you ensure the system behaves correctly despite these challenges?
* To keep a distributed online store correct and reliable despite crashes, delays, and duplicate requests, you need to build in strong fault-tolerance and consistency mechanisms:
    * Use idempotent operations so repeated requests don’t change the outcome.
    * Assign a unique request or transaction ID to each order to detect and ignore duplicates.
    * Persist state using durable storage or write-ahead logs so work can resume correctly after a crash.
    * Use message queues with at-least-once delivery to ensure no order is lost, even if messages arrive late.
    * Implement timeouts and retries to handle slow or failed network communication safely.
    * Apply graceful failure handling so that partial failures don’t bring down the whole system.
    * These strategies help ensure the system behaves correctly despite the challenges of distributed environments

#  Partitioning and Replication
* Partitioning :  primary mechanisms of achieving scalability / Performace by a process of splitting datasets into multiple smaller ones and then assigning the responsibility of storing & processing them to different nodes. This allows us to add more nodes to our system and increase the size of data it can can handle. Two variations: 
    1. Vertical (1 Table (c1, c2...cN) => 2+ Table (c1..ck), (ck,...cN) => Join):
        * scatters related columns across multiple nodes, so queries needing the full record require join operations across nodes. These joins can slow down the retrieval of complete records, even though vertical partitioning helps with scalability. While vertical partitioning helps with scalability by distributing data, it can hinder the speed of queries that need the full record.
    2. Horizontal Partitioning (Shrading)
        * splitting a table into multiple, smaller tables, where each table contains a percentage of the initial table’s rows. We can then store these different subtables in different nodes. 

Algo for Horizontal Partitioning:
* Range Partioning, Hash Partitioning, Consistent Hashing
* Hybrid approach : Range + Hash. Say Node 1 - 4 (caters to US), 5-8, (EU), 9 (others). Range will decide US, EU or others and partition based on hash will distribute each geographical location, so skew can be handled.

* Replication: The technique we use to achieve availability is replication.
    * The main difference between replication and partitioning in distributed systems lies in their purpose and method of data handling. 
    * Replication involves duplicating data or components across multiple nodes to enhance fault tolerance and availability. This means if one node fails, the system can continue operating using the replicated data on other nodes. 
    * On the flip side, partitioning divides data or tasks into partitions, with each partition assigned to a specific node. This approach improves scalability and performance by enabling parallel processing and more efficient resource utilization. 

## Primary-Backup replication (leader and follower) - good for read
* synchronous replication provides increased durability. This is because the update is not lost even if the leader crashes right after it acknowledges the update. But slow
* async replication: the node replies to the client as soon as it performs the update in its local storage, without waiting for responses from the other replicas.
* Advantages of primary-backup replication
    - It is simple to understand and implement. Concurrent operations serialized in the leader node remove the need for more complicated, distributed concurrency protocols. In general, this property also makes it easier to support transactional operations
    - It is scalable for read-heavy workloads because the capacity for reading requests can be increased by adding more read replicas
* Disadvantages of primary-backup replication:
    - It is not very scalable for write-heavy workloads because a single node’s capacity (the leader’s capacity) determines the capacity for writes

It imposes an obvious trade-off between performance, durability, and consistency. Scaling the read capacity by adding more follower nodes can create a bottleneck in the network bandwidth of the leader node, if there’s a large number of followers listening for updates. The process of failing over to a follower node when the leader node crashes is not instant. This may create some downtime and also introduce the risk of errors

## Multi-Primary Replication Algorithm
- Multi-primary replication has a significant difference from primary-backup replication. In multi-primary replication, there is no single leader node that serializes the requests and imposes a single order, as write requests are concurrently handled by all the nodes. This means that nodes might disagree on what is the right order for some requests. We usually refer to this as a conflict.
- Last one wins
- Causality tracking

## Quorum:
- R+W > N
- W > N/2

- When two nodes in a distributed system receive conflicting write requests simultaneously, a multi-primary replication algorithm can resolve the conflict and ensure data consistency using several methods:

    1. Client-Driven Conflict Resolution: This method involves presenting multiple versions of the data to the client, allowing the client to select the appropriate version, thereby resolving the conflict.
    2. Last-Write-Wins (LWW) Resolution: Each node timestamps its versions locally. During a conflict, the version with the latest timestamp is chosen. However, this approach can lead to unexpected outcomes because it lacks a global notion of time, and the “latest” write might not always be the correct choice from an application logic perspective.
    3. Causality Tracking Algorithms: These algorithms track the causal relationships between different requests. In the event of a conflict, the system retains the write that is causally linked to the others, maintaining a sense of order. This method is effective for maintaining consistency, but it can be challenging when concurrent requests lack a clear causal relationship.

# PACELC 
- CAP says: During a network Partition (P), choose Availability (A) or Consistency (C). But CAP says nothing about: What happens when the network is healthy
- In reality, most of the time: There is no partition. Yet systems still make trade-offs. PACELC fills that gap.
-  PACELC stands for: If there is a Partition (P), choose Availability (A) or Consistency (C); Else (E), when there is no partition, choose Latency (L) or Consistency (C).
    - P : A or C Else → L or C
- What does “Else: Latency vs Consistency” mean?Even with no failures: 
    - Do you wait for multiple replicas to confirm a write/read?
        - Higher consistency
        - Higher latency
    - Or respond immediately from one node?
        - Lower latency
        - Weaker consistency

That’s a constant design choice.

-  Examples of systems in PACELC terms
    - DynamoDB / Cassandra → PA/EL
        - On partition → choose Availability | Else → choose Low Latency | Accept writes anywhere | Serve reads fast | Reconcile later
    - ZooKeeper / etcd → PC/EC
        - On partition → choose Consistency | Else → also choose Consistency | Use quorom | Block if cannot reach majority | Even when healthy, still wait for quorum
    - Google Spanner → PC/EC
        - Partition → consistency | Else → consistency (waits for sync + TrueTime)
    - MongoDB (majority) → PC/EL?
        - Partition → consistency | Else → lower latency reads from primary, but can allow stale reads | So it’s configurable.



