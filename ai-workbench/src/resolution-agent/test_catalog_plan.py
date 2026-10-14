import json
import traceback
from ai_workbench_common.models import Context
from common.models import Recommendation

try:
    with open('/tmp/scratch_context.json') as f:
        ctx_data = json.load(f)
    ctx = Context.model_validate(ctx_data)
    rec = Recommendation(
        tenant_id=ctx.tenant_id,
        incident_id=ctx.incident_id,
        root_cause='The service process or container for robot-shop-rabbitmq terminated or failed to respond.',
        confidence=0.9109,
        impact='high',
        recommended_action='restart_service',
        severity=ctx.alert.severity,
        rationale='RabbitMQ is down',
        metadata={'iterative_investigation': {'conclusive': True, 'conclusion': {'confidence': 0.9109}}}
    )
    from app import _catalog_plan_for, _apply_catalog_plan
    plan = _catalog_plan_for(ctx, {}, rec)
    print('Catalog plan id:', plan.get('playbook_id'))
    print('Catalog plan commands:', plan.get('commands'))
    print('Catalog plan target_action:', plan.get('target_action'))
    print('Catalog plan readiness_blocks:', plan.get('readiness_blocks'))
    applied = _apply_catalog_plan(rec, ctx, {})
    print('Applied plan target_action:', applied.get('target_action'))
    print('Applied plan commands:', applied.get('commands'))
    print('Applied plan readiness_blocks:', applied.get('readiness_blocks'))
    print('Applied plan execution_ready:', applied.get('execution_ready'))
    print('Applied plan requires_approval:', applied.get('requires_approval'))
    print('Rec remediation_plan:', rec.remediation_plan)
except Exception as e:
    traceback.print_exc()
