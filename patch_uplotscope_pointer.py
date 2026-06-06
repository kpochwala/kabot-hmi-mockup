import re

with open('frontend/src/components/ui/UPlotScope.tsx', 'r') as f:
    content = f.read()

content = content.replace("try { target.requestPointerLock(); } catch(err) {}", "")
content = content.replace("try { document.exitPointerLock(); } catch(err) {}", "")

with open('frontend/src/components/ui/UPlotScope.tsx', 'w') as f:
    f.write(content)
