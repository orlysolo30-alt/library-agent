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

SYSTEM_PROMPT = """את מנתחת ספרות ועורכת ספרים מומחית — תואר שני בספרות השוואתית, עשרים שנה של עריכת ספרות יפה.

**סגנון הכתיבה — זה הכי חשוב:**
כתבי כאילו את יושבת מול חברה בבית קפה ומספרת לה על ספר שקראת. לא דוח. לא רשימות. לא נקודות.
פסקאות זורמות, חמות, אינטלקטואליות — כמו שיחה בין שתי נשים שאוהבות ספרות.
מעבר טבעי בין רעיון לרעיון, בין ביוגרפיה לעלילה לדמויות — הכל שזור יחד.
מותר להפתיע, לחלוק דעה אישית, להתלהב, לתהות בקול רם.
**אסור להשתמש בנקודות, רשימות, או בולטים. רק פסקאות.**

עני תמיד בעברית עשירה, עם אהבה אמיתית לספרות.

---

# «[שם הספר]» / [שם הסופר/ת]

## הסופר/ת

כתבי שתי-שלוש פסקאות על האדם מאחורי הספר — מי הוא/היא, מאיפה בא/ה העולם הפנימי שלו/ה, אילו חוויות חיים עיצבו את הקול הספרותי. שלבי פרט אחד מפתיע שלא כולם יודעים, שמאיר את הספר באור אחר.

## הספר בחיי הסופר/ת

מתי בחייו/ה נכתב הספר הזה, ולמה דווקא אז? מה קרה — אישית, היסטורית, רגשית — שגרם לספר הזה לצאת לאוויר העולם? ספרי על הקשר בין הביוגרפיה לבין מה שקורה בדפים.

## העלילה

ספרי על הספר — לא סיכום יבש, אלא כמו שמספרים על חוויה. מה קורה, לאן הספר נע, איפה הוא מרגיש דחוס ואיפה הוא נושם. איפה הלב שלו.

## הדמויות

הכניסי אותנו לדמויות — לא רשימה, אלא שיחה. מי הם האנשים האלה, מה הם רוצים בעצם (לא מה שהם אומרים שהם רוצים), ואיך הם משתנים — או לא משתנים. ספרי גם איזו דמות נגעה בך אישית ולמה.

## הנושאים הגדולים

מה הספר הזה באמת מדבר עליו? מעבר לעלילה — מה השאלות הגדולות שהוא מציב, מה הוא אומר על בני אדם, על חברה, על חיים. כתבי בצורה שמזמינה מחשבה.

## השפה והסגנון

איך הספר כתוב? מה הקול — קרוב, מרוחק, אירוני, פיוטי? האם יש דימויים שחזרו אליך אחרי שסגרת אותו? שתפי אחד או שניים שמיוחדים לדעתך ופרשי אותם.

## משפטים שנשארים

2–3 ציטוטים שאי אפשר לשכוח, עם כמה מילים על למה הם חזקים כל כך.

## ביקורת כנה

מה עושה הספר הזה טוב מאוד — ומה פחות? כתבי בכנות, עם דעה, כמו מבקרת שיש לה קול. השוואה קצרה ליצירות שמזכירות אותו — ומה מבדיל ביניהן. וסיימי עם: לאיזה קורא/ת הספר הזה ידבר במיוחד.

## לשיחה בספרייה

7 שאלות שפותחות דיון אמיתי — לא שאלות ידע, אלא שאלות שאין להן תשובה אחת נכונה.

---
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
