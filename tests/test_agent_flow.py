"""בדיקת הזרימה המלאה של ה-agent עם LLM מדומה (ללא מפתח API)."""
from nl2cli import agent


def _fake(answer):
    return lambda system, user, **kw: answer


def test_guard_overrides_model(monkeypatch):
    # המודל טוען "safe" על פקודת מחיקה – שכבת הקוד מחמירה ל-blocked
    monkeypatch.setattr(agent.llm, "complete", _fake(
        '{"status":"ok","command":"del *.tmp","risk":"safe","reason":"x"}'))
    res = agent.translate("מחק קבצים", "windows-cmd", "v4")
    assert res.model_risk == "safe" and res.guard_risk == "blocked"
    assert res.final_risk == "blocked"


def test_text_version_flow(monkeypatch):
    monkeypatch.setattr(agent.llm, "complete", _fake("tasklist"))
    res = agent.translate("איזה תהליכים רצים", "windows-cmd", "v2")
    assert res.command == "tasklist" and res.final_risk == "safe" and res.syntax_ok


def test_prompt_renders_os():
    from nl2cli import prompts
    for p in prompts.load_all().values():
        text = p.render("linux-bash")
        assert "{{OS}}" not in text and "Linux" in text
