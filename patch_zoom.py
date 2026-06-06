import re

with open('frontend/src/components/ui/UPlotScope.tsx', 'r') as f:
    content = f.read()

# Replace onGlobalZoom signature
content = content.replace(
    'onGlobalZoom: (mouseX: number, deltaY: number) => void;',
    'onGlobalZoom: (pctX: number, deltaY: number) => void;'
)

old_wheel = """    const handleWheel = (e: WheelEvent) => {
        // Only trigger if hovering over the canvas, not the labels
        if ((e.target as HTMLElement).tagName.toLowerCase() === 'canvas') {
            e.preventDefault();
            const rect = containerRef.current!.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            onGlobalZoom(mouseX, e.deltaY);
        }
    };"""

new_wheel = """    const handleWheel = (e: WheelEvent) => {
        if ((e.target as HTMLElement).tagName.toLowerCase() === 'canvas') {
            e.preventDefault();
            const rect = (e.target as HTMLElement).getBoundingClientRect();
            const pctX = (e.clientX - rect.left) / rect.width;
            if (pctX >= 0 && pctX <= 1) {
                onGlobalZoom(pctX, e.deltaY);
            }
        }
    };"""
content = content.replace(old_wheel, new_wheel)

with open('frontend/src/components/ui/UPlotScope.tsx', 'w') as f:
    f.write(content)


with open('frontend/src/app/page.tsx', 'r') as f:
    page_content = f.read()

old_uplot = """onScrollLabel={(k, dir, mult) => setYScales(p => ({...p, [k]: Math.max(0.001, (p[k] ?? 1) + dir * 0.1 * mult)}))}
                          />"""

new_uplot = """onScrollLabel={(k, dir, mult) => setYScales(p => ({...p, [k]: Math.max(0.001, (p[k] ?? 1) + dir * 0.1 * mult)}))}
                            onGlobalZoom={(pctX, deltaY) => {
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
                            }}
                          />"""

page_content = page_content.replace(old_uplot, new_uplot)

with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(page_content)

