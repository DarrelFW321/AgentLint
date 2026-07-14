"""Install a wheel into a clean environment and run the complete test suite."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def venv_python(environment: Path) -> Path:
    executable = "python.exe" if sys.platform == "win32" else "python"
    directory = "Scripts" if sys.platform == "win32" else "bin"
    return environment / directory / executable


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--openai-agents-version")
    args = parser.parse_args()
    wheel = args.wheel.resolve()

    with tempfile.TemporaryDirectory(prefix="agentlint-wheel-") as temporary:
        root = Path(temporary)
        environment = root / "venv"
        workspace = root / "workspace"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = venv_python(environment)

        requirement = f"agentlint-trace[dev,otel-demo,openai-agents] @ {wheel.as_uri()}"
        subprocess.run(
            [str(python), "-m", "pip", "install", "--upgrade", "pip", requirement],
            check=True,
        )
        if args.openai_agents_version:
            subprocess.run(
                [
                    str(python),
                    "-m",
                    "pip",
                    "install",
                    f"openai-agents=={args.openai_agents_version}",
                ],
                check=True,
            )

        workspace.mkdir()
        shutil.copytree(ROOT / "tests", workspace / "tests")
        shutil.copytree(ROOT / "examples", workspace / "examples")
        (workspace / "pytest.ini").write_text(
            """[pytest]
testpaths = tests
addopts = --strict-config --strict-markers
markers =
    live_openai: opt-in tests that may call an external API
    performance: lightweight performance smoke tests
""",
            encoding="utf-8",
        )

        subprocess.run([str(python), "-m", "pytest", "-q"], cwd=workspace, check=True)
        subprocess.run([str(python), str(ROOT / "scripts" / "release_smoke.py")], check=True)


if __name__ == "__main__":
    main()
