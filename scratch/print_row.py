import urllib.request, json
req = urllib.request.Request('http://localhost:55112/auth/login', data=json.dumps({'username':'admin','password':'Admin@123456'}).encode(), headers={'Content-Type':'application/json'}, method='POST')
token = json.loads(urllib.request.urlopen(req).read().decode())['access_token']
headers = {'Authorization': f'Bearer {token}'}
r = urllib.request.Request('http://localhost:55112/incidents/inbox/feed', headers=headers)
rows = json.loads(urllib.request.urlopen(r).read().decode())['data']['rows']
inner = rows[0].get('row', {})
print('Inner keys:', list(inner.keys()))
for k in inner:
    val = inner[k]
    if isinstance(val, (str, int, float, bool)) or val is None:
        print(f"  {k}: {val}")
