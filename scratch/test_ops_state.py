import asyncio
import pymysql
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import json
from common.repository import ContextEnrichmentRepository

async def main():
    engine = create_async_engine("mysql+aiomysql://kaiops:kaiops@127.0.0.1:3307/kaiops")
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        repo = ContextEnrichmentRepository(session)
        state = await repo.incident_operations_state(
            tenant_id="default",
            incident_id="de350ed1804a4d518bc78eeaa6c32b9b"
        )
        print("lifecycle_state:", state.get("lifecycle_state"))
        print("validation:", json.dumps(state.get("validation"), indent=2))
        print("execution:", json.dumps(state.get("execution"), indent=2))
        print("investigation_workspace rca status:", state.get("investigation_workspace", {}).get("rca", {}).get("status"))

asyncio.run(main())
