"""Crea un PostgreSQL descartable local; nunca conecta a una BD del proyecto o VPS."""
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

import psycopg


def main():
    nombre = "eventos-video-pg-" + secrets.token_hex(4)
    repo = Path(__file__).resolve().parents[1]
    subprocess.run(["docker", "run", "--rm", "-d", "--name", nombre, "-p", "127.0.0.1:25439:5432",
        "-e", "POSTGRES_USER=eventos", "-e", "POSTGRES_DB=video_test", "-e", "POSTGRES_PASSWORD=prueba-local-video",
        "postgres:16-alpine"], check=True, capture_output=True)
    try:
        for _ in range(100):
            try:
                with psycopg.connect("postgresql://eventos:prueba-local-video@127.0.0.1:25439/video_test", connect_timeout=1): pass
                break
            except psycopg.Error: time.sleep(0.2)
        else: raise RuntimeError("No inicio el PostgreSQL descartable")
        env = {**os.environ, "VIDEO_TEST_DATABASE_URL": "postgresql+psycopg://eventos:prueba-local-video@127.0.0.1:25439/video_test"}
        subprocess.run([sys.executable, "-m", "pytest", "tests/test_video_postgres.py", "-q"], cwd=repo / "backend", env=env, check=True)
    finally:
        subprocess.run(["docker", "rm", "-f", nombre], capture_output=True)


if __name__ == "__main__":
    main()
