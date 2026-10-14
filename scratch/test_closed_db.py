import asyncio
import os
import sys

# Ensure backend/src/common is in sys.path
sys.path.insert(0, os.path.abspath('backend/src/common'))

from common.database import get_engine, get_session_factory
from common.repository import IncidentRepository
from sqlalchemy import text

async def test():
    engine = get_engine()
    sf = get_session_factory()
    async with sf() as session:
        res = await session.execute(text("SELECT incident_id, tenant_id, status FROM incident_projections WHERE status IN ('closed', 'resolved')"))
        rows = res.all()
        print('Direct SQL closed projections count:', len(rows))
        for r in rows:
            print('  Row:', r)

        res_all = await session.execute(text("SELECT incident_id, tenant_id, status FROM incident_projections ORDER BY updated_at DESC LIMIT 5"))
        print('\nLatest 5 projections:')
        for r in res_all.all():
            print('  Row:', r)

        repo = IncidentRepository(session)
        closed_default = await repo.list_closed_incidents(tenant_id='default')
        print('\nrepo.list_closed_incidents(tenant_id="default") count:', len(closed_default))
        if closed_default:
            print('Sample closed item:', closed_default[0])

if __name__ == '__main__':
    asyncio.run(test())
