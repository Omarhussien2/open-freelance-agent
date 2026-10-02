# -*- coding: utf-8 -*-
"""اقرأ الدروس المرتبطة بمهمة قبل تنفيذها (الطبقة 2 من التعلم الذاتي).

Usage: python lessons_read.py <كلمة مفتاحية> [كلمة أخرى ...]
يطبع كل درس فيه أي كلمة من المفتاحيات (بحث في topic + context + lesson + rule).
Print-only: لا يكتب أي ملف."""
import json
import sys

LESSONS_FILE = r"lessons.jsonl"


def main():
    keys = [k.strip() for k in sys.argv[1:] if k.strip()]
    if not keys:
        print("USAGE: lessons_read.py <keyword> [...]")
        sys.exit(2)
    hits = []
    try:
        with open(LESSONS_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                blob = " ".join(str(d.get(k) or "") for k in ("topic", "context", "lesson", "rule"))
                if any(k in blob for k in keys):
                    hits.append(d)
    except FileNotFoundError:
        print("NO_LESSONS_FILE")
        sys.exit(3)
    print("LESSONS_FOUND:", len(hits))
    for i, d in enumerate(hits, 1):
        print(f"{i}. [{d.get('date','')}] {d.get('topic','')}: {d.get('lesson','')}")
        print(f"   القاعدة: {d.get('rule','')}")


if __name__ == "__main__":
    main()
