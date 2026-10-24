import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from code.evaluation.test_scenarios import execute_scenarios_against_engine
from code.prediction_engine import PredictionEngine

engine = PredictionEngine(dataset_dir=PROJECT_ROOT / "dataset")
res = execute_scenarios_against_engine(engine)
print(f"Custom scenarios: {res['passed_count']}/{res['total_scenarios']} passed")
for r in res["results"]:
    print(f"  [{r['execution_result']}] {r['scenario_id']}: {r['category']} -> {r['pred_status']}")
assert res["passed_count"] == 10, "Not all scenarios passed!"
print("ALL 10 CUSTOM SCENARIOS PASSED WITH ZERO ERRORS.")
