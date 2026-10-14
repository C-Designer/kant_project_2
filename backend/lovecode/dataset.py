"""Dataset contract: CSV writer, validator and per-pair fact loader. Never manufactures labels."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from .contracts import TAXONOMY, Person

HEADERS = ["couple_id", "group_id", "input_text", "label", "label_reason", "review_status", "split"]
DEFAULT_DIR = "data/lovecode-rule5/train4800h"


def write_csv(path, rows):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


<<<<<<< HEAD
def generate(dest):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    if (dest / "couples.csv").exists():
        raise ValueError("기존 CSV 보호: 새 출력 디렉터리를 지정하세요.")
    rng = random.Random(SEED)
    mbtis = [a + b + c + d for a in "EI" for b in "SN" for c in "TF" for d in "JP"]
    people = []
    pairs = []
    rows = []
    # Disjoint pairs are connected components of size two; no reused identity.
    ids = list(range(600))
    rng.shuffle(ids)
    splits = {
        i: ("train" if rank < 360 else "validation" if rank < 480 else "test")
        for rank, i in enumerate(ids)
    }
    for i in range(600):
        ps = []
        pids = []
        for j in range(2):
            d = date(1960, 1, 1) + timedelta(days=rng.randrange(16437))
            p = Person(
                gender=rng.choice(["male", "female", "unspecified"]),
                birth_date=d,
                birth_time=None
                if rng.random() < 0.22
                else f"{rng.randrange(24):02}:{rng.randrange(60):02}",
                mbti=rng.choice(mbtis),
            )
            pid = f"P{2 * i + j + 1:04}"
            pids.append(pid)
            ps.append(p)
            people.append(
                {"person_id": pid, **p.model_dump(mode="json"), "source": "synthetic", "seed": SEED}
            )
        cid = f"C{i + 1:04}"
        gid = f"G{i + 1:04}"
        pairs.append(
            {"couple_id": cid, "group_id": gid, "person_a_id": pids[0], "person_b_id": pids[1]}
        )
        rows.append(dict(zip(HEADERS, [cid, gid, input_text(*ps), "", "", "pending", splits[i]])))
    write_csv(dest / "couples.csv", rows)
    for name, values in [("synthetic_people", people), ("synthetic_pairs", pairs)]:
        (dest / f"{name}.json").write_text(
            json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    manifest = {
        "dataset_version": "synthetic-v1",
        "source": "synthetic",
        "seed": SEED,
        "count": 600,
        "calendar_version": VERSION,
        "calendar_validation": "experimental_not_full_range",
        "label_status": "not_called",
        "human_review": "incomplete",
        "taxonomy_version": "love-code-v1",
        "splits": dict(Counter(r["split"] for r in rows)),
        "input_sha256": hashlib.sha256("".join(r["input_text"] for r in rows).encode()).hexdigest(),
    }
    (dest / "dataset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (dest / "annotation_records.jsonl").touch()
    return validate(dest)


=======
>>>>>>> origin/main
def validate(dest):
    dest = Path(dest)
    with (dest / "couples.csv").open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != HEADERS:
            raise ValueError("CSV 컬럼 불일치")
        rows = list(reader)
    pairs = json.loads((dest / "synthetic_pairs.json").read_text(encoding="utf-8"))
    people = json.loads((dest / "synthetic_people.json").read_text(encoding="utf-8"))
    manifest = json.loads((dest / "dataset_manifest.json").read_text(encoding="utf-8"))
    # Default is the assignment-scale 600 (360/120/120); a train-size experiment declares its
    # own counts in the manifest ("train_size_experiment").
    sizes = (
        manifest["splits"]
        if manifest.get("train_size_experiment")
        else {"train": 360, "validation": 120, "test": 120}
    )
    count = sum(sizes.values())
    if len(rows) != count or len({r["couple_id"] for r in rows}) != count:
        raise ValueError(f"{count}개 고유 커플 필요")
    if Counter(r["split"] for r in rows) != Counter(sizes):
        raise ValueError("분할 불일치")
    if manifest["source"] != "synthetic" or any(p["source"] != "synthetic" for p in people):
        raise ValueError("가상 데이터만 허용")
    # Validate source birthdays before any classifier training can start.
    for person in people:
        Person.model_validate({key: person[key] for key in Person.model_fields})
    pairmap = {p["couple_id"]: p for p in pairs}
    personmap = {p["person_id"]: p for p in people}
    seen = {}
    groups = {}
    labels = {t["label"] for t in TAXONOMY.values()}
    approvals = {}
    for line in (dest / "annotation_records.jsonl").read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if (
            rec.get("source") == "human"
            and rec.get("reviewer")
            and rec.get("reviewed_at")
            and rec.get("status") == "approved"
        ):
            approvals[rec["couple_id"]] = rec
    for r in rows:
        pair = pairmap[r["couple_id"]]
        if r["group_id"] != pair["group_id"]:
            raise ValueError("그룹 불일치")
        for pid in [pair["person_a_id"], pair["person_b_id"]]:
            if pid in seen and seen[pid] != r["split"]:
                raise ValueError("인물 분할 누수")
            if pid in groups and groups[pid] != r["group_id"]:
                raise ValueError("연결 인물 그룹 불일치")
            if pid not in personmap:
                raise ValueError("인물 누락")
            seen[pid] = r["split"]
            groups[pid] = r["group_id"]
        if (
            not r["input_text"]
            or len(r["input_text"]) > 12000
            or any(label in r["input_text"] for label in labels)
        ):
            raise ValueError("입력/라벨 유출 오류")
        if r["label"] and r["label"] not in labels:
            raise ValueError("알 수 없는 라벨")
        # Only "approved" with a matching human record counts as human review.
        if r["review_status"] not in ("pending", "ai_reviewed", "rule_labeled", "approved", "needs_revision"):
            raise ValueError("검수 상태 오류")
        if r["review_status"] == "approved" and (
            not r["label_reason"] or approvals.get(r["couple_id"], {}).get("label") != r["label"]
        ):
            raise ValueError("사람 검수 증거 없음")
        if any(v.startswith(("=", "+", "-", "@", "\t", "\r")) for v in r.values()):
            raise ValueError("CSV 수식 접두 문자")
    if (
        hashlib.sha256("".join(r["input_text"] for r in rows).encode()).hexdigest()
        != manifest["input_sha256"]
    ):
        raise ValueError("원본 입력 digest 불일치")
    return {
        "rows": len(rows),
        "splits": dict(Counter(r["split"] for r in rows)),
        "labeled": sum(bool(r["label"]) for r in rows),
        "approved": sum(r["review_status"] == "approved" for r in rows),
        "cross_split_people": 0,
        "human_review": "incomplete",
    }


def load_pair_facts(directory):
    """couple_id -> (A, B, F) rebuilt from the dataset's own people/pairs (same facts as the text)."""
    from .saju import analyze_pair, build_person

    root = Path(directory)
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
        a, b = person(pair["person_a_id"]), person(pair["person_b_id"])
        out[pair["couple_id"]] = (a, b, analyze_pair(a, b))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["validate"])
    p.add_argument("--dir", default=DEFAULT_DIR)
    a = p.parse_args()
    print(json.dumps(validate(a.dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
