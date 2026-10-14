import json
import subprocess
import urllib.request
import re

def main():
    res = subprocess.run(['docker', 'ps', '--format', '{{json .}}'], capture_output=True, text=True)
    containers = [json.loads(line) for line in res.stdout.strip().split('\n') if line]

    print(f"Total running containers: {len(containers)}\n")
    
    # Map port patterns: e.g. 0.0.0.0:51441->8000/tcp or 127.0.0.1:8501->80/tcp
    service_status = []
    
    for c in sorted(containers, key=lambda x: x['Names']):
        name = c['Names']
        status = c['Status']
        ports_str = c.get('Ports', '')
        
        # Extract host ports
        host_ports = re.findall(r'(?:0\.0\.0\.0|127\.0\.0\.1|\[::\]):(\d+)->', ports_str)
        host_ports = sorted(list(set(host_ports)))
        
        http_check = "N/A"
        if host_ports:
            port = host_ports[0]
            # Try health check
            paths = ['/healthz', '/', '/login'] if name.endswith('jenkins-1') else ['/healthz', '/']
            for path in paths:
                url = f"http://127.0.0.1:{port}{path}"
                try:
                    req = urllib.request.Request(url, headers={'User-Agent': 'HealthCheck/1.0'})
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        http_check = f"HTTP {resp.status} on {port}{path}"
                        break
                except Exception as e:
                    http_check = f"Err on {port}{path}: {type(e).__name__}"
        
        service_status.append({
            'name': name,
            'status': status,
            'ports': host_ports,
            'http': http_check
        })
        print(f"[{name}]")
        print(f"  Status : {status}")
        print(f"  Ports  : {host_ports}")
        print(f"  Check  : {http_check}\n")

if __name__ == '__main__':
    main()
