"""러브코드 600쌍 → kant CSV 7열 데이터셋 (data/lovecode-v2).

입력
- data/labeling/source/persons.csv : 가상 인물 400명 (원본 생년월일시·MBTI)
- data/labeling/source/pairs.jsonl : 600쌍 (pair_id, split, 인물 id)
- data/labeling/labels/v11_batch_*.jsonl : 1차 라벨 (판단 기준 v1.1, 600건)
- data/labeling/labels/reviewed_*.jsonl  : v1.2 기준 AI 검수 결과 (있으면 1차 라벨을 덮어씀)

review_status
- ai_reviewed : v1.2 검수를 거친 라벨 (사람 검수 아님 → approved 쓰지 않음)
- pending     : 1차 라벨만 있음

사용: uv run python scripts/build_lovecode_dataset.py [--out data/lovecode-v2] [--check-against pairs.jsonl]
"""

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from lovecode.contracts import TAXONOMY
from lovecode.dataset import HEADERS, validate, write_csv
from lovecode.features import VERSION
from lovecode.saju import build_pair, build_person
from lovecode.saju.textgen import make_fixed_text

SEED = 20261012  # 2일차 gen_data.py와 같은 시드 → 같은 텍스트
LABELS = ROOT / "data/labeling/labels"
SOURCE = ROOT / "data/labeling/source"
AXES = {
    "케미": ("닮은꼴", "보완형"),
    "온도": ("열정형", "안정형"),
    "거리": ("밀착형", "독립형"),
    "갈등": ("바로 풀기", "시간 두기"),
}
GENDER = {"M": "male", "F": "female"}


def type_id(r):
    idx = 0
    for ax, poles in AXES.items():
        if r[ax] not in poles:
            raise ValueError(f"{r['pair_id']} {ax}={r[ax]!r}")
        idx = idx * 2 + poles.index(r[ax])
    return f"T{idx + 1:02d}"


def load_labels(pattern):
    out = {}
    for path in sorted(LABELS.glob(pattern)):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[r["pair_id"]] = r | {"_file": path.name}
    return out


def components(pairs):
    """인물 연결 요소 → group_id. 한 사람이 3쌍에 나오므로 쌍 단위 id로는 누수를 못 막는다."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for p in pairs:
        parent[find(p["person_a"])] = find(p["person_b"])
    roots = {}
    return {
        p["pair_id"]: roots.setdefault(find(p["person_a"]), f"G{len(roots) + 1:03d}") for p in pairs
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/lovecode-v2")
    ap.add_argument("--check-against", help="2일차 원본 pairs.jsonl: 사주·특징·텍스트 동일성 확인")
    ap.add_argument(
        "--text",
        choices=["templated", "fixed"],
        default="templated",
        help="templated: 서비스 입력(v2, 템플릿 4종). fixed: 고정 형식 v3 실험용",
    )
    a = ap.parse_args()
    out = ROOT / a.out
    if (out / "couples.csv").exists():
        raise SystemExit("기존 데이터셋 보호: 새 --out 지정")

    with (SOURCE / "persons.csv").open(encoding="utf-8-sig", newline="") as f:
        people = {r["person_id"]: r for r in csv.DictReader(f)}
    built = {}
    for pid, r in people.items():
        y, m, d = map(int, r["birth_date"].split("-"))
        h, mi = map(int, r["birth_time"].split(":")) if r["birth_time"] else (None, None)
        built[pid] = build_person(r["gender"], y, m, d, h, mi, r["mbti"])
    pairs = [
        json.loads(x) for x in (SOURCE / "pairs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    groups = components(pairs)

    first = load_labels("v11_batch_*.jsonl")
    reviewed = load_labels("reviewed_*.jsonl")
    if set(first) != {p["pair_id"] for p in pairs}:
        raise SystemExit("1차 라벨이 600쌍과 맞지 않음")

    original = None
    if a.check_against:
        original = {
            r["pair_id"]: r
            for r in map(json.loads, Path(a.check_against).read_text(encoding="utf-8").splitlines())
        }

    rows, records, mismatch = [], [], 0
    for i, p in enumerate(pairs):
        A, B = built[p["person_a"]], built[p["person_b"]]
        pair = build_pair(A, B, seed=SEED + i, pair_id=p["pair_id"])
        if original is not None:
            o = original[p["pair_id"]]
            same = (
                o["a"] == A
                and o["b"] == B
                and o["features"] == pair["features"]
                and (
                    a.text == "fixed"
                    or o["text"].replace("\n- ", "\n• ").removeprefix("- ")
                    == pair["text"].removeprefix("• ")
                )
            )
            mismatch += not same
        lab = reviewed.get(p["pair_id"]) or first[p["pair_id"]]
        tid = type_id(lab)
        status = "ai_reviewed" if p["pair_id"] in reviewed else "pending"
        reason = " ".join(str(lab.get("근거", "")).split()) or "근거 없음"
        rows.append(
            dict(
                zip(
                    HEADERS,
                    [
                        p["pair_id"],
                        groups[p["pair_id"]],
                        pair["text"]
                        if a.text == "templated"
                        else make_fixed_text(A, B, pair["features"]),
                        TAXONOMY[tid]["label"],
                        reason.lstrip("=+-@"),
                        status,
                        p["split"],
                    ],
                )
            )
        )
        records.append(
            {
                "couple_id": p["pair_id"],
                "source": "claude_review" if status == "ai_reviewed" else "llm_first_pass",
                "guideline": "v1.2" if status == "ai_reviewed" else "v1.1",
                "file": lab["_file"],
                "status": status,
                "human_review": False,
                "type_id": tid,
                "label": TAXONOMY[tid]["label"],
                "confidence": lab.get("confidence"),
                "changed_from_first_pass": status == "ai_reviewed"
                and type_id(first[p["pair_id"]]) != tid,
            }
        )
    if mismatch:
        raise SystemExit(f"원본과 다른 쌍 {mismatch}개: 이식 코드가 2일차 결과를 재현하지 못함")

    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "couples.csv", rows)
    split_of = {}
    for p in pairs:
        split_of[p["person_a"]] = split_of[p["person_b"]] = p["split"]
    people_out = [
        {
            "person_id": pid,
            "gender": GENDER[r["gender"]],
            "birth_date": r["birth_date"],
            "birth_time": r["birth_time"] or None,
            "mbti": r["mbti"],
            "case_tag": r["case_tag"],
            "split": split_of[pid],
            "source": "synthetic",
            "seed": SEED,
        }
        for pid, r in people.items()
    ]
    pairs_out = [
        {
            "couple_id": p["pair_id"],
            "group_id": groups[p["pair_id"]],
            "person_a_id": p["person_a"],
            "person_b_id": p["person_b"],
        }
        for p in pairs
    ]
    for name, values in [("synthetic_people", people_out), ("synthetic_pairs", pairs_out)]:
        (out / f"{name}.json").write_text(
            json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    (out / "annotation_records.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8"
    )
    status = Counter(r["review_status"] for r in rows)
    manifest = {
        "dataset_version": "lovecode-v2" if a.text == "templated" else "lovecode-v3-fixed-text",
        "text_format": a.text,
        "source": "synthetic",
        "seed": SEED,
        "count": len(rows),
        "calendar_version": VERSION,
        "calendar_validation": "public_ipchun_4of4_boundary_20of20_random3000_100pct",
        "label_status": dict(status),
        "label_guideline": {"pending": "v1.1", "ai_reviewed": "v1.2"},
        "human_review": "incomplete",
        "taxonomy_version": "love-code-v1",
        "splits": dict(Counter(r["split"] for r in rows)),
        "groups": len(set(groups.values())),
        "input_sha256": hashlib.sha256("".join(r["input_text"] for r in rows).encode()).hexdigest(),
    }
    (out / "dataset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = validate(out)
    coverage = {
        s: len({r["label"] for r in rows if r["split"] == s})
        for s in ("train", "validation", "test")
    }
    print(
        json.dumps(
            summary
            | {
                "review_status": dict(status),
                "classes_per_split": coverage,
                "checked_against_original": original is not None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
