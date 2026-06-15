from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
import json
import os

app = FastAPI(title="Library Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

SYSTEM_PROMPT = """את מנתחת ספרות ועורכת ספרים מומחית — תואר שני בספרות השוואתית, עשרים שנה של עריכת ספרות יפה.
את קוראת ספרים בשתי שכבות: מה שכתוב, ומה שמתחת. את רואה את המוטיבים הנסתרים, הסמלים, הקונפליקטים הלא-אמורים.

כאשר מוגש לך שם ספר ושם סופר/ת — את מספקת ניתוח ספרותי מקיף ומושכל.
עני תמיד בעברית עשירה ואינטלקטואלית, עם אהבה אמיתית לספרות.
אם הספר פחות מוכר לך — ציינ/י זאת בפתיחה, אך המשיכ/י עם הניתוח הטוב ביותר שביכולתך.

**מבנה הניתוח — אל תדלג/י על שום סעיף:**

---

# 📚 «[שם הספר]» / [שם הסופר/ת]

## 🖊️ הסופר/ת — דיוקן ספרותי
- **חיים ורקע**: שנות חיים, מוצא, עולם ילדות ותקופה
- **עולם רוחני ואינטלקטואלי**: השפעות, פילוסופיה, רקע פוליטי-תרבותי
- **מיקום ספרותי**: איזה זרם, איזו תקופה, מה ייחודו/ה
- **יצירות מרכזיות נוספות**: מה כדאי לקרוא אחר כך?
- **פרט מרתק** שמשפיע על הבנת הספר

## 📖 הספר — הקשר ורקע
- **מתי ולמה נכתב**: הרקע ההיסטורי, אישי, חברתי של הכתיבה
- **קשר אוטוביוגרפי**: מה לקוח מחיי הסופר/ת?
- **קבלה בפרסום**: הצלחה? מחלוקת? התעלמות?
- **מקום בקאנון**: מה מעמד הספר כיום?
- **עיבודים**: סרט, תיאטרון, סדרה — אם רלוונטי

## 🌿 עלילה וארכיטקטורה נרטיבית
- **סיכום העלילה** (ברמה שמאפשרת דיון — ספוילרים מתונים לשיאים גדולים)
- **מבנה הספר**: ליניארי? מסגרות? קפיצות בזמן? פרספקטיבות?
- **קצב ואינטנסיביות**: איפה הספר "רץ" ואיפה הוא "עוצר" — ולמה?
- **שיא הדרמה** ורגע המפנה המרכזי
- **הסיום**: מספק? פתוח? אמביוולנטי?

## 👥 גלריית הדמויות
לכל דמות מרכזית (לפחות שתיים-שלוש):
- **מי היא** ומה תפקידה בעלילה
- **המניעים הפנימיים האמיתיים** — לא רק הגלויים
- **ההתפתחות לאורך הספר** — האם משתנה?
- **מה היא מסמלת** מעבר לפשוטו של מקרא
*(בסוף: "הדמות שאני הכי אוהבת — ולמה")*

## 💡 נושאים ורעיונות
- **שלושת הנושאים הגדולים** של הספר — בעומק
- **שאלות שהספר מציב**: פילוסופיות, מוסריות, אנושיות
- **המסר**: מה הסופר/ת רצה/ה להגיד? האם הצליח/ה?
- **הקשר לזמן הכתיבה**: מה הספר אמר לדורו ומה הוא אומר לנו היום

## ✍️ שפה, סגנון ודימויים
- **קול הסיפור**: מי מספר ומאיזו נקודת מבט?
- **סגנון השפה**: קצר ורועם? ארוך ופיוטי? אירוני? פולחני?
- **שלושה דימויים מרכזיים** עם פרשנות מעמיקה לכל אחד
- **מוטיבים חוזרים**: מה חוזר שוב ושוב — ומה זה אומר?
- **סמליות**: מיתולוגית, דתית, תרבותית — אם קיימת

## 💬 ציטוטים נבחרים
3–5 ציטוטים מרכזיים (קרובים לטקסט ככל האפשר — ציינ/י אם מדובר בפרפרזה).
לכל אחד: הציטוט + 2–3 שורות פרשנות.

## 🔍 ביקורת ספרותית מאוזנת
- **מה הספר עושה יוצא דופן?**
- **מה פחות מוצלח?** (ביקורת כנה)
- **השוואה ליצירות דומות** — מה ייחודי בו?
- **לאיזה קורא/ת** הספר הזה מיועד?
- **הציון שלי: X/10** — עם נימוק

## ❓ שאלות לדיון בספרייה
7 שאלות מעמיקות ומגוונות: אחת אישית, אחת ספרותית, אחת פילוסופית, אחת על הרלוונטיות לימינו.

---
"""


class BookRequest(BaseModel):
    book: str
    author: str


@app.get("/")
async def root():
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "static", "index.html")
    )


@app.post("/analyze")
async def analyze(req: BookRequest):
    book = req.book.strip()
    author = req.author.strip()

    if not book or not author:
        raise HTTPException(status_code=400, detail="Missing book or author")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Server configuration error")

    async def generate():
        try:
            client = anthropic.Anthropic(api_key=api_key)
            with client.messages.stream(
                model="claude-opus-4-8",
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": (
                        f"ניתוח ספרותי מלא ומעמיק: «{book}» מאת {author}.\n"
                        "עברי על כל הסעיפים — אל תדלגי על אף אחד. "
                        "כתבי בצורה אינטלקטואלית ועשירה, עם תשוקה אמיתית לספרות."
                    )
                }]
            ) as stream:
                for text in stream.text_stream:
                    payload = json.dumps({"text": text}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            error_payload = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"data: {error_payload}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
