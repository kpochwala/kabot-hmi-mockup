import re

with open('frontend/src/components/ui/spinbox.tsx', 'r') as f:
    content = f.read()

# Remove requestPointerLock
content = content.replace("containerRef.current.requestPointerLock();", "")

# Remove exitPointerLock
content = content.replace("document.exitPointerLock();", "")

# Remove pointerlockchange
content = re.sub(r'const handlePointerLockChange = \(\) => \{.*?};\n', '', content, flags=re.DOTALL)
content = content.replace("document.addEventListener('pointerlockchange', handlePointerLockChange);\n", "")
content = content.replace("document.removeEventListener('pointerlockchange', handlePointerLockChange);\n", "")

with open('frontend/src/components/ui/spinbox.tsx', 'w') as f:
    f.write(content)
