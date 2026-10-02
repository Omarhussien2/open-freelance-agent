# -*- coding: utf-8 -*-
"""سجّل درسًا جديدًا بعد أي تجربة (الطبقة 3 من التعلم الذاتي).

الاستخدام: اكتب الدرس في الملف الثابت incoming_lesson.txt بهذا الشكل (سطر لكل عنصر):
  topic: الموضوع
  context: السياق
  lesson: الدرس المستفاد
  rule: القاعدة القابلة للتنفيذ
ثم: python lessons_add.py
يطبع السطر المضاف للتأكيد. المسارات ثابتة حرفية."""
import json
import time

IN_FILE = r"incoming_lesson.txt"
LESSONS_FILE = r"lessons.jsonl"


def main():
    fields = {}
    try:
        with open(IN_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                for k in ("topic:", "context:", "lesson:", "rule:"):
                    if line.startswith(k):
                        fields[k[:-1]] = line[len(k):].strip()
    except FileNotFoundError:
        print("NO_INCOMING: اكتب الدرس في incoming_lesson.txt الأول")
        raise SystemExit(2)
    if not all(fields.get(k) for k in ("topic", "context", "lesson", "rule")):
        print("INCOMPLETE: لازم topic و context و lesson و rule كلهم")
        raise SystemExit(3)
    record = {
        "date": time.strftime("%Y-%m-%d"),
        "topic": fields["topic"][:40],
        "context": fields["context"][:120],
        "lesson": fields["lesson"][:200],
        "rule": fields["rule"][:200],
    }
    line = json.dumps(record, ensure_ascii=False)
    with open(LESSONS_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    with open(IN_FILE, "w", encoding="utf-8") as f:
        f.write("")
    print("LESSON_ADDED:", line)


if __name__ == "__main__":
    main()
