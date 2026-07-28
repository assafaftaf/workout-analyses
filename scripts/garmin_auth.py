#!/usr/bin/env python3
"""
התחברות חד-פעמית ל-Garmin Connect ליצירת הטוקן ל-GitHub.

הרצה מקומית:
    pip install garminconnect
    python scripts/garmin_auth.py

הסקריפט מבקש אימייל, סיסמה, וקוד דו-שלבי אם צריך, ומדפיס מחרוזת base64.
את המחרוזת שמים ב-GitHub כ-secret בשם GARMIN_TOKENS.
הסיסמה עצמה לא נשמרת בשום מקום.
"""

import base64
import getpass
import sys

from garminconnect import Garmin


def main():
    email = input("אימייל Garmin: ").strip()
    password = getpass.getpass("סיסמה: ")

    api = Garmin(email, password, prompt_mfa=lambda: input("קוד דו-שלבי: ").strip())
    api.login()

    name = (api.get_full_name() or "").strip()
    print(f"\nמחובר{' כ-' + name if name else ''}.")

    blob = base64.b64encode(api.client.dumps().encode()).decode()
    print("\n" + "=" * 62)
    print("העתק את השורה הבאה ל-GitHub secret בשם GARMIN_TOKENS:")
    print("=" * 62)
    print(blob)
    print("=" * 62)
    print("\nהטוקן תקף כשנה. כשהוא יפוג, הרץ את הסקריפט שוב ועדכן את ה-secret.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
