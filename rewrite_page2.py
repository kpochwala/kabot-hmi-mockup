import re

with open('frontend/src/app/page.tsx', 'r') as f:
    code = f.read()

# Add imports
code = code.replace(
    'import { Checkbox } from "@/components/ui/checkbox";',
    'import { Checkbox } from "@/components/ui/checkbox";\nimport { Input } from "@/components/ui/input";\nimport { Switch } from "@/components/ui/switch";'
)

# Replace states
state_old = """  const [plottedKeys, setPlottedKeys] = useState<string[]>(['effort.x', 'effort.y']);
  const recentStampsRef = useRef<Record<string, number[]>>({});"""

state_new = """  const [plottedKeys, setPlottedKeys] = useState<string[]>(['effort.x', 'effort.y']);
  const recentStampsRef = useRef<Record<string, number[]>>({});
  
  const [isPaused, setIsPaused] = useState(false);
  const isPausedRef = useRef(false);
  
  const [bufferSeconds, setBufferSeconds] = useState(5);
  const bufferSecondsRef = useRef(5);
  
  const [yAxisDomain, setYAxisDomain] = useState<any[]>(['auto', 'auto']);
  
  const [trigger, setTrigger] = useState({ enabled: false, key: 'effort.x', threshold: 0 });
  const triggerRef = useRef({ enabled: false, key: 'effort.x', threshold: 0, waiting: false });"""

code = code.replace(state_old, state_new)

# Replace ws logic
ws_old = """          const now = new Date().toLocaleTimeString('en-US', { hour12: false, hour: "numeric", minute: "numeric", second: "numeric" });
          
          setPlotHistory(prev => {
             const entry: any = { time: now, timestamp: Date.now() };
             if (d.distance !== undefined) entry['distance'] = d.distance;
             if (d.effort) { entry['effort.x'] = d.effort.x; entry['effort.y'] = d.effort.y; }
             if (d.accel) { entry['accel.x'] = d.accel.x; entry['accel.y'] = d.accel.y; entry['accel.z'] = d.accel.z; }
             if (d.gyro) { entry['gyro.x'] = d.gyro.x; entry['gyro.y'] = d.gyro.y; entry['gyro.z'] = d.gyro.z; }
             if (d.mag) { entry['mag.x'] = d.mag.x; entry['mag.y'] = d.mag.y; entry['mag.z'] = d.mag.z; }
             
             const newHistory = [...prev, entry];
             return newHistory.slice(-50);
          });"""

# Note: The original page.tsx didn't have entry.timestamp. So I'll just replace from `const now =` to `});`.
ws_search = r"          const now = new Date\(\)\.toLocaleTimeString\('en-US'.*?\);\s*setPlotHistory\(prev => \{.*?\n             return newHistory\.slice\(-50\);\s*\}\);"
ws_new = """          const now = new Date().toLocaleTimeString('en-US', { hour12: false, hour: "numeric", minute: "numeric", second: "numeric" });
          const entry: any = { time: now, timestamp: Date.now() };
          if (d.distance !== undefined) entry['distance'] = d.distance;
          if (d.effort) { entry['effort.x'] = d.effort.x; entry['effort.y'] = d.effort.y; }
          if (d.accel) { entry['accel.x'] = d.accel.x; entry['accel.y'] = d.accel.y; entry['accel.z'] = d.accel.z; }
          if (d.gyro) { entry['gyro.x'] = d.gyro.x; entry['gyro.y'] = d.gyro.y; entry['gyro.z'] = d.gyro.z; }
          if (d.mag) { entry['mag.x'] = d.mag.x; entry['mag.y'] = d.mag.y; entry['mag.z'] = d.mag.z; }
          
          if (triggerRef.current.enabled && triggerRef.current.waiting) {
              const val = entry[triggerRef.current.key];
              if (val !== undefined && val >= triggerRef.current.threshold) {
                  triggerRef.current.waiting = false;
              }
          }
          
          if (!isPausedRef.current && !triggerRef.current.waiting) {
              setPlotHistory(prev => {
                 const newHistory = [...prev, entry];
                 const cutoff = Date.now() - (bufferSecondsRef.current * 1000);
                 return newHistory.filter(e => e.timestamp >= cutoff);
              });
          }"""

code = re.sub(ws_search, ws_new, code, flags=re.DOTALL)

# Replace renderTree
rt_old_search = r"  const renderTree = \(obj: any, parentKey: string = ''\) => \{.*?  \};\n\n  const chartColors"
rt_new = """  const renderTree = (obj: any, parentKey: string = '') => {
    if (obj === null || obj === undefined) return null;
    if (typeof obj === 'number') {
       const fullKey = parentKey;
       const baseKey = parentKey.split('.')[0]; // for Hz lookup
       const hz = hzStats[baseKey] || hzStats['state'] || '0.0';
       return (
          <div key={fullKey} className="flex items-center justify-between py-1 border-b last:border-0 hover:bg-muted/10">
             <div className="flex items-center gap-2">
               <Checkbox 
                 checked={plottedKeys.includes(fullKey)} 
                 onCheckedChange={(c) => {
                   if (c) setPlottedKeys(p => [...p, fullKey]);
                   else setPlottedKeys(p => p.filter(k => k !== fullKey));
                 }}
               />
               <span className="font-mono text-xs text-muted-foreground">{fullKey}</span>
             </div>
             <div className="flex items-center gap-3">
               <span className="font-mono text-[10px] text-muted-foreground/70 w-12 text-right">{hz} Hz</span>
               <span className="font-mono text-sm w-16 text-right font-medium">{obj.toFixed(3)}</span>
             </div>
          </div>
       );
    }
    return Object.keys(obj).map(k => {
       const fullKey = parentKey ? `${parentKey}.${k}` : k;
       if (typeof obj[k] === 'number') {
          return renderTree(obj[k], fullKey);
       }
       return (
          <div key={fullKey} className={parentKey ? "ml-4 mt-2" : "mt-2"}>
             <div className="text-[10px] font-semibold text-foreground uppercase tracking-wider mb-1 bg-muted/30 px-2 py-1 rounded">{k}</div>
             <div className="border-l-2 border-border/50 pl-3 ml-1">
               {renderTree(obj[k], fullKey)}
             </div>
          </div>
       );
    });
  };

  const chartColors"""

code = re.sub(rt_old_search, rt_new, code, flags=re.DOTALL)

# Replace the Data View rendering
tab_search = r"<TabsContent value=\"data\" className=\"h-full flex p-4 m-0 outline-none data-\[state=inactive\]:hidden gap-4\">.*?</TabsContent>"

tab_new = """<TabsContent value="data" className="h-full p-4 m-0 outline-none data-[state=inactive]:hidden">
                  <ResizablePanelGroup orientation="horizontal" className="h-full border rounded-md bg-muted/5">
                      <ResizablePanel defaultSize={30} minSize={20} className="p-2 flex flex-col overflow-y-auto border-r">
                        <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2 ml-1">State Tree</div>
                        <div className="flex-1 min-h-0">
                          {renderTree(stateData)}
                        </div>
                      </ResizablePanel>
                      
                      <ResizableHandle withHandle className="w-1 bg-border cursor-col-resize hover:bg-muted-foreground/30 transition-colors" />
                      
                      <ResizablePanel defaultSize={70} minSize={30} className="flex flex-col">
                        <div className="h-10 border-b flex items-center px-4 gap-4 bg-background/50 shrink-0">
                            {/* Controls */}
                            <Button 
                              variant={isPaused ? "default" : "outline"} 
                              size="sm" 
                              className="h-6 text-xs"
                              onClick={() => {
                                setIsPaused(!isPaused);
                                isPausedRef.current = !isPaused;
                              }}
                            >
                                {isPaused ? "Resume" : "Pause"}
                            </Button>
                            
                            <div className="w-px h-4 bg-border" />
                            
                            <Select value={bufferSeconds.toString()} onValueChange={(v) => {
                                const s = parseInt(v);
                                setBufferSeconds(s);
                                bufferSecondsRef.current = s;
                            }}>
                              <SelectTrigger className="w-24 h-6 text-xs focus:ring-0">
                                <SelectValue placeholder="Buffer" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="1">1 second</SelectItem>
                                <SelectItem value="5">5 seconds</SelectItem>
                                <SelectItem value="10">10 seconds</SelectItem>
                                <SelectItem value="30">30 seconds</SelectItem>
                              </SelectContent>
                            </Select>
                            
                            <Select value={yAxisDomain[0] === 'auto' ? 'auto' : `${yAxisDomain[0]}`} onValueChange={(v) => {
                                if (v === 'auto') setYAxisDomain(['auto', 'auto']);
                                else if (v === '-1') setYAxisDomain([-1, 1]);
                                else if (v === '-10') setYAxisDomain([-10, 10]);
                                else if (v === '0') setYAxisDomain([0, 100]);
                            }}>
                              <SelectTrigger className="w-24 h-6 text-xs focus:ring-0">
                                <SelectValue placeholder="Scale" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="auto">Auto Scale</SelectItem>
                                <SelectItem value="-1">[-1, 1]</SelectItem>
                                <SelectItem value="-10">[-10, 10]</SelectItem>
                                <SelectItem value="0">[0, 100]</SelectItem>
                              </SelectContent>
                            </Select>
                            
                            <div className="w-px h-4 bg-border" />
                            
                            <div className="flex items-center gap-2">
                                <span className="text-[10px] text-muted-foreground uppercase">Trigger</span>
                                <Switch 
                                    checked={trigger.enabled} 
                                    onCheckedChange={(c) => {
                                        const newTrigger = { ...trigger, enabled: c, waiting: c };
                                        setTrigger(newTrigger);
                                        triggerRef.current = newTrigger;
                                        if (c) {
                                            setIsPaused(false);
                                            isPausedRef.current = false;
                                        }
                                    }} 
                                    className="scale-75"
                                />
                                {trigger.enabled && (
                                    <>
                                        <Select value={trigger.key} onValueChange={(v) => {
                                            const newTrigger = { ...trigger, key: v };
                                            setTrigger(newTrigger);
                                            triggerRef.current = newTrigger;
                                        }}>
                                          <SelectTrigger className="w-24 h-6 text-xs focus:ring-0">
                                            <SelectValue />
                                          </SelectTrigger>
                                          <SelectContent>
                                            {plottedKeys.map(k => <SelectItem key={k} value={k}>{k}</SelectItem>)}
                                          </SelectContent>
                                        </Select>
                                        <span className="text-[10px]">&gt;</span>
                                        <Input 
                                            className="w-16 h-6 text-xs" 
                                            type="number" 
                                            value={trigger.threshold} 
                                            onChange={(e) => {
                                                const newTrigger = { ...trigger, threshold: parseFloat(e.target.value) || 0 };
                                                setTrigger(newTrigger);
                                                triggerRef.current = newTrigger;
                                            }} 
                                        />
                                        {triggerRef.current.waiting && <span className="text-[10px] text-yellow-500 animate-pulse">Waiting...</span>}
                                    </>
                                )}
                            </div>
                        </div>
                        
                        <div className="flex-1 min-h-0 p-2">
                          <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={plotHistory}>
                              <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                              <XAxis dataKey="time" hide />
                              <YAxis domain={yAxisDomain} tick={{fontSize: 10}} width={30} />
                              <Tooltip contentStyle={{ fontSize: '12px' }} />
                              {plottedKeys.map((key, i) => (
                                 <Line 
                                   key={key} 
                                   type="monotone" 
                                   dataKey={key} 
                                   stroke={chartColors[i % chartColors.length]} 
                                   strokeWidth={2} 
                                   dot={false} 
                                   isAnimationActive={false} 
                                 />
                              ))}
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                      </ResizablePanel>
                  </ResizablePanelGroup>
                </TabsContent>"""

code = re.sub(tab_search, tab_new, code, flags=re.DOTALL)

with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(code)

print("Rewrote page.tsx successfully.")
