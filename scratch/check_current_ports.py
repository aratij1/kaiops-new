import urllib.request
import socket

# Scan ports or check what is listening
def check_port(p):
    try:
        url = f"http://127.0.0.1:{p}/healthz"
        req = urllib.request.Request(url, headers={"User-Agent": "test"})
        with urllib.request.urlopen(req, timeout=0.5) as resp:
            return resp.status, resp.read().decode('utf-8', errors='ignore')
    except Exception:
        return None, None

print("Checking port 62673...")
st, body = check_port(62673)
print(f"Port 62673: status={st}, body={body}")

print("Checking port 52888 (monitoring adapter)...")
st_ma, body_ma = check_port(52888)
print(f"Port 52888: status={st_ma}, body={body_ma}")

print("Checking port 8501 (UI)...")
try:
    with urllib.request.urlopen("http://127.0.0.1:8501", timeout=1) as resp:
        print(f"Port 8501: status={resp.status}")
except Exception as e:
    print(f"Port 8501: error={e}")
