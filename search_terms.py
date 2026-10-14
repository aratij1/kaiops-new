import os

search_terms = ['telemetry fallback', 'pattern investigation', 'advanced sre', '
k', 'failed to load sre', 'what kai knows so far', 'automated evidence collection']

for root, dirs, files in os.walk(r'C:\Users\arati.joshi'):
    # skip some huge cache dirs
    if any(p in root for p in ['.cache', '.gemini', '.antigravity-ide', '.vscode', 'AppData', 'node_modules', '.git']):
        continue
    for file in files:
        if file.endswith(('.tsx', '.jsx', '.ts', '.js', '.py', '.json', '.html', '.md', '.txt')):
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    for t in search_terms:
                        if t in content:
                            print(f'MATCH "{t}": {path}')
            except:
                pass
print("SEARCH COMPLETE")
