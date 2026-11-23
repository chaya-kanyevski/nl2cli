"""שכבת בטיחות דטרמיניסטית (Guardrail בקוד).

עיקרון: המודל יכול להחמיר את רמת הסיכון, אך הקוד לעולם לא מאפשר לו להקל.
רמות: safe < confirm < blocked
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .shell_utils import first_token, split_segments

LEVELS = ["safe", "confirm", "blocked"]


def max_level(*levels: str | None) -> str:
    valid = [lv for lv in levels if lv in LEVELS]
    return max(valid, key=LEVELS.index) if valid else "safe"


# --- פקודות לפי שם (טוקן ראשון) ---
BLOCKED_CMDS = {
    "windows-cmd": {"del", "erase", "rd", "rmdir", "format", "shutdown", "diskpart",
                    "bcdedit", "cipher", "vssadmin", "logoff"},
    "linux-bash": {"rm", "rmdir", "shred", "mkfs", "dd", "shutdown", "reboot",
                   "poweroff", "halt", "init", "wipefs", "fdisk", "parted"},
}
CONFIRM_CMDS = {
    "windows-cmd": {"taskkill", "move", "ren", "rename", "attrib", "icacls", "takeown",
                    "setx", "netsh", "sc", "net", "reg", "schtasks", "winget", "choco",
                    "robocopy", "xcopy", "runas", "route", "mklink"},
    "linux-bash": {"kill", "pkill", "killall", "mv", "chmod", "chown", "chgrp", "sudo",
                   "apt", "apt-get", "yum", "dnf", "snap", "systemctl", "service",
                   "crontab", "iptables", "ufw", "useradd", "userdel", "passwd",
                   "mount", "umount", "ln", "truncate", "tee"},
}

# --- תבניות על כל השורה (תופסות גם הסתרות) ---
# (regex, סיבה, מערכת: None = כולן)
BLOCKED_PATTERNS = [
    (r"\bremove-item\b|\bclear-content\b", "מחיקת קבצים (PowerShell)", None),
    (r"\brm\s+-", "מחיקת קבצים", None),
    (r"\b(cmd|powershell|pwsh)\b.*\b(del|erase|rd|rmdir|format)\b", "מחיקה/פרמוט עקיפים", "windows-cmd"),
    (r"\b(bash|sh)\s+-c\b.*\b(rm|mkfs|dd)\b", "מחיקה עקיפה", "linux-bash"),
    (r"\bformat(-volume)?\s+[a-z]:", "פרמוט כונן", None),
    (r"\b(stop|restart)-computer\b", "כיבוי/הפעלה מחדש", None),
    (r"\bfind\b.*\s-delete\b", "מחיקה דרך find", None),
    (r"\breg\s+delete\b", "מחיקת ערכי Registry", None),
    (r"\bwmic\b.*\b(delete|call\s+terminate)\b", "פעולה הרסנית דרך wmic", "windows-cmd"),
    (r"\b(curl|wget|iwr|invoke-webrequest)\b.*\|\s*(sudo\s+)?(ba|z)?sh\b", "הורדה והרצה של קוד מרוחק", None),
    (r"\b(curl|wget)\b.*&&\s*(ba|z)?sh\b", "הורדה והרצה של קוד מרוחק", None),
    (r"\b(iex|invoke-expression)\b", "הרצת קוד דינמי (PowerShell)", None),
    (r":\(\)\s*\{.*\};\s*:", "Fork bomb", None),
    (r">\s*/dev/(sd|nvme|hd)", "כתיבה ישירה לדיסק", None),
    (r"\bchmod\s+(-R\s+)?[0-7]*777\s+/(\s|$)", "שינוי הרשאות לשורש המערכת", None),
    (r"\bgit\s+clean\s+-[a-z]*f", "מחיקת קבצים לא במעקב", None),
]
CONFIRM_PATTERNS = [
    (r"(?<![>&0-9])>(?!>)\s*(?!nul\b|/dev/null)\S", "דריסת קובץ באמצעות >", None),
    (r"\bcopy\b.*\s/y\b|\bcp\b.*\s-f\b", "העתקה עם דריסה", None),
    (r"\bsed\b.*\s-i", "עריכת קובץ במקום (sed -i)", "linux-bash"),
    (r"\bgit\s+(push\s+.*--force|reset\s+--hard)", "פעולת git הרסנית", None),
    (r"\b(pip|npm)\s+(install|uninstall)\b", "התקנה/הסרה של חבילות", None),
    (r"\b(stop-process|stop-service|set-[a-z]+|move-item|rename-item|new-itemproperty)\b", "פעולת שינוי (PowerShell)", None),
    (r"\b(xargs|-exec)\b", "הרצה עקיפה של פקודות", None),
]


@dataclass
class SafetyResult:
    level: str = "safe"
    reasons: list[str] = field(default_factory=list)


def assess(command: str, os_key: str) -> SafetyResult:
    """מסווג פקודה לרמת סיכון על בסיס כללים קבועים."""
    res = SafetyResult()
    if not command or command in ("UNSUPPORTED", "BLOCKED"):
        return res
    text = command if os_key == "linux-bash" else command.lower()

    for seg in split_segments(command, os_key):
        tok = first_token(seg, os_key)
        if tok in BLOCKED_CMDS[os_key]:
            res.level = max_level(res.level, "blocked")
            res.reasons.append(f"פקודה אסורה: {tok}")
        elif tok in CONFIRM_CMDS[os_key]:
            res.level = max_level(res.level, "confirm")
            res.reasons.append(f"פקודה הדורשת אישור: {tok}")
        if os_key == "linux-bash" and seg.strip().startswith("sudo "):
            res.level = max_level(res.level, "confirm")
            res.reasons.append("הרצה עם sudo")

    for pattern, reason, scope in BLOCKED_PATTERNS:
        if scope in (None, os_key) and re.search(pattern, text, flags=re.IGNORECASE):
            res.level = "blocked"
            res.reasons.append(reason)
    for pattern, reason, scope in CONFIRM_PATTERNS:
        if scope in (None, os_key) and re.search(pattern, text, flags=re.IGNORECASE):
            res.level = max_level(res.level, "confirm")
            res.reasons.append(reason)

    res.reasons = list(dict.fromkeys(res.reasons))  # הסרת כפילויות
    return res
