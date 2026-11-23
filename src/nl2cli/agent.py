"""ה-Agent עצמו: פרומפט -> LLM -> פענוח פלט -> בדיקות בטיחות ותחביר."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

from . import config, llm, prompts
from .safety import assess, max_level
from .validator import check_syntax

SPECIAL = {config.UNSUPPORTED, config.BLOCKED}
_PREFIX_RE = re.compile(r"^(command|פקודה|cmd)\s*:\s*|^(\$|>|C:\\[^>]*>)\s*", re.IGNORECASE)
_PROSE_RE = re.compile(r"^(here|sure|this|the|to |you |הנה|כדי|ניתן|אפשר|זו|זוהי)", re.IGNORECASE)


@dataclass
class ParsedOutput:
    command: str
    status: str = "ok"            # ok / unsupported / blocked
    model_risk: str | None = None  # רק בפלט JSON
    reason: str = ""
    format_ok: bool = True
    format_note: str = ""


@dataclass
class AgentResult:
    instruction: str
    os_key: str
    version: str
    raw: str
    command: str
    status: str
    model_risk: str | None
    guard_risk: str
    final_risk: str
    risk_reasons: list[str] = field(default_factory=list)
    model_reason: str = ""
    format_ok: bool = True
    format_note: str = ""
    syntax_ok: bool | None = None
    syntax_note: str = ""
    latency_ms: int = 0


def _strip_fences(text: str) -> str:
    m = re.search(r"```[a-zA-Z]*\n?(.*?)```", text, flags=re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def _clean_line(line: str) -> str:
    line = line.strip().strip("`").strip()
    line = _PREFIX_RE.sub("", line).strip()
    return line


def parse_text_output(raw: str) -> ParsedOutput:
    """פענוח פלט טקסט חופשי (גרסאות v1–v3). מחלץ פקודה גם מפלט 'מלוכלך'
    ומסמן format_ok=False כשהפלט חרג מהפורמט הנדרש."""
    stripped = raw.strip()
    notes = []
    if "```" in stripped:
        notes.append("code fence")
    if "`" in stripped.replace("```", ""):
        notes.append("backticks")
    lines = [ln for ln in stripped.splitlines() if ln.strip()]
    if len(lines) > 1:
        notes.append(f"{len(lines)} שורות")
    if lines and _PREFIX_RE.match(lines[0].strip()):
        notes.append("קידומת")

    body = _strip_fences(stripped)
    candidates = [_clean_line(ln) for ln in body.splitlines() if ln.strip()]
    candidates = [c for c in candidates if not _PROSE_RE.match(c)] or candidates
    command = candidates[0] if candidates else ""

    status = "ok"
    if command.upper() in SPECIAL:
        command = command.upper()
        status = "unsupported" if command == config.UNSUPPORTED else "blocked"
    return ParsedOutput(command=command, status=status,
                        format_ok=not notes, format_note=", ".join(notes))


def parse_json_output(raw: str) -> ParsedOutput:
    """פענוח פלט JSON (גרסה v4) + ולידציה של המבנה והערכים."""
    stripped = raw.strip()
    notes = []
    if not stripped.startswith("{"):
        notes.append("טקסט מחוץ ל-JSON")
    m = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    try:
        data = json.loads(m.group(0) if m else stripped)
    except (json.JSONDecodeError, AttributeError):
        # נפילה לאחור: ננסה לפרש כטקסט
        parsed = parse_text_output(raw)
        parsed.format_ok = False
        parsed.format_note = "JSON לא תקין"
        return parsed

    status = str(data.get("status", "")).lower()
    risk = str(data.get("risk", "")).lower()
    command = str(data.get("command", "") or "").strip()
    if status not in {"ok", "unsupported", "blocked"}:
        notes.append(f"status לא חוקי: {status!r}")
        status = "ok" if command else "unsupported"
    if risk not in {"safe", "confirm", "blocked"}:
        notes.append(f"risk לא חוקי: {risk!r}")
        risk = None
    missing = {"status", "command", "risk", "reason"} - set(data)
    if missing:
        notes.append(f"חסרים שדות: {', '.join(sorted(missing))}")
    if status == "ok" and not command:
        notes.append("status=ok בלי פקודה")
    if status == "ok" and "\n" in command:
        notes.append("פקודה מרובת שורות")

    if status == "unsupported":
        command = config.UNSUPPORTED
    elif status == "blocked":
        command = config.BLOCKED
        risk = "blocked"
    return ParsedOutput(command=command, status=status, model_risk=risk,
                        reason=str(data.get("reason", "")),
                        format_ok=not notes, format_note=", ".join(notes))


def translate(instruction: str, os_key: str = config.DEFAULT_OS,
              version: str | None = None) -> AgentResult:
    prompt = prompts.load(version or prompts.latest_version())
    system = prompt.render(os_key)

    t0 = time.perf_counter()
    raw = llm.complete(system, instruction.strip())
    latency = int((time.perf_counter() - t0) * 1000)

    parsed = parse_json_output(raw) if prompt.output == "json" else parse_text_output(raw)

    guard = assess(parsed.command, os_key)
    final = max_level(parsed.model_risk, guard.level)
    if parsed.status == "blocked":
        final = "blocked"

    result = AgentResult(
        instruction=instruction, os_key=os_key, version=prompt.version, raw=raw,
        command=parsed.command, status=parsed.status, model_risk=parsed.model_risk,
        guard_risk=guard.level, final_risk=final, risk_reasons=guard.reasons,
        model_reason=parsed.reason, format_ok=parsed.format_ok,
        format_note=parsed.format_note, latency_ms=latency,
    )
    if parsed.command and parsed.command not in SPECIAL:
        syn = check_syntax(parsed.command, os_key)
        result.syntax_ok, result.syntax_note = syn.ok, syn.note
    return result
