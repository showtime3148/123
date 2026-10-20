import math
import re
from collections import Counter
from difflib import SequenceMatcher


def normalize(text):
    return " ".join(re.findall(r"[a-z0-9가-힣]+", text.lower()))


def tokens(text):
    return set(normalize(text).split())


class SearchIndex:
    def __init__(self, entries):
        self.entries = [entry for entry in entries if entry.get("question")]
        counts = Counter(token for entry in self.entries for token in tokens(entry["question"]))
        self.idf = {token: math.log((len(self.entries) + 1) / (count + 1)) + 1 for token, count in counts.items()}

    def search(self, query):
        normalized = normalize(query)
        query_tokens = tokens(query)
        results = []
        for entry in self.entries:
            question = normalize(entry["question"])
            expected = tokens(question)
            overlap = query_tokens & expected
            recall = sum(self.idf[t] for t in overlap) / sum(self.idf[t] for t in expected)
            precision = sum(self.idf[t] for t in overlap) / max(
                1, sum(self.idf.get(t, 3) for t in query_tokens)
            )
            sequence = SequenceMatcher(None, normalized, question).ratio()
            score = 0.6 * recall + 0.2 * precision + 0.2 * sequence
            # Full question plus OCR'ed choices is a strong match.
            if question in normalized and len(query_tokens) >= 8:
                score = 1.0
            results.append({**entry, "similarity": round(score, 3)})
        results.sort(key=lambda row: row["similarity"], reverse=True)
        top = results[:3]
        confident = bool(
            len(query_tokens) >= 8 and top and top[0]["similarity"] >= 0.77
            and (len(top) == 1 or top[0]["similarity"] - top[1]["similarity"] >= 0.10)
        )
        return top, confident
