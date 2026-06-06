import re

# 1. Update UPlotScope.tsx
with open('frontend/src/components/ui/UPlotScope.tsx', 'r') as f:
    content = f.read()

# Replace the move handler
old_move = "const move = (ev: PointerEvent) => { if(isDragging) onDragLabel(k, ev.movementY); };"
new_move = """const move = (ev: PointerEvent) => { 
                              if(isDragging) {
                                  const H = containerRef.current?.clientHeight || 400;
                                  const scale = yScales[k] || 2;
                                  const dyUnits = (ev.movementY / H) * scale;
                                  onDragLabel(k, dyUnits); 
                              }
                          };"""
content = content.replace(old_move, new_move)

# Remove the return null if out of bounds, just clamp or let it render
old_bounds = "if (pct < 0 || pct > 1) return null;"
new_bounds = "if (pct < -1 || pct > 2) return null; // Only hide if way off screen"
content = content.replace(old_bounds, new_bounds)

with open('frontend/src/components/ui/UPlotScope.tsx', 'w') as f:
    f.write(content)

# 2. Update page.tsx to not multiply by 0.05
with open('frontend/src/app/page.tsx', 'r') as f:
    page_content = f.read()

old_drag = "onDragLabel={(k, dy) => setYOffsets(p => ({...p, [k]: (p[k] || 0) + dy * 0.05}))}"
new_drag = "onDragLabel={(k, dyUnits) => setYOffsets(p => ({...p, [k]: (p[k] || 0) + dyUnits}))}"
page_content = page_content.replace(old_drag, new_drag)

with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(page_content)
