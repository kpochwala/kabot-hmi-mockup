const fs = require('fs');
let code = fs.readFileSync('frontend/src/app/page.tsx', 'utf8');

code = code.replace('onMouseMove={(s: any) => {', `onMouseMove={(s: any) => {
                                    if (Math.random() < 0.05) console.log("onMouseMove", s);`);

fs.writeFileSync('frontend/src/app/page.tsx', code);
