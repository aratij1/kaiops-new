"""Run three explicitly scoped external availability incidents through verification."""
import run_current_kaims_recovery as runner
runner.COHORT=runner.ROOT/"docs/architecture/external-recovered-cohort-2026-09-07.json"
runner.RESULT=runner.ROOT/"docs/architecture/external-recovered-run-2026-09-07.json"
runner.COMMENT="User requested closure of the displayed incidents. The original external endpoints have resumed responding. Independently verify each linked availability/probe-success signal, HTTPS transport and full stability window; no local corrective execution or internal application recovery is asserted."
if __name__=="__main__":runner.main()
