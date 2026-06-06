import re

with open('frontend/src/app/page.tsx', 'r') as f:
    content = f.read()

# 1. Imports
content = re.sub(
    r'import \{ LineChart.*?\} from "recharts";',
    'import { UPlotScope } from "@/components/ui/UPlotScope";',
    content,
    flags=re.DOTALL
)

# Remove CustomTooltip and CustomArrowLabel
content = re.sub(
    r'const CustomTooltip = .*?return null;\n};\n',
    '',
    content,
    flags=re.DOTALL
)

content = re.sub(
    r'const CustomArrowLabel = .*?\n};\n',
    '',
    content,
    flags=re.DOTALL
)

# 2. State
content = re.sub(
    r'const \[plotHistory, setPlotHistory\] = useState<any\[\]>\(\[\]\);',
    'const dataBufferRef = useRef<any[]>([]);',
    content
)

# 3. Websocket
# Replace the setPlotHistory block
ws_block_old = """          if (!isPausedRef.current && !triggerRef.current.waiting) {
              setPlotHistory(prev => {
                 const newHistory = [...prev, entry];
                 const maxRetention = 60 * 1000; 
                 const cutoff = ts - maxRetention;
                 return newHistory.filter(e => e.timestamp >= cutoff);
              });
          }"""
ws_block_new = """          if (!isPausedRef.current && !triggerRef.current.waiting) {
              dataBufferRef.current.push(entry);
              const cutoff = ts - 60000;
              while (dataBufferRef.current.length > 0 && dataBufferRef.current[0].timestamp < cutoff) {
                  dataBufferRef.current.shift();
              }
          }"""
content = content.replace(ws_block_old, ws_block_new)

# maxTs calculation
content = re.sub(
    r'const maxTs = plotHistory\.length > 0 \? plotHistory\[plotHistory\.length - 1\]\.timestamp : now;',
    'const maxTs = dataBufferRef.current.length > 0 ? dataBufferRef.current[dataBufferRef.current.length - 1].timestamp : now;',
    content
)

# 4. Rendering
# We need to replace the entire <ResponsiveContainer>...</ResponsiveContainer> block
chart_regex = r'<ResponsiveContainer width="100%" height="100%">\s*<LineChart.*?</ResponsiveContainer>'
new_chart = """<UPlotScope 
                            dataRef={dataBufferRef}
                            plottedKeys={plottedKeys}
                            chartColors={chartColors}
                            xScale={xScale}
                            xOffset={xOffset}
                            yScales={yScales}
                            yOffsets={yOffsets}
                            activeYChannel={activeYChannel}
                            isPaused={isPaused}
                            onHoverData={setHoveredData}
                            setActiveYChannel={setActiveYChannel}
                            onDragLabel={(k, dy) => setYOffsets(p => ({...p, [k]: (p[k] || 0) + dy * 0.05}))}
                            onScrollLabel={(k, dir, mult) => setYScales(p => ({...p, [k]: Math.max(0.001, (p[k] ?? 1) + dir * 0.1 * mult)}))}
                          />"""
content = re.sub(chart_regex, new_chart, content, flags=re.DOTALL)

with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(content)

