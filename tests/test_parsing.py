from nl2cli.agent import parse_json_output, parse_text_output
from nl2cli.validator import check_syntax


def test_clean_text():
    p = parse_text_output("ipconfig")
    assert p.command == "ipconfig" and p.format_ok


def test_fenced_text_is_extracted_but_flagged():
    p = parse_text_output("Here is the command:\n```cmd\ndir /o-s\n```\nThis sorts files.")
    assert p.command == "dir /o-s"
    assert not p.format_ok


def test_prompt_symbol_removed():
    p = parse_text_output("$ ls -la")
    assert p.command == "ls -la" and not p.format_ok


def test_unsupported_token():
    p = parse_text_output("unsupported")
    assert p.command == "UNSUPPORTED" and p.status == "unsupported"


def test_json_ok():
    p = parse_json_output('{"status":"ok","command":"whoami","risk":"safe","reason":"x"}')
    assert p.command == "whoami" and p.model_risk == "safe" and p.format_ok


def test_json_blocked():
    p = parse_json_output('{"status":"blocked","command":"","risk":"blocked","reason":"x"}')
    assert p.command == "BLOCKED" and p.model_risk == "blocked"


def test_json_in_fence_flagged():
    p = parse_json_output('```json\n{"status":"ok","command":"dir","risk":"safe","reason":"x"}\n```')
    assert p.command == "dir" and not p.format_ok


def test_json_invalid_values_flagged():
    p = parse_json_output('{"status":"ok","command":"dir","risk":"low"}')
    assert not p.format_ok and p.model_risk is None


def test_broken_json_falls_back():
    p = parse_json_output("dir /s")
    assert p.command == "dir /s" and not p.format_ok


def test_syntax_windows():
    assert check_syntax("dir /o-s", "windows-cmd").ok
    assert not check_syntax("ls -la", "windows-cmd").ok          # פקודת Linux ב-Windows
    assert not check_syntax('findstr "error app.log', "windows-cmd").ok


def test_syntax_linux():
    assert check_syntax("ps aux | head -n 5", "linux-bash").ok
    assert not check_syntax("ipconfig", "linux-bash").ok
    assert not check_syntax("if then fi (", "linux-bash").ok
