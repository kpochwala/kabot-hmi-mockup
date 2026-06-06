const fs = require('fs');
let code = fs.readFileSync('frontend/src/app/page.tsx', 'utf8');

const oldLineChart = `<LineChart 
                                data={plotHistory}
                                margin={{ top: 5, right: 5, left: 40, bottom: 5 }}
                            >`;

const newLineChart = `<LineChart 
                                data={plotHistory}
                                margin={{ top: 5, right: 5, left: 40, bottom: 5 }}
                                style={{ overflow: 'visible' }}
                            >`;

code = code.replace(oldLineChart, newLineChart);

// Also let's try removing pointerEvents: 'none' from the label to make it clickable
// Currently CustomArrowLabel has pointerEvents: 'auto' on the <g>

fs.writeFileSync('frontend/src/app/page.tsx', code);
