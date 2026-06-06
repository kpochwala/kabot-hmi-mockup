import re

with open('/home/kpochwala/git/kabot-io/hmi-antigravity/frontend/src/app/page.tsx', 'r') as f:
    code = f.read()

old_tree_block = """\
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
"""

new_tree_block = """\
       return (
          <div 
             key={fullKey} 
             className={`flex items-center justify-between py-1 px-2 border-b last:border-0 transition-colors cursor-pointer ${isActive ? '' : 'hover:bg-muted/10'}`}
             style={isActive && color ? { backgroundColor: `${color}20`, borderLeft: `3px solid ${color}` } : { borderLeft: '3px solid transparent' }}
             onClick={() => {
                 if (isPlotted) {
                     setPlottedKeys(p => p.filter(k => k !== fullKey));
                 } else {
                     setPlottedKeys(p => [...p, fullKey]);
                     setActiveYChannel(fullKey);
                 }
             }}
          >
             <div className="flex items-center gap-2">
               <Checkbox 
                 checked={isPlotted} 
                 className="pointer-events-none"
               />
"""

old_toolbar_block = """\
                    <div className="flex flex-col items-start justify-center px-3 border-r border-border/50 shrink-0">
                        <span className="text-[9px] uppercase font-bold text-muted-foreground mb-1 tracking-wider">Channel</span>
                        <Select value={activeYChannel} onValueChange={(v) => setActiveYChannel(v || "")}>
                          <SelectTrigger className="w-28 h-6 text-xs bg-background border shadow-sm focus:ring-0"><SelectValue /></SelectTrigger>
                          <SelectContent>{plottedKeys.map(k => <SelectItem key={k} value={k} className="text-xs">{k}</SelectItem>)}</SelectContent>
                        </Select>
                    </div>
"""

new_toolbar_block = """\
                    <div className="flex flex-col items-start justify-center px-3 border-r border-border/50 shrink-0">
                        <span className="text-[9px] uppercase font-bold text-muted-foreground mb-1 tracking-wider">Channel</span>
                        <Select value={activeYChannel} onValueChange={(v) => setActiveYChannel(v || "")}>
                          <SelectTrigger 
                            className="w-28 h-6 text-xs border shadow-sm focus:ring-0 font-bold"
                            style={{ 
                                backgroundColor: plottedKeys.indexOf(activeYChannel) >= 0 ? `${chartColors[plottedKeys.indexOf(activeYChannel) % chartColors.length]}20` : 'var(--background)',
                                color: plottedKeys.indexOf(activeYChannel) >= 0 ? chartColors[plottedKeys.indexOf(activeYChannel) % chartColors.length] : 'inherit',
                                borderColor: plottedKeys.indexOf(activeYChannel) >= 0 ? chartColors[plottedKeys.indexOf(activeYChannel) % chartColors.length] : 'var(--border)'
                            }}
                          ><SelectValue /></SelectTrigger>
                          <SelectContent>
                             {plottedKeys.map((k, i) => (
                               <SelectItem key={k} value={k} className="text-xs font-bold" style={{ color: chartColors[i % chartColors.length] }}>{k}</SelectItem>
                             ))}
                          </SelectContent>
                        </Select>
                    </div>
"""

code = code.replace(old_tree_block, new_tree_block)
code = code.replace(old_toolbar_block, new_toolbar_block)

with open('/home/kpochwala/git/kabot-io/hmi-antigravity/frontend/src/app/page.tsx', 'w') as f:
    f.write(code)

print("Rewrote page.tsx with updated tree click and toolbar styling.")
