#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📚 סוכן הספרייה — ניתוח ספרותי מעמיק
שימוש: python book_agent.py "שם הספר" "שם הסופר"
       python book_agent.py   (מצב אינטראקטיבי)
"""

import anthropic
import sys
import os
from datetime import datetime

# Force UTF-8 output on Windows consoles
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")

# Load API key from .env file if not in environment
def _load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())

_load_env()

if not os.environ.get("ANTHROPIC_API_KEY"):
    print("\n❌ חסר ANTHROPIC_API_KEY")
    print("   הוסיפי שורה זו לקובץ .env שבתיקיית הסוכן:")
    print("   ANTHROPIC_API_KEY=sk-ant-...")
    sys.exit(1)

SYSTEM_PROMPT = """את מנתחת ספרות ועורכת ספרים מומחית — תואר שני בספרות השוואתית, עשרים שנה של עריכת ספרות יפה.
את קוראת ספרים בשתי שכבות: מה שכתוב, ומה שמתחת. את רואה את המוטיבים הנסתרים, הסמלים, הקונפליקטים הלא-אמורים.

כאשר מוגש לך שם ספר ושם סופר/ת — את מספקת ניתוח ספרותי מקיף ומושכל.
עני תמיד בעברית עשירה ואינטלקטואלית, עם אהבה אמיתית לספרות.

אם הספר פחות מוכר לך — ציינি זאת בפתיחה, אך המשיכי לספק את הניתוח הטוב ביותר שביכולתך.

**מבנה הניתוח — אל תדלגי על שום סעיף:**

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
- **מבנה הספר**: ליניארי? מסגרות? זמנים מקוטעים? פרספקטיבות?
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
- **מה פחות מוצלח?** (ביקורת כנה ולא מחמיאה)
- **השוואה ליצירות דומות** — מה ייחודי בו?
- **לאיזה קורא/ת** הספר הזה מיועד?
- **הציון שלי: X/10** — ועם נימוק

## ❓ שאלות לדיון בספרייה
7 שאלות מעמיקות ומעוררות שיחה, מגוונות: אחת אישית, אחת ספרותית, אחת פילוסופית, אחת על הרלוונטיות לימינו.

---

"""


def analyze_book(title: str, author: str) -> str:
    client = anthropic.Anthropic()

    bar = "═" * 62
    print(f"\n{bar}")
    print(f"  📚 סוכן הספרייה — ניתוח ספרותי מעמיק")
    print(f"{bar}")
    print(f"  ספר:    «{title}»")
    print(f"  סופר/ת: {author}")
    print(f"{bar}\n")
    print("  מכין ניתוח... ⏳\n")

    full_text = ""

    with client.messages.stream(
        model="claude-opus-4-8",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"ניתוח ספרותי מלא ומעמיק: «{title}» מאת {author}.\n"
                "עברי על כל הסעיפים במבנה — אל תדלגי על אף אחד. "
                "כתבי בצורה אינטלקטואלית ועשירה, עם תשוקה אמיתית לספרות."
            )
        }]
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            full_text += text

    return full_text


def save_analysis(title: str, author: str, content: str) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    # Safe ASCII portion for filename + Hebrew title in content
    safe_name = "".join(
        c if c.isalnum() or c in " -_" else "_"
        for c in title
    ).strip().replace(" ", "_")
    if not safe_name or all(c == "_" for c in safe_name):
        safe_name = "book"

    filename = f"{timestamp}_{safe_name}.md"
    save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ניתוחים")
    os.makedirs(save_dir, exist_ok=True)
    filepath = os.path.join(save_dir, filename)

    header = (
        f"# ניתוח ספרותי: «{title}» / {author}\n"
        f"*{datetime.now().strftime('%d/%m/%Y %H:%M')}*\n\n"
    )
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(header + content)

    return filepath


def main():
    if len(sys.argv) == 3:
        title, author = sys.argv[1], sys.argv[2]
    elif len(sys.argv) == 2:
        title = sys.argv[1]
        print(f"📖 ספר: {title}")
        author = input("שם הסופר/ת: ").strip()
    else:
        print("\n📖 סוכן הספרייה")
        title = input("שם הספר: ").strip()
        author = input("שם הסופר/ת: ").strip()

    if not title or not author:
        print("❌ חסרים פרטים: נדרש שם ספר ושם סופר/ת")
        sys.exit(1)

    content = analyze_book(title, author)
    filepath = save_analysis(title, author, content)

    bar = "═" * 62
    print(f"\n\n{bar}")
    print(f"  ✅ הניתוח הושלם!")
    print(f"  📄 נשמר ב: {filepath}")
    print(f"{bar}\n")


if __name__ == "__main__":
    main()
