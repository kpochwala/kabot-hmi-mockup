import re

with open('/home/kpochwala/git/kabot-io/hmi-antigravity/frontend/src/app/page.tsx', 'r') as f:
    code = f.read()

old_tree_block = """\
       return (
          <div 
             key={fullKey} 
             className={`flex items-center justify-between py-1 px-2 border-b last:border-0 transition-colors cursor-pointer ${isActive ? '' : 'hover:bg-muted/10'}`}
             style={isActive && color ? { backgroundColor: `${color}20`, borderLeft: `3px solid ${color}` } : { borderLeft: '3px solid transparent' }}
             onClick={() => {
"""

new_tree_block = """\
       return (
          <div 
             key={fullKey} 
             className={`flex items-center justify-between py-1 px-2 border-b last:border-0 transition-colors cursor-pointer hover:bg-muted/10`}
             style={isPlotted && color ? { backgroundColor: isActive ? `${color}30` : `${color}15`, borderLeft: isActive ? `4px solid ${color}` : `2px solid ${color}` } : { borderLeft: '2px solid transparent' }}
             onClick={() => {
"""

old_tree_text_block = """\
               <span className={`font-mono text-xs ${!isActive && 'text-muted-foreground'}`} style={isActive && color ? { color, fontWeight: 'bold' } : {}}>{fullKey}</span>
             </div>
             <div className="flex items-center gap-3">
               <span className="font-mono text-[10px] text-muted-foreground/70 w-12 text-right">{hz} Hz</span>
               <span className="font-mono text-sm w-16 text-right font-medium" style={isActive && color ? { color } : {}}>{typeof val === 'number' ? val.toFixed(3) : val}</span>
             </div>
          </div>
       );
"""

new_tree_text_block = """\
               <span className="font-mono text-xs" style={isPlotted && color ? { color, fontWeight: isActive ? 'bold' : 'normal' } : { color: 'var(--muted-foreground)' }}>{fullKey}</span>
             </div>
             <div className="flex items-center gap-3">
               <span className="font-mono text-[10px] text-muted-foreground/70 w-12 text-right" style={isPlotted && color ? { color: `${color}99` } : {}}>{hz} Hz</span>
               <span className="font-mono text-sm w-16 text-right font-medium" style={isPlotted && color ? { color } : {}}>{typeof val === 'number' ? val.toFixed(3) : val}</span>
             </div>
          </div>
       );
"""

old_toolbar_block = """\
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

new_toolbar_block = """\
                    <div 
                      className="flex flex-col items-start justify-center px-3 border-r border-border/50 shrink-0 h-full transition-colors"
                      style={{ backgroundColor: plottedKeys.indexOf(activeYChannel) >= 0 ? `${chartColors[plottedKeys.indexOf(activeYChannel) % chartColors.length]}15` : 'transparent' }}
                    >
                        <span className="text-[9px] uppercase font-bold mb-1 tracking-wider" style={{ color: plottedKeys.indexOf(activeYChannel) >= 0 ? chartColors[plottedKeys.indexOf(activeYChannel) % chartColors.length] : 'var(--muted-foreground)' }}>Channel</span>
                        <Select value={activeYChannel} onValueChange={(v) => setActiveYChannel(v || "")}>
                          <SelectTrigger 
                            className="w-28 h-6 text-xs bg-background border shadow-sm focus:ring-0 font-bold"
                            style={{ 
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
code = code.replace(old_tree_text_block, new_tree_text_block)
code = code.replace(old_toolbar_block, new_toolbar_block)

with open('/home/kpochwala/git/kabot-io/hmi-antigravity/frontend/src/app/page.tsx', 'w') as f:
    f.write(code)

print("Rewrote page.tsx with updated tree color logic and toolbar background tinting.")
