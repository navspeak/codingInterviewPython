### Creatong topic
```
cd /app/confluent-7.9.1/bin

./kafka-topics --bootstrap-server localhost:9092 \
               --create \
               --partitions 2 \
               --replication-factor 1 \
               --topic test \
``

### Console Consumer
```
./kafka-console-consumer --bootstrap-server localhost:9092 --topic test
```