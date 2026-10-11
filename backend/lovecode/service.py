"""Server-only orchestration. Never persist raw inputs or substitute a fixture on failure."""

from .calendar import VERSION, facts, input_text
from .inference import Classifier
from .provider import OpenAIProvider
from .settings import settings


class AnalysisService:
    def __init__(self, provider=None, classifier=None):
        self.provider = provider or OpenAIProvider()
        self.classifier = classifier

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
            type_id = self.classifier.predict(text.replace("인물", "가상 인물"))
        else:
            label, _ = self.provider.label(text, allow_paid=True, synthetic=False)
            type_id = label["type_id"]
        result, _ = self.provider.explain(
            text, type_id, allow_paid=True, synthetic=False, limitations=missing
        )
        return result, {
            "generator": settings().model,
            "classifier": settings().classifier_mode,
            "calendar": VERSION,
        }
