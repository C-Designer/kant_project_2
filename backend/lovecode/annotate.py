import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from .contracts import TAXONOMY
from .dataset import validate, write_csv
from .provider import OpenAIProvider, ProviderError
from .settings import settings


def main():
    p = argparse.ArgumentParser(
        description="Explicit paid, synthetic-only labeling; never approves labels."
    )
    p.add_argument("--dir", default="data/synthetic-v1")
    p.add_argument("--max-calls", type=int, default=1)
    p.add_argument("--allow-paid", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    return annotate(a)


def annotate(a, *, provider=None):
    def fail(message):
        raise ValueError(message)

    dest = Path(a.dir)
    validate(dest)
    if not 1 <= a.max_calls <= 600:
        fail("--max-calls must be 1..600")
    with (dest / "couples.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    pending = [r for r in rows if not r["label"]][: a.max_calls]
    if a.dry_run:
        print(
            json.dumps(
                {
                    "would_call": len(pending),
                    "paid_calls": 0,
                    "provider": "openai",
                    "human_review": "incomplete",
                }
            )
        )
        return
    if not a.allow_paid:
        fail("유료 실행은 --allow-paid 필요")
    api = provider or OpenAIProvider()
    for r in pending:
        try:
            data, usage = api.label(r["input_text"], allow_paid=True)
        except ProviderError as e:
            raise SystemExit(str(e)) from None
        r["label"] = TAXONOMY[data["type_id"]]["label"]
        r["label_reason"] = data["label_reason"]
        r["review_status"] = "pending"
        # Persist successful row before moving on. No automatic paid retry on any failure.
        write_csv(dest / "couples.csv", rows)
        with (dest / "annotation_records.jsonl").open("a") as f:
            f.write(
                json.dumps(
                    {
                        "couple_id": r["couple_id"],
                        "source": "openai",
                        "model": settings().model,
                        "status": "pending",
                        "human_review": False,
                        "label": r["label"],
                        "prompt_version": "label-v1",
                        "created_at": datetime.now(UTC).isoformat(),
                        "usage": usage,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    result = {"labeled_this_run": len(pending), "review_status": "pending"}
    print(json.dumps(result))
    return result


if __name__ == "__main__":
    main()
