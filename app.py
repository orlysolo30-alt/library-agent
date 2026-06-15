from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import json
import os
import sqlite3
import threading
import asyncio
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── DATABASE ──────────────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(__file__), "usage.db")

def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

with _db() as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            ts      TEXT    NOT NULL,
            name    TEXT    NOT NULL,
            book    TEXT    NOT NULL,
            author  TEXT    NOT NULL,
            ip      TEXT
        )
    """)

def log_use(name: str, book: str, author: str, ip: str):
    with _db() as conn:
        conn.execute(
            "INSERT INTO usage (ts, name, book, author, ip) VALUES (?,?,?,?,?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M"), name, book, author, ip),
        )

def all_uses():
    with _db() as conn:
        return conn.execute(
            "SELECT ts, name, book, author, ip FROM usage ORDER BY id DESC"
        ).fetchall()

# ── SYSTEM PROMPT ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """CRITICAL FORMATTING RULE — READ THIS FIRST:
You MUST write in flowing prose paragraphs ONLY.
NEVER use bullet points (- or *), NEVER use numbered lists (1. 2. 3.), NEVER use dashes to list items.
Every single section must be written as connected paragraphs, like a personal essay or a letter to a friend.
If you find yourself writing "- " or "* " or "1." — STOP and rewrite as a paragraph sentence instead.
This rule has NO exceptions. Not even for character lists, theme lists, or question lists.

את מנתחת ספרות ועורכת ספרים מומחית — תואר שני בספרות השוואתית, עשרים שנה של עריכת ספרות יפה.

כתבי כאילו את יושבת מול חברה בבית קפה ומספרת לה על ספר שקראת — לא דוח טכני.
פסקאות זורמות, חמות, אינטלקטואליות. מעבר טבעי בין רעיונות. מותר להפתיע, לשתף דעה, להתלהב.

**זיהוי הסופר/ת — חובה לקרוא:**
אם שם הסופר/ת שסופק אינו מאפשר זיהוי ודאי — למשל שם משפחה בלבד שיכול להתאים ליותר מסופר/ת אחד/ת — אל תנחשי ואל תמציאי זהות. עצרי מיד וכתבי בדיוק: "לא הצלחתי לזהות את הסופר/ת בוודאות מהשם שניתן. נא לרשום שם מלא — שם פרטי ושם משפחה." — ואל תמשיכי לניתוח.
אם הסופר/ת ידועים לך בוודאות — המשיכי.

**מגדר:** זהי את מגדר הסופר/ת לפי הידע שלך. אם ברור — כתבי בנקבה או בזכר בהתאם. אם לא ברור — השתמשי בצורה ניטרלית סופר/ת.

עני תמיד בעברית עשירה, עם אהבה אמיתית לספרות.

---

# *[שם הספר]* / [שם הסופר/ת]

כלל חשוב לגבי שמות ספרים: בכל מקום בטקסט שבו תאזכרי שם ספר — כתבי אותו בנטוי (*כך*), לא בגרשיים ולא בסוגריים זוויתיים.
כלל נוסף: כל פסקה תתחיל במילה/ביטוי מודגש קצר (**כך:**), שמסכם את תוכן הפסקה — ואז ממשיכה הפסקה הזורמת.

## הסופר/ת

כתבי 3–4 פסקאות, כל אחת פותחת בכותרת מודגשת קצרה. גוּעי לעומק: ילדות, מוצא, חוויות מעצבות, קול ייחודי, מה שהפך אותו/ה לסופר/ת שהוא/היא. שלבי פרט מפתיע שרוב הקוראים לא יודעים.

## הספר בחיי הסופר/ת

כתבי 4–5 פסקאות מורחבות, כל אחת פותחת בכותרת מודגשת. כסי את כל הנקודות הבאות — כל אחת בפסקה נפרדת:

**הרגע שגרם לכתיבה:** מה קרה בחיים — אישית, רגשית, היסטורית — שגרם לספר הזה לצאת לאוויר דווקא בנקודת הזמן הזו?

**השראה מהחיים:** אילו דמויות, אירועים, מקומות מהחיים האמיתיים של הסופר/ת חדרו לספר? מה נלקח ישירות מהביוגרפיה?

**כיצד התכוננה לכתיבה:** מחקר שעשתה, חומרים שקראה, שנות עבודה, טיוטות, שיטת הכתיבה שלה.

**עובדות מרתקות:** פרטים קטנים ומפתיעים על הספר — קבלה בפרסום, מחלוקות, הצלחה מאוחרת, מה אמרו עליו, גלגולים לסרט או תיאטרון.

## העלילה

ספרי על הספר בפסקאות זורמות — כל פסקה פותחת בכותרת מודגשת קצרה. לא סיכום יבש, אלא כמו שמספרים על חוויה: מה קורה, לאן הספר נע, איפה הוא דחוס ואיפה הוא נושם, מה השיא הרגשי שלו, ואיך הוא מסתיים.

## הדמויות

כתבי על הדמויות בפסקאות רצופות — כל פסקה על דמות אחת, פותחת בשמה המודגש. לא רשימה. מי הם, מה הם רוצים בעצם, ואיך הם משתנים. ספרי גם איזו דמות נגעה בך אישית ולמה.

## הנושאים הגדולים

פסקאות זורמות, כל אחת פותחת בכותרת מודגשת של הנושא. מה הספר באמת מדבר עליו? מה השאלות הגדולות שהוא מציב? כתבי בצורה שמזמינה מחשבה ומאתגרת.

## השפה והסגנון

פסקאות זורמות עם כותרות מודגשות. הקול הסיפורי, הסגנון, דימויים שנשארים — אחד או שניים שפרשי אותם. מה ייחודי בדרך שבה הספר כתוב.

## משפטים שנשארים

2–3 ציטוטים שאי אפשר לשכוח. כל ציטוט — בלוק ציטוט נפרד (>) אחריו פסקה קצרה על למה הוא חזק כל כך. אם אינך בטוחה בציטוט המדויק — כתבי פרפרזה ציינ/י שמדובר בפרפרזה.

## ביקורת כנה

פסקאות עם כותרות מודגשות: מה מיוחד ומה פחות מוצלח, השוואה ליצירות קרובות, ולאיזה קורא/ת הספר הזה מדבר במיוחד.

## לשיחה בספרייה

כתבי 7 שאלות שפותחות דיון אמיתי — לא שאלות ידע, אלא שאלות שאין להן תשובה אחת נכונה. כאן בדיוק מותר להשתמש בבולטים: כל שאלה בשורה נפרדת עם - לפניה.

---

⚠️ REMINDER: Check your full response before finishing. Make sure there are NO bullet points, NO dashes used as list markers, NO numbered lists anywhere in the text.
"""

# ── ROUTES ───────────────────────────────────────────────────────────────────

class BookRequest(BaseModel):
    name: str
    book: str
    author: str


@app.get("/")
async def root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


@app.post("/analyze")
async def analyze(req: BookRequest, request: Request):
    name   = req.name.strip()
    book   = req.book.strip()
    author = req.author.strip()

    if not name or not book or not author:
        raise HTTPException(400, "Missing fields")

    # If author is a single word, it's likely just a last name — ask for full name
    if len(author.split()) == 1:
        async def need_full_name():
            msg = (
                "כדי לספק ניתוח מדויק, אני זקוקה ל**שם מלא של הסופר/ת** — שם פרטי ושם משפחה.\n\n"
                f"למשל: במקום _{author}_ בלבד, כתבי את השם המלא כגון _מרלן האוסהופר_, _עמוס עוז_ וכדומה."
            )
            yield f"data: {json.dumps({'text': msg}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(
            need_full_name(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    gh_token = os.environ.get("GITHUB_TOKEN")
    if not gh_token:
        raise HTTPException(500, "Server configuration error")

    ip = request.client.host if request.client else "unknown"
    log_use(name, book, author, ip)

    client = OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=gh_token,
    )
    prompt = (
        f"ניתוח ספרותי מלא ומעמיק: «{book}» מאת {author}.\n"
        "עברי על כל הסעיפים — אל תדלגי על אף אחד. כתבי בצורה אינטלקטואלית ועשירה."
    )

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def _stream():
        try:
            stream = client.chat.completions.create(
                model="Llama-3.3-70B-Instruct",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                stream=True,
                max_tokens=8000,
            )
            for chunk in stream:
                text = chunk.choices[0].delta.content
                if text:
                    loop.call_soon_threadsafe(queue.put_nowait, text)
            loop.call_soon_threadsafe(queue.put_nowait, None)
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, exc)

    threading.Thread(target=_stream, daemon=True).start()

    async def generate():
        while True:
            item = await queue.get()
            if item is None:
                yield "data: [DONE]\n\n"
                break
            if isinstance(item, Exception):
                yield f"data: {json.dumps({'error': str(item)})}\n\n"
                break
            yield f"data: {json.dumps({'text': item}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/admin")
async def admin(key: str = Query("")):
    admin_key = os.environ.get("ADMIN_KEY", "")
    if not admin_key or key != admin_key:
        raise HTTPException(403, "Forbidden")

    rows = all_uses()
    total = len(rows)

    rows_html = "".join(
        f"<tr><td>{r['ts']}</td><td>{r['name']}</td>"
        f"<td>«{r['book']}» / {r['author']}</td><td>{r['ip']}</td></tr>"
        for r in rows
    ) or "<tr><td colspan='4' style='text-align:center;color:#888'>אין שימושים עדיין</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Admin — סוכן הספרייה</title>
  <style>
    body{{font-family:'Segoe UI',Arial,sans-serif;background:#0d0b09;color:#e8e0d0;
         direction:rtl;padding:2rem;}}
    h1{{color:#e8c060;font-size:1.6rem;margin-bottom:.25rem;}}
    .meta{{color:#a09070;font-size:.9rem;margin-bottom:2rem;}}
    table{{width:100%;border-collapse:collapse;background:#1a1714;border-radius:12px;overflow:hidden;}}
    th{{background:#2a2418;color:#c4983a;font-size:.8rem;letter-spacing:.07em;
        text-transform:uppercase;padding:.75rem 1rem;text-align:right;}}
    td{{padding:.7rem 1rem;border-bottom:1px solid #2a2418;font-size:.92rem;}}
    tr:last-child td{{border-bottom:none;}}
    tr:hover td{{background:#221e18;}}
    .ip{{color:#706050;font-size:.82rem;direction:ltr;text-align:left;}}
  </style>
</head>
<body>
  <h1>📊 לוח שימושים — סוכן הספרייה</h1>
  <div class="meta">סה"כ ניתוחים: <strong>{total}</strong></div>
  <table>
    <thead><tr><th>תאריך ושעה</th><th>שם</th><th>ספר</th><th class="ip">IP</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</body>
</html>"""
    return HTMLResponse(html)
