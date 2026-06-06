const fs = require('fs');
let code = fs.readFileSync('frontend/src/app/page.tsx', 'utf8');

// Add CustomTooltip component at the top, outside Home
const customTooltipCode = `
const CustomTooltip = ({ active, payload, setHoveredData }: any) => {
    import("react").then((React) => {
        React.useEffect(() => {
            if (active && payload && payload.length > 0) {
                setHoveredData(payload[0].payload);
            } else {
                setHoveredData(null);
            }
        }, [active, payload, setHoveredData]);
    });
    return null;
};
`;

code = code.replace('export default function Home() {', customTooltipCode + '\nexport default function Home() {');

// Remove onMouseMove from LineChart
code = code.replace(/onMouseMove=\{\(s: any\) => \{\s*if \(Math\.random\(\) < 0\.05\) console\.log\("onMouseMove", s\);\s*if \(s && s\.activePayload && s\.activePayload\.length > 0\) \{\s*setHoveredData\(s\.activePayload\[0\]\.payload\);\s*\}\s*\}\}/g, '');
code = code.replace(/onMouseLeave=\{\(\) => setHoveredData\(null\)\}/g, '');

// Replace Tooltip
code = code.replace(/<Tooltip \/>/g, '<Tooltip content={<CustomTooltip setHoveredData={setHoveredData} />} cursor={{ stroke: "yellow", strokeWidth: 1, strokeDasharray: "3 3" }} />');

fs.writeFileSync('frontend/src/app/page.tsx', code);
