with open('frontend/react/src/App.jsx', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        if 'loadIncidentMetadata' in line:
            print(f'{i}: {line.strip()[:120]}')
        if 'pendingApprovals' in line and ('const' in line or '=' in line):
            print(f'{i}: {line.strip()[:120]}')
