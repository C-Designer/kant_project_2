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


def test_git_build_removes_obsolete_staged_sources(tmp_path):
    root = tmp_path / 'deploy/vercel'
    root.mkdir(parents=True)
    source = tmp_path / 'backend/lovecode'
    source.mkdir(parents=True)
    (source / 'api.py').write_text('app = 1\n')
    stale = root / 'lovecode'
    stale.mkdir()
    (stale / 'db.py').write_text('obsolete = True\n')
    stage = runpy.run_path(str(BUILD_SCRIPT))['stage_sources']
    stage(root)
    assert (stale / 'api.py').is_file()
    assert not (stale / 'db.py').exists()


def test_manual_package_includes_all_relative_runtime_imports():
    import ast

    repo = BUILD_SCRIPT.parents[2]
    modules = set(runpy.run_path(str(repo / 'scripts/prepare_vercel.py'))['API_MODULES'])
    for module in modules:
        tree = ast.parse((repo / 'backend/lovecode' / (module + '.py')).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
                dependency = node.module.split('.')[0]
                assert dependency in modules | {'saju'}, (module, dependency)
