"""로컬 LLM(Ollama) vs 상용 LLM(OpenAI) 해설 비교 (같은 입력·프롬프트·스키마).

1) 세트 만들기 (한 번만): validation에서 개발용 15건, test에서 최종 비교용 24건
   uv run python scripts/compare_generators.py make-sets
2) 실행: 개발 세트로 프롬프트를 다듬고, 최종 세트는 모델별로 한 번씩만 돌린다
   uv run python scripts/compare_generators.py run --set development --backend ollama
   uv run python scripts/compare_generators.py run --set eval --backend openai --allow-paid \
       --price-in 0.25 --price-out 2.0          # USD / 1M tokens, 실행 당일 가격표 값
3) 요약표: uv run python scripts/compare_generators.py summarize

type_id는 데이터셋 라벨을 쓴다(두 LLM에 같은 유형을 주고 해설 품질만 비교).
자동 점검은 규칙 기반 1차 점검이며, 최종 품질 판단은 사람이 결과 파일을 읽고 기록한다.
"""

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from lovecode.contracts import AXIS_KEYS, AXIS_LABELS, AXIS_VALUES, TAXONOMY, PublicResult
from lovecode.features import limitations
from lovecode.saju import build_pair, build_person

DATA = ROOT / "data/lovecode-v2"
OUT = ROOT / "artifacts/reports/generation"
SETS = {"development": ("validation", 15), "eval": ("test", 24)}
# Quotas so both sets include the hard cases named in the plan.
QUOTA = {"missing_hour": 0.25, "same_day_element": 0.2}

ASSERTIVE = re.compile(r"반드시|무조건|틀림없|절대로?|운명|100\s?%|확실히 .{0,6}(될|할) 것")
SUPERIOR = re.compile(r"더 (좋은|나은|우월)|우월|열등|나쁜 (유형|쪽|관계)")
RELATIONS = ["천간합", "천간충", "육합", "반합", "삼합", "방합", "암합", "원진"]
LEAK = re.compile(r"[EI][SN][TF][JP]|[一-鿿]|https?://|[<>#*]")


def type_of(label):
    return next(k for k, v in TAXONOMY.items() if v["label"] == label)


def poles(type_id):
    axes = TAXONOMY[type_id]["axes"]
    return [lab[val.index(axes[k])] for k, lab, val in zip(AXIS_KEYS, AXIS_LABELS, AXIS_VALUES)]


def make_sets(_):
    with (ROOT / "data/labeling/source/persons.csv").open(encoding="utf-8-sig", newline="") as f:
        people = {r["person_id"]: r for r in csv.DictReader(f)}
    pairs = {
        p["pair_id"]: p
        for p in map(
            json.loads,
            (ROOT / "data/labeling/source/pairs.jsonl").read_text(encoding="utf-8").splitlines(),
        )
    }
    with (DATA / "couples.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    def person(pid):
        r = people[pid]
        y, m, d = map(int, r["birth_date"].split("-"))
        h, mi = map(int, r["birth_time"].split(":")) if r["birth_time"] else (None, None)
        return build_person(r["gender"], y, m, d, h, mi, r["mbti"])

    for name, (split, n) in SETS.items():
        dest = DATA / f"generation_{name}.jsonl"
        if dest.exists():
            raise SystemExit(f"{dest.name} 이미 있음: 세트는 고정한다")
        cands = []
        for r in rows:
            if r["split"] != split:
                continue
            p = pairs[r["couple_id"]]
            A, B = person(p["person_a"]), person(p["person_b"])
            F = build_pair(A, B)["features"]
            cands.append(
                {
                    "couple_id": r["couple_id"],
                    "type_id": type_of(r["label"]),
                    "input_text": r["input_text"],
                    "limitations": limitations(A, B),
                    "tags": [
                        t
                        for t, on in (
                            (
                                "missing_hour",
                                not (A["saju"]["time_known"] and B["saju"]["time_known"]),
                            ),
                            ("same_day_element", F["same_day_element"]),
                        )
                        if on
                    ],
                    "_key": hashlib.sha256(f"{name}:{r['couple_id']}".encode()).hexdigest(),
                }
            )
        cands.sort(key=lambda c: c["_key"])
        chosen = []
        for tag, share in QUOTA.items():
            need = round(n * share)
            for c in cands:
                if need <= sum(tag in x["tags"] for x in chosen):
                    break
                if tag in c["tags"] and c not in chosen:
                    chosen.append(c)
        # Fill the rest preferring types not yet covered.
        while len(chosen) < n:
            seen = Counter(c["type_id"] for c in chosen)
            c = min(
                (c for c in cands if c not in chosen), key=lambda c: (seen[c["type_id"]], c["_key"])
            )
            chosen.append(c)
        dest.write_text(
            "".join(
                json.dumps({k: v for k, v in c.items() if k != "_key"}, ensure_ascii=False) + "\n"
                for c in chosen
            ),
            encoding="utf-8",
        )
        print(
            name,
            len(chosen),
            "types",
            len({c["type_id"] for c in chosen}),
            dict(Counter(t for c in chosen for t in c["tags"])),
        )


def check(item, parsed):
    """Rule-based first-pass checks. True means a problem was found."""
    if parsed is None:
        return {}
    texts = [
        parsed["summary"],
        *parsed["strengths"],
        *parsed["adjustments"],
        parsed["conversation_tip"],
    ]
    joined = " ".join(texts)
    try:
        PublicResult(
            **parsed,
            type_id=item["type_id"],
            axes=TAXONOMY[item["type_id"]]["axes"],
            limitations=item["limitations"],
            evidence_status="ai_draft_unreviewed",
        )
        contract = None
    except (ValueError, TypeError) as e:
        contract = str(e).splitlines()[1] if "\n" in str(e) else str(e)
    mentioned = [p for p in poles(item["type_id"]) if p in joined]
    return {
        "contract_error": contract,
        "too_long": any(len(t) > 180 for t in texts) or len(parsed["summary"]) > 120,
        "leak": bool(LEAK.search(joined)),
        "assertive": ASSERTIVE.findall(joined),
        "superiority": SUPERIOR.findall(joined),
        "fabricated_relations": [
            r for r in RELATIONS if r in joined and r not in item["input_text"]
        ],
        "axis_mentions": len(mentioned),
    }


def run(a):
    from lovecode.generator import LangChainExplainer

    items = [
        json.loads(x)
        for x in (DATA / f"generation_{a.set}.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    explainer = LangChainExplainer(a.backend, a.model)
    slug = re.sub(r"[^A-Za-z0-9.-]+", "_", explainer.model or "unset")
    dest = OUT / f"{a.set}__{a.backend}__{slug}__{a.tag}.jsonl"
    if dest.exists():
        raise SystemExit(f"{dest.name} 이미 있음: 새 --tag 지정 (최종 세트는 모델당 한 번)")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as f:
        for i, item in enumerate(items, 1):
            parsed, meta = explainer.draft(
                item["input_text"], item["type_id"], allow_paid=a.allow_paid
            )
            u = meta["usage"]
            cost = None
            if a.price_in is not None and u:
                cost = (
                    u.get("input_tokens", 0) * a.price_in + u.get("output_tokens", 0) * a.price_out
                ) / 1e6
            rec = {
                "couple_id": item["couple_id"],
                "type_id": item["type_id"],
                "tags": item["tags"],
                "meta": meta,
                "cost_usd": cost,
                "output": parsed,
                "checks": check(item, parsed),
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(
                f"[{i}/{len(items)}] {item['couple_id']} {meta['error'] or 'ok'} {meta['elapsed_seconds']:.1f}s"
            )
    print("저장:", dest)


def summarize(_):
    lines = [
        "| 세트 | 백엔드 | 모델 | 프롬프트 태그 | 건수 | 호출 실패 | 스키마 실패 | 계약 위반 | 길이 초과 | 금지 정보 노출 | 단정 표현 | 극 우열 | 지어낸 관계 | 축 언급(평균/4) | 응답 시간 중앙값(s) | 출력 토큰 평균 | 비용 합계(USD) |",
        "|" + "---|" * 17,
    ]
    summary = []
    for path in sorted(OUT.glob("*.jsonl")):
        recs = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
        set_, backend, model, tag = path.stem.split("__")
        ok = [r for r in recs if r["output"]]
        lat = sorted(r["meta"]["elapsed_seconds"] for r in recs)
        out_tok = [r["meta"]["usage"].get("output_tokens", 0) for r in ok if r["meta"]["usage"]]
        costs = [r["cost_usd"] for r in recs if r["cost_usd"] is not None]
        s = {
            "set": set_,
            "backend": backend,
            "model": model,
            "tag": tag,
            "n": len(recs),
            "request_failed": sum(r["meta"]["error"] == "PROVIDER_REQUEST_FAILED" for r in recs),
            "schema_rejected": sum(r["meta"]["error"] == "SCHEMA_REJECTED" for r in recs),
            "contract_violation": sum(bool(r["checks"].get("contract_error")) for r in ok),
            "too_long": sum(r["checks"].get("too_long", False) for r in ok),
            "leak": sum(r["checks"].get("leak", False) for r in ok),
            "assertive": sum(bool(r["checks"].get("assertive")) for r in ok),
            "superiority": sum(bool(r["checks"].get("superiority")) for r in ok),
            "fabricated_relations": sum(bool(r["checks"].get("fabricated_relations")) for r in ok),
            "axis_mentions_mean": sum(r["checks"]["axis_mentions"] for r in ok) / len(ok)
            if ok
            else None,
            "latency_median_s": lat[len(lat) // 2] if lat else None,
            "output_tokens_mean": sum(out_tok) / len(out_tok) if out_tok else None,
            "cost_usd_total": sum(costs) if costs else None,
        }
        summary.append(s)
        fmt = lambda v, d=2: (
            "-" if v is None else (f"{v:.{d}f}" if isinstance(v, float) else str(v))
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    set_,
                    backend,
                    model,
                    tag,
                    str(s["n"]),
                    *(
                        str(s[k])
                        for k in (
                            "request_failed",
                            "schema_rejected",
                            "contract_violation",
                            "too_long",
                            "leak",
                            "assertive",
                            "superiority",
                            "fabricated_relations",
                        )
                    ),
                    fmt(s["axis_mentions_mean"]),
                    fmt(s["latency_median_s"], 1),
                    fmt(s["output_tokens_mean"], 0),
                    fmt(s["cost_usd_total"], 4),
                ]
            )
            + " |"
        )
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("make-sets").set_defaults(fn=make_sets)
    r = sub.add_parser("run")
    r.add_argument("--set", choices=list(SETS), required=True)
    r.add_argument("--backend", choices=["ollama", "openai"], required=True)
    r.add_argument("--model")
    r.add_argument("--tag", default="v1")
    r.add_argument("--allow-paid", action="store_true")
    r.add_argument("--price-in", type=float, help="USD per 1M input tokens")
    r.add_argument("--price-out", type=float, help="USD per 1M output tokens")
    r.set_defaults(fn=run)
    sub.add_parser("summarize").set_defaults(fn=summarize)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
