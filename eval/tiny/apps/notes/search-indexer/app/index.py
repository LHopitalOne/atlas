import re
from collections import defaultdict
from threading import Lock

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


class InvertedIndex:
    def __init__(self) -> None:
        self._docs: dict[str, dict] = {}
        self._postings: dict[str, set[str]] = defaultdict(set)
        self._lock = Lock()

    def add(self, doc_id: str, title: str, body: str) -> None:
        with self._lock:
            self._drop(doc_id)
            self._docs[doc_id] = {"id": doc_id, "title": title, "body": body}
            for token in set(tokenize(f"{title} {body}")):
                self._postings[token].add(doc_id)

    def remove(self, doc_id: str) -> bool:
        with self._lock:
            return self._drop(doc_id)

    def search(self, query: str, limit: int) -> list[dict]:
        terms = tokenize(query)
        if not terms:
            return []
        scores: dict[str, int] = defaultdict(int)
        with self._lock:
            for term in terms:
                for doc_id in self._postings.get(term, ()):
                    scores[doc_id] += 1
            ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
            return [
                {**self._docs[doc_id], "score": score}
                for doc_id, score in ranked[:limit]
            ]

    def _drop(self, doc_id: str) -> bool:
        doc = self._docs.pop(doc_id, None)
        if doc is None:
            return False
        for token in set(tokenize(f"{doc['title']} {doc['body']}")):
            self._postings[token].discard(doc_id)
        return True
