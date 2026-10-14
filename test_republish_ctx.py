import asyncio
import json
import pymysql
from common.rabbitmq import RabbitMQProducer
from common.config import Settings
from common.topics import CONTEXT_EVENTS

conn = pymysql.connect(host='mysql', user='root', password='root', database='kaiops')
cur = conn.cursor()
cur.execute("SELECT payload FROM resolution_outbox WHERE event_id='context:7b9b5012-8cb5-4884-a9d5-ffcc32290cd9:d76e5b59-2b8e-5431-995f-131e394d2371'")
row = cur.fetchone()
payload = json.loads(row[0])
payload['event_id'] = 'context:7b9b5012-8cb5-4884-a9d5-ffcc32290cd9:test-run-3'

settings = Settings()

async def send():
    p = RabbitMQProducer(settings)
    await p.start()
    await p.publish(CONTEXT_EVENTS, payload, key='7b9b5012-8cb5-4884-a9d5-ffcc32290cd9')
    await p.stop()
    print("SUCCESS: Context event published to RabbitMQ!")

asyncio.run(send())
