"""lovecode-v2: ported saju text, dataset, classifier candidates, LangChain explainer (offline)."""

import csv
import json
import shutil
from datetime import date
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from lovecode.contracts import TAXONOMY, Person
from lovecode.dataset import validate
from lovecode.features import pair_text, to_saju_person
from lovecode.generator import Explanation, LangChainExplainer
from lovecode.provider import ProviderError
from lovecode.settings import settings
from lovecode.train import train


def person(**kw):
    base = {
        "gender": "male",
        "birth_date": date(1995, 12, 11),
        "birth_time": "22:12",
        "mbti": "INTP",
    }
    return Person(**(base | kw))


def test_pair_text_is_swap_invariant_and_keeps_caller_limitations():
    a = person()
    b = person(gender="unspecified", birth_date=date(1997, 7, 8), birth_time=None, mbti="ENFJ")
    text_ab, lim_ab = pair_text(a, b)
    text_ba, lim_ba = pair_text(b, a)
    assert text_ab == text_ba
    assert lim_ab == ["missing_hour_b"] and lim_ba == ["missing_hour_a"]
    assert not text_ab.startswith(("=", "+", "-", "@"))


def test_dst_and_utc830_are_corrected():
    # 1987 summer time was UTC+10; 1955 standard time was UTC+8:30.
    dst = to_saju_person(person(birth_date=date(1987, 7, 1), birth_time="10:30"))["saju"]
    old = to_saju_person(person(birth_date=date(1955, 3, 1), birth_time="10:30"))["saju"]
    assert dst["std_time"] == "1987-07-01 09:30"
    assert old["std_time"] == "1955-03-01 11:00"


def test_lovecode_v2_dataset_is_valid_and_covers_all_types():
    summary = validate("data/lovecode-v2")
    assert summary["rows"] == 600 and summary["approved"] == 0
    with open("data/lovecode-v2/couples.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert {r["review_status"] for r in rows} <= {"ai_reviewed", "pending"}
    for s in ("train", "validation", "test"):
        assert len({r["label"] for r in rows if r["split"] == s}) == 16


@pytest.fixture
def fixture_labels(tmp_path):
    dest = tmp_path / "data"
    shutil.copytree("data/synthetic-v1", dest)
    from lovecode.dataset import write_csv

    rows = list(csv.DictReader((dest / "couples.csv").open(encoding="utf-8", newline="")))
    labels = [v["label"] for v in TAXONOMY.values()]
    counters = {}
    for r in rows:
        n = counters.get(r["split"], 0)
        r.update(label=labels[n % 16], label_reason="모의 학습 배선 검증 전용")
        counters[r["split"]] = n + 1
    write_csv(dest / "couples.csv", rows)
    return dest


def test_candidate_selection_and_bert_revision_guard(fixture_labels, tmp_path):
    base = {
        "dir": fixture_labels,
        "allow_ai_drafts": True,
        "dry_run": False,
        "encoder": "x",
        "encoder_revision": None,
        "fixture": True,
    }
    with pytest.raises(ValueError, match="bert-revision"):
        train(
            SimpleNamespace(
                **base, candidates="tfidf_lr,klue_bert", bert_revision=None, output=tmp_path / "a"
            )
        )
    with pytest.raises(ValueError, match="candidates"):
        train(SimpleNamespace(**base, candidates="klue_bert", output=tmp_path / "b"))
    report = train(SimpleNamespace(**base, candidates="tfidf_lr", output=tmp_path / "c"))
    assert set(report["candidates"]) == {"tfidf_lr"} and report["selected"] == "tfidf_lr"
    assert list(report["artifact_sha256"]) == ["tfidf_lr.joblib"]


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    def with_structured_output(self, schema, **kwargs):
        def respond(_):
            raw = AIMessage(
                content="",
                usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            )
            return {
                "raw": raw,
                "parsed": schema(**self.payload) if self.payload else None,
                "parsing_error": None if self.payload else ValueError("bad"),
            }

        return RunnableLambda(respond)


GOOD = {
    "summary": "서로 다른 결이 만나 차분하게 맞춰 가는 보완형 관계예요.",
    "strengths": [
        "보완형이라 서로 없는 부분을 채워 줄 수 있어요.",
        "안정형이라 꾸준한 하루가 쌓여요.",
    ],
    "adjustments": [
        "독립형이라 각자의 시간을 미리 말해 보세요.",
        "시간 두기 방식이라 다시 이야기할 때를 약속해 보세요.",
    ],
    "conversation_tip": "요즘 가장 편안했던 순간을 서로 물어보세요.",
}


def test_langchain_explainer_returns_public_result():
    result, meta = LangChainExplainer("ollama", llm=FakeLLM(GOOD)).explain(
        "입력", "T16", limitations=["missing_hour_a"]
    )
    assert result.type_id == "T16" and result.axes == TAXONOMY["T16"]["axes"]
    assert result.evidence_status == "ai_draft_unreviewed" and meta["usage"]["output_tokens"] == 5


def test_langchain_explainer_rejects_bad_output():
    with pytest.raises(ProviderError, match="OUTPUT_REJECTED"):
        LangChainExplainer("ollama", llm=FakeLLM(None)).explain("입력", "T01")
    leaky = GOOD | {"summary": "INTP와 ENFJ의 만남"}
    with pytest.raises(ProviderError, match="OUTPUT_REJECTED"):
        LangChainExplainer("ollama", llm=FakeLLM(leaky)).explain("입력", "T01")


def test_openai_explainer_is_gated(monkeypatch):
    monkeypatch.setattr(settings(), "model", "configured-model")
    explainer = LangChainExplainer("openai", llm=FakeLLM(GOOD))
    assert explainer.external
    with pytest.raises(ProviderError, match="API_DISABLED"):
        explainer.explain("입력", "T01", allow_paid=True)
    monkeypatch.setattr(settings(), "api_enabled", True)
    monkeypatch.setattr(settings(), "api_key", "")
    with pytest.raises(ProviderError, match="CONFIGURATION"):
        explainer.explain("입력", "T01", allow_paid=True)


def test_explanation_schema_requires_two_items():
    with pytest.raises(ValueError):
        Explanation(**(GOOD | {"strengths": ["하나"]}))


def test_ollama_llm_turns_off_thinking_and_caps_context(monkeypatch):
    from lovecode import generator

    monkeypatch.setattr(generator, "_ollama_can_think", lambda base_url, model: True)
    llm = generator.make_llm("ollama", "hybrid-model")
    assert llm.reasoning is False and llm.num_ctx == generator.OLLAMA_NUM_CTX
    monkeypatch.setattr(generator, "_ollama_can_think", lambda base_url, model: False)
    assert generator.make_llm("ollama", "plain-model").reasoning is None


def test_openai_llm_uses_low_reasoning_effort_without_temperature():
    from lovecode import generator

    llm = generator.make_llm("openai", "configured-model", api_key="test-only")
    assert llm.reasoning == {"effort": generator.OPENAI_REASONING_EFFORT}
    assert llm.temperature is None


class FakeChoiceLLM:
    def __init__(self, type_id):
        self.type_id = type_id

    def with_structured_output(self, schema, **kwargs):
        def respond(_):
            raw = AIMessage(
                content="",
                usage_metadata={"input_tokens": 9, "output_tokens": 3, "total_tokens": 12},
            )
            parsed = schema(type_id=self.type_id) if self.type_id else None
            return {
                "raw": raw,
                "parsed": parsed,
                "parsing_error": None if parsed else ValueError("bad"),
            }

        return RunnableLambda(respond)


def test_llm_classifier_returns_one_of_sixteen_and_is_gated(monkeypatch):
    from lovecode.llm_classifier import LLMClassifier, TypeChoice

    pred, meta = LLMClassifier("ollama", llm=FakeChoiceLLM("T07")).classify("입력")
    assert pred == "T07" and meta["error"] is None and meta["usage"]["output_tokens"] == 3
    assert LLMClassifier("ollama", llm=FakeChoiceLLM(None)).classify("입력")[0] is None
    with pytest.raises(ValueError):
        TypeChoice(type_id="T17")
    monkeypatch.setattr(settings(), "model", "configured-model")
    with pytest.raises(ProviderError, match="API_DISABLED"):
        LLMClassifier("openai", llm=FakeChoiceLLM("T01")).classify("입력", allow_paid=True)


def test_jev_classifier_request_parse_and_retry(monkeypatch):
    import httpx
    from lovecode import jev_classifier as jev

    monkeypatch.setenv("LC_JEV_API_KEY", "test-only")
    monkeypatch.setattr(jev.time, "sleep", lambda s: None)
    seen = []

    def handle(request):
        seen.append(json.loads(request.content))
        if len(seen) == 1:
            return httpx.Response(429)
        opt = jev.option("T15")
        return httpx.Response(
            200,
            json={
                "model": "jev-1.13.0",
                "answers": {
                    "relationship_type": {
                        "type": "choice",
                        "choice": opt,
                        "confidence": 0.7,
                        "probabilities": {opt: 0.7, jev.option("T01"): 0.3},
                    }
                },
                "usage": {"input_tokens": 10, "output_tokens": 0},
            },
        )

    clf = jev.JevClassifier("guided", transport=httpx.MockTransport(handle))
    pred, meta = clf.classify("입력", allow_paid=True)
    assert pred == "T15" and meta["error"] is None and meta["probabilities"]["T01"] == 0.3
    body = seen[-1]
    assert len(seen) == 2 and body["model"] == jev.MODEL
    criteria = body["questions"]["relationship_type"]["criteria"]
    assert len(criteria) == 16 and "labeling_rules" in body["state"]
    assert "labeling_rules" not in jev.request_body("입력", "noguide")["state"]
    assert jev.JevClassifier().classify("입력")[1]["error"] == "API_DISABLED"


def test_compact_text_matches_training_format_and_is_swap_invariant():
    from lovecode.features import compact_text

    a = person()
    b = person(gender="female", birth_date=date(1997, 7, 8), birth_time=None, mbti="ENFJ")
    text_ab, lim_ab = compact_text(a, b)
    text_ba, _ = compact_text(b, a)
    assert text_ab == text_ba and lim_ab == ["missing_hour_b"]
    assert "MBTI비교" in text_ab and text_ab.startswith("A ") and "\n관계 " in text_ab


def test_generation_checks_and_ranking_order():
    import sys

    sys.path.insert(0, "scripts")
    import compare_generators as cg

    item = {"type_id": "T03", "limitations": [], "input_text": "A 월지 술과 B 월지 진이 충입니다."}
    parsed = GOOD | {
        "summary": "차분한 안정형 관계예요."
    }  # T03 is 열정형: 안정형 is the opposite pole
    checks = cg.check(item, parsed)
    assert "안정형" in checks["opposite_pole"]
    rows = [
        {
            "violations": 1,
            "cost_usd": 0.0,
            "latency_median_s": 5.0,
            "external_transfer": False,
            "m": "a",
        },
        {
            "violations": 0,
            "cost_usd": 0.02,
            "latency_median_s": 6.0,
            "external_transfer": True,
            "m": "b",
        },
        {
            "violations": 0,
            "cost_usd": 0.0,
            "latency_median_s": 30.0,
            "external_transfer": False,
            "m": "c",
        },
    ]
    # 품질 > 비용 > 시간 > 개인정보
    assert [r["m"] for r in cg.ranked(rows)] == ["c", "b", "a"]
