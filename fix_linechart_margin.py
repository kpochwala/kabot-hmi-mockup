import re

with open('/home/kpochwala/git/kabot-io/hmi-antigravity/frontend/src/app/page.tsx', 'r') as f:
    code = f.read()

code = re.sub(
    r'<LineChart\s+data=\{plotHistory\}\s*>',
    '<LineChart data={plotHistory} margin={{ top: 5, right: 5, left: 40, bottom: 5 }} style={{ overflow: "visible" }}>',
    code
)

with open('/home/kpochwala/git/kabot-io/hmi-antigravity/frontend/src/app/page.tsx', 'w') as f:
    f.write(code)

print("Fixed LineChart margin and overflow.")
