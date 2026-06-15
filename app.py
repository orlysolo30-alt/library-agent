from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types as genai_types
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
את קוראת ספרים בשתי שכבות: מה שכתוב, ומה שמתחת. את רואה מוטיבים נסתרים, סמלים, קונפליקטים לא-אמורים.
עני תמיד בעברית עשירה ואינטלקטואלית, עם אהבה אמיתית לספרות.
אם הספר פחות מוכר לך — ציינ/י זאת, אך המשיכ/י עם הניתוח הטוב ביותר שביכולתך.

**מבנה הניתוח — אל תדלג/י על שום סעיף:**

---

# 📚 «[שם הספר]» / [שם הסופר/ת]

## 🖊️ הסופר/ת — דיוקן ספרותי
- **חיים ורקע**: שנות חיים, מוצא, עולם ילדות ותקופה
- **עולם רוחני ואינטלקטואלי**: השפעות, פילוסופיה, רקע פוליטי-תרבותי
- **מיקום ספרותי**: זרם, תקופה, ייחוד
- **יצירות מרכזיות נוספות**: מה כדאי לקרוא אחר כך?
- **פרט מרתק** שמשפיע על הבנת הספר

## 📖 הספר — הקשר ורקע
- **מתי ולמה נכתב**: רקע היסטורי, אישי, חברתי
- **קשר אוטוביוגרפי**: מה לקוח מחיי הסופר/ת?
- **קבלה בפרסום**: הצלחה? מחלוקת? התעלמות?
- **מקום בקאנון**: מעמד הספר כיום
- **עיבודים**: סרט, תיאטרון, סדרה — אם רלוונטי

## 🌿 עלילה וארכיטקטורה נרטיבית
- **סיכום העלילה** (ספוילרים מתונים)
- **מבנה הספר**: ליניארי? מסגרות? קפיצות בזמן?
- **קצב ואינטנסיביות**: איפה הספר "רץ" ואיפה "עוצר"
- **שיא הדרמה** ורגע המפנה
- **הסיום**: מספק? פתוח? אמביוולנטי?

## 👥 גלריית הדמויות
לכל דמות מרכזית (לפחות שתיים-שלוש):
- **מי היא** ותפקידה
- **מניעים פנימיים אמיתיים**
- **התפתחות לאורך הספר**
- **מה היא מסמלת**
*(בסוף: "הדמות שאני הכי אוהבת — ולמה")*

## 💡 נושאים ורעיונות
- **שלושת הנושאים הגדולים** — בעומק
- **שאלות שהספר מציב**: פילוסופיות, מוסריות, אנושיות
- **המסר**: מה הסופר/ת רצה/ה להגיד?
- **הקשר לזמן הכתיבה**: מה הספר אמר לדורו ולנו היום

## ✍️ שפה, סגנון ודימויים
- **קול הסיפור**: מי מספר ומאיזו נקודת מבט?
- **סגנון השפה**: קצר? פיוטי? אירוני?
- **שלושה דימויים מרכזיים** עם פרשנות
- **מוטיבים חוזרים** ומשמעותם
- **סמליות**: מיתולוגית, דתית, תרבותית

## 💬 ציטוטים נבחרים
3–5 ציטוטים מרכזיים עם פרשנות (ציינ/י אם מדובר בפרפרזה).

## 🔍 ביקורת ספרותית מאוזנת
- **מה יוצא דופן?**
- **מה פחות מוצלח?**
- **השוואה ליצירות דומות**
- **לאיזה קורא/ת** מיועד?
- **הציון שלי: X/10** עם נימוק

## ❓ שאלות לדיון בספרייה
7 שאלות מגוונות: אחת אישית, אחת ספרותית, אחת פילוסופית, אחת על הרלוונטיות לימינו.

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

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(500, "Server configuration error")

    ip = request.client.host if request.client else "unknown"
    log_use(name, book, author, ip)

    client = genai.Client(api_key=api_key)
    prompt = (
        f"ניתוח ספרותי מלא ומעמיק: «{book}» מאת {author}.\n"
        "עברי על כל הסעיפים — אל תדלגי על אף אחד. כתבי בצורה אינטלקטואלית ועשירה."
    )
    config = genai_types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        max_output_tokens=8192,
    )

    # Run blocking Gemini stream in a thread; feed chunks via asyncio.Queue
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def _stream():
        try:
            for chunk in client.models.generate_content_stream(
                model="gemini-1.5-flash",
                contents=prompt,
                config=config,
            ):
                if chunk.text:
                    loop.call_soon_threadsafe(queue.put_nowait, chunk.text)
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
