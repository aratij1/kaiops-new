"""Configured latency thresholds must have exact cumulative bucket boundaries."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/"backend/src/common"))
from common.telemetry import REQUEST_LATENCY

def test_latency_buckets_distinguish_healthy_and_threshold_breaching_requests():
    metric=REQUEST_LATENCY.labels("bucket-regression", "request")
    metric.observe(1.1);metric.observe(1.6);metric.observe(2.1);metric.observe(3.1)
    buckets={float(s.labels["le"]):s.value for family in metric.collect() for s in family.samples if s.name.endswith("_bucket")}
    assert buckets[1.5]==1
    assert buckets[2.0]==2
    assert buckets[3.0]==3
    REQUEST_LATENCY.remove("bucket-regression", "request")
