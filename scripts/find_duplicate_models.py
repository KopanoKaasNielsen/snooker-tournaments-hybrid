import re
from collections import Counter

path = "app/models.py"
try:
    src = open(path, "r", encoding="utf-8").read()
except FileNotFoundError:
    print("⚠️  app/models.py not found; skipping duplicate scan.")
    raise SystemExit(0)

# crude regexes – good enough to flag likely issues
tablenames = re.findall(r"__tablename__\s*=\s*['\"]([^'\"]+)['\"]", src)
classes = re.findall(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(Base\)\s*:", src, flags=re.M)

dup_tabs = [t for t, c in Counter(tablenames).items() if c > 1]
dup_classes = [t for t, c in Counter(classes).items() if c > 1]

if not dup_tabs and not dup_classes:
    print("✅ No duplicate __tablename__ or model class names detected in app/models.py")
else:
    if dup_tabs:
        print("❌ Duplicate __tablename__ values detected:", ", ".join(dup_tabs))
    if dup_classes:
        print("❌ Duplicate model class names detected:", ", ".join(dup_classes))
    print("\n👉 Open app/models.py and remove duplicate declarations. "
          "You should have exactly one class per table name.")
