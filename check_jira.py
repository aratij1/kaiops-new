import httpx

email = 'arati.joshi@datamatics.com'
token = 'ATATT3xFfGF0rxaWogDEoBfLnOHUW9CkLrQkixfULhhZ3cBYG5N2dw2c3z5b8cWxEJ5z7TujZY3cKhOCe00cuU6GZT-OKC0Y6eNcSmExIS7FPJcI2Ng86K0eOc65OO9y272jEUZRJ2E0gmczZU3y59aD5Lqy74VUeaFYO-xsZ3TURTMSo2wtN_s=D6DA4A9B'
base_url = 'https://kaiops-test.atlassian.net'

r = httpx.get(f'{base_url}/rest/api/2/issue/KAN-2247/transitions', auth=(email, token))
print('Transitions Status:', r.status_code)
for t in r.json().get('transitions', []):
    print(f"ID: {t['id']}, Name: {t['name']}, To: {t['to']['name']}")
