import json
import os

from confluent_kafka import Consumer
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from simulator.orm import Base as ORMBase
from simulator.orm import DataModel2, DataModel1, DataModel3

TOPIC_TO_ORM = {"topic1": DataModel2, "topic2": DataModel1, "topic3": DataModel3}


def dump_event_to_db(event: dict, topic: str) -> None:
    """Translates event to ORM instance and dumps it to the DB

    Parameters
    ----------
    event
        Deserialized Kafka event message
    topic
        Topic of origin
    """
    try:
        model = TOPIC_TO_ORM[topic]
        instance = model(**event)

        with Session(engine) as session:
            session.add(instance)
            session.commit()
    except TypeError:
        print("ERROR: Malformed event, skip dumping")
    except IntegrityError as e:
        print(f"ERROR: Skipping event dumping because of\n{e!r}")


def run(consumer: Consumer) -> None:
    """Consumes messages from pre-defined topics until stopped manually"""

    try:
        while True:
            message = consumer.poll(1.0)

            if message is None:
                continue
            if message.error():
                print(f"Consumer error: {message.error()}")
                continue

            print(f"Received message in topic {message.topic()} @ offset {message.offset()}")
            payload = json.loads(message.value())
            dump_event_to_db(payload, message.topic())

    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    # Set up database and connection
    engine = create_engine("sqlite://", echo=False)
    ORMBase.metadata.create_all(engine)

    # Set up Kafka consumer
    kafka_server_addr = os.getenv("KAFKA_SERVER")
    consumer = Consumer(
        {"bootstrap.servers": kafka_server_addr, "group.id": "db_dump", "auto.offset.reset": "earliest"}
    )
    consumer.subscribe(list(TOPIC_TO_ORM.keys()))

    run(consumer)
    consumer.close()
