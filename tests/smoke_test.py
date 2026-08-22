"""
בדיקת עשן ל-app.py — טוענת את כל חמש התצוגות דרך AppTest ומוודאת
שאין exception. נועדה לתפוס רגרסיות כמו זו שבה app.py קרא
ל-theme.insights()/theme.section(desc) שלא היו קיימים ב-theme.py,
וזה נשבר רק ב-Streamlit Cloud.
"""
import os
import sys

from streamlit.testing.v1 import AppTest

APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")
VIEWS = ["Z2", "Z3", "Z4", "LONG", "RUN"]


def check(at, label):
    if not at.exception:
        print(f"[{label}] OK")
        return True
    print(f"[{label}] נכשל:")
    for e in at.exception:
        print(f"  {e}")
    return False


def main():
    ok = True
    for view in VIEWS:
        at = AppTest.from_file(APP_PATH)
        at.run(timeout=60)
        if not check(at, f"{view} (טעינה ראשונית)"):
            ok = False
            continue
        at.sidebar.radio[0].set_value(view).run(timeout=60)
        if not check(at, view):
            ok = False

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
