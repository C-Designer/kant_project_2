"""CatBoost 비교 실험 (CPU). BERT와 별개, test는 쓰지 않는다.

① TF-IDF + CatBoost : TF-IDF 파이프라인에서 LR 자리만 CatBoost로 교체
② 구조화 특징 + CatBoost : v5 고정 형식 텍스트를 파싱한 사실 표 (규칙 점수는 넣지 않음)
각각 16유형 직접 분류와 축별(2지선다 4개) 분류. 조기 종료는 dev1200, 보고는 dev1200과 validation.

사용: uv run python scripts/train_catboost.py [--data data/lovecode-rule5]
"""

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from lovecode.axes import from_bits, to_bits
from lovecode.contracts import TAXONOMY

HAP = {"천간합", "육합", "반합", "삼합", "방합", "암합"}
CLASH = {"충", "천간충"}
HIDDEN = {"원진", "해", "형"}
SPOTS = ("daystem", "day", "month", "other")
TAGS = ("press", "block", "help", "burden", "untagged")
ELEMS = "목화토금수"


def parse(text):
    """v5 compact text → flat feature dict (facts only)."""
    lines = text.split("\n")
    f = {}
    for line in lines[:2]:
        t = line.split(" ")
        p = t[0]
        f[p + "_gender"], f[p + "_mbti_full"] = t[1], t[2]
        for i, ch in enumerate(t[2]):
            f[f"{p}_mbti{i}"] = ch
        cnt = t[9]
        for e, n in re.findall(r"([목화토금수])(\d)", cnt):
            f[f"{p}_cnt_{e}"] = int(n)
        f[p + "_day_element"] = t[11][-1]
        f[p + "_season"], f[p + "_strength"] = t[12], t[13]
        f[p + "_strength_score"] = float(t[14])
        f[p + "_climate"] = t[15]
        needs, gi, lack = t[16][2:], t[17][2:], t[18][2:]
        for e in ELEMS:
            f[f"{p}_need_{e}"] = int(e in needs)
            f[f"{p}_lack_{e}"] = int(e in lack)
        f[p + "_gi"] = gi
        f[p + "_hour_unknown"] = int("생시모름" in t)
        f[p + "_day_branch"] = t[6][1]
        f[p + "_month_branch"] = t[5][1]
    s = lines[2]
    m = re.search(r"공급 B→A (\S+) A→B (\S+) 유사도 ([\d.]+) 정반대 (\S+) 합친온도 (\S+) "
                  r"같은계절 (\S+) 같은일간 (\S+) A→B (\S+) B→A (\S+) MBTI같음 (\d)", s)
    (f["supply_ba"], f["supply_ab"], sim, opp, f["combined_climate"], season, dayel,
     ab, ba, same) = m.groups()
    f["similarity"], f["opposite"], f["same_season"], f["same_day_element"] = (
        float(sim), int(opp == "예"), int(season == "예"), int(dayel == "예"))
    f["spouse_a"], f["spouse_b"] = int("배우자성" in ab), int("배우자성" in ba)
    f["god_ab"], f["god_ba"] = ab.replace("배우자성", ""), ba.replace("배우자성", "")
    f["mbti_same"] = int(same)
    for k, v in re.findall(r"(EI|SN|TF|JP)(둘다\w|다름)", s):
        f["mbti_cmp_" + k] = v
    # Relations: counts by family x spot x tag (no deduplication or points: raw facts).
    for fam in ("hap", "clash", "hidden"):
        f[f"{fam}_max_rank"] = 0
        for spot in SPOTS:
            for tag in (*TAGS, "n"):
                f[f"{fam}_{spot}_{tag}"] = 0
    body = lines[3].removeprefix("관계 ")
    for rel in ([] if body == "없음" else body.split(" / ")):
        m = re.match(r"(\S+?)(\d) A(\S+) B(\S+)(.*)", rel)
        typ, rank, sa, sb, tags = m.groups()
        parts = set(typ.split("·"))
        fam = "hap" if parts & HAP else ("clash" if parts & CLASH else "hidden")
        pa = re.findall(r"(년|월|일|시)(간|지)", sa)
        pb = re.findall(r"(년|월|일|시)(간|지)", sb)
        if ("일", "간") in pa and ("일", "간") in pb:
            spot = "daystem"
        elif ("일", "지") in pa and ("일", "지") in pb:
            spot = "day"
        elif ("월", "지") in pa + pb:  # 월지끼리 or 일지×월지 cross
            spot = "month"
        else:
            spot = "other"
        f[f"{fam}_{spot}_n"] += 1
        f[f"{fam}_max_rank"] = max(f[f"{fam}_max_rank"], int(rank))
        tags = tags.split()
        if not tags:
            f[f"{fam}_{spot}_untagged"] += 1
        for t in tags:
            key = ("press" if "기신누름" in t else "block" if "필요막음" in t
                   else "help" if "도움" in t else "burden")
            f[f"{fam}_{spot}_{key}"] += 1
    return f


def load(path, split=None):
    with Path(path).open(encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if split is None or r["split"] == split]
    return [r["input_text"] for r in rows], [r["label"] for r in rows]


def metrics(gold, pred):
    from sklearn.metrics import accuracy_score, f1_score

    labels = sorted(v["label"] for v in TAXONOMY.values())
    axis = [sum(p.split("·")[j] == g.split("·")[j] for p, g in zip(pred, gold, strict=True)) / len(gold)
            for j in range(4)]
    return {"macro_f1": f1_score(gold, pred, labels=labels, average="macro", zero_division=0),
            "accuracy": accuracy_score(gold, pred), "axis_accuracy": axis}


def fit_predict(Xtr, ytr, Xdev, ydev, evals, cat, axes, threads):
    from catboost import CatBoostClassifier

    common = {"iterations": 3000, "learning_rate": 0.08, "depth": 6, "random_seed": 42,
              "thread_count": threads, "verbose": False, "early_stopping_rounds": 200,
              "cat_features": cat or None, "auto_class_weights": "Balanced"}
    if not axes:
        m = CatBoostClassifier(loss_function="MultiClass", **common)
        m.fit(Xtr, ytr, eval_set=(Xdev, ydev))
        return [[str(p[0]) for p in m.predict(X)] for X in evals], [m.get_best_iteration()]
    cols, iters = [], []
    btr, bdev = [to_bits(v) for v in ytr], [to_bits(v) for v in ydev]
    for j in range(4):
        m = CatBoostClassifier(loss_function="Logloss", **common)
        m.fit(Xtr, [b[j] for b in btr], eval_set=(Xdev, [b[j] for b in bdev]))
        cols.append([m.predict(X) for X in evals])
        iters.append(m.get_best_iteration())
    preds = [[from_bits([int(cols[j][k][i]) for j in range(4)]) for i in range(len(evals[k]))]
             for k in range(len(evals))]
    return preds, iters


def main():
    import pandas as pd
    from sklearn.feature_extraction.text import TfidfVectorizer

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/lovecode-rule5")
    ap.add_argument("--train", default="train4800h")
    ap.add_argument("--threads", type=int, default=6)
    a = ap.parse_args()
    d = ROOT / a.data
    xtr, ytr = load(d / a.train / "couples.csv", "train")
    xva, yva = load(d / a.train / "couples.csv", "validation")
    xdev, ydev = load(d / "dev1200.csv")
    report = {"data": a.data, "train": a.train, "train_rows": len(xtr), "results": {}}

    # ① TF-IDF + CatBoost (top 3000 n-grams to keep boosting tractable)
    vec = TfidfVectorizer(analyzer="char", ngram_range=(2, 4), min_df=2, max_features=3000)
    Ttr = vec.fit_transform(xtr)
    Tdev, Tva = vec.transform(xdev), vec.transform(xva)
    # ② structured features parsed from the text
    Ftr, Fdev, Fva = (pd.DataFrame([parse(t) for t in xs]) for xs in (xtr, xdev, xva))
    Fdev, Fva = Fdev.reindex(columns=Ftr.columns, fill_value=0), Fva.reindex(columns=Ftr.columns, fill_value=0)
    cat = [c for c in Ftr.columns if Ftr[c].dtype == object]
    report["structured_features"] = {"n": len(Ftr.columns), "categorical": len(cat)}

    for name, (Xtr, Xdev, Xva, cats) in {
        "TF-IDF + CatBoost": (Ttr, Tdev, Tva, []),
        "구조화 특징 + CatBoost": (Ftr, Fdev, Fva, cat),
    }.items():
        for axes in (False, True):
            label = f"{name} {'축별' if axes else '16유형'}"
            t0 = time.perf_counter()
            (pdev, pva), iters = fit_predict(Xtr, ytr, Xdev, ydev, [Xdev, Xva], cats, axes, a.threads)
            r = {"dev1200": metrics(ydev, pdev), "validation": metrics(yva, pva),
                 "best_iterations": iters, "train_seconds": time.perf_counter() - t0}
            report["results"][label] = r
            dv, vv = r["dev1200"], r["validation"]
            print(f"{label:24s} dev macro-F1 {dv['macro_f1']:.3f} acc {dv['accuracy']:.3f} 축 "
                  + " ".join(f"{x:.2f}" for x in dv["axis_accuracy"])
                  + f" | val macro-F1 {vv['macro_f1']:.3f} acc {vv['accuracy']:.3f} | {r['train_seconds']:.0f}s",
                  flush=True)
    out = ROOT / "artifacts/reports" / f"catboost-{Path(a.data).name}-{a.train}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("저장:", out)


if __name__ == "__main__":
    main()
