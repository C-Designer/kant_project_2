"""lovecode-v2: ported saju text, dataset, classifier candidates, LangChain explainer (offline)."""

import csv
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
