"""הגדרות מרכזיות של הפרויקט (נטענות מקובץ .env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

PROMPTS_DIR = ROOT / "prompts"
SCENARIOS_FILE = ROOT / "tests" / "scenarios.csv"
RESULTS_DIR = ROOT / "results"
SANDBOX_DIR = ROOT / "sandbox"

LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip() or None
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))

SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "nl2cli-sandbox").strip()

# מערכות היעד הנתמכות: מפתח -> תיאור שמוזרק לפרומפט
TARGET_OSES = {
    "windows-cmd": "Windows Command Prompt (cmd.exe)",
    "linux-bash": "Linux (bash shell)",
}
DEFAULT_OS = "windows-cmd"

# טוקנים מיוחדים שהמודל מחזיר כשאין פקודה להחזיר
UNSUPPORTED = "UNSUPPORTED"
BLOCKED = "BLOCKED"
