import re

with open('frontend/src/app/page.tsx', 'r') as f:
    code = f.read()

# Add Checkbox import
code = code.replace(
    'import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";',
    'import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";\nimport { Checkbox } from "@/components/ui/checkbox";'
)

# State replacements
state_old = """  const [logs, setLogs] = useState<string[]>([]);
  const [verifyLogs, setVerifyLogs] = useState<string[]>([]);
  const [distance, setDistance] = useState(0);
  const [effort, setEffort] = useState({ x: 0, y: 0 });
  const [effortHistory, setEffortHistory] = useState<{time: string, x: number, y: number}[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);"""

state_new = """  const [logs, setLogs] = useState<string[]>([]);
  const [verifyLogs, setVerifyLogs] = useState<string[]>([]);
  const [stateData, setStateData] = useState<any>({});
  const [plotHistory, setPlotHistory] = useState<any[]>([]);
  const [hzStats, setHzStats] = useState<Record<string, string>>({});
  const [plottedKeys, setPlottedKeys] = useState<string[]>(['effort.x', 'effort.y']);
  const recentStampsRef = useRef<Record<string, number[]>>({});
  const [isRunning, setIsRunning] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);"""

code = code.replace(state_old, state_new)

ws_old = """        } else if (msg.type === "state") {
          setDistance(msg.data.distance);
          setEffort(msg.data.effort);
          
          const now = new Date().toLocaleTimeString('en-US', { hour12: false, hour: "numeric", minute: "numeric", second: "numeric" });
          setEffortHistory(prev => {
             const newHistory = [...prev, { time: now, x: msg.data.effort.x, y: msg.data.effort.y }];
             return newHistory.slice(-20);
          });
        }"""

ws_new = """        } else if (msg.type === "state") {
          const d = msg.data;
          const s = msg.stamps || {};
          
          setStateData(d);
          
          // Calculate Hz
          const newHz: any = {};
          for (const key of Object.keys(s)) {
              if (!recentStampsRef.current[key]) recentStampsRef.current[key] = [];
              const history = recentStampsRef.current[key];
              const stamp = s[key];
              
              if (history.length === 0 || stamp > history[history.length - 1]) {
                  history.push(stamp);
                  if (history.length > 5) history.shift();
              }
              
              if (history.length >= 2) {
                  const deltaNs = history[history.length - 1] - history[0];
                  if (deltaNs > 0) {
                      newHz[key] = ((history.length - 1) * 1e9 / deltaNs).toFixed(1);
                  } else {
                      newHz[key] = "0.0";
                  }
              } else {
                  newHz[key] = "0.0";
              }
          }
          setHzStats(newHz);
          
          const now = new Date().toLocaleTimeString('en-US', { hour12: false, hour: "numeric", minute: "numeric", second: "numeric" });
          
          setPlotHistory(prev => {
             const entry: any = { time: now };
             if (d.distance !== undefined) entry['distance'] = d.distance;
             if (d.effort) { entry['effort.x'] = d.effort.x; entry['effort.y'] = d.effort.y; }
             if (d.accel) { entry['accel.x'] = d.accel.x; entry['accel.y'] = d.accel.y; entry['accel.z'] = d.accel.z; }
             if (d.gyro) { entry['gyro.x'] = d.gyro.x; entry['gyro.y'] = d.gyro.y; entry['gyro.z'] = d.gyro.z; }
             if (d.mag) { entry['mag.x'] = d.mag.x; entry['mag.y'] = d.mag.y; entry['mag.z'] = d.mag.z; }
             
             const newHistory = [...prev, entry];
             return newHistory.slice(-50);
          });
        }"""

code = code.replace(ws_old, ws_new)

# Add renderTree function before return
render_tree = """  const renderTree = (obj: any, parentKey: string = '') => {
    if (!obj) return null;
    if (typeof obj === 'number') {
       const fullKey = parentKey;
       const baseKey = parentKey.split('.')[0]; // for Hz lookup
       const hz = hzStats[baseKey] || hzStats['state'] || '0.0';
       return (
          <div className="flex items-center justify-between py-1 border-b last:border-0 hover:bg-muted/10">
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
               <span className="font-mono text-[10px] text-muted-foreground/70">{hz} Hz</span>
               <span className="font-mono text-sm w-16 text-right font-medium">{obj.toFixed(3)}</span>
             </div>
          </div>
       );
    }
    return Object.keys(obj).map(k => {
       const fullKey = parentKey ? `${parentKey}.${k}` : k;
       if (typeof obj[k] === 'number') {
          return <div key={fullKey} className={parentKey ? "ml-4" : ""}>{renderTree(obj[k], fullKey)}</div>;
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

  const chartColors = ["#2563eb", "#16a34a", "#dc2626", "#d97706", "#9333ea", "#0891b2", "#be185d"];

  return ("""

code = code.replace('  return (', render_tree)

# Replace the Data View tab content
tab_old = """                <TabsContent value="data" className="h-full flex p-4 m-0 outline-none data-[state=inactive]:hidden gap-4">
                  <div className="flex flex-col gap-4 w-48 shrink-0">
                    <div className="border p-3 rounded-md bg-muted/5">
                      <div className="text-xs text-muted-foreground mb-1 uppercase tracking-wider">Distance</div>
                      <div className="text-xl font-medium">{distance.toFixed(3)}</div>
                    </div>
                    <div className="flex gap-2">
                      <div className="border p-3 rounded-md bg-muted/5 flex-1">
                        <div className="text-[10px] text-muted-foreground mb-1 uppercase tracking-wider">Effort X</div>
                        <div className="text-lg">{effort.x.toFixed(3)}</div>
                      </div>
                      <div className="border p-3 rounded-md bg-muted/5 flex-1">
                        <div className="text-[10px] text-muted-foreground mb-1 uppercase tracking-wider">Effort Y</div>
                        <div className="text-lg">{effort.y.toFixed(3)}</div>
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex-1 min-w-0 border rounded-md bg-muted/5 p-2 flex flex-col">
                    <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2 ml-2">Effort Vectors</div>
                    <div className="flex-1 min-h-0">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={effortHistory}>
                          <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                          <XAxis dataKey="time" hide />
                          <YAxis domain={[-1, 1]} tick={{fontSize: 10}} width={30} />
                          <Tooltip contentStyle={{ fontSize: '12px' }} />
                          <Line type="stepAfter" dataKey="x" stroke="#2563eb" strokeWidth={2} dot={false} isAnimationActive={false} />
                          <Line type="stepAfter" dataKey="y" stroke="#16a34a" strokeWidth={2} dot={false} isAnimationActive={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </TabsContent>"""

tab_new = """                <TabsContent value="data" className="h-full flex p-4 m-0 outline-none data-[state=inactive]:hidden gap-4">
                  <div className="flex flex-col w-72 shrink-0 border rounded-md bg-muted/5 p-2 overflow-y-auto">
                    <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2 ml-1">State Tree</div>
                    <div className="flex-1 min-h-0">
                      {renderTree(stateData)}
                    </div>
                  </div>
                  
                  <div className="flex-1 min-w-0 border rounded-md bg-muted/5 p-2 flex flex-col">
                    <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2 ml-2 flex items-center justify-between">
                       <span>Real-time Plot</span>
                       <span className="text-muted-foreground/50 lowercase">({plottedKeys.length} signals)</span>
                    </div>
                    <div className="flex-1 min-h-0">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={plotHistory}>
                          <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                          <XAxis dataKey="time" hide />
                          <YAxis domain={['auto', 'auto']} tick={{fontSize: 10}} width={30} />
                          <Tooltip contentStyle={{ fontSize: '12px' }} />
                          {plottedKeys.map((key, i) => (
                             <Line 
                               key={key} 
                               type="linear" 
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
                  </div>
                </TabsContent>"""

code = code.replace(tab_old, tab_new)

with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(code)

print("Rewrote page.tsx successfully.")
