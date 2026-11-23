"""כלי עזר לפירוק שורת פקודה לחלקים (segments) מחוץ למרכאות."""
from __future__ import annotations

import os
import re


def split_segments(command: str, os_key: str) -> list[str]:
    """מפצל שורת פקודה לפי &&, ||, |, & (Windows) או ; (Linux) – רק מחוץ למרכאות."""
    quotes = {'"'} if os_key == "windows-cmd" else {'"', "'"}
    separators = ["&&", "||", "|", "&"] if os_key == "windows-cmd" else ["&&", "||", "|", ";"]
    segments, buf, quote, i = [], [], None, 0
    while i < len(command):
        ch = command[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in quotes:
            quote = ch
            buf.append(ch)
            i += 1
            continue
        matched = next((s for s in separators if command.startswith(s, i)), None)
        # "2>&1" / ">&" אינם מפרידים
        if matched == "&" and i > 0 and command[i - 1] in "<>":
            matched = None
        if matched:
            segments.append("".join(buf).strip())
            buf = []
            i += len(matched)
            continue
        buf.append(ch)
        i += 1
    segments.append("".join(buf).strip())
    return [s for s in segments if s]


def first_token(segment: str, os_key: str) -> str:
    """מחזיר את שם הפקודה בתחילת הקטע (ללא נתיב וללא .exe)."""
    seg = segment.strip().lstrip("(").strip()
    if os_key == "linux-bash":
        # דילוג על השמות משתני סביבה בתחילת השורה: FOO=bar cmd
        while re.match(r"^[A-Za-z_][A-Za-z0-9_]*=\S*\s+", seg):
            seg = re.sub(r"^[A-Za-z_][A-Za-z0-9_]*=\S*\s+", "", seg, count=1)
        if seg.startswith("sudo "):
            seg = seg[5:].lstrip()
    if seg.startswith('"'):
        tok = seg[1:].split('"', 1)[0]
    else:
        tok = seg.split()[0] if seg.split() else ""
    if os_key == "windows-cmd" and tok.startswith("@"):
        tok = tok[1:]
    tok = os.path.basename(tok.replace("\\", "/"))
    tok = tok.lower() if os_key == "windows-cmd" else tok
    if os_key == "windows-cmd" and tok.endswith(".exe"):
        tok = tok[:-4]
    return tok
