import urllib.request

for p, name in [(64592, 'api-gateway'), (64593, 'monitoring-adapter'), (8501, 'ui')]:
    try:
        url = f'http://localhost:{p}/healthz' if p != 8501 else f'http://localhost:{p}/'
        with urllib.request.urlopen(url, timeout=5) as resp:
            print(f'{name} (port {p}): HTTP {resp.status}')
    except Exception as e:
        print(f'{name} (port {p}): {e}')
