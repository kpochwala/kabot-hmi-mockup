import re

with open('/home/kpochwala/git/kabot-io/hmi-antigravity/frontend/src/app/page.tsx', 'r') as f:
    code = f.read()

# We need to replace the `if (typeof obj === 'number') { ... return (...) }` inside renderTree.

old_block = """\
       return (
          <div key={fullKey} className="flex items-center justify-between py-1 border-b last:border-0 hover:bg-muted/10">
             <div className="flex items-center gap-2">
               <Checkbox 
                 checked={plottedKeys.includes(fullKey)} 
                 onCheckedChange={(c) => {
                   if (c) {
                       setPlottedKeys(p => [...p, fullKey]);
                       setActiveYChannel(fullKey);
                   }
                   else setPlottedKeys(p => p.filter(k => k !== fullKey));
                 }}
               />
               <span className="font-mono text-xs text-muted-foreground">{fullKey}</span>
             </div>
             <div className="flex items-center gap-3">
               <span className="font-mono text-[10px] text-muted-foreground/70 w-12 text-right">{hz} Hz</span>
               <span className="font-mono text-sm w-16 text-right font-medium">{typeof val === 'number' ? val.toFixed(3) : val}</span>
             </div>
          </div>
       );
"""

new_block = """\
       const plottedIdx = plottedKeys.indexOf(fullKey);
       const isPlotted = plottedIdx >= 0;
       const color = isPlotted ? chartColors[plottedIdx % chartColors.length] : undefined;
       const isActive = fullKey === activeYChannel;

       return (
          <div 
             key={fullKey} 
             className={`flex items-center justify-between py-1 px-2 border-b last:border-0 transition-colors cursor-pointer ${isActive ? '' : 'hover:bg-muted/10'}`}
             style={isActive && color ? { backgroundColor: `${color}20`, borderLeft: `3px solid ${color}` } : {}}
             onClick={() => isPlotted && setActiveYChannel(fullKey)}
          >
             <div className="flex items-center gap-2">
               <Checkbox 
                 checked={isPlotted} 
                 onCheckedChange={(c) => {
                   if (c) {
                       setPlottedKeys(p => [...p, fullKey]);
                       setActiveYChannel(fullKey);
                   }
                   else setPlottedKeys(p => p.filter(k => k !== fullKey));
                 }}
               />
               <span className={`font-mono text-xs ${!isActive && 'text-muted-foreground'}`} style={isActive && color ? { color, fontWeight: 'bold' } : {}}>{fullKey}</span>
             </div>
             <div className="flex items-center gap-3">
               <span className="font-mono text-[10px] text-muted-foreground/70 w-12 text-right">{hz} Hz</span>
               <span className="font-mono text-sm w-16 text-right font-medium" style={isActive && color ? { color } : {}}>{typeof val === 'number' ? val.toFixed(3) : val}</span>
             </div>
          </div>
       );
"""

if old_block in code:
    code = code.replace(old_block, new_block)
    with open('/home/kpochwala/git/kabot-io/hmi-antigravity/frontend/src/app/page.tsx', 'w') as f:
        f.write(code)
    print("Replaced successfully.")
else:
    print("Could not find the block.")

