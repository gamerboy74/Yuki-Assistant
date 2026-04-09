import sys, os
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env')

from backend import intent_router

tests = [
    ("lock my screen",          "lock_screen"),
    ("screen lock karo",        "lock_screen"),
    ("scroll down",             "chrome_action"),
    ("neeche karo",             "chrome_action"),
    ("what apps are running",   "list_apps"),
    ("kaunse apps chal rahe",   "list_apps"),
    ("wifi off karo",           "wifi_control"),
    ("turn on wifi",            "wifi_control"),
    ("what time is it",         "none"),
    ("time kya hua",            "none"),
    ("play despacito on youtube", "play_youtube"),
    ("open spotify",            "open_app"),
    ("close chrome",            "close_app"),
    ("what is on my screen",    "screenshot_ai"),
    ("switch to notepad",       "window_focus"),
    ("hey yuki",                "none"),
    ("thanks",                  "none"),
]

print(f"{'PHRASE':<35} {'EXPECTED':<18} {'GOT':<18} STATUS")
print("-" * 85)
passed = failed = 0
for phrase, expected in tests:
    r = intent_router.route(phrase)
    got = r['action']['type'] if r else "NO MATCH"
    ok = got == expected
    if ok: passed += 1
    else: failed += 1
    sym = "PASS" if ok else "FAIL"
    print(f"{sym} {phrase!r:<33} {expected:<18} {got:<18}")

print()
print(f"Passed: {passed}/{passed+failed}")
