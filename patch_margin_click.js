const fs = require('fs');
let code = fs.readFileSync('frontend/src/app/page.tsx', 'utf8');

const oldArrowLabel = `const CustomArrowLabel = (props: any) => {
    const { viewBox, color, isActive, text } = props;
    if (!viewBox) return null;
    const { x, y } = viewBox;
    
    // Position on the far left inside the chart. viewBox.x is the left edge of the chart area.
    // We'll shift it slightly left so it hangs off the edge like a real oscilloscope tag.
    return (
       <g transform={\`translate(\${x - 2}, \${y - 8})\`}>
          {isActive ? (
             <polygon points="0,0 16,0 22,8 16,16 0,16" fill={color} />
          ) : (
             <polygon points="0,0 16,0 22,8 16,16 0,16" fill="var(--background)" stroke={color} strokeWidth={1.5} />
          )}
          <text x={9} y={11} fill={isActive ? '#000' : color} fontSize={9} fontWeight="bold" textAnchor="middle" style={{ pointerEvents: 'none' }}>
              {text.split('.').pop().substring(0, 2).toUpperCase()}
          </text>
       </g>
    );
};`;

const newArrowLabel = `const CustomArrowLabel = (props: any) => {
    const { viewBox, color, isActive, text, onClick } = props;
    if (!viewBox) return null;
    const { x, y } = viewBox;
    
    // Shift the tag entirely into the left margin
    return (
       <g transform={\`translate(\${x - 24}, \${y - 8})\`} onClick={onClick} style={{ cursor: 'pointer', pointerEvents: 'auto' }}>
          {isActive ? (
             <polygon points="0,0 16,0 22,8 16,16 0,16" fill={color} />
          ) : (
             <polygon points="0,0 16,0 22,8 16,16 0,16" fill="var(--background)" stroke={color} strokeWidth={1.5} />
          )}
          <text x={9} y={11} fill={isActive ? '#000' : color} fontSize={9} fontWeight="bold" textAnchor="middle" style={{ pointerEvents: 'none' }}>
              {text.split('.').pop().substring(0, 2).toUpperCase()}
          </text>
       </g>
    );
};`;

code = code.replace(oldArrowLabel, newArrowLabel);

const oldLineChart = `<LineChart 
                                data={plotHistory}
                            >`;
const newLineChart = `<LineChart 
                                data={plotHistory}
                                margin={{ top: 5, right: 5, left: 24, bottom: 5 }}
                            >`;

code = code.replace(oldLineChart, newLineChart);

const oldRefLine = `label={<CustomArrowLabel color={color} isActive={isActive} text={key} />}`;
const newRefLine = `label={<CustomArrowLabel color={color} isActive={isActive} text={key} onClick={() => setActiveYChannel(key)} />}`;

code = code.replace(oldRefLine, newRefLine);

fs.writeFileSync('frontend/src/app/page.tsx', code);
