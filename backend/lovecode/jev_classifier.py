"""Experimental Jev (TypeSafe AI System One) classifier for the 16-type comparison.

API (docs.typesafe.ai/api): POST https://api.typesafe.ai/v1/systemone, Bearer key, body
{state, model, questions:{id:{type:"choice", instructions, criteria:{option: description}}}};
the answer carries `choice`, `probabilities` over every option, and `confidence`.

Docs advice applied: English instructions/criteria (English is the primary training language,
Korean input is accepted at lower accuracy), an object state that keeps the facts next to the
policy they are judged against, and judgments kept in the question.

Modes
- "guided": the state also carries the labeling rules (guideline v1.2 + conventions, the same
  procedure lovecode.labeler implements). Best accuracy, but the model is told the rule that
  produced the labels, so report it as rule-following, not as independent judgment.
- "noguide": only what the four axes mean (fair comparison with the trained classifiers).
"""

import os
import time

from .contracts import TAXONOMY

URL = os.environ.get("LC_JEV_URL", "https://api.typesafe.ai/v1/systemone")
MODEL = os.environ.get("LC_JEV_MODEL", "jev-latest")
POLE_EN = {
    "닮은꼴": "Similar",
    "보완형": "Complementary",
    "열정형": "Passionate",
    "안정형": "Steady",
    "밀착형": "Close",
    "독립형": "Independent",
    "바로 풀기": "ResolveNow",
    "시간 두기": "TakeTime",
}

AXES_EN = (
    "Four axes, two poles each, no pole is better:\n"
    "1 chemistry: Similar (alike temperaments feel comfortable) vs Complementary (each fills "
    "what the other lacks)\n"
    "2 temperature: Passionate (strong, changing emotional expression) vs Steady (calm, consistent)\n"
    "3 distance: Close (time together comes first) vs Independent (each keeps their own space)\n"
    "4 conflict: ResolveNow (talk it out on the spot) vs TakeTime (cool down, then talk)"
)

GLOSSARY = (
    "Korean terms in the facts: 닮은꼴/보완형/열정형/안정형/밀착형/독립형/바로 풀기/시간 두기 = the poles; "
    "A,B = the two people; 사주 = four pillars (year month day hour, 없음 = hour unknown); "
    "오행 목화토금수 = wood fire earth metal water with counts; 일간 = day stem; 봄/여름/가을/겨울생 = "
    "season; 신강/신약/중화 = strong/weak/balanced self; 차가움/뜨거움/온화 = cold/hot/mild chart; "
    "필요 = needed elements; 기신 = harmful element; 없는 = missing elements; 생시모름 = birth hour "
    "unknown; 공급 B→A 많음/보통/적음 = how much B supplies what A needs (many/some/few); 유사도 = "
    "element-distribution similarity 0-1; 정반대 = opposite chart temperatures (예 yes / 아니오 no); "
    "합친온도 = combined temperature; 같은계절/같은일간 = same season / same day-stem element; "
    "A→B 편재 etc. = the ten-god B's day stem is to A; 배우자성 = that ten-god is A's spouse star; "
    "MBTI같음 N = number of identical MBTI letters. 관계 = relations between the two charts, "
    "written TYPE+importance (4 day stems, 3 day branches or 암합, 2 month involved, 1 other), "
    "positions (년/월/일/시 + 간 stem / 지 branch), tags: X기신누름 = presses X's harmful element, "
    "X필요막음 = blocks what X needs, X도움 / X부담 = the combination helps / burdens X. Types: 천간합 "
    "stem combination, 육합 반합 삼합 방합 암합 = branch combinations, 충 천간충 = clash, 원진 해 형 = "
    "hidden conflicts (combined like 원진·해)."
)

RULES = (
    "Labeling procedure (apply exactly). Count each character pair once per axis at its highest "
    "importance; if a pair has both 충 and 원진/해/형, count it only as 충. For each axis add saju "
    "points per pole. If the gap is >= 1.5, saju decides. Otherwise the MBTI rule decides. If MBTI "
    "ties, take the pole with more saju points; if saju is also exactly tied, use the axis tie rule.\n"
    "CHEMISTRY. Similar: 유사도>=0.85 (1), same day-stem element (1), same season (1), needed "
    "elements identical (1) or overlapping (0.5). Complementary: 유사도<0.65 (1), opposite "
    "temperatures (2), supply 많음 both ways (2) or one way (0.5), one person's missing element "
    "present in the other's 오행 counts (1). MBTI: 3-4 same letters Similar, 0-1 Complementary, "
    "2 tie. Tie rule: 유사도>=0.75 Similar else Complementary.\n"
    "TEMPERATURE. Passionate: day-stem 천간합 (2), day-stem 천간충 (2 if tagged, 0.5 if untagged), "
    "each other 충/천간충 of importance>=2 (기신누름 1, 필요막음 0.5, both 0.75, untagged 0.5), any "
    "spouse star (1), combined 뜨거움 or either person 뜨거움 (1). Steady: some combination "
    "(육합 반합 삼합 방합 암합) and no clash of importance>=2 (1), either ten-god is 비견 겁재 편인 "
    "정인 (1), combined 차가움 (1), both 온화 (1). MBTI: count both-F and both-E for Passionate, "
    "both-T and both-I for Steady. Tie rule: Passionate if day-stem 천간합, spouse star, or the "
    "day-stem ten-god family is wealth/officer (재성 관성), else Steady.\n"
    "DISTANCE. Day branches (일지 vs 일지, or 삼합/방합 containing both day branches): combination "
    "Close 2, clash/hidden Independent 2 regardless of tags, if both then Close +0.5; no day-branch "
    "relation Independent 1. Month-involved branch relations (월지-월지 or 일지-월지): combination "
    "Close 1, 충 Independent 1, hidden Independent 0.5. Spouse star or day-stem 천간합 Close 1. A 신약 "
    "person receiving 공급 많음 Close 1. Both 신강 Independent 1. MBTI: both E Close / both I "
    "Independent; if E/I differ use both J Close / both P Independent. Tie rule: Independent.\n"
    "CONFLICT. Untagged clash ResolveNow 0.5; untagged hidden TakeTime 0.5 (hidden tagged only "
    "기신누름 does not count). Tagged day-branch or day-stem clash ResolveNow 2; tagged day-branch "
    "hidden with 필요막음 TakeTime 2. If neither strong signal: no clash at all TakeTime 1; else "
    "compare the highest importance of tagged clash vs tagged hidden, higher side +1, equal: clash "
    "기신누름 and hidden 필요막음 -> ResolveNow 1, clash without 기신누름 and hidden 필요막음 -> "
    "TakeTime 1. Any tagged clash with 기신누름 ResolveNow 1; any tagged hidden with 필요막음 TakeTime 1. "
    "Either person 신강 ResolveNow 1; both 신약 TakeTime 1. MBTI: both-T and both-E ResolveNow, both-F "
    "and both-I TakeTime. Tie rule: both T ResolveNow, both F TakeTime, else ResolveNow if any clash."
)


def option(type_id):
    return "_".join(POLE_EN[p] for p in TAXONOMY[type_id]["label"].split("·"))


OPTIONS = {option(k): k for k in TAXONOMY}


def request_body(text, mode):
    state = {"couple_facts": text, "glossary": GLOSSARY, "axes": AXES_EN}
    if mode == "guided":
        state["labeling_rules"] = RULES
    instructions = (
        "Classify this couple into exactly one of the 16 relationship types: pick one pole on each "
        "of the four axes from couple_facts"
        + (", following labeling_rules exactly." if mode == "guided" else ".")
    )
    criteria = {
        option(k): f"{' / '.join(POLE_EN[p] for p in v['label'].split('·'))} ({v['label']})"
        for k, v in TAXONOMY.items()
    }
    return {
        "state": state,
        "model": MODEL,
        "questions": {
            "relationship_type": {
                "type": "choice",
                "instructions": instructions,
                "criteria": criteria,
            }
        },
    }


class JevClassifier:
    """Same interface as LLMClassifier: classify(text, allow_paid) -> (type_id | None, meta)."""

    backend = "jev"

    def __init__(self, mode="guided", transport=None, retries=3):
        if mode not in ("guided", "noguide"):
            raise ValueError("UNKNOWN_MODE")
        self.mode = mode
        self.model = MODEL
        self.prompt_version = f"jev-{mode}-v1"
        self.transport = transport
        self.retries = retries
        self._chain = None

    def _post(self, body):
        import httpx

        key = os.environ.get("LC_JEV_API_KEY") or _dotenv("LC_JEV_API_KEY")
        if not key:
            raise RuntimeError("LC_JEV_API_KEY_REQUIRED")
        with httpx.Client(
            timeout=httpx.Timeout(60, connect=10), transport=self.transport, trust_env=False
        ) as client:
            for attempt in range(self.retries + 1):
                r = client.post(URL, json=body, headers={"Authorization": f"Bearer {key}"})
                # Docs: back off on 429 rate limit and 529 overloaded.
                if r.status_code in (429, 529) and attempt < self.retries:
                    time.sleep(2**attempt)
                    continue
                r.raise_for_status()
                return r.json()

    def chain(self):
        if self._chain is None:
            from langchain_core.runnables import RunnableLambda

            self._chain = RunnableLambda(
                lambda text: request_body(text, self.mode)
            ) | RunnableLambda(self._post)
        return self._chain

    def classify(self, text, *, allow_paid=False):
        meta = {
            "backend": "jev",
            "model": self.model,
            "prompt_version": self.prompt_version,
            "settings": {"mode": self.mode},
            "error": None,
            "usage": {},
        }
        if not allow_paid:
            meta.update(error="API_DISABLED", elapsed_seconds=0.0)
            return None, meta
        start = time.perf_counter()
        try:
            data = self.chain().invoke(text)
            ans = data["answers"]["relationship_type"]
            pred = OPTIONS[ans["choice"]]
        except Exception as e:  # noqa: BLE001 - network/HTTP/shape errors map to one code
            # Type name only: messages may echo request content.
            meta.update(
                error=f"PROVIDER_REQUEST_FAILED:{type(e).__name__}",
                elapsed_seconds=time.perf_counter() - start,
            )
            return None, meta
        meta["elapsed_seconds"] = time.perf_counter() - start
        meta["usage"] = data.get("usage", {})
        meta["model"] = data.get("model", self.model)
        meta["confidence"] = ans.get("confidence")
        meta["probabilities"] = {
            OPTIONS[k]: v for k, v in ans.get("probabilities", {}).items() if k in OPTIONS
        }
        return pred, meta


def _dotenv(name):
    from dotenv import dotenv_values

    return dotenv_values(".env").get(name)
