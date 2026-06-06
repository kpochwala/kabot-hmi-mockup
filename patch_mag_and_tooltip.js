const fs = require('fs');
let code = fs.readFileSync('frontend/src/app/page.tsx', 'utf8');

// Fix CustomTooltip
const oldTooltipCode = `const CustomTooltip = ({ active, payload, setHoveredData }: any) => {
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
};`;

const newTooltipCode = `import * as React from "react";\n\nconst CustomTooltip = ({ active, payload, setHoveredData }: any) => {
    React.useEffect(() => {
        if (active && payload && payload.length > 0) {
            setHoveredData(payload[0].payload);
        } else {
            setHoveredData(null);
        }
    }, [active, payload, setHoveredData]);
    return null;
};`;

code = code.replace(oldTooltipCode, newTooltipCode);

// Change defaults
code = code.replace("useState<string[]>(['effort.x', 'effort.y']);", "useState<string[]>(['mag.x', 'mag.y', 'mag.z']);");
code = code.replace("useState<string>('effort.x');", "useState<string>('mag.x');");
code = code.replace("key: 'effort.x'", "key: 'mag.x'");
code = code.replace("key: 'effort.x'", "key: 'mag.x'");

fs.writeFileSync('frontend/src/app/page.tsx', code);
