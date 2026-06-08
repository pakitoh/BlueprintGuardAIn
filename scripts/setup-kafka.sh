#!/bin/bash

# Wait for Kafka to be ready
echo "Waiting for Kafka to be ready..."
until /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server kafka:9092 &> /dev/null; do
  echo "Kafka is unavailable - sleeping"
  sleep 2
done

echo "Kafka is up - creating topics..."

# Create topics
/opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic webhook-events --partitions 3 --replication-factor 1
/opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic analysis-results --partitions 3 --replication-factor 1

# Dead-letter topics for messages that cannot be deserialized
/opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic webhook-events-dlq --partitions 3 --replication-factor 1
/opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic analysis-results-dlq --partitions 3 --replication-factor 1

echo "Kafka topics created successfully."
