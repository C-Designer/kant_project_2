"""Download only the pinned public Release model; verify before extracting runtime files."""
import hashlib
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent
URL = "https://github.com/C-Designer/kant_project_2/releases/download/model-lovecode-rule5-axes-v1/lovecode-rule5-v5-train4800h-axes-reg.zip"
SHA256 = "dde7c4e61ea99f2588b4bc52ec50f90986291801bcf7e0401ec8e6cdb64eb3f6"
def stage_sources(root=ROOT):
    """Git builds include backend sources outside this project's root directory."""
    source = root.resolve().parents[1] / "backend/lovecode"
    destination = root / "lovecode"
    if source.is_dir():
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", ".env*"))
    if not (destination / "api.py").is_file():
        raise RuntimeError("Backend sources missing; enable sourceFilesOutsideRootDirectory")


def main():
    stage_sources()
    archive = ROOT / "release.zip"
    urllib.request.urlretrieve(URL, archive)
    with archive.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != SHA256:
            raise ValueError("Release archive checksum mismatch")
    prefix = "lovecode-rule5-v5-train4800h-axes-reg/"
    target = ROOT / "model"
    (target / "klue_bert_axes").mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        report = json.loads(z.read(prefix + "report.json"))
        assert report["selected"] == "klue_bert_axes"
        (target / "report.json").write_text(json.dumps(report))
        for filename in ("config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json"):
            relative = "klue_bert_axes/" + filename
            data = z.read(prefix + relative)
            if filename == "model.safetensors":
                assert hashlib.sha256(data).hexdigest() == report["artifact_sha256"][relative]
            (target / relative).write_bytes(data)
    archive.unlink()
    print("Release checksum verified; BERT runtime files extracted")


if __name__ == "__main__":
    main()
