"""טעינת גרסאות הפרומפט מתיקיית prompts/.

כל קובץ פרומפט מתחיל ב-front matter:
---
version: v1
output: text | json
title: ...
---
ובגוף מופיע {{OS}} שמוחלף במערכת היעד.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import config


@dataclass
class Prompt:
    version: str
    output: str  # "text" או "json"
    title: str
    body: str
    path: Path

    def render(self, os_key: str) -> str:
        return self.body.replace("{{OS}}", config.TARGET_OSES[os_key])


def _parse(path: Path) -> Prompt:
    text = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = text
    if text.startswith("---"):
        _, header, body = text.split("---", 2)
        for line in header.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
    return Prompt(
        version=meta.get("version", path.stem),
        output=meta.get("output", "text"),
        title=meta.get("title", path.stem),
        body=body.strip(),
        path=path,
    )


def load_all() -> dict[str, Prompt]:
    prompts = [_parse(p) for p in sorted(config.PROMPTS_DIR.glob("v*.md"))]
    return {p.version: p for p in prompts}


def load(version: str) -> Prompt:
    allp = load_all()
    if version not in allp:
        raise KeyError(f"גרסת פרומפט לא קיימת: {version}. קיימות: {list(allp)}")
    return allp[version]


def latest_version() -> str:
    return list(load_all())[-1]
