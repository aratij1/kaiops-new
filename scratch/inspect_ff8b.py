import pymysql
import json

conn = pymysql.connect(host='127.0.0.1', port=3307, user='root', password='root', database='kaiops')
with conn.cursor() as cur:
    cur.execute("SELECT projection_payload FROM incident_projections WHERE incident_id LIKE %s", ('%ff8b909b%',))
    row = cur.fetchone()
    if row:
        p = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        print('Root cause:', p.get('root_cause'))
        print('Confidence:', p.get('confidence'))
        print('Impact:', p.get('customer_impact'))
        print('Action:', p.get('recommended_action'))
        print('Metadata rca_status:', p.get('metadata', {}).get('rca_status'))
        rec = p.get('metadata', {}).get('recommendation', {})
        print('Recommendation root_cause:', rec.get('root_cause'))
        print('Recommendation confidence:', rec.get('confidence'))
        print('Iterative investigation:', json.dumps(p.get('metadata', {}).get('iterative_investigation'), indent=2))
