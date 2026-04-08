import json
import re
import os
from difflib import SequenceMatcher

_MAPPING_PATH = os.path.join(os.path.dirname(__file__), "mapping.json")
FUZZY_THRESHOLD = 0.6  # 0.6–0.7 works well for typical mis-hearings

class IntentClassifier:
    def __init__(self):
        with open(_MAPPING_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self._intents = []
        for intent, info in raw.items():
            # compile each regex pattern
            patterns = [re.compile(p, re.IGNORECASE) for p in info["patterns"]]
            # also keep literal strings (patterns without regex special chars)
            literals = [p for p in info["patterns"]
                        if not re.search(r"[\\^$.|?*+(){}\[\]]", p)]
            self._intents.append((intent, patterns, literals))

    def classify(self, text: str):
        # 1) Try regex patterns first
        for intent, patterns, _ in self._intents:
            for pat in patterns:
                m = pat.search(text)
                if m:
                    return intent, m.groupdict()

        # 2) Fuzzy match against literal patterns
        txt = text.lower().strip()
        for intent, _, literals in self._intents:
            for lit in literals:
                ratio = SequenceMatcher(None, txt, lit.lower()).ratio()
                if ratio >= FUZZY_THRESHOLD:
                    return intent, {}  # no params in fallback

        # 3) No match
        return None, {}

# singleton
classifier = IntentClassifier()

def get_intent(text: str):
    return classifier.classify(text)
