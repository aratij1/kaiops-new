import json
import traceback
import asyncio
from ai_workbench_common.models import Context
from app import _require_context_snapshot_binding, _bind_next_rca_version, investigate_context, persist_final_investigation_snapshot, bind_context_to_snapshot, _resolve_context, _attach_rca_governance_binding, _validate_recommendation_snapshot_evidence, _apply_catalog_plan

from common.config import Settings
from common.database import create_engine, create_session_factory
from app import app, settings

async def main():
    try:
        engine = create_engine(settings)
        app.state.session_factory = create_session_factory(engine)
        
        with open('/tmp/scratch_context.json') as f:
            ctx_data = json.load(f)
        context = Context.model_validate(ctx_data)
        print('1. Context loaded for incident:', context.incident_id, flush=True)
        
        initial_snapshot = await _require_context_snapshot_binding(context)
        print('2. Initial snapshot bound:', initial_snapshot.get('snapshot_id'), flush=True)
        
        context = await _bind_next_rca_version(context)
        print('3. Bound RCA version:', context.metadata.get('rca_version'), flush=True)
        
        investigated_context, investigation_report = await investigate_context(context)
        print('4. Investigation complete. Conclusive:', investigation_report.get('conclusive'), flush=True)
        print('   Investigation conclusion:', investigation_report.get('conclusion'), flush=True)
        
        final_snapshot = await persist_final_investigation_snapshot(
            investigated_context, investigation_report, initial_snapshot["snapshot_id"],
        )
        print('5. Final snapshot persisted:', final_snapshot.snapshot_id, flush=True)
        
        context = bind_context_to_snapshot(investigated_context, snapshot=final_snapshot)
        print('6. Bound context to snapshot. Metadata keys:', list(context.metadata.keys()), flush=True)
        
        recommendation = await _resolve_context(context)
        print('7. _resolve_context done. Rec confidence:', recommendation.confidence, flush=True)
        print('   Rec root_cause:', recommendation.root_cause, flush=True)
        print('   Rec metadata iterative_investigation:', recommendation.metadata.get('iterative_investigation', {}).get('conclusive'), flush=True)
        
        _attach_rca_governance_binding(recommendation, context)
        print('8. Governance attached.', flush=True)
        
        _validate_recommendation_snapshot_evidence(recommendation, final_snapshot)
        print('9. Evidence validated.', flush=True)
        
        plan = _apply_catalog_plan(recommendation, context)
        print('10. _apply_catalog_plan done.', flush=True)
        print('    Plan execution_ready:', plan.get('execution_ready'), flush=True)
        print('    Plan target_action:', plan.get('target_action'), flush=True)
        print('    Plan commands:', plan.get('commands'), flush=True)
        print('    Plan readiness_blocks:', plan.get('readiness_blocks'), flush=True)
        print('    Rec remediation_plan:', recommendation.remediation_plan, flush=True)
        
        from common.repository import IncidentRepository
        async with app.state.session_factory() as session:
            repo = IncidentRepository(session)
            await repo.save_recommendation_as_audit(recommendation)
            await session.commit()
        print('11. repo.save_recommendation_as_audit done!', flush=True)
    except Exception as e:
        traceback.print_exc()

asyncio.run(main())
