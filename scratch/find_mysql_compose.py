with open('docker-compose.yml', 'rb') as f:
    raw = f.read()
print('Length:', len(raw))
print('Null bytes:', b'\x00' in raw)
text = raw.decode('utf-8', errors='ignore')
lines = [l for l in text.splitlines() if 'mysql' in l.lower()]
print('MySQL lines found:', len(lines))
for l in lines[:15]:
    print(' ', l)
