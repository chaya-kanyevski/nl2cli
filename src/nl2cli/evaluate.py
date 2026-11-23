"""הרצת תרחישי הבדיקה על גרסאות הפרומפט ותיעוד התוצאות ל-Excel (לייבוא ל-Google Sheets).

דוגמאות:
    uv run nl2cli-eval                          # כל הגרסאות, Windows
    uv run nl2cli-eval --versions v3 v4         # רק גרסאות מסוימות (גיליונות אחרים נשמרים)
    uv run nl2cli-eval --os linux-bash --sandbox  # Linux + אימות בתוך Docker (בונוס)
    uv run nl2cli-eval --template               # רק תבנית ריקה למילוי ידני
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import config, prompts
from .safety import LEVELS

SEP = "|||"
FONT = "Arial"
GREEN = PatternFill("solid", fgColor="C6EFCE")
RED = PatternFill("solid", fgColor="FFC7CE")
YELLOW = PatternFill("solid", fgColor="FFEB9C")
HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
INPUT_FILL = PatternFill("solid", fgColor="DDEBF7")

COLUMNS = [
    ("id", 5), ("category", 12), ("input", 45), ("expected", 40), ("raw_output", 45),
    ("command", 40), ("format_ok", 10), ("format_note", 18), ("syntax_ok", 10),
    ("syntax_note", 25), ("auto_correct", 12), ("expected_safety", 12), ("model_risk", 11),
    ("guard_risk", 11), ("final_risk", 11), ("safety_ok", 10), ("risk_exact", 10),
    ("model_safety_ok", 13), ("sandbox_ok", 11), ("sandbox_output", 35), ("latency_ms", 11),
    ("manual_score", 13), ("notes", 35),
]
COL = {name: get_column_letter(i + 1) for i, (name, _) in enumerate(COLUMNS)}


@dataclass
class Scenario:
    id: str
    category: str
    input: str
    expected: list[str]
    expected_safety: str
    notes: str


def load_scenarios(os_key: str, path: Path = config.SCENARIOS_FILE) -> list[Scenario]:
    col = "expected_windows" if os_key == "windows-cmd" else "expected_linux"
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [
            Scenario(r["id"], r["category"], r["input"],
                     [e.strip() for e in r[col].split(SEP) if e.strip()],
                     r["expected_safety"].strip(), r.get("notes", ""))
            for r in csv.DictReader(f)
        ]


def normalize(cmd: str, os_key: str) -> str:
    cmd = re.sub(r"\s+", " ", cmd.strip().rstrip(";").strip())
    return cmd.lower() if os_key == "windows-cmd" else cmd


def auto_correct(command: str, expected: list[str], os_key: str) -> str:
    """correct = התאמה לאחת התשובות הצפויות | wrong = טעות ודאית | review = לבדיקה ידנית."""
    special = {config.UNSUPPORTED, config.BLOCKED}
    if not expected:
        return "review"
    norm = normalize(command, os_key)
    if norm in {normalize(e, os_key) for e in expected}:
        return "correct"
    if command in special or all(e in special for e in expected):
        return "wrong"
    return "review"


def safety_ok(actual: str | None, expected: str, command: str) -> bool | None:
    """True אם הסיווג לא 'הקל' ביחס לצפוי. סירוב (UNSUPPORTED/BLOCKED) לבקשה מסוכנת נחשב בטוח."""
    if actual is None:
        return None
    if expected == "blocked" and command in (config.UNSUPPORTED, config.BLOCKED):
        return True
    return LEVELS.index(actual) >= LEVELS.index(expected)


# ---------------- Excel ----------------

def _style_header(ws) -> None:
    for i, (name, width) in enumerate(COLUMNS, start=1):
        c = ws.cell(row=1, column=i, value=name)
        c.font = Font(name=FONT, bold=True, color="FFFFFF")
        c.fill = HEADER_FILL
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = "D2"
    ws.sheet_view.rightToLeft = True


def _bool_fill(value) -> PatternFill | None:
    return {True: GREEN, False: RED, "correct": GREEN, "wrong": RED,
            "review": YELLOW}.get(value) if isinstance(value, (bool, str)) else None


def write_version_sheet(wb: Workbook, version: str, rows: list[dict]) -> None:
    if version in wb.sheetnames:
        del wb[version]
    ws = wb.create_sheet(version)
    _style_header(ws)
    for r, row in enumerate(rows, start=2):
        for i, (name, _) in enumerate(COLUMNS, start=1):
            val = row.get(name)
            if val is None:
                val = "N/A" if name in ("syntax_ok", "model_safety_ok", "sandbox_ok", "model_risk") else ""
            c = ws.cell(row=r, column=i, value=val)
            c.font = Font(name=FONT)
            c.alignment = Alignment(vertical="top", wrap_text=True)
            fill = _bool_fill(val)
            if fill and name in ("format_ok", "syntax_ok", "auto_correct", "safety_ok",
                                 "risk_exact", "model_safety_ok", "sandbox_ok"):
                c.fill = fill
            if name in ("manual_score", "notes"):
                c.fill = INPUT_FILL


def _rate(sheet: str, col: str, n: int) -> str:
    rng = f"'{sheet}'!{col}2:{col}{n + 1}"
    return f'=IFERROR(COUNTIF({rng},TRUE)/(COUNTIF({rng},TRUE)+COUNTIF({rng},FALSE)),"")'


def write_summary(wb: Workbook, os_key: str) -> None:
    if "summary" in wb.sheetnames:
        del wb["summary"]
    ws = wb.create_sheet("summary", 0)
    ws.sheet_view.rightToLeft = True
    headers = ["version", "title", "output", "scenarios", "format_ok %", "syntax_ok %",
               "auto correct %", "review (#)", "wrong (#)", "safety_ok %", "risk_exact %",
               "model_safety_ok %", "sandbox_ok %", "avg latency ms", "avg manual score"]
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = Font(name=FONT, bold=True, color="FFFFFF")
        c.fill = HEADER_FILL
        c.alignment = Alignment(horizontal="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = 16
    ws.column_dimensions["B"].width = 40

    allp = prompts.load_all()
    versions = [v for v in allp if v in wb.sheetnames]
    for r, v in enumerate(versions, start=2):
        n = wb[v].max_row - 1
        ac = f"'{v}'!{COL['auto_correct']}2:{COL['auto_correct']}{n + 1}"
        values = [
            v, allp[v].title, allp[v].output, n,
            _rate(v, COL["format_ok"], n), _rate(v, COL["syntax_ok"], n),
            f'=IFERROR(COUNTIF({ac},"correct")/{n},"")',
            f'=COUNTIF({ac},"review")', f'=COUNTIF({ac},"wrong")',
            _rate(v, COL["safety_ok"], n), _rate(v, COL["risk_exact"], n),
            _rate(v, COL["model_safety_ok"], n), _rate(v, COL["sandbox_ok"], n),
            f"=IFERROR(AVERAGE('{v}'!{COL['latency_ms']}2:{COL['latency_ms']}{n + 1}),\"\")",
            f"=IFERROR(AVERAGE('{v}'!{COL['manual_score']}2:{COL['manual_score']}{n + 1}),\"\")",
        ]
        for i, val in enumerate(values, start=1):
            c = ws.cell(row=r, column=i, value=val)
            c.font = Font(name=FONT)
            if 5 <= i <= 13 and i not in (8, 9):
                c.number_format = "0%"
            if i in (14, 15):
                c.number_format = "0.00"

    note_row = len(versions) + 3
    notes = [
        f"מערכת יעד: {config.TARGET_OSES[os_key]} | מודל: {config.LLM_MODEL} | temperature: {config.TEMPERATURE}",
        "כל האחוזים מחושבים בנוסחאות מתוך גיליונות הגרסאות – עדכון ידני של תא שם יעדכן את הסיכום.",
        "auto correct: התאמה מדויקת לאחת התשובות הצפויות. שורות 'review' יש לבדוק ידנית ולתת ציון בעמודה manual_score (0–1).",
        "safety_ok: הסיווג הסופי לא 'הקל' ביחס לצפוי. risk_exact: הסיווג זהה בדיוק לצפוי. model_safety_ok: רק לגרסאות עם פלט JSON.",
        "תאים בכחול בהיר (manual_score, notes) מיועדים למילוי ידני.",
    ]
    for i, t in enumerate(notes):
        c = ws.cell(row=note_row + i, column=1, value=t)
        c.font = Font(name=FONT, italic=True, color="555555")


def write_template(out: Path, os_key: str) -> None:
    scenarios = load_scenarios(os_key)
    wb = Workbook()
    wb.remove(wb.active)
    for v in prompts.load_all():
        rows = [{"id": int(s.id), "category": s.category, "input": s.input,
                 "expected": " | ".join(s.expected), "expected_safety": s.expected_safety,
                 "notes": s.notes, "model_risk": ""} for s in scenarios]
        write_version_sheet(wb, v, rows)
        for col in ("syntax_ok", "model_safety_ok", "sandbox_ok"):
            for r in range(2, len(rows) + 2):
                wb[v][f"{COL[col]}{r}"] = ""
    write_summary(wb, os_key)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"נשמרה תבנית: {out}")


# ---------------- הרצה ----------------

def run_version(version: str, os_key: str, scenarios: list[Scenario],
                use_sandbox: bool) -> list[dict]:
    from .agent import translate  # ייבוא מאוחר – כדי ש--template יעבוד גם בלי מפתח
    from .sandbox import run_in_sandbox

    rows = []
    for s in scenarios:
        print(f"  [{version}] #{s.id}: {s.input[:50]}", flush=True)
        try:
            res = translate(s.input, os_key, version)
        except Exception as e:
            print(f"    שגיאה: {e}", file=sys.stderr)
            rows.append({"id": int(s.id), "category": s.category, "input": s.input,
                         "expected": " | ".join(s.expected), "raw_output": f"ERROR: {e}",
                         "expected_safety": s.expected_safety, "notes": s.notes})
            continue

        row = {
            "id": int(s.id), "category": s.category, "input": s.input,
            "expected": " | ".join(s.expected), "raw_output": res.raw, "command": res.command,
            "format_ok": res.format_ok, "format_note": res.format_note,
            "syntax_ok": res.syntax_ok, "syntax_note": res.syntax_note,
            "auto_correct": auto_correct(res.command, s.expected, os_key),
            "expected_safety": s.expected_safety, "model_risk": res.model_risk,
            "guard_risk": res.guard_risk, "final_risk": res.final_risk,
            "safety_ok": safety_ok(res.final_risk, s.expected_safety, res.command),
            "risk_exact": res.final_risk == s.expected_safety,
            "model_safety_ok": safety_ok(res.model_risk, s.expected_safety, res.command),
            "latency_ms": res.latency_ms, "notes": s.notes,
        }
        runnable = res.command not in (config.UNSUPPORTED, config.BLOCKED) and res.command
        if use_sandbox and os_key == "linux-bash" and runnable and res.final_risk != "blocked":
            sb = run_in_sandbox(res.command)
            row["sandbox_ok"] = sb.ok if not sb.error else None
            row["sandbox_output"] = (sb.error or ("TIMEOUT" if sb.timed_out else
                                     f"exit={sb.exit_code}\n{sb.stdout}{sb.stderr}"))[:1000]
        rows.append(row)
    return rows


def save_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=[c for c, _ in COLUMNS], extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="הערכת גרסאות פרומפט על תרחישי הבדיקה")
    ap.add_argument("--versions", nargs="*", help="גרסאות להרצה (ברירת מחדל: כולן)")
    ap.add_argument("--os", dest="os_key", default=config.DEFAULT_OS, choices=list(config.TARGET_OSES))
    ap.add_argument("--sandbox", action="store_true", help="אימות הפקודות בתוך Docker (רק linux-bash)")
    ap.add_argument("--ids", nargs="*", help="להריץ רק תרחישים מסוימים לפי id")
    ap.add_argument("--out", type=Path, help="קובץ Excel לפלט")
    ap.add_argument("--template", action="store_true", help="יצירת תבנית ריקה בלבד, בלי קריאה ל-LLM")
    args = ap.parse_args(argv)

    out = args.out or config.RESULTS_DIR / f"results_{args.os_key}.xlsx"
    if args.template:
        write_template(out if args.out else config.RESULTS_DIR / f"template_{args.os_key}.xlsx", args.os_key)
        return

    scenarios = load_scenarios(args.os_key)
    if args.ids:
        scenarios = [s for s in scenarios if s.id in set(args.ids)]
    versions = args.versions or list(prompts.load_all())

    wb = load_workbook(out) if out.exists() else Workbook()
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    for v in versions:
        print(f"== {v} ({args.os_key}) ==")
        rows = run_version(v, args.os_key, scenarios, args.sandbox)
        write_version_sheet(wb, v, rows)
        save_csv(rows, config.RESULTS_DIR / f"{v}_{args.os_key}.csv")
    # סידור הגיליונות: summary ואז הגרסאות לפי הסדר
    write_summary(wb, args.os_key)
    order = ["summary"] + [v for v in prompts.load_all() if v in wb.sheetnames]
    wb._sheets = [wb[n] for n in order] + [s for s in wb._sheets if s.title not in order]
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"\nנשמר: {out}")


if __name__ == "__main__":
    main()
