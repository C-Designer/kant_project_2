"""Check that native Git builds assemble the runtime without local staging or secrets."""
import runpy
from pathlib import Path

import pytest

BUILD_SCRIPT = Path(__file__).resolve().parents[1] / "deploy/vercel/build_model.py"


def test_git_build_copies_backend_from_outside_project_root(tmp_path):
    root = tmp_path / "deploy/vercel"
    root.mkdir(parents=True)
    source = tmp_path / "backend/lovecode"
    source.mkdir(parents=True)
    (source / "api.py").write_text("app = 'test'\n")
    (source / ".env").write_text("TEST_SECRET=must-not-copy\n")
    stage = runpy.run_path(str(BUILD_SCRIPT))["stage_sources"]
    stage(root)
    assert (root / "lovecode/api.py").read_text() == "app = 'test'\n"
    assert not (root / "lovecode/.env").exists()


def test_missing_git_sources_fail_before_model_download(tmp_path):
    root = tmp_path / "deploy/vercel"
    root.mkdir(parents=True)
    stage = runpy.run_path(str(BUILD_SCRIPT))["stage_sources"]
    with pytest.raises(RuntimeError, match="sourceFilesOutsideRootDirectory"):
        stage(root)
