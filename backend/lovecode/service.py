"""Server-only orchestration. Never persist raw inputs or substitute a fixture on failure."""

import threading

from .calendar import VERSION, facts, input_text
from .features import compact_text
from .generator import LangChainExplainer
from .inference import Classifier
from .provider import OpenAIProvider
from .settings import settings


class AnalysisService:
    def __init__(self, provider=None, classifier=None, explainer=None):
        self.provider = provider or OpenAIProvider()
        self.classifier = classifier
        self._classifier_lock = threading.Lock()
        self.explainer = explainer or provider or LangChainExplainer("openai")

    def ready(self):
        s = settings()
        if not (
            s.real_analysis_enabled
            and s.api_enabled
            and s.api_key
            and s.model
            and s.provider == "openai"
        ):
            return False
        if s.classifier_mode == "openai":
            return True
        if s.classifier_mode != "local":
            return False
        if self.classifier is None:
            try:
                with self._classifier_lock:
                    if self.classifier is None:
                        self.classifier = Classifier(s.models_dir)
            except (OSError, ValueError, KeyError):
                return False
        return True

    def analyse(self, body):
        # Raw birthday, time and gender stay on this server; only derived chart/MBTI go out.
        text = input_text(body.person_a, body.person_b)
        missing = []
        for suffix, person in (("a", body.person_a), ("b", body.person_b)):
            fact = facts(person)
            if fact["missing_hour"]:
                missing.append("missing_hour_" + suffix)
            if fact["pillar_candidates"]:
                missing.append("boundary_time_unknown_" + suffix)
        text = text.replace("가상 인물", "인물")
        if settings().classifier_mode == "local":
            # Release models declare their training format; keep historical models compatible.
            dataset = self.classifier.report.get("dataset", {})
            if dataset.get("text_format") == "compact-v5":
                classifier_text, missing = compact_text(body.person_a, body.person_b)
            else:
                classifier_text = text.replace("인물", "가상 인물")
            type_id = self.classifier.predict(classifier_text)
        else:
            label, _ = self.provider.label(text, allow_paid=True, synthetic=False)
            type_id = label["type_id"]
        result, explanation_meta = self.explainer.explain(
            text, type_id, allow_paid=True, synthetic=False, limitations=missing
        )
        return result, {
            "generator": settings().model,
            "classifier": settings().classifier_mode,
            "calendar": VERSION,
            "explanation": explanation_meta.get("prompt_version", "direct-responses"),
        }
