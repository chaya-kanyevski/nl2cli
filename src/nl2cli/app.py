"""ממשק Gradio: הוראה בשפה טבעית -> פקודת CLI."""
from __future__ import annotations

import gradio as gr

from . import config, prompts
from .agent import translate
from .sandbox import run_in_sandbox

RISK_BADGE = {
    "safe": "🟢 **בטוחה** – ניתן להריץ",
    "confirm": "🟡 **דורשת אישור** – יש לאשר לפני הרצה",
    "blocked": "🔴 **חסומה** – הפקודה לא תורץ",
}

EXAMPLES = [
    "מה כתובת ה-IP של המחשב שלי",
    "איזה תהליכים רצים כרגע במערכת",
    "לסדר את רשימת הקבצים לפי גודל מהגדול לקטן",
    "חפש את המילה error בקובץ app.log",
    "סגור את התוכנה notepad",
    "אני רוצה למחוק את כל הקבצים עם סיומת .tmp בתיקייה downloads",
]

CSS = """
#instruction textarea {direction: rtl; text-align: right;}
#command textarea {direction: ltr; text-align: left; font-family: monospace; font-size: 1.1em;}
"""


def on_translate(instruction: str, os_key: str, version: str):
    if not instruction or not instruction.strip():
        return "", "נא להזין הוראה.", "", None
    try:
        res = translate(instruction, os_key, version)
    except Exception as e:
        return "", f"❌ שגיאה: {e}", "", None

    lines = [RISK_BADGE[res.final_risk]]
    if res.command == config.UNSUPPORTED:
        lines = ["⚪ לא נמצאה פקודת טרמינל מתאימה להוראה (UNSUPPORTED)."]
    if res.risk_reasons:
        lines.append("סיבות (שכבת הבטיחות בקוד): " + "; ".join(res.risk_reasons))
    if res.model_reason:
        lines.append(f"הסבר המודל: {res.model_reason}")
    if res.syntax_ok is False:
        lines.append(f"⚠️ בדיקת תחביר: {res.syntax_note}")
    if not res.format_ok:
        lines.append(f"⚠️ הפלט חרג מהפורמט: {res.format_note}")
    lines.append(f"<sub>גרסת פרומפט: {res.version} · {res.latency_ms}ms</sub>")

    command = "" if res.final_risk == "blocked" else res.command
    state = {"command": command, "risk": res.final_risk, "os": os_key}
    return command, "\n\n".join(lines), res.raw, state


def on_sandbox(state: dict | None, confirmed: bool):
    if not state or not state.get("command") or state["command"] in (config.UNSUPPORTED,):
        return "אין פקודה להרצה."
    if state["os"] != "linux-bash":
        return "ה-sandbox מבוסס Linux – בחרי מערכת יעד linux-bash כדי לאמת בו פקודות."
    if state["risk"] == "blocked":
        return "🔴 פקודה חסומה – לא תורץ."
    if state["risk"] == "confirm" and not confirmed:
        return "🟡 הפקודה דורשת אישור – סמני את תיבת האישור ונסי שוב."
    res = run_in_sandbox(state["command"])
    if res.error:
        return f"❌ {res.error}"
    if res.timed_out:
        return "⏱️ הפקודה חרגה ממגבלת הזמן והקונטיינר נעצר."
    status = "✅ הפקודה רצה בהצלחה" if res.ok else f"❌ הפקודה החזירה קוד שגיאה {res.exit_code}"
    return f"{status}\n\n```\n{(res.stdout + res.stderr).strip() or '(אין פלט)'}\n```"


def build() -> gr.Blocks:
    versions = list(prompts.load_all())
    with gr.Blocks(title="NL → CLI", css=CSS) as demo:
        gr.Markdown("# 🗣️ → 💻 ממיר הוראות לפקודות טרמינל")
        with gr.Row():
            os_key = gr.Dropdown(list(config.TARGET_OSES), value=config.DEFAULT_OS,
                                 label="מערכת יעד")
            version = gr.Dropdown(versions, value=versions[-1], label="גרסת פרומפט")
        instruction = gr.Textbox(label="הוראה בשפה טבעית", lines=2, elem_id="instruction",
                                 placeholder="לדוגמה: מה כתובת ה-IP של המחשב שלי")
        btn = gr.Button("המר לפקודה", variant="primary")
        command = gr.Textbox(label="פקודת CLI", elem_id="command", interactive=False,
                             show_copy_button=True)
        info = gr.Markdown()
        with gr.Accordion("פלט גולמי של המודל", open=False):
            raw = gr.Textbox(lines=4, interactive=False, show_label=False)
        with gr.Accordion("🧪 אימות ב-Sandbox (בונוס – Docker)", open=False):
            confirmed = gr.Checkbox(label="אני מאשרת הרצה של פקודה הדורשת אישור")
            sb_btn = gr.Button("הרץ בסביבה מבודדת")
            sb_out = gr.Markdown()
        state = gr.State()

        gr.Examples(EXAMPLES, inputs=instruction)
        btn.click(on_translate, [instruction, os_key, version], [command, info, raw, state])
        instruction.submit(on_translate, [instruction, os_key, version], [command, info, raw, state])
        sb_btn.click(on_sandbox, [state, confirmed], sb_out)
    return demo


def main() -> None:
    build().launch()


if __name__ == "__main__":
    main()
