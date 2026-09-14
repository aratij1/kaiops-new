"""RabbitMQ adapter for small, persistent, confirmed reference events."""
import asyncio
import json
import aio_pika


class RabbitPublisher:
    def __init__(self, exchange):
        self.exchange = exchange

    async def __call__(self, topic, envelope):
        await self.exchange.publish(aio_pika.Message(
            body=json.dumps(envelope,separators=(",", ":")).encode(),
            content_type="application/json", delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=envelope["event_id"],correlation_id=envelope["correlation_id"]),
            routing_key=topic, mandatory=True, timeout=10)


async def topology(connection, namespace, bindings):
    # bindings map consumer names to topics, ensuring fan-out between logical consumers.
    channel = await connection.channel(publisher_confirms=True,on_return_raises=True)
    await channel.set_qos(prefetch_count=1)
    exchange = await channel.declare_exchange(namespace,aio_pika.ExchangeType.TOPIC,durable=True)
    queues = {}
    for consumer, topic in bindings.items():
        queue = await channel.declare_queue(namespace + "." + consumer,durable=True)
        await queue.bind(exchange,routing_key=topic)
        queues[consumer] = queue
    return channel,RabbitPublisher(exchange),queues


async def recovery_routes(channel, namespace, consumer, topic, delay_ms=5000):
    retry_exchange=await channel.declare_exchange(namespace+".retry",aio_pika.ExchangeType.DIRECT,durable=True)
    dead_exchange=await channel.declare_exchange(namespace+".dead",aio_pika.ExchangeType.DIRECT,durable=True)
    # Explicit confirmed retry relay avoids unconfirmed broker DLX forwarding
    # and prevents one consumer's retry from fanning out to sibling subscribers.
    retry_queue=await channel.declare_queue(namespace+"."+consumer+".retry",durable=True)
    await retry_queue.bind(retry_exchange,routing_key=consumer)
    replay_exchange=await channel.declare_exchange(namespace+"."+consumer+".replay",aio_pika.ExchangeType.DIRECT,durable=True)
    main_queue=await channel.get_queue(namespace+"."+consumer)
    await main_queue.bind(replay_exchange,routing_key=topic)
    dead_queue=await channel.declare_queue(namespace+"."+consumer+".dead",durable=True)
    await dead_queue.bind(dead_exchange,routing_key=consumer)
    async def replay(message):
        async with message.process(requeue=True):
            await asyncio.sleep(delay_ms/1000)
            await replay_exchange.publish(aio_pika.Message(body=message.body,content_type=message.content_type,
                message_id=message.message_id,correlation_id=message.correlation_id,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,headers=message.headers),
                routing_key=topic,mandatory=True,timeout=10)
    await retry_queue.consume(replay)
    async def transfer(exchange, message, extra):
        await exchange.publish(aio_pika.Message(body=message.body,content_type=message.content_type,
            message_id=message.message_id,correlation_id=message.correlation_id,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,headers={**(message.headers or {}),**extra}),
            routing_key=consumer,mandatory=True,timeout=10)
    async def retry(message,attempt): await transfer(retry_exchange,message,{"kaims-attempt":attempt})
    async def quarantine(message,reason): await transfer(dead_exchange,message,{"kaims-failure":reason})
    return retry,quarantine,[retry_queue,dead_queue]
