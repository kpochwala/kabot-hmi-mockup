import re

with open('frontend/src/app/page.tsx', 'r') as f:
    content = f.read()

# Replace onScrollLabel
old_scroll_label = "onScrollLabel={(k, dir, mult) => setYScales(p => ({...p, [k]: Math.max(0.001, (p[k] ?? 1) + dir * 0.1 * mult)}))}"
new_scroll_label = "onScrollLabel={(k, dir, mult) => setYScales(p => ({...p, [k]: Math.max(0.0001, (p[k] ?? 2) * (dir < 0 ? 1.1 : 0.9) * (mult > 1 ? 1.5 : mult < 1 ? 0.75 : 1))}))}"
content = content.replace(old_scroll_label, new_scroll_label)

# Replace onGlobalZoom
old_global_zoom = """                            onGlobalZoom={(pctX, deltaY) => {
                                const zoomFactor = deltaY > 0 ? 1.1 : 0.9;
                                setXScale(oldScale => {
                                    const newScale = oldScale * zoomFactor;
                                    setXOffset(oldOffset => {
                                        const newOffset = oldOffset - (1 - pctX) * (newScale - oldScale);
                                        return Math.max(0, newOffset);
                                    });
                                    xScaleRef.current = newScale;
                                    return newScale;
                                });
                            }}"""

new_global_zoom = """                            onGlobalZoom={(pctX, deltaY) => {
                                const factor = deltaY > 0 ? 1.1 : 0.9;
                                setYScales(prev => {
                                    const next = { ...prev };
                                    plottedKeys.forEach(k => {
                                        next[k] = Math.max(0.0001, (next[k] ?? 2) * factor);
                                    });
                                    return next;
                                });
                            }}"""
content = content.replace(old_global_zoom, new_global_zoom)

with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(content)
