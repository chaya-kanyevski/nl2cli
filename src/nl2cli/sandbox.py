"""בונוס: הרצת פקודה בתוך קונטיינר Docker מבודד וחד-פעמי.

שכבות ההגנה:
- --rm                     : הקונטיינר נמחק מיד בסיום
- --network none           : אין גישה לרשת
- --memory / --cpus / --pids-limit : הגבלת משאבים (גם מול fork bomb)
- --cap-drop ALL + no-new-privileges : ללא הרשאות מערכת
- --user sandbox            : משתמש רגיל, לא root
- timeout                   : הקונטיינר נהרג אם הפקודה נתקעת
הסביבה היא Linux, ולכן האימות רלוונטי לפקודות linux-bash.
"""
from __future__ import annotations

import shutil
import subprocess
import uuid
from dataclasses import dataclass

from . import config


@dataclass
class SandboxResult:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.error


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True,
                              timeout=10).returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def ensure_image() -> None:
    """בונה את האימג' אם הוא עדיין לא קיים."""
    exists = subprocess.run(["docker", "image", "inspect", config.SANDBOX_IMAGE],
                            capture_output=True).returncode == 0
    if not exists:
        subprocess.run(["docker", "build", "-t", config.SANDBOX_IMAGE,
                        str(config.SANDBOX_DIR)], check=True)


def run_in_sandbox(command: str, timeout: int = 15) -> SandboxResult:
    if not docker_available():
        return SandboxResult(None, "", "", error="Docker לא זמין / לא רץ")
    try:
        ensure_image()
    except subprocess.CalledProcessError as e:
        return SandboxResult(None, "", "", error=f"בניית האימג' נכשלה: {e}")

    name = f"nl2cli-{uuid.uuid4().hex[:10]}"
    docker_cmd = [
        "docker", "run", "--rm", "--name", name,
        "--network", "none",
        "--memory", "256m", "--cpus", "0.5", "--pids-limit", "64",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--user", "sandbox", "--workdir", "/home/sandbox",
        config.SANDBOX_IMAGE, "bash", "-c", command,
    ]
    try:
        proc = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=timeout)
        return SandboxResult(proc.returncode, proc.stdout[-4000:], proc.stderr[-2000:])
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True)
        return SandboxResult(None, "", "", timed_out=True)
