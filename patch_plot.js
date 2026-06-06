const fs = require('fs');
let code = fs.readFileSync('frontend/src/app/page.tsx', 'utf8');

// Add ReferenceLine import
code = code.replace(/import \{ LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer \} from "recharts";/, 'import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";');

// Add CustomArrowLabel component outside Home
const arrowLabelCode = `
const CustomArrowLabel = (props: any) => {
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
};
`;

code = code.replace('export default function Home() {', arrowLabelCode + '\nexport default function Home() {');

// Update the LineChart rendering block
const oldLineChartBlock = `                              {plottedKeys.map((key, i) => (
                                 <Line 
                                    key={key} 
                                    yAxisId={key}
                                    type="monotone" 
                                    dataKey={key} 
                                    stroke={chartColors[i % chartColors.length]} 
                                    strokeWidth={2} 
                                    dot={false} 
                                    isAnimationActive={false} 
                                 />
                              ))}`;

const newLineChartBlock = `                              {plottedKeys.map((key, i) => {
                                 const color = chartColors[i % chartColors.length];
                                 const isActive = key === activeYChannel;
                                 return (
                                     <ReferenceLine 
                                         key={\`ref-\${key}\`}
                                         y={0} 
                                         yAxisId={key} 
                                         stroke={color} 
                                         strokeDasharray="3 3" 
                                         strokeWidth={isActive ? 1.5 : 1}
                                         opacity={isActive ? 0.8 : 0.3}
                                         label={<CustomArrowLabel color={color} isActive={isActive} text={key} />}
                                         isFront={true}
                                     />
                                 );
                              })}
                              
                              {plottedKeys.map((key, i) => {
                                 const color = chartColors[i % chartColors.length];
                                 const isActive = key === activeYChannel;
                                 return (
                                     <Line 
                                        key={key} 
                                        yAxisId={key}
                                        type="monotone" 
                                        dataKey={key} 
                                        stroke={color} 
                                        strokeWidth={isActive ? 3 : 1.5} 
                                        opacity={isActive ? 1 : 0.7}
                                        dot={false} 
                                        isAnimationActive={false} 
                                     />
                                 );
                              })}`;

code = code.replace(oldLineChartBlock, newLineChartBlock);

fs.writeFileSync('frontend/src/app/page.tsx', code);
