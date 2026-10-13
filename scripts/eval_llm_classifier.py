"""LLM 분류 사후 실험: TF-IDF/klue-bert와 같은 입력·분할·지표로 비교.

사용:
  uv run python scripts/eval_llm_classifier.py run --dir data/lovecode-v3 --backend openai --allow-paid
  uv run python scripts/eval_llm_classifier.py summarize --dir data/lovecode-v3

- 기본은 validation만. test는 이미 klue/bert 공식 평가에 썼으므로 --posthoc-test 없이는 거부
- 결과는 한 건씩 바로 저장 (artifacts/reports/llm-classify/), 같은 이름 파일이 있으면 중단
"""

import argparse
import csv
import json
import re
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from lovecode.contracts import TAXONOMY
from lovecode.jev_classifier import JevClassifier
from lovecode.llm_classifier import PROMPT_VERSION, LLMClassifier

OUT = ROOT / "artifacts/reports/llm-classify"
LABEL_TO_ID = {v["label"]: k for k, v in TAXONOMY.items()}


def load_rows(directory, split):
    with (ROOT / directory / "couples.csv").open(encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f) if r["split"] == split]


def load_pair_facts(directory):
    """couple_id -> (A, B, F) rebuilt from the dataset's own people/pairs (same facts as the text)."""
    from lovecode.saju import analyze_pair, build_person

    root = ROOT / directory
    people = {
        p["person_id"]: p
        for p in json.loads((root / "synthetic_people.json").read_text(encoding="utf-8"))
    }
    gender = {"male": "M", "female": "F"}

    def person(pid):
        p = people[pid]
        y, m, d = map(int, p["birth_date"].split("-"))
        h, mi = map(int, p["birth_time"].split(":")) if p["birth_time"] else (None, None)
        return build_person(gender.get(p["gender"], "U"), y, m, d, h, mi, p["mbti"])

    out = {}
    for pair in json.loads((root / "synthetic_pairs.json").read_text(encoding="utf-8")):
        A, B = person(pair["person_a_id"]), person(pair["person_b_id"])
        out[pair["couple_id"]] = (A, B, analyze_pair(A, B))
    return out


def run(a):
    if a.split == "test" and not a.posthoc_test:
        raise SystemExit("test는 이미 공식 평가에 사용됨: 사후 실험이면 --posthoc-test")
    rows = load_rows(a.dir, a.split)
    if a.limit:  # prompt development on a fixed sample (use --split train, never validation)
        import random

        rows = random.Random(20261012).sample(rows, a.limit)
    pair_facts = None
    if a.backend == "jev" and a.mode == "axes-json":
        from lovecode.jev_axes import JevAxesClassifier

        clf = JevAxesClassifier()
        version = clf.prompt_version + (f"-dev{a.limit}" if a.limit else "")
        pair_facts = load_pair_facts(a.dir)
    elif a.backend == "jev":
        clf = JevClassifier(a.mode)
        version = clf.prompt_version
    else:
        clf = LLMClassifier(a.backend, a.model)
        version = PROMPT_VERSION
    slug = re.sub(r"[^A-Za-z0-9.-]+", "_", clf.model or "unset")
    data = (
        "-".join(Path(a.dir).parts[-2:]) if Path(a.dir).parent.name != "data" else Path(a.dir).name
    )
    dest = OUT / f"{data}__{a.split}__{a.backend}__{slug}__{version}.jsonl"
    if dest.exists():
        raise SystemExit(f"{dest.name} 이미 있음: 같은 조건 재실행 금지")
    dest.parent.mkdir(parents=True, exist_ok=True)

    def one(r):
        if pair_facts is not None:
            pred, meta = clf.classify_pair(*pair_facts[r["couple_id"]], allow_paid=a.allow_paid)
        else:
            pred, meta = clf.classify(r["input_text"], allow_paid=a.allow_paid)
        return {
            "couple_id": r["couple_id"],
            "gold": LABEL_TO_ID[r["label"]],
            "pred": pred,
            "meta": meta,
        }

    done = 0
    with dest.open("w", encoding="utf-8") as f, ThreadPoolExecutor(a.workers) as pool:
        for rec in pool.map(one, rows):
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            done += 1
            if done % 20 == 0 or done == len(rows):
                print(f"[{done}/{len(rows)}]")
    print("저장:", dest)


def summarize(a):
    from sklearn.metrics import accuracy_score, f1_score

    ids = sorted(TAXONOMY)
    result = []
    for path in sorted(OUT.glob("*.jsonl")):
        recs = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
        gold = [r["gold"] for r in recs]
        pred = [r["pred"] or "NONE" for r in recs]
        axes = [
            sum(
                p != "NONE"
                and TAXONOMY[g]["label"].split("·")[j] == TAXONOMY[p]["label"].split("·")[j]
                for g, p in zip(gold, pred, strict=True)
            )
            / len(recs)
            for j in range(4)
        ]
        ok = [r for r in recs if not r["meta"]["error"]]
        usage = [r["meta"]["usage"] for r in ok]
        s = {
            "file": path.name,
            "n": len(recs),
            "failed": len(recs) - len(ok),
            "macro_f1": f1_score(gold, pred, labels=ids, average="macro", zero_division=0),
            "accuracy": accuracy_score(gold, pred),
            "axis_accuracy": dict(zip(["케미", "온도", "거리", "갈등"], axes, strict=True)),
            "latency_median_s": statistics.median(r["meta"]["elapsed_seconds"] for r in recs),
            "input_tokens": sum(u.get("input_tokens", 0) for u in usage),
            "output_tokens": sum(u.get("output_tokens", 0) for u in usage),
            "predicted_types": len({p for p in pred if p != "NONE"}),
            # Jev returns probabilities over all 16 types: is the gold type in its top 3?
            "top3_accuracy": (
                sum(
                    r["gold"]
                    in sorted(r["meta"]["probabilities"], key=r["meta"]["probabilities"].get)[-3:]
                    for r in ok
                )
                / len(recs)
                if ok and all(r["meta"].get("probabilities") for r in ok)
                else None
            ),
        }
        result.append(s)
        ax = " ".join(f"{k} {v:.2f}" for k, v in s["axis_accuracy"].items())
        print(
            f"{path.stem}: macro-F1 {s['macro_f1']:.3f} acc {s['accuracy']:.3f} | {ax} | "
            f"실패 {s['failed']} | 예측 유형 {s['predicted_types']}종 | "
            f"시간 중앙값 {s['latency_median_s']:.1f}s | 토큰 {s['input_tokens']}/{s['output_tokens']}"
            + (f" | top3 {s['top3_accuracy']:.3f}" if s["top3_accuracy"] is not None else "")
        )
    (OUT / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--dir", default="data/lovecode-rule5/train4800h")
    r.add_argument("--split", default="validation", choices=["train", "validation", "test"])
    r.add_argument("--limit", type=int, help="fixed random sample size (prompt development)")
    r.add_argument("--backend", default="openai", choices=["openai", "ollama", "jev"])
    r.add_argument(
        "--mode", default="guided", choices=["guided", "noguide", "axes-json"], help="jev only"
    )
    r.add_argument("--model")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--allow-paid", action="store_true")
    r.add_argument("--posthoc-test", action="store_true")
    r.set_defaults(fn=run)
    s = sub.add_parser("summarize")
    s.add_argument("--dir", default="data/lovecode-rule5/train4800h")
    s.set_defaults(fn=summarize)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
