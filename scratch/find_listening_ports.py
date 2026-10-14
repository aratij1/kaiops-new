import subprocess
import re

res = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
lines = res.stdout.splitlines()
listening = [l for l in lines if "LISTENING" in l]
print(f"Total listening sockets: {len(listening)}")
for l in listening:
    if any(p in l for p in [":80", ":5", ":6", ":3"]):
        print(" ", l)
