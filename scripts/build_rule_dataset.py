"""규칙 라벨 데이터셋 (lovecode-rule): 새 가상 인물 → 만세력 → 규칙 라벨러 → 고정 형식 텍스트.

- 라벨: lovecode.labeler (판단 기준 v1.2 + 해석 규약을 코드로). review_status = rule_labeled
- 입력: make_compact_text (모든 관계·태그·수치, 512토큰 이내)
- 인물 단위 분할. validation 120쌍과 test 120쌍은 모든 실험이 공유하고, train만 크기를 바꾼다.
  train 블록은 포함 관계: 360 ⊂ 1200 ⊂ 2400 ⊂ 4800 (블록마다 새 인물, 블록 안에서만 짝을 지음)
- 경계 사례·MBTI 분포·매칭 방식은 2일차 gen_data.py와 같다 (시드만 다름 → 다른 인물)

사용: uv run python scripts/build_rule_dataset.py [--out data/lovecode-rule]
출력: <out>/train360, train1200, train2400, train4800 (각각 kant CSV 7열 데이터셋)
"""

import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from lovecode.contracts import TAXONOMY
from lovecode.dataset import HEADERS, validate, write_csv
from lovecode.features import VERSION
from lovecode.labeler import label
from lovecode.saju import analyze_pair, build_person
from lovecode.saju.textgen import make_compact_text
from lunar_python import Solar


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


SEED = 20261013
# 성별당 인물 수 → 쌍 = 3 × 인물 수 (한 사람이 정확히 3쌍)
BLOCKS = {
    "validation": 40, "test": 40, "train_a": 120, "train_b": 280, "train_c": 400,
    "train_d": 800,  # appended last, so every earlier block draws exactly as before
    "dev": 400,  # large tuning/analysis set (1,200 pairs), never part of train/validation/test
    # Hard-case pool: only pairs with an axis decided by a slight saju lead or a full tie are kept.
    "train_hard_pool": 1200,
    # Tie-case pool: only pairs with an axis decided by a full tie (final rule) are kept.
    "train_tie_pool": 4000,
}
TRAIN_SETS = {
    "train360": ["train_a"],
    "train1200": ["train_a", "train_b"],
    "train2400": ["train_a", "train_b", "train_c"],
    "train4800": ["train_a", "train_b", "train_c", "train_d"],
    "train4800h": ["train_a", "train_b", "train_c", "train_d", "train_hard"],
    "train4800ht": ["train_a", "train_b", "train_c", "train_d", "train_hard", "train_tie"],
}
MBTI_W = {
    "ISTJ": 10,
    "ISFJ": 9,
    "INFP": 9,
    "ENFP": 8,
    "ESFJ": 7,
    "ESTJ": 7,
    "ISFP": 7,
    "ISTP": 6,
    "ESFP": 6,
    "INFJ": 5,
    "INTP": 5,
    "ENFJ": 5,
    "INTJ": 4,
    "ESTP": 4,
    "ENTP": 4,
    "ENTJ": 3,
}
JIE = [
    "立春",
    "惊蛰",
    "清明",
    "立夏",
    "芒种",
    "小暑",
    "立秋",
    "白露",
    "寒露",
    "立冬",
    "大雪",
    "小寒",
]
GENDER = {"M": "male", "F": "female"}


def birth(rnd):
    """2일차 gen_data.birth와 같음: 절입 ±90분 4%, 서머타임 3%, 23시대 4%, 생시 모름 10%."""
    kind = rnd.random()
    y = rnd.randint(1975, 2004)
    if kind < 0.04:
        t = Solar.fromYmd(y, 6, 1).getLunar().getJieQiTable()
        name = rnd.choice(JIE)
        js = t[name] if name in t else t["立春"]
        dt = datetime(js.getYear(), js.getMonth(), js.getDay(), js.getHour(), js.getMinute())
        dt += timedelta(hours=1) + timedelta(minutes=rnd.randint(-90, 90))
        return {
            "y": dt.year,
            "m": dt.month,
            "d": dt.day,
            "h": dt.hour,
            "mi": dt.minute,
            "tag": "절입 근처",
        }
    if kind < 0.07:
        y = rnd.choice([1987, 1988])
        d0 = date(y, 5, 11) + timedelta(days=rnd.randint(0, 145))
        return {
            "y": y,
            "m": d0.month,
            "d": d0.day,
            "h": rnd.randint(0, 23),
            "mi": rnd.randint(0, 59),
            "tag": "서머타임",
        }
    d0 = date(y, 1, 1) + timedelta(days=rnd.randint(0, 364 + (1 if y % 4 == 0 else 0)))
    if kind < 0.11:
        return {
            "y": d0.year,
            "m": d0.month,
            "d": d0.day,
            "h": 23,
            "mi": rnd.randint(0, 59),
            "tag": "23시대",
        }
    if kind < 0.21:
        return {"y": d0.year, "m": d0.month, "d": d0.day, "h": None, "mi": None, "tag": "생시 모름"}
    return {
        "y": d0.year,
        "m": d0.month,
        "d": d0.day,
        "h": rnd.randint(0, 23),
        "mi": rnd.randint(0, 59),
        "tag": "",
    }


def matchings(men, women, rnd, rounds=3):
    """2일차 gen_data.matchings와 같음: 나이 비슷한 이성끼리 3회, 같은 쌍 중복 없음."""
    seen, out = set(), []
    for _ in range(rounds):
        m_sorted = sorted(men, key=lambda p: p["b"]["y"] + rnd.gauss(0, 3))
        w_sorted = sorted(women, key=lambda p: p["b"]["y"] - 1.5 + rnd.gauss(0, 3))
        cand = [[m, w] for m, w in zip(m_sorted, w_sorted, strict=True)]
        for _fix in range(5000):
            dup = [i for i, (m, w) in enumerate(cand) if (m["id"], w["id"]) in seen]
            if not dup:
                break
            i = dup[0]
            j = min(len(cand) - 1, max(0, i + rnd.choice([-3, -2, -1, 1, 2, 3])))
            cand[i][1], cand[j][1] = cand[j][1], cand[i][1]
        else:
            raise RuntimeError("매칭 실패")
        for m, w in cand:
            seen.add((m["id"], w["id"]))
            out.append((m, w))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/lovecode-rule")
    ap.add_argument("--text", choices=["v4", "v5"], default="v4",
                    help="v5: 삼합/방합 글자 위치 + MBTI 글자별 비교 추가")
    a = ap.parse_args()
    out = ROOT / a.out
    if out.exists():
        raise SystemExit("기존 데이터셋 보호: 새 --out 지정")
    rnd = random.Random(SEED)
    mbtis, weights = list(MBTI_W), list(MBTI_W.values())
    people, rows_by_block, n_person, n_pair = {}, {}, 0, 0
    for block, n in BLOCKS.items():
        group = {"M": [], "F": []}
        for g in ("M", "F"):
            for _ in range(n):
                n_person += 1
                b = birth(rnd)
                mbti = rnd.choices(mbtis, weights)[0]
                P = build_person(g, b["y"], b["m"], b["d"], b["h"], b["mi"], mbti)
                rec = {
                    "id": f"R{n_person:05d}",
                    "g": g,
                    "b": b,
                    "mbti": mbti,
                    "P": P,
                    "block": block,
                }
                group[g].append(rec)
                people[rec["id"]] = rec
        pairs = matchings(group["M"], group["F"], rnd)
        rnd.shuffle(pairs)
        rows = []
        for m, w in pairs:
            x, y = (m, w) if rnd.random() < 0.5 else (w, m)
            n_pair += 1
            F = analyze_pair(x["P"], y["P"])
            lab = label(x["P"], y["P"], F)
            rows.append(
                {
                    "pair_id": f"RC{n_pair:05d}",
                    "a": x["id"],
                    "b": y["id"],
                    "label": lab,
                    "text": make_compact_text(x["P"], y["P"], F, v5=a.text == "v5"),
                }
            )
        rows_by_block[block] = rows

    hard_paths = {"saju_slight", "final"}
    hard = [r for r in rows_by_block.pop("train_hard_pool")
            if hard_paths & set(r["label"]["decided_by"].values())]
    rows_by_block["train_hard"] = hard[:1200]
    tie = [r for r in rows_by_block.pop("train_tie_pool")
           if "final" in r["label"]["decided_by"].values()]
    rows_by_block["train_tie"] = tie[:1200]
    summary = {}
    for name, blocks in TRAIN_SETS.items():
        dest = out / name
        dest.mkdir(parents=True)
        chosen = [(b, r) for b in [*blocks, "validation", "test"] for r in rows_by_block[b]]
        split_of = lambda b: "train" if b.startswith("train") else b
        groups = components(
            [{"pair_id": r["pair_id"], "person_a": r["a"], "person_b": r["b"]} for _, r in chosen]
        )
        csv_rows, records = [], []
        for b, r in chosen:
            lab = r["label"]
            reason = " / ".join(
                f"{ax} {lab['scores'][ax][0]:g}:{lab['scores'][ax][1]:g} {lab['decided_by'][ax]}"
                for ax in ("케미", "온도", "거리", "갈등")
            )
            csv_rows.append(
                dict(
                    zip(
                        HEADERS,
                        [
                            r["pair_id"],
                            groups[r["pair_id"]],
                            r["text"],
                            TAXONOMY[lab["type_id"]]["label"],
                            reason,
                            "rule_labeled",
                            split_of(b),
                        ],
                        strict=True,
                    )
                )
            )
            records.append(
                {
                    "couple_id": r["pair_id"],
                    "source": "rule_labeler",
                    "guideline": "v1.2",
                    "status": "rule_labeled",
                    "human_review": False,
                    "type_id": lab["type_id"],
                    "confidence": lab["confidence"],
                    "decided_by": lab["decided_by"],
                    "scores": lab["scores"],
                }
            )
        write_csv(dest / "couples.csv", csv_rows)
        used = {p for _, r in chosen for p in (r["a"], r["b"])}
        (dest / "synthetic_people.json").write_text(
            json.dumps(
                [
                    {
                        "person_id": pid,
                        "gender": GENDER[people[pid]["g"]],
                        "birth_date": f"{people[pid]['b']['y']}-{people[pid]['b']['m']:02d}-{people[pid]['b']['d']:02d}",
                        "birth_time": (
                            f"{people[pid]['b']['h']:02d}:{people[pid]['b']['mi']:02d}"
                            if people[pid]["b"]["h"] is not None
                            else None
                        ),
                        "mbti": people[pid]["mbti"],
                        "case_tag": people[pid]["b"]["tag"],
                        "split": split_of(people[pid]["block"]),
                        "source": "synthetic",
                        "seed": SEED,
                    }
                    for pid in sorted(used)
                ],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (dest / "synthetic_pairs.json").write_text(
            json.dumps(
                [
                    {
                        "couple_id": r["pair_id"],
                        "group_id": groups[r["pair_id"]],
                        "person_a_id": r["a"],
                        "person_b_id": r["b"],
                    }
                    for _, r in chosen
                ],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (dest / "annotation_records.jsonl").write_text(
            "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in records), encoding="utf-8"
        )
        splits = dict(Counter(x["split"] for x in csv_rows))
        manifest = {
            "dataset_version": f"lovecode-rule-{name}",
            "source": "synthetic",
            "seed": SEED,
            "count": len(csv_rows),
            "splits": splits,
            "train_size_experiment": name != "train360",
            "calendar_version": VERSION,
            "label_source": "rule_labeler (guideline v1.2 + conventions)",
            "text_format": f"compact-{a.text}",
            "human_review": "incomplete",
            "taxonomy_version": "love-code-v1",
            "shared_eval_blocks": ["validation", "test"],
            "input_sha256": hashlib.sha256(
                "".join(x["input_text"] for x in csv_rows).encode()
            ).hexdigest(),
        }
        (dest / "dataset_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        validate(dest)
        cover = {s: len({x["label"] for x in csv_rows if x["split"] == s}) for s in splits}
        summary[name] = {
            "splits": splits,
            "classes_per_split": cover,
            "confidence": dict(Counter(x["confidence"] for x in records)),
        }
    # Dev set: same columns, split "dev", plus the labeler's decision path for error analysis.
    dev = rows_by_block["dev"]
    write_csv(out / "dev1200.csv", [
        dict(zip(HEADERS, [r["pair_id"], "dev", r["text"], TAXONOMY[r["label"]["type_id"]]["label"],
                           "rule_labeled", "rule_labeled", "dev"], strict=True)) for r in dev])
    (out / "dev1200_annotations.jsonl").write_text("".join(
        json.dumps({"couple_id": r["pair_id"], "type_id": r["label"]["type_id"],
                    "confidence": r["label"]["confidence"], "decided_by": r["label"]["decided_by"],
                    "scores": r["label"]["scores"]}, ensure_ascii=False) + "\n" for r in dev),
        encoding="utf-8")
    summary["dev1200"] = {"pairs": len(dev),
                          "types": len({r["label"]["type_id"] for r in dev})}
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
