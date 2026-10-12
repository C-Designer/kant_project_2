"""Same immutable split, validation selection, one test evaluation. No fabricated labels."""

import argparse
import csv
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from .bert import WEIGHTS as BERT_WEIGHTS
from .contracts import TAXONOMY
from .dataset import validate

CANDIDATES = ("tfidf_lr", "pretrained_encoder_lr", "klue_bert")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default="data/synthetic-v1")
    p.add_argument("--allow-ai-drafts", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-test", action="store_true", help="stop after validation selection")
    p.add_argument(
        "--encoder", default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    p.add_argument("--encoder-revision")
    p.add_argument(
        "--candidates",
        default="tfidf_lr,pretrained_encoder_lr",
        help="comma list of tfidf_lr, pretrained_encoder_lr, klue_bert",
    )
    p.add_argument("--bert-model", default="klue/bert-base")
    p.add_argument("--bert-revision")
    p.add_argument("--bert-epochs", type=int, default=12)
    p.add_argument("--bert-lr", type=float, default=3e-5)
    p.add_argument("--bert-batch-size", type=int, default=8)
    p.add_argument("--bert-max-length", type=int, default=512)
    p.add_argument("--output", default="artifacts/models/comparison-v1")
    a = p.parse_args()
    return train(a)


def train(a, *, encoder_factory=None):
    def fail(message):
        raise ValueError(message)

    validate(a.dir)
    with (Path(a.dir) / "couples.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    names = [
        n.strip() for n in getattr(a, "candidates", "tfidf_lr,pretrained_encoder_lr").split(",")
    ]
    if not names or set(names) - set(CANDIDATES) or "tfidf_lr" not in names:
        fail(f"--candidates는 tfidf_lr를 포함한 {CANDIDATES} 조합")
    eligible = [
        r
        for r in rows
        if r["label"]
        and (
            r["review_status"] == "approved"
            or (a.allow_ai_drafts and r["review_status"] in ("pending", "ai_reviewed"))
        )
    ]
    missing = len(rows) - len(eligible)
    classes = {t["label"] for t in TAXONOMY.values()}
    coverage = {
        s: len({r["label"] for r in eligible if r["split"] == s})
        for s in ("train", "validation", "test")
    }
    ready = missing == 0 and all(v == 16 for v in coverage.values())
    if a.dry_run:
        print(
            json.dumps(
                {
                    "ready": ready,
                    "eligible_rows": len(eligible),
                    "ineligible_rows": missing,
                    "classes_per_split": coverage,
                    "training_executed": False,
                    "human_review": "incomplete",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if not ready:
        fail("라벨/검수 정책 및 split별 16유형 coverage 충족 전 학습 차단")
    import re

    fixture = bool(getattr(a, "fixture", False))
    sha = re.compile(r"[0-9a-f]{40}")
    if (
        "pretrained_encoder_lr" in names
        and not fixture
        and not sha.fullmatch(a.encoder_revision or "")
    ):
        fail("재현 가능한 --encoder-revision commit SHA 필요")
    if "klue_bert" in names and not sha.fullmatch(getattr(a, "bert_revision", None) or ""):
        fail("재현 가능한 --bert-revision commit SHA 필요")
    output = Path(a.output)
    if output.exists():
        fail("기존 실험 보호: 새 --output 지정")
    import joblib
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
    from sklearn.pipeline import make_pipeline

    split = {s: [r for r in eligible if r["split"] == s] for s in coverage}
    x = {s: [r["input_text"] for r in split[s]] for s in split}
    y = {s: [r["label"] for r in split[s]] for s in split}
    baseline = make_pipeline(
        TfidfVectorizer(analyzer="char", ngram_range=(2, 4), min_df=2),
        LogisticRegression(max_iter=2000, random_state=42, class_weight="balanced"),
    )
    start = time.perf_counter()
    baseline.fit(x["train"], y["train"])
    train_seconds = {"tfidf_lr": time.perf_counter() - start}
    encoder = encoded = bert = None
    if "pretrained_encoder_lr" in names:
        if encoder_factory is None:
            from sentence_transformers import SentenceTransformer

            encoder_factory = SentenceTransformer
        start = time.perf_counter()
        encoder = encoder_factory(a.encoder, revision=a.encoder_revision, trust_remote_code=False)
        train_features = encoder.encode(x["train"], normalize_embeddings=True)
        encoded = LogisticRegression(max_iter=2000, random_state=42, class_weight="balanced").fit(
            train_features, y["train"]
        )
        train_seconds["pretrained_encoder_lr"] = time.perf_counter() - start
    bert_log = None
    if "klue_bert" in names:
        from .bert import BertModel, finetune

        bert_log = finetune(
            x,
            y,
            sorted(classes),
            output / "klue_bert",
            model_name=a.bert_model,
            revision=a.bert_revision,
            epochs=a.bert_epochs,
            lr=a.bert_lr,
            batch_size=a.bert_batch_size,
            max_length=a.bert_max_length,
        )
        train_seconds["klue_bert"] = bert_log["train_seconds"]
        bert = BertModel(output / "klue_bert", max_length=a.bert_max_length)
    report = {
        "fixture": fixture,
        "human_review": "incomplete"
        if any(r["review_status"] != "approved" for r in eligible)
        else "complete",
        "purpose": "experimental_teacher_label_reproduction_not_real_relationship_validity",
        "csv_sha256": hashlib.sha256((Path(a.dir) / "couples.csv").read_bytes()).hexdigest(),
        "dataset": json.loads((Path(a.dir) / "dataset_manifest.json").read_text(encoding="utf-8")),
        "review_status": dict(Counter(r["review_status"] for r in eligible)),
        "split_rows": {s: len(split[s]) for s in split},
        "encoder": a.encoder if encoder else None,
        "encoder_revision": a.encoder_revision if encoder else None,
        "bert": bert_log,
        "train_seconds": train_seconds,
        "candidates": {},
    }

    def evaluate(name, s):
        start = time.perf_counter()
        if name == "tfidf_lr":
            pred = baseline.predict(x[s])
        elif name == "klue_bert":
            pred = bert.predict(x[s])
        else:
            pred = encoded.predict(encoder.encode(x[s], normalize_embeddings=True))
        return {
            "macro_f1": f1_score(
                y[s], pred, labels=sorted(classes), average="macro", zero_division=0
            ),
            "accuracy": accuracy_score(y[s], pred),
            "elapsed_seconds": time.perf_counter() - start,
            "confusion_matrix": confusion_matrix(y[s], pred, labels=sorted(classes)).tolist(),
        }

    for name in names:
        report["candidates"][name] = evaluate(name, "validation")
    winner = max(
        report["candidates"],
        key=lambda n: (
            report["candidates"][n]["macro_f1"],
            report["candidates"][n]["accuracy"],
            -report["candidates"][n]["elapsed_seconds"],
        ),
    )
    report["selected"] = winner
    # --skip-test: select on validation now, spend the single test evaluation later.
    report["test"] = None if getattr(a, "skip_test", False) else evaluate(winner, "test")
    report["label_order"] = sorted(classes)
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump(baseline, output / "tfidf_lr.joblib")
    artifacts = ["tfidf_lr.joblib"]
    if encoded is not None:
        joblib.dump(encoded, output / "encoder_lr.joblib")
        artifacts.append("encoder_lr.joblib")
    if bert is not None:
        artifacts.append("klue_bert/" + BERT_WEIGHTS)
    report["artifact_sha256"] = {
        name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in artifacts
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("학습 완료. 실험 보고서:", output / "report.json")
    return report


if __name__ == "__main__":
    main()
