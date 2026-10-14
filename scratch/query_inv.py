import pymysql
import json

conn = pymysql.connect(host='127.0.0.1', port=3307, user='root', password='root', database='kaiops')
with conn.cursor() as cur:
    cur.execute('SELECT incident_id, status, stop_reason, conclusion, missing_sources, payload FROM resolution_investigations ORDER BY started_at DESC LIMIT 2')
    for r in cur.fetchall():
        print('Incident:', r[0], 'Status:', r[1], 'Stop:', r[2])
        print('Conclusion:', r[3])
        print('Missing sources:', r[4])
        p = json.loads(r[5]) if isinstance(r[5], str) else r[5]
        for h in p.get('hypotheses', [])[:4]:
            print('  H:', h.get('claim')[:60], '| status:', h.get('status'), '| conf:', h.get('confidence'), '| indep_src:', h.get('independent_sources'), '| supp:', h.get('supporting_evidence_ids'))
