"""Server-only orchestration. Never persist raw inputs or substitute a fixture on failure."""

import threading
import time

from .concurrency import StageLimit
from .features import VERSION, analysis_inputs
from .generator import LangChainExplainer
from .inference import Classifier
from .provider import OpenAIProvider
from .settings import settings


class AnalysisService:
    def __init__(self, provider=None, classifier=None, explainer=None):
        self.provider = provider or OpenAIProvider()
        self.classifier = classifier
        self._classifier_lock = threading.Lock()
        self._bert_slots = StageLimit(settings().bert_concurrency)
        self._explanation_slots = StageLimit(settings().explanation_concurrency)
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
        deadline = time.monotonic() + settings().analysis_wait_seconds
        # Raw birthday, time and gender stay on this server; only derived chart/MBTI go out.
        # One saju computation feeds the classifier, the explainer and the limitations.
        inputs = analysis_inputs(body.person_a, body.person_b)
        text, missing = inputs["narrative"], inputs["limitations"]
        if settings().classifier_mode == "local":
            # Release models declare their training format; keep historical models compatible.
            dataset = self.classifier.report.get("dataset", {})
            if dataset.get("text_format") == "compact-v5":
                classifier_text = inputs["compact"]
            else:
                # Pre-rule5 models were trained on the legacy calendar text.
                from .calendar import input_text

                classifier_text = input_text(body.person_a, body.person_b)
            with self._bert_slots.acquire(deadline):
                type_id = self.classifier.predict(classifier_text)
        else:
            with self._explanation_slots.acquire(deadline):
                label, _ = self.provider.label(text, allow_paid=True, synthetic=False)
            type_id = label["type_id"]
        with self._explanation_slots.acquire(deadline):
            result, explanation_meta = self.explainer.explain(
                text, type_id, allow_paid=True, synthetic=False, limitations=missing
            )
        return result, {
            "generator": settings().model,
            "classifier": settings().classifier_mode,
            "calendar": VERSION,
            "explanation": explanation_meta.get("prompt_version", "direct-responses"),
        }
