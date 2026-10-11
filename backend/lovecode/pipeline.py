"""Explicit synthetic workflow; partial runs stop rather than inventing missing labels."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from .annotate import annotate
from .dataset import validate
from .experiment import experiment
from .train import train


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default="data/synthetic-v1")
    p.add_argument("--output", default="artifacts/models/comparison-v1")
    p.add_argument(
        "--encoder", default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    p.add_argument("--encoder-revision")
    p.add_argument("--max-label-calls", type=int, default=1)
    p.add_argument("--couple-id", default="C0001")
    p.add_argument("--allow-paid", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    data = validate(a.dir)
    if not 1 <= a.max_label_calls <= 600:
        p.error("max-label-calls must be 1..600")
    if a.dry_run:
        print(
            json.dumps(
                {
                    "dataset": data,
                    "paid_calls": 0,
                    "max_requested_calls": min(a.max_label_calls, 600 - data["labeled"]) + 1,
                    "stages": [
                        "label pending rows",
                        "train two candidates if coverage ready",
                        "explain one synthetic pair",
                    ],
                    "human_review": "incomplete",
                }
            )
        )
        return
    if not a.allow_paid or not a.encoder_revision:
        p.error("--allow-paid and pinned --encoder-revision required")
    if Path(a.output).exists():
        p.error("Use a fresh output path; existing experiment is never overwritten")
    annotate(
        SimpleNamespace(dir=a.dir, max_calls=a.max_label_calls, allow_paid=True, dry_run=False)
    )
    train(
        SimpleNamespace(
            dir=a.dir,
            allow_ai_drafts=True,
            dry_run=False,
            encoder=a.encoder,
            encoder_revision=a.encoder_revision,
            output=a.output,
        )
    )
    experiment(
        SimpleNamespace(
            dir=a.dir,
            couple_id=a.couple_id,
            models=a.output,
            output=str(Path(a.output) / "explanation.json"),
            dry_run=False,
            allow_paid=True,
        )
    )


if __name__ == "__main__":
    main()
