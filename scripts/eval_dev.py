"""큰 개발 세트(dev1200)로 저장된 분류 모델을 비교하고 오류를 분석한다 (학습 없음).

dev는 튜닝·분석 전용이다. 공식 validation·test 120쌍은 건드리지 않는다.
- 지표: 16유형 macro-F1, accuracy(95% 부트스트랩 구간), 축별 정확도
- 오류 분석: 라벨러가 그 축을 어떻게 정했는지(saju / mbti / saju_slight / final)별 축 정확도,
  확신도(high/mid/low)별 16유형 정확도

사용: uv run python scripts/eval_dev.py [--dev data/lovecode-rule5 --set v5]
"""

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from lovecode.contracts import TAXONOMY

M = ROOT / "artifacts/models"
MODELS = {
    "TF-IDF 16유형": ("joblib", M / "lovecode-rule3-train4800-lr2e5/tfidf_lr.joblib"),
    "TF-IDF 축별": ("joblib", M / "lovecode-rule3-train4800-axes-lr2e5/tfidf_lr_axes.joblib"),
    "BERT 16유형": ("bert", M / "lovecode-rule3-train4800-lr2e5/klue_bert"),
    "BERT 축별": ("bert", M / "lovecode-rule3-train4800-axes-lr2e5/klue_bert_axes"),
    "RoBERTa 16유형": ("bert", M / "lovecode-rule3-train4800-roberta-lr3e5-ep30/klue_bert"),
}
# v5 text models (A·B text facts, C hard cases) are scored on the v5 rendering of the same dev pairs.
M5 = ROOT / "artifacts/models"
MODELS_V5 = {
    "TF-IDF 축별 v5": ("joblib", M5 / "lovecode-rule5-v5-train4800-axes/tfidf_lr_axes.joblib"),
    "BERT 축별 v5": ("bert", M5 / "lovecode-rule5-v5-train4800-axes/klue_bert_axes"),
    "TF-IDF 축별 v5+어려운사례": ("joblib", M5 / "lovecode-rule5-v5-train4800h-axes/tfidf_lr_axes.joblib"),
    "BERT 축별 v5+어려운사례": ("bert", M5 / "lovecode-rule5-v5-train4800h-axes/klue_bert_axes"),
    "BERT 축별 v5+어려운사례+규제": ("bert", M5 / "lovecode-rule5-v5-train4800h-axes-reg/klue_bert_axes"),
    "BERT 축별 v5+어려운사례+동률": ("bert", M5 / "lovecode-rule6-v5-train4800ht-axes/klue_bert_axes"),
}
AXES = ["케미", "온도", "거리", "갈등"]
PATHS = ["saju", "mbti", "saju_slight", "final"]


def load(kind, path):
    if kind == "joblib":
        import joblib

        return joblib.load(path)
    from lovecode.bert import BertModel

    return BertModel(path)


def bootstrap(correct, n=2000, seed=0):
    rnd = random.Random(seed)
    k = len(correct)
    accs = sorted(sum(correct[rnd.randrange(k)] for _ in range(k)) / k for _ in range(n))
    return accs[int(0.025 * n)], accs[int(0.975 * n)]


def main():
    from sklearn.metrics import f1_score

    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", default="data/lovecode-rule5")
    # v4 models need the v4 dev text: regenerate with build_rule_dataset.py (default --text v4).
    ap.add_argument("--set", choices=["v4", "v5"], default="v5", help="which saved models to score")
    ap.add_argument("--out", default="artifacts/reports/dev1200-eval.json")
    a = ap.parse_args()
    models = MODELS if a.set == "v4" else {k: v for k, v in MODELS_V5.items() if v[1].exists()}
    dev = ROOT / a.dev
    with (dev / "dev1200.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    ann = {
        x["couple_id"]: x
        for x in map(json.loads, (dev / "dev1200_annotations.jsonl").read_text(encoding="utf-8").splitlines())
    }
    texts, gold = [r["input_text"] for r in rows], [r["label"] for r in rows]
    labels = sorted(v["label"] for v in TAXONOMY.values())
    report = {"dev_pairs": len(rows), "models": {}}
    for name, (kind, path) in models.items():
        pred = load(kind, path).predict(texts)
        ok = [p == g for p, g in zip(pred, gold, strict=True)]
        axis = [
            sum(p.split("·")[j] == g.split("·")[j] for p, g in zip(pred, gold, strict=True)) / len(rows)
            for j in range(4)
        ]
        by_path = defaultdict(Counter)
        by_conf = defaultdict(Counter)
        for r, p, g in zip(rows, pred, gold, strict=True):
            a_ = ann[r["couple_id"]]
            for j, ax in enumerate(AXES):
                by_path[ax][(a_["decided_by"][ax], p.split("·")[j] == g.split("·")[j])] += 1
            by_conf[a_["confidence"]][p == g] += 1
        lo, hi = bootstrap(ok)
        s = {
            "macro_f1": f1_score(gold, pred, labels=labels, average="macro", zero_division=0),
            "accuracy": sum(ok) / len(ok),
            "accuracy_ci95": [lo, hi],
            "axis_accuracy": dict(zip(AXES, axis, strict=True)),
            "axis_accuracy_by_path": {
                ax: {
                    pth: [c[(pth, True)], c[(pth, True)] + c[(pth, False)]]
                    for pth in PATHS if c[(pth, True)] + c[(pth, False)]
                }
                for ax, c in by_path.items()
            },
            "accuracy_by_confidence": {
                k: [c[True], c[True] + c[False]] for k, c in sorted(by_conf.items())
            },
        }
        report["models"][name] = s
        print(f"{name:14s} macro-F1 {s['macro_f1']:.3f} acc {s['accuracy']:.3f} "
              f"[{lo:.3f}~{hi:.3f}] | 축 " + " ".join(f"{v:.3f}" for v in axis))
    out = ROOT / a.out
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("저장:", out)


if __name__ == "__main__":
    main()
