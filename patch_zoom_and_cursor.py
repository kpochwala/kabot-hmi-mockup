import re

with open('frontend/src/components/ui/UPlotScope.tsx', 'r') as f:
    content = f.read()

# Fix the handleWheel target checking
old_wheel = """    const handleWheel = (e: WheelEvent) => {
        if ((e.target as HTMLElement).tagName.toLowerCase() === 'canvas') {
            e.preventDefault();
            const rect = (e.target as HTMLElement).getBoundingClientRect();
            const pctX = (e.clientX - rect.left) / rect.width;
            if (pctX >= 0 && pctX <= 1) {
                onGlobalZoom(pctX, e.deltaY);
            }
        }
    };"""

new_wheel = """    const handleWheel = (e: WheelEvent) => {
        const target = e.target as HTMLElement;
        if (target.classList.contains('u-over') || target.tagName.toLowerCase() === 'canvas') {
            e.preventDefault();
            const rect = target.getBoundingClientRect();
            const pctX = (e.clientX - rect.left) / rect.width;
            if (pctX >= 0 && pctX <= 1) {
                onGlobalZoom(pctX, e.deltaY);
            }
        }
    };"""
content = content.replace(old_wheel, new_wheel)

# Add mouse tracking and synthetic dispatch
# We need to insert lastMousePos ref inside UPlotScope
ref_injection = """  const plotRef = useRef<uPlot | null>(null);
  
  // We need to keep a ref"""
new_ref_injection = """  const plotRef = useRef<uPlot | null>(null);
  const lastMousePos = useRef<{x: number, y: number} | null>(null);
  
  useEffect(() => {
     const moveHandler = (e: MouseEvent) => {
         lastMousePos.current = { x: e.clientX, y: e.clientY };
     };
     document.addEventListener('mousemove', moveHandler);
     return () => document.removeEventListener('mousemove', moveHandler);
  }, []);
  
  // We need to keep a ref"""
content = content.replace(ref_injection, new_ref_injection)

# Replace the cursor restore logic with synthetic event
old_set_data = """             const oldLeft = plotRef.current.cursor.left;
             const oldTop = plotRef.current.cursor.top;
             plotRef.current.setData(cols as uPlot.AlignedData);
             if (oldLeft !== undefined && oldLeft >= 0) {
                 plotRef.current.setCursor({ left: oldLeft, top: oldTop || 0 });
             }"""

new_set_data = """             plotRef.current.setData(cols as uPlot.AlignedData);
             if (lastMousePos.current && containerRef.current) {
                 const over = containerRef.current.querySelector('.u-over');
                 if (over) {
                     const rect = over.getBoundingClientRect();
                     if (
                         lastMousePos.current.x >= rect.left && lastMousePos.current.x <= rect.right &&
                         lastMousePos.current.y >= rect.top && lastMousePos.current.y <= rect.bottom
                     ) {
                         over.dispatchEvent(new MouseEvent('mousemove', {
                             clientX: lastMousePos.current.x,
                             clientY: lastMousePos.current.y,
                             bubbles: true
                         }));
                     }
                 }
             }"""
content = content.replace(old_set_data, new_set_data)

with open('frontend/src/components/ui/UPlotScope.tsx', 'w') as f:
    f.write(content)
