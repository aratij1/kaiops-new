with open('frontend/react/src/App.jsx', 'r', encoding='utf-8') as f:
    for idx, line in enumerate(f, 1):
        if 'homeDetailTab ===' in line or 'Resolve' in line:
            if any(k in line for k in ['execution', 'evidence', 'audit', 'overview', 'tab', 'Tab']):
                print(f'{idx}: {line.strip()[:120]}')
