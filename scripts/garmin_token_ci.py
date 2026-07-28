#!/usr/bin/env python3
"""
יוצר טוקן Garmin בתוך GitHub Actions ומדפיס אותו ל-step summary.
מיועד לעקוף בעיות SSL/חומת אש ברשת המקומית — רץ משרת GitHub.

קלט דרך משתני סביבה (מגיעים מ-workflow_dispatch):
  GARMIN_EMAIL, GARMIN_PASSWORD   חובה
  GARMIN_MFA                      קוד דו-שלבי, אם מופעל בחשבון

הפלט הוא בלוק Markdown ל-GITHUB_STEP_SUMMARY עם מחרוזת ה-base64.
"""

import base64
import os
import sys

from garminconnect import Garmin


def main():
    email = os.getenv("GARMIN_EMAIL", "").strip()
    password = os.getenv("GARMIN_PASSWORD", "")
    mfa = os.getenv("GARMIN_MFA", "").strip()

    if not email or not password:
        print("### ❌ חסר אימייל או סיסמה")
        return 1

    try:
        # return_on_mfa מאפשר להזין קוד דו-שלבי שהגיע מראש כקלט,
        # בלי צורך באינטראקציה חיה שאין ב-CI.
        api = Garmin(email, password, return_on_mfa=True)
        result = api.login()

        needs_mfa = result[0] if isinstance(result, tuple) else None
        if needs_mfa == "needs_mfa":
            if not mfa:
                print("### ❌ החשבון דורש קוד דו-שלבי\n\n"
                      "הרץ שוב את ה-workflow והפעם מלא את שדה הקוד הדו-שלבי.")
                return 1
            # ה-client שומר בעצמו את מצב ה-MFA, ה-state לא בשימוש בגרסה הזו
            api.resume_login({}, mfa)
    except Exception as e:
        print(f"### ❌ ההתחברות נכשלה\n\n```\n{type(e).__name__}: {e}\n```")
        return 1

    try:
        blob = base64.b64encode(api.client.dumps().encode()).decode()
    except Exception as e:
        print(f"### ❌ נכשלה יצירת הטוקן\n\n```\n{e}\n```")
        return 1

    name = ""
    try:
        name = (api.get_full_name() or "").strip()
    except Exception:
        pass

    print("### ✅ הטוקן נוצר" + (f" · מחובר כ-{name}" if name else ""))
    print("\nהעתק את כל השורה הבאה ל-secret בשם `GARMIN_TOKENS`, "
          "ואז מחק את ה-workflow הזה:\n")
    print("```")
    print(blob)
    print("```")
    return 0


if __name__ == "__main__":
    sys.exit(main())
