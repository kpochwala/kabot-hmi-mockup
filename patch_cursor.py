import re

with open('frontend/src/components/ui/UPlotScope.tsx', 'r') as f:
    content = f.read()

old_set_data = "plotRef.current.setData(cols as uPlot.AlignedData);"
new_set_data = """const oldLeft = plotRef.current.cursor.left;
             const oldTop = plotRef.current.cursor.top;
             plotRef.current.setData(cols as uPlot.AlignedData);
             if (oldLeft !== undefined && oldLeft >= 0) {
                 plotRef.current.setCursor({ left: oldLeft, top: oldTop });
             }"""
content = content.replace(old_set_data, new_set_data)

# Add onGlobalZoom to props
content = content.replace(
    'onScrollLabel: (k: string, dir: number, mult: number) => void;\n}',
    'onScrollLabel: (k: string, dir: number, mult: number) => void;\n  onGlobalZoom: (mouseX: number, deltaY: number) => void;\n}'
)
content = content.replace(
    'onScrollLabel\n}: UPlotScopeProps)',
    'onScrollLabel,\n  onGlobalZoom\n}: UPlotScopeProps)'
)

# Add wheel listener to container
hook_str = """    const ro = new ResizeObserver(entries => {
      if (plotRef.current) plotRef.current.setSize({ width: entries[0].contentRect.width, height: entries[0].contentRect.height });
    });
    ro.observe(containerRef.current);"""
new_hook_str = hook_str + """

    const handleWheel = (e: WheelEvent) => {
        // Only trigger if hovering over the canvas, not the labels
        if ((e.target as HTMLElement).tagName.toLowerCase() === 'canvas') {
            e.preventDefault();
            const rect = containerRef.current!.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            onGlobalZoom(mouseX, e.deltaY);
        }
    };
    containerRef.current.addEventListener('wheel', handleWheel, { passive: false });
"""
content = content.replace(hook_str, new_hook_str)

cleanup_str = """      ro.disconnect();
      if (plotRef.current) plotRef.current.destroy();"""
new_cleanup_str = """      ro.disconnect();
      if (containerRef.current) containerRef.current.removeEventListener('wheel', handleWheel);
      if (plotRef.current) plotRef.current.destroy();"""
content = content.replace(cleanup_str, new_cleanup_str)

with open('frontend/src/components/ui/UPlotScope.tsx', 'w') as f:
    f.write(content)
