import re

with open('frontend/src/components/ui/UPlotScope.tsx', 'r') as f:
    content = f.read()

old_xmax = "const xMax = isPaused ? (maxTs - xOffset * 1000) : now;"
new_xmax = "const xMax = (isPaused ? maxTs : now) - xOffset * 1000;"
content = content.replace(old_xmax, new_xmax)

with open('frontend/src/components/ui/UPlotScope.tsx', 'w') as f:
    f.write(content)
