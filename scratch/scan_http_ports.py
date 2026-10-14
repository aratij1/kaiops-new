import urllib.request
import urllib.error

ports = [3307, 5040, 5672, 6380, 8012, 8013, 8014, 8015, 8016, 8017, 8018, 8019, 8020, 8022, 8027, 8028, 8083, 52888, 53460, 61979, 62002, 62005, 62006, 62007, 62673, 62677, 62678, 62680, 80, 8501]

for p in ports:
    for path in ["/", "/healthz", "/docs"]:
        url = f"http://127.0.0.1:{p}{path}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "test"})
            with urllib.request.urlopen(req, timeout=0.3) as resp:
                print(f"ALIVE: {url} -> HTTP {resp.status}")
                break
        except urllib.error.HTTPError as e:
            print(f"ALIVE (HTTP {e.code}): {url}")
            break
        except Exception:
            pass
