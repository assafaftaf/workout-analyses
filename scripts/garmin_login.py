#!/usr/bin/env python3
"""
מתחבר ל-Garmin ושומר טוקן טרי לקובץ, לשימוש הסנכרון באותה הרצה.

נועד לרוץ בתחילת כל workflow, כדי שלא נסתמך על טוקן ישן שפג תוקפו.

סדר הניסיונות:
  1. אימייל וסיסמה מה-secrets — יוצר טוקן חדש לגמרי
  2. אם נכשל ויש GARMIN_TOKENS שמור — משתמש בו כגיבוי

משתני סביבה:
  GARMIN_EMAIL, GARMIN_PASSWORD   ליצירת טוקן טרי
  GARMIN_MFA                      קוד דו-שלבי, אם מופעל בחשבון
  GARMIN_TOKENS                   טוקן base64 שמור, כגיבוי
  GARMIN_TOKEN_DIR                לאן לשמור. ברירת מחדל ~/.garminconnect
"""

import base64
import os
import sys

from garminconnect import Garmin

TOKEN_DIR = os.getenv("GARMIN_TOKEN_DIR",
                      os.path.expanduser("~/.garminconnect"))
TOKEN_FILE = os.path.join(TOKEN_DIR, "tokens.json")


def log(msg):
    print(msg, flush=True)


def save(api):
    os.makedirs(TOKEN_DIR, exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(api.client.dumps())
    log(f"הטוקן נשמר ל-{TOKEN_FILE}")


def from_credentials():
    email = os.getenv("GARMIN_EMAIL", "").strip()
    password = os.getenv("GARMIN_PASSWORD", "")
    mfa = os.getenv("GARMIN_MFA", "").strip()
    if not (email and password):
        log("אין GARMIN_EMAIL/GARMIN_PASSWORD, מדלג על יצירת טוקן טרי")
        return None

    log(f"מתחבר כ-{email[:3]}…@{email.split('@')[-1]} ליצירת טוקן טרי")
    api = Garmin(email, password, return_on_mfa=True)
    result = api.login()
    needs_mfa = result[0] if isinstance(result, tuple) else None

    if needs_mfa == "needs_mfa":
        if not mfa:
            raise RuntimeError(
                "החשבון דורש אימות דו-שלבי. הרצה מתוזמנת לא יכולה להזין קוד — "
                "השתמש ב-GARMIN_TOKENS כגיבוי, או בטל אימות דו-שלבי לחשבון")
        api.resume_login({}, mfa)

    save(api)
    return api


def from_saved_token():
    blob = os.getenv("GARMIN_TOKENS", "").strip()
    if not blob:
        return None
    log("משתמש בטוקן השמור מה-secret")
    os.makedirs(TOKEN_DIR, exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(base64.b64decode(blob).decode())
    api = Garmin()
    api.login(tokenstore=TOKEN_FILE)
    save(api)
    return api


def main():
    try:
        api = from_credentials()
    except Exception as e:
        log(f"יצירת טוקן טרי נכשלה — {type(e).__name__}: {e}")
        api = None

    if api is None:
        try:
            api = from_saved_token()
        except Exception as e:
            log(f"גם הטוקן השמור נכשל — {type(e).__name__}: {e}")
            api = None

    if api is None:
        log("לא הצלחתי להתחבר ל-Garmin בשום דרך")
        return 1

    try:
        name = (api.get_full_name() or "").strip()
        log(f"מחובר{' כ-' + name if name else ''}")
    except Exception:
        log("מחובר")
    return 0


if __name__ == "__main__":
    sys.exit(main())
