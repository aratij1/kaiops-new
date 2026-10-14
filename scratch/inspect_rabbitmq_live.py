import json
import urllib.request

url = "http://localhost:15672/api/queues"
password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
password_mgr.add_password(None, url, "guest", "guest")
handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
opener = urllib.request.build_opener(handler)

try:
    with opener.open(url, timeout=5) as resp:
        queues = json.loads(resp.read().decode())
        print(f"Total RabbitMQ queues: {len(queues)}")
        for q in sorted(queues, key=lambda x: x.get("name", "")):
            print(f"  Queue: {q.get('name'):35} | Messages: {q.get('messages', 0):3} | Consumers: {q.get('consumers', 0):2}")
except Exception as e:
    print("Failed to query RabbitMQ Management API:", e)
