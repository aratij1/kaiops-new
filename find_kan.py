import subprocess

containers = subprocess.check_output('docker ps -q', shell=True).decode().split()
for c in containers:
    name = subprocess.check_output(f'docker inspect -f "{{{{.Name}}}}" {c}', shell=True).decode().strip()
    try:
        logs = subprocess.check_output(f'docker logs {c} 2>&1', shell=True).decode(errors='ignore')
        if 'KAN-2247' in logs:
            print(f'FOUND KAN-2247 in {name}')
    except Exception as e:
        print(f'error in {name}: {e}')
