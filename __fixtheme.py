path = "_config.yml"
c = open(path, "r", encoding="utf-8-sig").read()
# 精确匹配，用 re.sub 行首的 theme: landscape
import re
c = re.sub(r'^theme:\s*landscape\s*$', 'theme: butterfly', c, flags=re.MULTILINE)
open(path, "w", encoding="utf-8").write(c)
# 验证
v = [l for l in open(path, encoding="utf-8") if l.startswith("theme")][0].strip()
print("theme 现在:", v)
