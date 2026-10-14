import urllib.request

for p in [62673, 52888, 80, 8501]:
    try:
        url = f"http://localhost:{p}/healthz" if p not in (80, 8501) else f"http://localhost:{p}/"
        with urllib.request.urlopen(url, timeout=3) as resp:
            print(f"Port {p} -> HTTP {resp.status}")
    except Exception as e:
        print(f"Port {p} -> {e}")
