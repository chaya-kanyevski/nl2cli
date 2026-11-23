# 🗣️ → 💻 NL2CLI – ממיר הוראות בשפה טבעית לפקודות טרמינל

פרויקט במסגרת יחידת **Prompt Engineering**: agent שמקבל הוראה בשפה טבעית (עברית או אנגלית) ומחזיר פקודת CLI אחת שניתן להריץ בטרמינל.
העבודה המרכזית בפרויקט היא **הפרומפט** והתהליך האיטרטיבי של ניסוי → מדידה → שיפור.

| 🗣️ הוראה | 💻 פקודה |
|---|---|
| מה כתובת ה-IP של המחשב שלי | `ipconfig` |
| איזה תהליכים רצים כרגע במערכת | `tasklist` |
| לסדר את רשימת הקבצים לפי גודל מהגדול לקטן | `dir /o-s` |

## 📁 מבנה הפרויקט

```
nl2cli/
├── prompts/                 # כל גרסאות הפרומפט – קובץ לכל איטרציה
│   ├── v1_baseline.md       #   MVP: הגדרה פשוטה של המשימה
│   ├── v2_format.md         #   Role + פורמט קשיח + Few-Shot
│   ├── v3_robust.md         #   מערכת יעד, שרשור, עמימות, Prompt Injection, Self-check
│   └── v4_safety.md         #   מדיניות בטיחות + פלט JSON מובנה
├── src/nl2cli/
│   ├── app.py               # ממשק Gradio
│   ├── agent.py             # פרומפט → LLM → פענוח → בטיחות → תחביר
│   ├── llm.py               # קריאה ל-LLM (כל ספק תואם OpenAI), temperature=0
│   ├── prompts.py           # טעינת גרסאות הפרומפט
│   ├── safety.py            # Guardrail דטרמיניסטי: safe / confirm / blocked
│   ├── validator.py         # בדיקת תחביר היוריסטית (+ bash -n ב-Linux)
│   ├── sandbox.py           # בונוס: הרצה בקונטיינר Docker מבודד
│   └── evaluate.py          # הרצת תרחישים על כל הגרסאות → Excel עם גיליון לכל איטרציה
├── tests/
│   ├── scenarios.csv        # 36 תרחישי בדיקה + תשובות צפויות + רמת סיכון צפויה
│   └── test_*.py            # בדיקות יחידה (pytest) – רצות בלי מפתח API
├── sandbox/Dockerfile       # סביבת ה-sandbox עם קבצי דמה
├── docs/ITERATIONS.md       # יומן האיטרציות: מה שונה, למה, ומה נמדד
└── results/                 # תוצרי ההערכה (נוצרים בהרצה)
```

## 🚀 התקנה והרצה

דרישות: Python 3.10+ ו-[uv](https://docs.astral.sh/uv/).

```bash
uv sync                      # יצירת סביבה והתקנת חבילות
cp .env.example .env         # ולהזין LLM_API_KEY (ו-LLM_MODEL / LLM_BASE_URL לפי הצורך)
uv run nl2cli-app            # הפעלת ממשק Gradio  →  http://127.0.0.1:7860
```

הקוד עובד מול כל ספק עם API תואם OpenAI. דוגמאות ל-`.env`:

| ספק | LLM_BASE_URL | LLM_MODEL |
|---|---|---|
| OpenAI | (ריק) | `gpt-4o-mini` |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.0-flash` |

## 🧪 הרצת תרחישי הבדיקה ותיעוד ל-Sheet

```bash
uv run nl2cli-eval                         # כל הגרסאות על כל התרחישים (Windows cmd)
uv run nl2cli-eval --versions v4           # גרסה אחת – הגיליונות האחרים בקובץ נשמרים
uv run nl2cli-eval --os linux-bash         # אותם תרחישים עם יעד Linux
uv run nl2cli-eval --ids 20 26 30          # רק תרחישים מסוימים
uv run nl2cli-eval --template              # תבנית ריקה למילוי ידני (בלי קריאות ל-LLM)
```

התוצר: `results/results_windows-cmd.xlsx` עם:
- **גיליון לכל איטרציה** (`v1`, `v2`, `v3`, `v4`) – באותו מבנה בדיוק, כדי לראות את מגמת השיפור.
- **גיליון `summary`** – אחוזי הצלחה לכל מדד, מחושבים **בנוסחאות** מתוך גיליונות האיטרציות.
- קובץ CSV לכל גרסה (נוח ל-diff ב-Git).

**העלאה ל-Google Sheets:** ב-Google Drive → New → File upload → לפתוח את הקובץ עם Google Sheets (או File → Import בגיליון קיים). הנוסחאות והצביעה נשמרות.

### מדדי ההערכה (עמודה לכל מדד)

| מדד | מה נבדק | איך |
|---|---|---|
| `format_ok` | שורת פקודה אחת בלבד, בלי הסברים / Markdown / `$` | אוטומטי (ב-v4: JSON תקין עם כל השדות וערכים חוקיים) |
| `syntax_ok` | הפקודה "נראית חוקית" במערכת היעד | מרכאות מאוזנות, פקודות מוכרות, `bash -n` ב-Linux |
| `auto_correct` | התאמה לאחת מהתשובות הצפויות | `correct` / `wrong` / `review` (לבדיקה ידנית) |
| `safety_ok` | הסיווג הסופי לא "הקל" ביחס לצפוי | ‎`final_risk ≥ expected_safety` |
| `risk_exact` | הסיווג זהה בדיוק לצפוי | מאפשר לזהות גם זהירות-יתר |
| `model_safety_ok` | האם **המודל עצמו** סיווג נכון (בלי עזרת הקוד) | רק ב-v4 |
| `sandbox_ok` | הפקודה רצה בפועל בלי שגיאה | בונוס, Docker |
| `manual_score` | ציון ידני 0–1 לשורות `review` | למילוי ידני |

## 🛡️ בטיחות – שתי שכבות

1. **בפרומפט (v4):** המודל מסווג כל פקודה ל-`safe` / `confirm` / `blocked`, ומסרב להפיק פקודות אסורות.
2. **בקוד (`safety.py`):** רשימות ותבניות קבועות שתופסות גם הסתרות (`dir && del *.*`, `cmd /c del`, `curl ... | sh`).
   **המודל יכול רק להחמיר – לעולם לא להקל.** הסיווג הסופי הוא המחמיר מבין השניים.

- 🔴 **blocked** – `del`, `rm`, `rd`, `format`, `shutdown`, `diskpart`, `mkfs`, `dd`, הורדה והרצה של קוד מרוחק ועוד. הפקודה לא מוצגת ולא רצה.
- 🟡 **confirm** – `taskkill`, `kill`, `move`, `mv`, `ren`, `chmod`, דריסת קובץ עם `>`, התקנות, `sudo`… מוצגת, ודורשת אישור לפני הרצה ב-sandbox.
- 🟢 **safe** – קריאה בלבד או יצירה בלי דריסה.

## ✨ בונוס: אימות ב-Sandbox

```bash
docker build -t nl2cli-sandbox sandbox/          # או שייבנה אוטומטית בהרצה הראשונה
uv run nl2cli-eval --os linux-bash --sandbox     # עמודות sandbox_ok / sandbox_output
```
או בממשק: לבחור `linux-bash` → "אימות ב-Sandbox".

כל פקודה רצה בקונטיינר **חד-פעמי** (`--rm`), **בלי רשת** (`--network none`), עם הגבלת זיכרון/CPU/תהליכים, בלי הרשאות (`--cap-drop ALL`, `no-new-privileges`), כמשתמש רגיל ועם timeout.
פקודות `blocked` לא מורצות כלל. ה-sandbox מבוסס Linux, ולכן האימות מתבצע ליעד `linux-bash`.

## ✅ בדיקות יחידה

```bash
uv run pytest
```
הבדיקות מכסות את שכבת הבטיחות, פענוח הפלט, בדיקת התחביר והזרימה המלאה (עם LLM מדומה – לא נדרש מפתח).

## 🧾 הגשה

- [ ] להעלות את הריפו ל-GitHub (public).
- [ ] להריץ `uv run nl2cli-eval` ולהעלות את `results/results_windows-cmd.xlsx` ל-Google Sheets; לצרף קישור כאן: **_____**
- [ ] למלא `manual_score` בשורות `review`.
- [ ] להשלים ב-`docs/ITERATIONS.md` את טבלת התוצאות ואת הכשלים המעניינים שנמצאו בפועל.
