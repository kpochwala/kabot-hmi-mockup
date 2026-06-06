import re

with open('frontend/src/components/ui/UPlotScope.tsx', 'r') as f:
    content = f.read()

# Add scale: k
old_series_map = """      ...plottedKeys.map((k, i) => ({
         show: true,
         spanGaps: false,
         label: k,
         stroke: chartColors[i % chartColors.length],
         width: k === activeYChannel ? 2 : 1.5,
      }))"""

new_series_map = """      ...plottedKeys.map((k, i) => ({
         show: true,
         spanGaps: false,
         label: k,
         scale: k,
         stroke: chartColors[i % chartColors.length],
         width: k === activeYChannel ? 2 : 1.5,
      }))"""
content = content.replace(old_series_map, new_series_map)

with open('frontend/src/components/ui/UPlotScope.tsx', 'w') as f:
    f.write(content)

with open('frontend/src/app/page.tsx', 'r') as f:
    page_content = f.read()

# Replace onScrollLabel
old_scroll_label = """onScrollLabel={(k, dir, mult) => setYScales(p => ({...p, [k]: Math.max(0.0001, (p[k] ?? 2) * (dir < 0 ? 1.1 : 0.9) * (mult > 1 ? 1.5 : mult < 1 ? 0.75 : 1))}))}"""

new_scroll_label = """onScrollLabel={(k, dir, mult) => {
                                const factor = (dir < 0 ? 1.1 : 0.9) * (mult > 1 ? 1.5 : mult < 1 ? 0.75 : 1);
                                setYScales(p => {
                                    const oldScale = p[k] ?? 2;
                                    const newScale = Math.max(0.0001, oldScale * factor);
                                    setYOffsets(po => ({...po, [k]: ((po[k] ?? 0) / oldScale) * newScale}));
                                    return {...p, [k]: newScale};
                                });
                            }}"""

page_content = page_content.replace(old_scroll_label, new_scroll_label)

# Replace onGlobalZoom
old_global_zoom = """                            onGlobalZoom={(pctX, deltaY) => {
                                const factor = deltaY > 0 ? 1.1 : 0.9;
                                setYScales(prev => {
                                    const next = { ...prev };
                                    plottedKeys.forEach(k => {
                                        next[k] = Math.max(0.0001, (next[k] ?? 2) * factor);
                                    });
                                    return next;
                                });
                            }}"""

new_global_zoom = """                            onGlobalZoom={(pctX, deltaY) => {
                                const factor = deltaY > 0 ? 1.1 : 0.9;
                                setYScales(prev => {
                                    const next = { ...prev };
                                    setYOffsets(prevOff => {
                                        const nextOff = { ...prevOff };
                                        plottedKeys.forEach(k => {
                                            const oldScale = next[k] ?? 2;
                                            const newScale = Math.max(0.0001, oldScale * factor);
                                            next[k] = newScale;
                                            const oldOffset = nextOff[k] ?? 0;
                                            nextOff[k] = (oldOffset / oldScale) * newScale;
                                        });
                                        return nextOff;
                                    });
                                    return next;
                                });
                            }}"""

page_content = page_content.replace(old_global_zoom, new_global_zoom)

with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(page_content)

