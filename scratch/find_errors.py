import subprocess

proc = subprocess.run(["docker", "logs", "--tail", "200", "kaims-latest-monitoring-adapter-1"], capture_output=True, text=True, errors="replace")
lines = proc.stdout.splitlines() + proc.stderr.splitlines()
errors = [line for line in lines if any(k in line.lower() for k in ["error", "exception", "traceback", "failed", "500"])]
for e in errors[-25:]:
    print(e)
