import re

with open('frontend/src/components/ui/UPlotScope.tsx', 'r') as f:
    content = f.read()

# Add isDraggingLabelRef
content = content.replace("const lastMousePos = useRef<{x: number, y: number} | null>(null);", "const lastMousePos = useRef<{x: number, y: number} | null>(null);\n  const isDraggingLabelRef = useRef(false);")

# Update handleWheel to check isDraggingLabelRef
old_handle_wheel = """    const handleWheel = (e: WheelEvent) => {
        const target = e.target as HTMLElement;
        if (target.classList.contains('u-over') || target.tagName.toLowerCase() === 'canvas') {
            e.preventDefault();"""

new_handle_wheel = """    const handleWheel = (e: WheelEvent) => {
        if (isDraggingLabelRef.current) return;
        const target = e.target as HTMLElement;
        if (target.classList.contains('u-over') || target.tagName.toLowerCase() === 'canvas') {
            e.preventDefault();"""

content = content.replace(old_handle_wheel, new_handle_wheel)

# Create configHash
content = content.replace("const visibleKeys = Object.values(channels).filter(c => c.visible).map(c => c.key);", "const visibleKeys = Object.values(channels).filter(c => c.visible).map(c => c.key);\n  const configHash = visibleKeys.map(k => `${k}:${channels[k]?.color}:${channels[k]?.focused}`).join('|');")

# Change useEffect dependency from channels to configHash
content = content.replace("  }, [visibleKeys.join(','), channels]); // recreate when visible channels or their focused/colors change", "  }, [configHash]); // recreate when visible channels or their focused/colors change")

# Update pointerDown to set isDraggingLabelRef
content = content.replace("let isDragging = true;", "let isDragging = true;\n                          isDraggingLabelRef.current = true;")

content = content.replace("isDragging = false;\n                              document.removeEventListener('pointermove', move);", "isDragging = false;\n                              isDraggingLabelRef.current = false;\n                              document.removeEventListener('pointermove', move);")

with open('frontend/src/components/ui/UPlotScope.tsx', 'w') as f:
    f.write(content)
