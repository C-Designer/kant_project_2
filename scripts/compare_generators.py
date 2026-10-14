"""해설 비교: 로컬 LLM(Ollama) vs 클라우드 LLM(OpenAI). 팀 공통 기준은 docs/generation_eval_protocol.md.

1) 세트 (한 번만, 레포에 커밋): data/lovecode-rule5 의 validation → 개발 15건, test → 최종 24건
   uv run python scripts/compare_generators.py make-sets
2) 실행 (모델만 바꾼다. 프롬프트·설정은 코드에 고정)
   uv run python scripts/compare_generators.py run --set eval --backend ollama --model <모델>
   uv run python scripts/compare_generators.py run --set eval --backend openai --allow-paid
       --price-in <USD/1M 입력> --price-out <USD/1M 출력>      # 실행 당일 가격표 값
3) 순위표: uv run python scripts/compare_generators.py rank      # 품질 > 비용 > 시간 > 개인정보

type_id는 데이터셋 라벨(규칙 라벨)을 쓴다. 모든 모델에 같은 유형을 주고 해설만 비교한다.
LLM 입력은 읽기 쉬운 v2 서술형 텍스트(분류기 입력인 v5 압축형과 같은 사실).
"""

import argparse
import hashlib
import json
import re
import statistics
import sys
import zlib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from lovecode.checks import ASSERTIVE, RELATIONS, SUPERIOR, opposite_poles, poles
from lovecode.contracts import TAXONOMY, PublicResult
from lovecode.features import limitations
from lovecode.saju import build_pair

DATA = ROOT / "data/lovecode-rule5"
SOURCE = DATA / "train4800h"  # couples.csv + synthetic_people/pairs (validation·test 공유)
OUT = ROOT / "artifacts/reports/generation/rule5"
SETS = {"development": ("validation", 15), "eval": ("test", 24)}
# Quotas so both sets include the hard cases named in the plan.
QUOTA = {"missing_hour": 0.25, "same_day_element": 0.2}

LEAK = re.compile(r"[EI][SN][TF][JP]|[一-鿿]|https?://|[<>#*]")


def type_of(label):
    return next(k for k, v in TAXONOMY.items() if v["label"] == label)


def make_sets(_):
    import csv

    from lovecode.dataset import load_pair_facts

    facts = load_pair_facts(SOURCE)
    with (SOURCE / "couples.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for name, (split, n) in SETS.items():
        dest = DATA / f"generation_{name}.jsonl"
        if dest.exists():
            raise SystemExit(f"{dest.name} 이미 있음: 세트는 고정한다")
        cands = []
        for r in rows:
            if r["split"] != split:
                continue
            A, B, F = facts[r["couple_id"]]
            text = build_pair(A, B, seed=zlib.crc32(r["couple_id"].encode()))["text"]
            cands.append(
                {
                    "couple_id": r["couple_id"],
                    "type_id": type_of(r["label"]),
                    "input_text": text,
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
    """Rule-based checks; a non-empty value means a problem was found."""
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
    return {
        # contract covers length limits and banned content (MBTI codes, hanja, URL, markup)
        "contract_error": contract,
        "fabricated_relations": [
            r for r in RELATIONS if r in joined and r not in item["input_text"]
        ],
        # e.g. the type is 열정형 but the text calls the couple 안정형
        "opposite_pole": [p for p in opposite_poles(item["type_id"]) if p in joined],
        "assertive": ASSERTIVE.findall(joined),
        "superiority": SUPERIOR.findall(joined),
        "axis_mentions": sum(p in joined for p in poles(item["type_id"])),
    }


VIOLATIONS = ("contract_error", "fabricated_relations", "opposite_pole", "assertive", "superiority")


def is_violation(rec):
    return bool(rec["meta"]["error"]) or any(rec["checks"].get(k) for k in VIOLATIONS)


def environment(backend, model):
    """Recorded with every result, because teammates run on different PCs."""
    import os
    import platform
    import subprocess

    env = {"backend": backend, "model": model, "os": platform.platform()}
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        env["gpu"] = out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        env["gpu"] = None
    if backend == "ollama":
        import httpx

        url = os.environ.get("LC_OLLAMA_URL", "http://127.0.0.1:11434")
        try:
            show = httpx.post(f"{url}/api/show", json={"model": model}, timeout=10).json()
            details = show.get("details", {})
            env["ollama_model"] = {
                k: details.get(k) for k in ("parameter_size", "quantization_level", "family")
            }
            env["ollama_version"] = (
                httpx.get(f"{url}/api/version", timeout=10).json().get("version")
            )
        except (httpx.HTTPError, ValueError):
            pass
    return env


def run(a):
    from lovecode.generator import LangChainExplainer

    items = [
        json.loads(x)
        for x in (DATA / f"generation_{a.set}.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    if a.backend == "openai" and a.set == "eval" and a.price_in is None:
        raise SystemExit(
            "클라우드 최종 비교는 --price-in/--price-out (실행 당일 USD/1M 토큰 단가) 필요"
        )
    explainer = LangChainExplainer(a.backend, a.model)
    slug = re.sub(r"[^A-Za-z0-9.-]+", "_", explainer.model or "unset")
    # --repair scores the service path (draft + one repair) under its own tag.
    tag = a.tag or ("v2r" if a.repair else "v2")
    write = explainer.revise if a.repair else explainer.draft
    dest = OUT / f"{a.set}__{a.backend}__{slug}__{tag}.jsonl"
    if dest.exists():
        raise SystemExit(f"{dest.name} 이미 있음: 새 --tag 지정 (최종 세트는 모델당 한 번)")
    dest.parent.mkdir(parents=True, exist_ok=True)
    env = environment(a.backend, explainer.model)
    with dest.open("w", encoding="utf-8") as f:
        for i, item in enumerate(items, 1):
            parsed, meta = write(item["input_text"], item["type_id"], allow_paid=a.allow_paid)
            meta["env"] = env
            u = meta["usage"]
            if a.backend == "ollama":
                cost = 0.0  # no API fee; hardware and electricity are not counted
            elif a.price_in is not None and u:
                cost = (
                    u.get("input_tokens", 0) * a.price_in + u.get("output_tokens", 0) * a.price_out
                ) / 1e6
            else:
                cost = None
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
            status = meta["error"] or "ok"
            print(f"[{i}/{len(items)}] {item['couple_id']} {status} {meta['elapsed_seconds']:.1f}s")
    print("저장:", dest)


def summarize_file(path):
    recs = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    _, backend, model, tag = path.stem.split("__")
    costs = [r["cost_usd"] for r in recs]
    env = recs[0]["meta"].get("env", {}) if recs else {}
    by_check = {k: sum(bool(r["checks"].get(k)) for r in recs) for k in VIOLATIONS}
    by_check["request_or_schema_error"] = sum(bool(r["meta"]["error"]) for r in recs)
    return {
        "file": path.name,
        "backend": backend,
        "model": model,
        "tag": tag,
        "n": len(recs),
        "violations": sum(is_violation(r) for r in recs),
        "by_check": by_check,
        "cost_usd": None if any(c is None for c in costs) else sum(costs),
        "latency_median_s": statistics.median(r["meta"]["elapsed_seconds"] for r in recs)
        if recs
        else None,
        "external_transfer": backend == "openai",
        "gpu": env.get("gpu"),
    }


def ranked(rows):
    """품질(위반 건수) > 비용 > 시간 > 개인정보(외부 전송 없는 쪽 우선)."""
    big = float("inf")
    return sorted(
        rows,
        key=lambda r: (
            r["violations"],
            big if r["cost_usd"] is None else r["cost_usd"],
            big if r["latency_median_s"] is None else r["latency_median_s"],
            r["external_transfer"],
        ),
    )


def rank(a):
    # One tag per table: v2 = first drafts (team protocol), v2r = with one repair.
    files = sorted(OUT.glob(f"{a.set}__*__*__{a.tag}.jsonl"))
    rows = ranked([summarize_file(p) for p in files])
    head = "| 순위 | 모델 | 백엔드 | 위반 (건/전체) | 계약 | 지어낸 관계 | 반대 극 | 단정 | 우열 "
    head += "| 호출·형식 오류 | 비용 USD | 응답 시간 중앙값 | 외부 전송 | GPU |"
    title = f"세트: {a.set} | 태그: {a.tag} | 순위 기준: 품질(위반 건수) > 비용 > 시간 > 개인정보"
    lines = [title, "", head]
    lines.append("|" + "---|" * 14)
    for i, r in enumerate(rows, 1):
        b = r["by_check"]
        cells = [
            str(i),
            r["model"],
            r["backend"],
            f"{r['violations']}/{r['n']}",
            str(b["contract_error"]),
            str(b["fabricated_relations"]),
            str(b["opposite_pole"]),
            str(b["assertive"]),
            str(b["superiority"]),
            str(b["request_or_schema_error"]),
            "-" if r["cost_usd"] is None else f"{r['cost_usd']:.4f}",
            "-" if r["latency_median_s"] is None else f"{r['latency_median_s']:.1f}s",
            "있음" if r["external_transfer"] else "없음",
            r["gpu"] or "-",
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines += [
        "",
        (
            "응답 시간은 PC마다 다르므로 GPU 열과 함께 읽는다. "
            "비용: 로컬 0(API 요금 없음), 클라우드는 토큰 × 실행 당일 단가."
        ),
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    name = f"ranking_{a.set}" + ("" if a.tag == "v2" else f"_{a.tag}")
    (OUT / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / f"{name}.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("make-sets").set_defaults(fn=make_sets)
    r = sub.add_parser("run")
    r.add_argument("--set", choices=list(SETS), required=True)
    r.add_argument("--backend", choices=["ollama", "openai"], required=True)
    r.add_argument("--model")
    r.add_argument("--tag", help="기본 v2, --repair면 v2r")
    r.add_argument("--repair", action="store_true", help="서비스 경로: 위반 시 1번 다시 쓰기")
    r.add_argument("--allow-paid", action="store_true")
    r.add_argument("--price-in", type=float, help="USD per 1M input tokens")
    r.add_argument("--price-out", type=float, help="USD per 1M output tokens")
    r.set_defaults(fn=run)
    k = sub.add_parser("rank")
    k.add_argument("--set", choices=list(SETS), default="eval")
    k.add_argument("--tag", default="v2", help="v2 = 첫 해설(팀 기준), v2r = 다시 쓰기 포함")
    k.set_defaults(fn=rank)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
