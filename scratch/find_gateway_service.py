with open('docker-compose.yml', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

import re
matches = re.finditer(r'^\s+api-gateway:\s*$', text, re.MULTILINE)
for m in matches:
    start = m.start()
    print("Found service declaration at offset", start)
    print(text[start:start+1200])
