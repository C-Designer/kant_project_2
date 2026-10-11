"""Tomorrow's synthetic-only classifier + OpenAI explanation command."""

import argparse
import csv
import json
from pathlib import Path

from .dataset import validate
from .provider import OpenAIProvider, ProviderError
from .settings import settings


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default="data/synthetic-v1")
    p.add_argument("--couple-id", default="C0001")
    p.add_argument("--models", default="artifacts/models/comparison-v1")
    p.add_argument("--output", default="artifacts/reports/explanation.json")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--allow-paid", action="store_true")
    a = p.parse_args()
    return experiment(a)


def experiment(a):
    def fail(message):
        raise ValueError(message)

    validate(a.dir)
    with (Path(a.dir) / "couples.csv").open(newline="") as f:
        row = next((r for r in csv.DictReader(f) if r["couple_id"] == a.couple_id), None)
    if row is None:
        fail("가상 manifest에 존재하는 couple-id 필요")
    report_path = Path(a.models) / "report.json"
    if a.dry_run:
        print(
            json.dumps(
                {
                    "synthetic": True,
                    "couple_id": a.couple_id,
                    "model_artifact_ready": report_path.exists(),
                    "api_enabled": settings().api_enabled,
                    "configured": bool(settings().api_key and settings().model),
                    "paid_calls": 0,
                }
            )
        )
        return
    if not a.allow_paid or not report_path.exists():
        fail("--allow-paid와 검증된 학습 artifact 필요")
    dest = Path(a.output)
    if dest.exists():
        fail("기존 결과 보호: 새 --output 지정")
    import hashlib

    report = json.loads(report_path.read_text())
    if (
        report["csv_sha256"]
        != hashlib.sha256((Path(a.dir) / "couples.csv").read_bytes()).hexdigest()
    ):
        fail("학습 CSV digest 불일치")
    from .inference import Classifier, limitations

    classifier = Classifier(a.models)
    type_id = classifier.predict(row["input_text"])
    missing = limitations(row["input_text"])
    try:
        result, usage = OpenAIProvider().explain(
            row["input_text"], type_id, allow_paid=True, limitations=missing
        )
    except ProviderError as e:
        raise SystemExit(str(e)) from None
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(
            {
                "source": "synthetic",
                "couple_id": a.couple_id,
                "human_review": "incomplete",
                "model": settings().model,
                "result": result.model_dump(),
                "usage": usage,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print("가상 해설 저장:", dest)


if __name__ == "__main__":
    main()
