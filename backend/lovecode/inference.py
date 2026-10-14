"""Load only operator-owned local artifacts; hashes detect drift, not untrusted pickle safety."""

import hashlib
import json
from pathlib import Path

from .contracts import TAXONOMY


class ArtifactError(ValueError):
    pass


class Classifier:
    def __init__(self, directory, *, allow_fixture=False):
        import joblib

        root = Path(directory)
        self.report = json.loads((root / "report.json").read_text(encoding="utf-8"))
        if self.report.get("fixture") and not allow_fixture:
            raise ArtifactError("FIXTURE_MODEL_NOT_ALLOWED")
        selected = self.report["selected"]
        files = {
            "tfidf_lr": "tfidf_lr.joblib",
            "klue_bert": "klue_bert/model.safetensors",
            "klue_bert_axes": "klue_bert_axes/model.safetensors",
            "tfidf_lr_axes": "tfidf_lr_axes.joblib",
        }
        if selected not in files:
            raise ArtifactError("UNKNOWN_CLASSIFIER")
        filename = files[selected]
        if hashlib.sha256((root / filename).read_bytes()).hexdigest() != self.report.get(
            "artifact_sha256", {}
        ).get(filename):
            raise ArtifactError("MODEL_DIGEST_MISMATCH")
        if selected in ("klue_bert", "klue_bert_axes"):
            from .bert import BertModel

            log = self.report["bert" if selected == "klue_bert" else "bert_axes"]
            self.model = BertModel(
                root / selected, max_length=log["hyperparameters"]["max_length"]
            )
        else:
            self.model = joblib.load(root / filename)
        if set(self.model.classes_) != {v["label"] for v in TAXONOMY.values()}:
            raise ArtifactError("CLASS_COVERAGE_MISMATCH")

    def predict(self, text):
        label = self.model.predict([text])[0]
        return next(k for k, v in TAXONOMY.items() if v["label"] == label)
