"""Start only the project's database. Never stop an unrelated container or port owner."""

import json
import secrets
import socket
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "lovecode-local-postgres"
PORT = 55439


def run(args, **kw):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kw)


def main():
    runtime = ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    env = ROOT / ".env"
    pg = runtime / "postgres.env"
    if env.exists() != pg.exists():
        raise SystemExit(
            "설정 파일 일부만 존재합니다. 기존 비밀을 보존하고 .env와 .runtime/postgres.env를 확인하세요."
        )
    if not env.exists():
        password = secrets.token_urlsafe(32)
        pg.write_text(
            f"POSTGRES_USER=lovecode\nPOSTGRES_PASSWORD={password}\nPOSTGRES_DB=lovecode\n"
        )
        pg.chmod(0o600)
        env.write_text(
            f"LC_DATABASE_URL=postgresql+psycopg://lovecode:{password}@127.0.0.1:{PORT}/lovecode\nLC_TEST_DATABASE_URL=postgresql+psycopg://lovecode:{password}@127.0.0.1:{PORT}/lovecode_test\nLC_SIGNING_KEY={secrets.token_urlsafe(48)}\nLC_API_ENABLED=false\nLC_PROVIDER=openai\nLC_API_KEY=\nLC_MODEL=\n"
        )
        env.chmod(0o600)
    found = subprocess.run(["docker", "inspect", NAME], check=False, capture_output=True, text=True)
    if found.returncode == 0:
        info = json.loads(found.stdout)[0]
        if not info["Config"]["Image"].startswith("postgres:17"):
            raise SystemExit("같은 이름의 다른 컨테이너가 있어 중단했습니다.")
        if not info["State"]["Running"]:
            run(["docker", "start", NAME])
    else:
        with socket.socket() as s:
            s.bind(("127.0.0.1", PORT))
        run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                NAME,
                "--env-file",
                str(pg),
                "-p",
                f"127.0.0.1:{PORT}:5432",
                "-v",
                "lovecode-local-pgdata:/var/lib/postgresql/data",
                "postgres:17",
                "-c",
                "log_min_error_statement=panic",
                "-c",
                "log_error_verbosity=terse",
            ]
        )
    for _ in range(30):
        r = subprocess.run(
            ["docker", "exec", NAME, "pg_isready", "-U", "lovecode"],
            check=False,
            capture_output=True,
        )
        if r.returncode == 0:
            break
        time.sleep(1)
    else:
        raise SystemExit("PostgreSQL 준비 시간 초과")
    exists = run(
        [
            "docker",
            "exec",
            NAME,
            "psql",
            "-U",
            "lovecode",
            "-d",
            "lovecode",
            "-Atc",
            "SELECT 1 FROM pg_database WHERE datname='lovecode_test'",
        ]
    ).stdout.strip()
    if not exists:
        run(["docker", "exec", NAME, "createdb", "-U", "lovecode", "lovecode_test"])
    print(f"프로젝트 DB 준비: 127.0.0.1:{PORT} / lovecode + lovecode_test (비밀 출력 없음)")


if __name__ == "__main__":
    main()
