"""선정된 분류기를 test split으로 한 번만 평가한다 (train.py --skip-test 이후).

사용: uv run python scripts/evaluate_test.py --models artifacts/models/lovecode-v2
- 학습 때와 같은 couples.csv인지 sha256으로 확인한다
- report.json에 test 결과가 이미 있으면 거부한다 (test는 한 번만)
"""

import argparse
import csv
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from lovecode.contracts import TAXONOMY
from lovecode.inference import Classifier


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="artifacts/models/lovecode-v2")
    ap.add_argument("--dir", default="data/lovecode-v2")
    ap.add_argument("--copy-to", default="artifacts/reports/classifier-selection-lovecode-v2.json")
    a = ap.parse_args()
    report_path = ROOT / a.models / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("test") is not None:
        raise SystemExit("test는 이미 평가됨: 다시 평가하지 않는다")
    csv_path = ROOT / a.dir / "couples.csv"
    if hashlib.sha256(csv_path.read_bytes()).hexdigest() != report["csv_sha256"]:
        raise SystemExit("학습 때와 다른 couples.csv")

    from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

    with csv_path.open(encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["split"] == "test"]
    labels = sorted(t["label"] for t in TAXONOMY.values())
    clf = Classifier(ROOT / a.models)
    start = time.perf_counter()
    pred = clf.model.predict([r["input_text"] for r in rows])
    elapsed = time.perf_counter() - start
    y = [r["label"] for r in rows]
    report["test"] = {
        "model": report["selected"],
        "rows": len(rows),
        "macro_f1": f1_score(y, pred, labels=labels, average="macro", zero_division=0),
        "accuracy": accuracy_score(y, pred),
        "elapsed_seconds": elapsed,
        "confusion_matrix": confusion_matrix(y, pred, labels=labels).tolist(),
        "evaluated_at": datetime.now(UTC).isoformat(),
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    report_path.write_text(text, encoding="utf-8")
    if a.copy_to:
        (ROOT / a.copy_to).write_text(text, encoding="utf-8")
    t = report["test"]
    print(f"test ({t['model']}, {t['rows']}건): macro-F1 {t['macro_f1']:.4f}, accuracy {t['accuracy']:.4f}")


if __name__ == "__main__":
    main()
