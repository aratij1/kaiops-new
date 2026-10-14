with open('docker-compose.yml', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

import re
m = re.search(r'api-gateway:.*?(?=^[a-zA-Z0-9_-]+:|\Z)', text, re.DOTALL | re.MULTILINE)
if m:
    print(m.group(0)[:1000])
