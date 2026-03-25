import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_run_sh_uses_default_port_and_forwards_extra_args(tmp_path: Path) -> None:
    result = _run_script(
        tmp_path=tmp_path,
        script_name="run.sh",
        shell_command=["bash"],
        args=["--debug"],
    )

    assert result.returncode == 0
    lines = result.stdout.strip().splitlines()
    assert lines[0] == str(ROOT)
    assert lines[1:] == [
        "run",
        "flask",
        "--app",
        "czech_vocab.web.app:create_app",
        "run",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--debug",
    ]


def test_run_sh_accepts_short_and_long_port_flags(tmp_path: Path) -> None:
    short_result = _run_script(
        tmp_path=tmp_path,
        script_name="run.sh",
        shell_command=["bash"],
        args=["-p", "5122"],
    )
    long_result = _run_script(
        tmp_path=tmp_path,
        script_name="run.sh",
        shell_command=["bash"],
        args=["--port", "6122", "--reload"],
    )

    assert short_result.returncode == 0
    assert "--port\n5122\n" in short_result.stdout
    assert long_result.returncode == 0
    assert "--port\n6122\n" in long_result.stdout
    assert long_result.stdout.endswith("--reload\n")


@pytest.mark.skipif(shutil.which("fish") is None, reason="fish is not installed")
def test_run_fish_accepts_port_flag_and_forwards_extra_args(tmp_path: Path) -> None:
    result = _run_script(
        tmp_path=tmp_path,
        script_name="run.fish",
        shell_command=["fish"],
        args=["--port", "7122", "--debug"],
    )

    assert result.returncode == 0
    lines = result.stdout.strip().splitlines()
    assert lines[0] == str(ROOT)
    assert lines[1:] == [
        "run",
        "flask",
        "--app",
        "czech_vocab.web.app:create_app",
        "run",
        "--host",
        "0.0.0.0",
        "--port",
        "7122",
        "--debug",
    ]


def _run_script(
    *,
    tmp_path: Path,
    script_name: str,
    shell_command: list[str],
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(exist_ok=True)
    capture_path = tmp_path / "captured.txt"
    _write_fake_uv(fake_bin / "uv", capture_path)
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["RUN_CAPTURE_PATH"] = str(capture_path)

    result = subprocess.run(
        [*shell_command, str(ROOT / script_name), *args],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if capture_path.exists():
        result.stdout = capture_path.read_text(encoding="utf-8")
    return result


def _write_fake_uv(path: Path, capture_path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'printf "%s\\n" "$PWD" > "$RUN_CAPTURE_PATH"',
                'for arg in "$@"; do',
                '  printf "%s\\n" "$arg" >> "$RUN_CAPTURE_PATH"',
                "done",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    capture_path.write_text("", encoding="utf-8")
