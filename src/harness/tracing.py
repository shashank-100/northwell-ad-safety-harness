import json
from pathlib import Path

RUNS = Path(__file__).resolve().parents[2] / "runs"


class Tracer:
    def __init__(self, run_id):
        RUNS.mkdir(exist_ok=True)
        self.path = RUNS / f"{run_id}.jsonl"
        self.run_id = run_id

    def record(self, **fields):
        with self.path.open("a") as f:
            f.write(json.dumps({"run_id": self.run_id, **fields}, default=str) + "\n")
