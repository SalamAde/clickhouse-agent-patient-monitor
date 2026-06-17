"""
Permanent store of the agent's query plans, keyed by question.

This is NOT a cache. A saved analysis is kept until you choose to regenerate it.
When reused, it ALWAYS re-runs the saved SQL against the live database, so the
result reflects the current data - only the (expensive) step of having the AI
decide which queries to run is skipped.
"""
import json
import pathlib
import time


class SavedQueries:
    def __init__(self, path):
        self.path = pathlib.Path(path)

    @staticmethod
    def _norm(question):
        return " ".join(question.lower().split())

    def _load(self):
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _write(self, data):
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get(self, question):
        return self._load().get(self._norm(question))

    def save(self, question, scripts, answer=""):
        data = self._load()
        key = self._norm(question)
        prev = data.get(key, {})
        data[key] = {
            "question": question,
            "scripts": scripts,
            "answer": answer,
            "created_at": prev.get("created_at", time.time()),
            "updated_at": time.time(),
            "uses": prev.get("uses", 0),
        }
        self._write(data)

    def mark_reused(self, question):
        data = self._load()
        key = self._norm(question)
        if key in data:
            data[key]["uses"] = data[key].get("uses", 0) + 1
            self._write(data)

    def delete(self, question):
        data = self._load()
        data.pop(self._norm(question), None)
        self._write(data)

    def list_questions(self):
        items = sorted(self._load().values(), key=lambda x: x.get("updated_at", 0), reverse=True)
        return [it["question"] for it in items]

    def clear(self):
        self._write({})
