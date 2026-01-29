```java
// 1. The Producer Side (Transactionally Atomic)
// This service ensures the business data and the message intent are saved together.

@Service
public class OrderService {
    private final OrderRepository orderRepository;
    private final OutboxRepository outboxRepository;


    @Transactional
    // Atomic Consistency: Everything happens inside one @Transactional block. If the unblock fails, the whole order placement rolls back.
    @Transactional
    public void process(CreditAgreementEvent event) {
        final String caId = event.caId();
        final int incomingVersion = event.version();
        final String payloadJson = event.payloadJson();

        // ------------------------------------------------------------
        // 1) UPSERT incoming event into outbox
        //
        // SQL (concept):
        //   -- blocked = 0 only for v1 (create). Everything else defaults blocked.
        //   INSERT INTO ca_outbox(ca_id, version, payload, status, is_blocked, created_at, updated_at)
        //   VALUES (:caId, :incomingVersion, :payload::jsonb, 'PENDING', :blocked, now(), now())
        //   ON CONFLICT (ca_id, version)
        //   DO UPDATE SET payload = EXCLUDED.payload,
        //                 updated_at = now();
        //
        // Notes:
        // - We keep status as-is on conflict (or you can force back to PENDING if your policy allows).
        // - PK (ca_id, version) provides idempotency.
        // ------------------------------------------------------------
        boolean blocked = incomingVersion != 1;

        jdbc.update(
            """
            INSERT INTO ca_outbox (ca_id, version, payload, status, is_blocked, created_at, updated_at)
            VALUES (:caId, :incomingVersion, CAST(:payload AS jsonb), 'PENDING', :blocked, now(), now())
            ON CONFLICT (ca_id, version)
            DO UPDATE SET
              payload    = EXCLUDED.payload,
              updated_at = now()
            """,
            Map.of(
                "caId", caId,
                "incomingVersion", incomingVersion,
                "payload", payloadJson,
                "blocked", blocked
            )
        );

        // ------------------------------------------------------------
        // 2) howManyVersionsLTE = COUNT(*) where version <= incomingVersion
        //
        // SQL (concept):
        //   SELECT COUNT(*)
        //   FROM ca_outbox
        //   WHERE ca_id = :caId AND version <= :incomingVersion;
        //
        // We only bother recomputing contiguous prefix when incomingVersion
        // "closes" the prefix up to itself (cnt == incomingVersion).
        // This is an optimization to avoid running the window-function update
        // on every out-of-order version that clearly can't unblock anything yet.
        // ------------------------------------------------------------
        Integer cnt = jdbc.queryForObject(
            """
            SELECT COUNT(*)
            FROM ca_outbox
            WHERE ca_id = :caId
              AND version <= :incomingVersion
            """,
            Map.of("caId", caId, "incomingVersion", incomingVersion),
            Integer.class
        );

        int howManyVersionsLTE = (cnt == null ? 0 : cnt);

        if (howManyVersionsLTE != incomingVersion) {
            // Not contiguous up to incomingVersion yet → nothing new to unblock.
            // Relay will continue to publish only (PENDING AND is_blocked=false).
            return;
        }

        // ------------------------------------------------------------
        // 3) Recompute and enforce contiguous prefix using ROW_NUMBER == version
        //    and keep non-contiguous versions blocked.
        //
        // SQL (your approach):
        //   WITH ordered AS (
        //     SELECT ca_id, version,
        //            ROW_NUMBER() OVER (PARTITION BY ca_id ORDER BY version) AS rn
        //     FROM ca_outbox
        //     WHERE ca_id = :caId
        //   ),
        //   contig_max AS (
        //     SELECT COALESCE(MAX(version), 0) AS max_contig
        //     FROM ordered
        //     WHERE version = rn
        //   )
        //   UPDATE ca_outbox
        //   SET is_blocked = CASE
        //                     WHEN version <= (SELECT max_contig FROM contig_max)
        //                     THEN false ELSE true
        //                   END,
        //       updated_at = now()
        //   WHERE ca_id = :caId
        //     AND status = 'PENDING';
        //
        // Behavior:
        // - If versions present are {1..N} contiguous, max_contig=N and we unblock <=N.
        // - If there's a gap, max_contig stops before the first missing version.
        // - This is idempotent and self-healing (enforces an invariant each run).
        // ------------------------------------------------------------
        jdbc.update(
            """
            WITH ordered AS (
              SELECT
                ca_id,
                version,
                ROW_NUMBER() OVER (PARTITION BY ca_id ORDER BY version) AS rn
              FROM ca_outbox
              WHERE ca_id = :caId
            ),
            contig_max AS (
              SELECT COALESCE(MAX(version), 0) AS max_contig
              FROM ordered
              WHERE version = rn
            )
            UPDATE ca_outbox
            SET is_blocked = CASE
                              WHEN version <= (SELECT max_contig FROM contig_max) THEN false
                              ELSE true
                            END,
                updated_at = now()
            WHERE ca_id = :caId
              AND status = 'PENDING'
            """,
            Map.of("caId", caId)
        );
    }

    // Example event record (adjust to your actual event schema)
    public record CreditAgreementEvent(String caId, int version, String payloadJson) {}
}

// 2. The Relay (Polling & Error Management)
// This background task bridges the DB to Kafka. It handles retries and "poison pill" detection.
// I use a Strictly Sequenced Outbox. My placeOrder logic buffers out-of-order events using an is_blocked flag. Then, my Relay uses a Self-Correcting SQL query that prevents 'version skipping.' This ensures that even if the external system is chaotic, my Kafka topic remains a perfectly ordered stream of truth for all downstream consumers."
public void relay() {
    /* * SQL: The "Strict Sequence" Fetch
     * We select messages that are:
     * 1. Not blocked (is_blocked = false)
     * 2. Not yet sent (status = 'PENDING')
     * 3. AND there is no PENDING message for the same order with a LOWER version.
     * (This ensures v2 is never sent if v1 is still pending/blocked)
     */
    String fetchSql = """
        SELECT * FROM outbox o1
        WHERE o1.status = 'PENDING'
        AND o1.is_blocked = false
        AND NOT EXISTS (
            SELECT 1 FROM outbox o2
            WHERE o2.order_id = o1.order_id
            AND o2.version < o1.version
            AND o2.status = 'PENDING'
        )
        ORDER BY o1.created_at ASC
        LIMIT 100;
    """;

    List<OutboxMessage> messages = jdbcTemplate.query(fetchSql, rowMapper);

    for (OutboxMessage msg : messages) {
        try {
            // Send to Kafka with the OrderID as the Key for Partition Ordering
            kafkaTemplate.send("orders-topic", msg.getOrderId().toString(), msg.getPayload());
            
            /* * SQL: Mark as Sent
             * UPDATE outbox SET status = 'SENT', sent_at = NOW() WHERE id = ?;
             */
            markAsSent(msg.getId());
        } catch (Exception e) {
            log.error("Failed to relay message {}", msg.getId(), e);
        }
    }
}
// 3. The Consumer Side (Idempotent Deduplication)
// This ensures that even if the Relay sends the message twice (at-least-once), the business logic only executes once.

@Service
public class InventoryConsumer {
    private final ProcessedMessageRepository processedRepo;

    @KafkaListener(topics = "orders-topic", groupId = "inventory-group")
    @Transactional
    public void consume(String payload, @Header(KafkaHeaders.RECEIVED_KEY) String messageId) {
        UUID id = UUID.fromString(messageId);

        // 1. Idempotency Check (The "Gatekeeper")
        if (processedRepo.existsById(id)) {
            log.warn("Duplicate message detected: {}. Skipping.", id);
            return; 
        }

        // 2. Business Logic (Deduct stock, etc.)
        updateInventory(payload);

        // 3. Mark as Processed in the same DB transaction
        processedRepo.save(new ProcessedMessage(id, LocalDateTime.now()));

        /* CLI VERIFICATION (CONSUMER LAG):
           kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group inventory-group
        */
    }
}
// 4. The SQL Entities 

@Entity
@Table(name = "outbox")
public class OutboxMessage {
    @Id
    // Use a manual UUID or String to match the business Order ID
    // This allows for end-to-end tracing and deduplication
    private UUID id; // Generated by OrderService
    private String topic;
    @Column(columnDefinition = "TEXT")
    private String payload;
    @Enumerated(EnumType.STRING)
    private OutboxStatus status; 
    //If this message has failed 5 times, mark it as FAILED and stop trying.
    // You can then set up an alert on your Grafana dashboard for any rows where status = 'FAILED'.
    private int retryCount;
    private LocalDateTime createdAt;
    @Version
    private Long version; // Optimistic locking for scaling multiple relays
}
public enum OutboxStatus {
    PENDING, RETRYING, SENT, FAILED
}
@Entity
@Table(name = "processed_messages")
public class ProcessedMessage {
    @Id
    private UUID messageId; // Matches Outbox ID
    private LocalDateTime processedAt;
}
```

```sql
-- See how many messages are stuck and how many times they've been retried
SELECT status, count(*), avg(retry_count) 
FROM outbox 
GROUP BY status;

-- Find specific "poison pills"
SELECT id, payload FROM outbox WHERE retry_count > 5;
```

> In this architecture, that single piece of data (the UUID/OrderID) carries three distinct "passports" as it travels through your system.

Here is the breakdown of why that specific identifier is doing triple-duty:

1. The Partition Key (Kafka Layer)
    - When the Relay sends the message, it uses the orderId as the Kafka Key.
    - The Benefit: Kafka uses a hash of this key to determine which partition the message goes to.
    - Why it matters: It ensures that all events for a specific order (Created, Updated, Cancelled) always land in the same partition, preserving Strict Ordering. You won't accidentally process a "Cancellation" before the "Creation."

2. The Idempotency Key (Consumer Layer)
    - When the Consumer receives the message, it treats the orderId /UUID as a unique fingerprint.
    - The Benefit: Since Kafka guarantees `"At-Least-Once"` delivery, you might get the same message twice if a network ACK was lost.
    - Why it matters: By checking the processed_messages table for that orderId, the consumer can say, "I've seen this ID before, I'm not going to charge the customer's credit card again."

3. The Audit Key (Troubleshooting Layer)
    - This is where the Kafka CLI becomes your best friend during a production incident.

#### "Is there ever a reason NOT to use the OrderID as the Partition Key?"

- Only if a single OrderID generates a massive amount of traffic that would cause a Hot Partition. For example, if one 'Order' had 1 million sub-items, that partition would grow too large while others stay empty. But for standard e-commerce or banking, using the Business ID (OrderID) is the gold standard for both partitioning and idempotency."

#### Tombstone
```Java
@Component
public class TableCleaner {
    
    @Scheduled(cron = "0 0 2 * * *") // Every night at 2 AM
    @Transactional
    public void cleanup() {
        // Delete processed IDs older than 7 days
        LocalDateTime limit = LocalDateTime.now().minusDays(7);
        processedRepo.deleteByProcessedAtBefore(limit);
        
        // Delete Outbox messages already SENT older than 1 day
        outboxRepo.deleteByStatusAndCreatedAtBefore(OutboxStatus.SENT, LocalDateTime.now().minusDays(1));
    }
}
```