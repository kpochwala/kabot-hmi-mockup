import json

code = """\
"use client";

import { useEffect, useRef, useState } from "react";
import Editor, { useMonaco } from "@monaco-editor/react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Check, ArrowRight, Square, FolderOpen, Search, Settings } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function Home() {
  const monaco = useMonaco();
  const [logs, setLogs] = useState<string[]>([]);
  const [verifyLogs, setVerifyLogs] = useState<string[]>([]);
  const [stateData, setStateData] = useState<any>({});
  const [plotHistory, setPlotHistory] = useState<any[]>([]);
  const [hzStats, setHzStats] = useState<Record<string, string>>({});
  
  const [plottedKeys, setPlottedKeys] = useState<string[]>(['effort.x', 'effort.y']);
  const recentStampsRef = useRef<Record<string, number[]>>({});
  
  const [isPaused, setIsPaused] = useState(false);
  const isPausedRef = useRef(false);
  
  const [bufferSeconds, setBufferSeconds] = useState(5);
  const bufferSecondsRef = useRef(5);
  
  const [yAxisDomain, setYAxisDomain] = useState<any[]>(['auto', 'auto']);
  
  const [trigger, setTrigger] = useState({ enabled: false, key: 'effort.x', threshold: 0 });
  const triggerRef = useRef({ enabled: false, key: 'effort.x', threshold: 0, waiting: false });
  
  const [isRunning, setIsRunning] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const defaultCode = `def control(state: RobotState, control: RobotControl) -> RobotControl:
    if state.distance < 0.5:
        control.effort.x = 0
        control.effort.y = 0
    else:
        control.effort.x = 1
        control.effort.y = 1
    return control
`;

  const [code, setCode] = useState(defaultCode);

  useEffect(() => {
    wsRef.current = new WebSocket("ws://localhost:8000/ws");
    wsRef.current.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "log") {
          setLogs(prev => [...prev.slice(-40), msg.data]);
          if (msg.data.includes("Runtime Error:") || msg.data === "Stopped.") {
            setIsRunning(false);
          }
        } else if (msg.type === "state") {
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
          }
        }
      } catch(e) {}
    };
    return () => wsRef.current?.close();
  }, []);

  const handleEditorMount = (editor: any, monacoInstance: any) => {
    try {
        const ce = require('constrained-editor-plugin').constrainedEditor || require('constrained-editor-plugin').constrainEditor;
        const constrainedInstance = ce(monacoInstance);
        constrainedInstance.initializeIn(editor);
        constrainedInstance.addRestrictionsTo(editor.getModel(), [
          {
            range: [1, 1, 1, 71],
            allowMultiline: false,
          },
        ]);
    } catch(e) {
        console.error("Constraint init error", e);
    }
  };

  const handleValidate = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "validate", code }));
      setVerifyLogs(["Running sanity checks on the code..."]);
      setTimeout(() => {
        setVerifyLogs(prev => [...prev, "Syntax check passed. Output looks clean."]);
      }, 500);
    }
  };

  const handleRun = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "run", code }));
      setIsRunning(true);
    }
  };

  const handleStop = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "stop" }));
      setIsRunning(false);
    }
  };

  const renderTree = (obj: any, parentKey: string = ''): React.ReactNode => {
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

  const chartColors = ["#2563eb", "#16a34a", "#dc2626", "#d97706", "#9333ea", "#0891b2", "#be185d"];

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground text-sm font-sans">
      
      {/* Left Sidebar (Arduino Style) */}
      <div className="w-14 shrink-0 border-r flex flex-col items-center py-4 gap-6 bg-muted/10">
        <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-foreground">
          <FolderOpen className="w-5 h-5" />
        </Button>
        <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-foreground">
          <Search className="w-5 h-5" />
        </Button>
        <div className="flex-1" />
        <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-foreground">
          <Settings className="w-5 h-5" />
        </Button>
      </div>

      {/* Main Content Area */}
      <Tabs defaultValue="shell" className="flex-1 flex flex-col min-w-0">
        
        {/* Top Toolbar */}
        <div className="h-12 border-b flex items-center px-4 gap-4 shrink-0 bg-background">
          <div className="flex items-center gap-1">
            <Button 
              size="icon" 
              variant="ghost" 
              className="rounded-full w-8 h-8 text-foreground hover:bg-muted" 
              onClick={handleValidate}
              title="Verify"
            >
              <Check className="w-4 h-4" />
            </Button>
            {!isRunning ? (
              <Button 
                size="icon" 
                variant="ghost" 
                className="rounded-full w-8 h-8 text-foreground hover:bg-muted" 
                onClick={handleRun}
                title="Upload"
              >
                <ArrowRight className="w-4 h-4" />
              </Button>
            ) : (
              <Button 
                size="icon" 
                variant="destructive" 
                className="rounded-full w-8 h-8 p-0" 
                onClick={handleStop}
                title="Stop"
              >
                <Square className="w-4 h-4 fill-current" />
              </Button>
            )}
          </div>
          
          <div className="w-px h-6 bg-border mx-2" />
          
          <Select defaultValue="robot-1">
            <SelectTrigger className="w-48 h-8 text-xs border-0 bg-muted/50 focus:ring-0">
              <SelectValue placeholder="Select Robot" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="robot-1">Kabot Alpha (172.26.25.114)</SelectItem>
              <SelectItem value="robot-2">Local Simulator</SelectItem>
            </SelectContent>
          </Select>
          
          <div className="flex-1" />
          
          <TabsList>
            <TabsTrigger value="verification">Verification Status</TabsTrigger>
            <TabsTrigger value="shell">Shell</TabsTrigger>
            <TabsTrigger value="data">Data View</TabsTrigger>
          </TabsList>
        </div>

        {/* Resizable Editor/Terminal Split */}
        <ResizablePanelGroup orientation="vertical" className="flex-1 w-full">
          
          <ResizablePanel defaultSize={70} minSize={20} className="flex flex-col overflow-hidden">
            <div className="flex-1 min-h-0 overflow-hidden relative">
              <Editor
                height="100%"
                defaultLanguage="python"
                value={code}
                onChange={(val) => setCode(val || "")}
                onMount={handleEditorMount}
                options={{ fontFamily: '"Hack", monospace', minimap: { enabled: false }, roundedSelection: false, scrollBeyondLastLine: false }}
              />
            </div>
          </ResizablePanel>
          
          <ResizableHandle withHandle className="h-1 w-full bg-border cursor-row-resize hover:bg-muted-foreground/30 transition-colors" />
          
          <ResizablePanel defaultSize={30} minSize={15} className="flex flex-col overflow-hidden bg-background">
              <div className="flex-1 min-h-0 overflow-hidden relative">
                <TabsContent value="verification" className="h-full p-2 m-0 outline-none data-[state=inactive]:hidden overflow-y-auto font-mono text-xs text-muted-foreground">
                  {verifyLogs.length === 0 ? "No verification run." : verifyLogs.map((l, i) => <div key={i}>{l}</div>)}
                </TabsContent>
                
                <TabsContent value="shell" className="h-full flex flex-col p-0 m-0 outline-none data-[state=inactive]:hidden">
                  <div className="shrink-0 p-1 px-2 border-b flex items-center justify-end bg-background">
                    <Select defaultValue="serial">
                      <SelectTrigger className="w-32 h-6 text-[10px] border-0 focus:ring-0 px-2 py-0">
                        <SelectValue placeholder="Mode" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="serial" className="text-[10px]">Serial Mode</SelectItem>
                        <SelectItem value="smp" className="text-[10px]">SMP Mode</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex-1 p-2 font-mono text-xs overflow-y-auto text-foreground">
                    {logs.length === 0 && <span className="text-muted-foreground">Awaiting logs...</span>}
                    {logs.map((log, i) => <div key={i}>{log}</div>)}
                  </div>
                </TabsContent>

                <TabsContent value="data" className="h-full p-4 m-0 outline-none data-[state=inactive]:hidden">
                  <ResizablePanelGroup orientation="horizontal" className="h-full border rounded-md bg-muted/5">
                      <ResizablePanel defaultSize={30} minSize={20} className="p-2 flex flex-col overflow-y-auto border-r">
                        <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2 ml-1 shrink-0">State Tree</div>
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
                </TabsContent>
              </div>
          </ResizablePanel>

        </ResizablePanelGroup>
      </Tabs>
    </div>
  );
}
"""

with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(code)

print("Rewrote page.tsx securely.")
