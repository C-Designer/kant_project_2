"""train 증강: A/B 자리 바꾸기 + 같은 중요도 관계 순서 섞기 → <dataset>/train_aug.csv.

- train 행만 증강한다 (validation·test·dev는 원래 분포 그대로).
- 바꾼 쌍을 규칙 라벨러로 다시 라벨링해서 원래 라벨과 같은 경우만 쓴다 (라벨 불변 검증).
- couples.csv는 그대로 두고 별도 파일로 쓴다. train.py --extra-train-csv 로 읽는다.

사용: uv run python scripts/build_augment.py --dir data/lovecode-rule5/train4800h --text v5
"""

import argparse
import csv
import json
import sys
import zlib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from eval_llm_classifier import load_pair_facts
from lovecode.contracts import TAXONOMY
from lovecode.dataset import HEADERS, write_csv
from lovecode.labeler import label
from lovecode.saju import analyze_pair
from lovecode.saju.textgen import make_compact_text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--text", choices=["v4", "v5"], default="v5")
    a = ap.parse_args()
    d = ROOT / a.dir
    dest = d / "train_aug.csv"
    if dest.exists():
        raise SystemExit(f"{dest} 이미 있음")
    with (d / "couples.csv").open(encoding="utf-8", newline="") as f:
        train = [r for r in csv.DictReader(f) if r["split"] == "train"]
    facts = load_pair_facts(a.dir)
    rows, stats = [], Counter()
    for r in train:
        A, B, F = facts[r["couple_id"]]
        orig = label(A, B, F)
        if TAXONOMY[orig["type_id"]]["label"] != r["label"]:
            stats["original_label_mismatch"] += 1
            continue
        F2 = analyze_pair(B, A)
        swapped = label(B, A, F2)
        if swapped["type_id"] != orig["type_id"]:
            stats["label_changes_on_swap"] += 1
            continue
        seed = zlib.crc32(r["couple_id"].encode())
        text = make_compact_text(B, A, F2, v5=a.text == "v5", shuffle_seed=seed)
        rows.append(dict(zip(HEADERS, [r["couple_id"] + "S", r["group_id"], text, r["label"],
                                       "augmented: A/B swap + same-importance shuffle",
                                       "rule_labeled", "train"], strict=True)))
        stats["augmented"] += 1
    write_csv(dest, rows)
    print(json.dumps({"train_rows": len(train), **stats, "file": str(dest)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
