"""Stage allowlisted deployment files without .env, local DB, training data, or caches."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / ".runtime/vercel-app"
API_MODULES = (
    "__init__", "api", "settings", "contracts", "concurrency", "checks", "service",
    "provider", "generator", "inference", "bert", "axes", "features", "share",
)


def stage():
    api = STAGE / "api"
    web = STAGE / "web"
    api.mkdir(parents=True, exist_ok=True)
    web.mkdir(parents=True, exist_ok=True)
    for name in ("main.py", "pyproject.toml", "vercel.json", "build_model.py"):
        shutil.copy2(ROOT / "deploy/vercel" / name, api / name)
    package = api / "lovecode"
    if package.exists():
        shutil.rmtree(package)
    package.mkdir()
    for name in API_MODULES:
        shutil.copy2(ROOT / "backend/lovecode" / (name + ".py"), package / (name + ".py"))
    shutil.copytree(ROOT / "backend/lovecode/saju", package / "saju", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("app", "components", "data", "lib", "public"):
        destination = web / name
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(ROOT / "frontend" / name, destination)
    for name in ("package.json", "package-lock.json", "next.config.ts", "tsconfig.json", "vercel.json"):
        shutil.copy2(ROOT / "frontend" / name, web / name)
    for directory in (api, web):
        (directory / ".vercelignore").write_text(
            ".env*\n.venv\n__pycache__\nnode_modules\n.next\nmodel\nrelease.zip\n"
        )
    print(f"Staged API and web in {STAGE}")


if __name__ == "__main__":
    stage()
