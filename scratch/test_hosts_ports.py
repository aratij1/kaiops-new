import urllib.request

for host in ["localhost", "127.0.0.1", "[::1]"]:
    for port in [80, 62673, 52888, 8027, 8501]:
        url = f"http://{host}:{port}/healthz" if port != 80 and port != 8501 else f"http://{host}:{port}/"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "test"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                print(f"SUCCESS: {url} -> HTTP {resp.status}")
        except Exception as e:
            # print(f"FAIL: {url} -> {e}")
            pass
