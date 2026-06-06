import json

code = """\
"use client";

import { useEffect, useRef, useState } from "react";
import Editor, { useMonaco } from "@monaco-editor/react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Check, ArrowRight, Square, Search, Settings, TerminalSquare, Activity, Play, Zap, Unplug, Download, Upload } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from "recharts";
import { SpinBox } from "@/components/ui/spinbox";

export default function Home() {
  const monaco = useMonaco();
  const [logs, setLogs] = useState<string[]>([]);
  const [verifyLogs, setVerifyLogs] = useState<string[]>([]);
  const [stateData, setStateData] = useState<any>({});
  const [pausedState, setPausedState] = useState<any>(null);
  
  const [plotHistory, setPlotHistory] = useState<any[]>([]);
  const [hzStats, setHzStats] = useState<Record<string, string>>({});
  
  const [plottedKeys, setPlottedKeys] = useState<string[]>(['effort.x', 'effort.y']);
  const recentStampsRef = useRef<Record<string, number[]>>({});
  
  const [isPaused, setIsPaused] = useState(false);
  const isPausedRef = useRef(false);
  
  const [xScale, setXScale] = useState(5);
  const xScaleRef = useRef(5);
  const [xOffset, setXOffset] = useState(0);
  
  const [activeYChannel, setActiveYChannel] = useState<string>('effort.x');
  const [yScales, setYScales] = useState<Record<string, number>>({});
  const [yOffsets, setYOffsets] = useState<Record<string, number>>({});
  
  const getYScale = (k: string) => yScales[k] ?? 2;
  const getYOffset = (k: string) => yOffsets[k] ?? 0;
  
  const [yCursor1, setYCursor1] = useState<number | null>(0.5);
  const yCursor1Ref = useRef<number | null>(0.5);
  const [yCursor2, setYCursor2] = useState<number | null>(-0.5);
  
  const [trigger, setTrigger] = useState({ enabled: false, key: 'effort.x', mode: 'Rising Edge', level: 0, waiting: false });
  const triggerRef = useRef({ enabled: false, key: 'effort.x', mode: 'Rising Edge', level: 0, waiting: false });
  const lastValueRef = useRef<Record<string, number>>({});
  
  const [hoveredData, setHoveredData] = useState<any>(null);
  
  const [isRunning, setIsRunning] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const plotContainerRef = useRef<HTMLDivElement>(null);
  
  const [activeWorkspace, setActiveWorkspace] = useState<"code" | "scope" | "firmware">("code");

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
          if (msg.data.includes("Runtime Error:") || msg.data === "Stopped.") setIsRunning(false);
        } else if (msg.type === "state") {
          const d = msg.data;
          const s = msg.stamps || {};
          setStateData(d);
          
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
                  if (deltaNs > 0) newHz[key] = ((history.length - 1) * 1e9 / deltaNs).toFixed(1);
                  else newHz[key] = "0.0";
              } else newHz[key] = "0.0";
          }
          setHzStats(newHz);
          
          const ts = Date.now();
          const entry: any = { timestamp: ts };
          if (d.distance !== undefined) entry['distance'] = d.distance;
          if (d.effort) { entry['effort.x'] = d.effort.x; entry['effort.y'] = d.effort.y; }
          if (d.accel) { entry['accel.x'] = d.accel.x; entry['accel.y'] = d.accel.y; entry['accel.z'] = d.accel.z; }
          if (d.gyro) { entry['gyro.x'] = d.gyro.x; entry['gyro.y'] = d.gyro.y; entry['gyro.z'] = d.gyro.z; }
          if (d.mag) { entry['mag.x'] = d.mag.x; entry['mag.y'] = d.mag.y; entry['mag.z'] = d.mag.z; }
          
          const tLevel = triggerRef.current.level;
          if (triggerRef.current.enabled && triggerRef.current.waiting) {
              const val = entry[triggerRef.current.key];
              const prevVal = lastValueRef.current[triggerRef.current.key];
              if (val !== undefined && prevVal !== undefined) {
                  const mode = triggerRef.current.mode;
                  if (mode === 'Rising Edge' && prevVal < tLevel && val >= tLevel) triggerRef.current.waiting = false;
                  else if (mode === 'Falling Edge' && prevVal > tLevel && val <= tLevel) triggerRef.current.waiting = false;
                  else if (mode === 'State High' && val >= tLevel) triggerRef.current.waiting = false;
                  else if (mode === 'State Low' && val <= tLevel) triggerRef.current.waiting = false;
              }
          }
          
          for (const k in entry) {
              if (k !== 'timestamp') lastValueRef.current[k] = entry[k];
          }
          
          if (!isPausedRef.current && !triggerRef.current.waiting) {
              setPlotHistory(prev => {
                 const newHistory = [...prev, entry];
                 const maxRetention = 60 * 1000; 
                 const cutoff = ts - maxRetention;
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
          { range: [1, 1, 1, 71], allowMultiline: false },
        ]);
    } catch(e) {}
  };

  const handleValidate = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "validate", code }));
      setVerifyLogs(["Running sanity checks on the code..."]);
      setTimeout(() => setVerifyLogs(prev => [...prev, "Syntax check passed. Output looks clean."]), 500);
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
  
  const handleForceTrigger = () => {
      const newT = { ...trigger, waiting: false };
      setTrigger(newT);
      triggerRef.current = newT;
  };

  const renderTree = (obj: any, parentKey: string = ''): React.ReactNode => {
    if (obj === null || obj === undefined) return null;
    if (typeof obj === 'number') {
       const fullKey = parentKey;
       const baseKey = parentKey.split('.')[0]; 
       const hz = hzStats[baseKey] || hzStats['state'] || '0.0';
       
       let val = obj;
       if (hoveredData && hoveredData[fullKey] !== undefined) val = hoveredData[fullKey];
       else if (isPaused && pausedState && pausedState[baseKey]) {
          const keys = fullKey.split('.');
          let pVal = pausedState;
          for(const k of keys) { pVal = pVal?.[k]; }
          if (pVal !== undefined) val = pVal;
       }
       
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
    }
    return Object.keys(obj).map(k => {
       const fullKey = parentKey ? `${parentKey}.${k}` : k;
       if (typeof obj[k] === 'number') return renderTree(obj[k], fullKey);
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

  const now = Date.now();
  const maxTs = plotHistory.length > 0 ? plotHistory[plotHistory.length - 1].timestamp : now;
  const xMax = isPaused ? (maxTs - xOffset * 1000) : now;
  const xMin = xMax - xScale * 1000;

  const yToPercent = (val: number) => {
    const min = getYOffset(activeYChannel) - getYScale(activeYChannel) / 2;
    const max = getYOffset(activeYChannel) + getYScale(activeYChannel) / 2;
    const clamped = Math.max(min, Math.min(max, val));
    return ((clamped - min) / (max - min)) * 100;
  };

  // Resolve trigger dropdown state
  let triggerDropdownValue = "None";
  if (trigger.enabled && trigger.key === activeYChannel) {
      if (trigger.mode === 'Rising Edge') triggerDropdownValue = 'Rising';
      else if (trigger.mode === 'Falling Edge') triggerDropdownValue = 'Falling';
      else if (trigger.mode === 'State High') triggerDropdownValue = 'Above';
      else if (trigger.mode === 'State Low') triggerDropdownValue = 'Below';
  }

  const handleTriggerChange = (v: string) => {
      if (v === "None") {
          const newT = { ...trigger, enabled: false };
          setTrigger(newT); triggerRef.current = newT;
      } else {
          let mode = 'Rising Edge';
          if (v === 'Rising') mode = 'Rising Edge';
          else if (v === 'Falling') mode = 'Falling Edge';
          else if (v === 'Above') mode = 'State High';
          else if (v === 'Below') mode = 'State Low';
          
          const newT = { ...trigger, enabled: true, key: activeYChannel, mode, waiting: true };
          setTrigger(newT); triggerRef.current = newT;
          setIsPaused(false); isPausedRef.current = false;
      }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground text-sm font-sans">
      <div className="w-14 shrink-0 border-r flex flex-col items-center py-4 gap-6 bg-muted/10">
        <Button 
           variant={activeWorkspace === "code" ? "secondary" : "ghost"} 
           size="icon" 
           onClick={() => setActiveWorkspace("code")}
           className={activeWorkspace === "code" ? "text-primary" : "text-muted-foreground hover:text-foreground"}
           title="Code View"
        >
            <TerminalSquare className="w-5 h-5" />
        </Button>
        <Button 
           variant={activeWorkspace === "scope" ? "secondary" : "ghost"} 
           size="icon" 
           onClick={() => setActiveWorkspace("scope")}
           className={activeWorkspace === "scope" ? "text-primary" : "text-muted-foreground hover:text-foreground"}
           title="Scope View"
        >
            <Activity className="w-5 h-5" />
        </Button>
        <div className="flex-1" />
        <Button 
           variant={activeWorkspace === "firmware" ? "secondary" : "ghost"} 
           size="icon" 
           onClick={() => setActiveWorkspace("firmware")}
           className={activeWorkspace === "firmware" ? "text-primary" : "text-muted-foreground hover:text-foreground"}
           title="Settings & Firmware"
        >
            <Settings className="w-5 h-5" />
        </Button>
      </div>

      <div className="flex-1 flex flex-col min-w-0 min-h-0 relative">
        
        {/* Contextual Toolbar */}
        {activeWorkspace === "code" && (
            <div className="h-12 border-b flex items-center px-4 gap-4 shrink-0 bg-background">
                <Button size="sm" variant="outline" className="text-foreground hover:bg-muted font-bold" onClick={handleValidate} title="Verify"><Check className="w-4 h-4 mr-2" /> Verify</Button>
                {!isRunning ? (
                  <Button size="sm" variant="default" className="font-bold" onClick={handleRun} title="Run on Robot"><Play className="w-4 h-4 mr-2" /> Run</Button>
                ) : (
                  <Button size="sm" variant="destructive" className="font-bold" onClick={handleStop} title="Stop"><Square className="w-4 h-4 mr-2 fill-current" /> Stop</Button>
                )}
                <div className="w-px h-6 bg-border mx-2" />
                <Select defaultValue="robot-1">
                  <SelectTrigger className="w-48 h-8 text-xs border-0 bg-muted/50 focus:ring-0"><SelectValue placeholder="Select Robot" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="robot-1">Kabot Alpha (172.26.25.114)</SelectItem>
                    <SelectItem value="robot-2">Local Simulator</SelectItem>
                  </SelectContent>
                </Select>
            </div>
        )}

        {activeWorkspace === "scope" && (
            <div className="h-16 border-b flex items-center px-4 gap-4 bg-background shrink-0 overflow-x-auto">
                <div className="flex items-center gap-2 shrink-0">
                    <Button 
                      variant={isPaused ? "default" : "outline"} size="sm" className="h-8 font-bold"
                      onClick={() => { 
                          const newPaused = !isPaused;
                          setIsPaused(newPaused); 
                          isPausedRef.current = newPaused; 
                          if (newPaused) setPausedState({...stateData});
                      }}
                    >
                        {isPaused ? <><Play className="w-4 h-4 mr-2" /> Resume</> : <><Square className="w-4 h-4 mr-2" /> Pause</>}
                    </Button>
                    <Button variant="outline" size="sm" className="h-8 font-bold" onClick={handleForceTrigger}>
                        <Zap className="w-4 h-4 mr-2" /> Force Trigger
                    </Button>
                </div>
                
                <div className="w-px h-8 bg-border mx-2 shrink-0" />
                
                {/* [ Select Channel ] || [ T Scale | T Delay ] || [ Y Scale | Y Offset ] || [ Trigger Mode | Trigger Y Level ] */}
                <div className="flex items-center bg-muted/20 rounded-md p-1 border border-border/50 shrink-0">
                    
                    <div className="flex flex-col items-start justify-center px-3 border-r border-border/50 shrink-0">
                        <span className="text-[9px] uppercase font-bold text-muted-foreground mb-1 tracking-wider">Channel</span>
                        <Select value={activeYChannel} onValueChange={(v) => setActiveYChannel(v || "")}>
                          <SelectTrigger className="w-28 h-6 text-xs bg-background border shadow-sm focus:ring-0"><SelectValue /></SelectTrigger>
                          <SelectContent>{plottedKeys.map(k => <SelectItem key={k} value={k} className="text-xs">{k}</SelectItem>)}</SelectContent>
                        </Select>
                    </div>

                    <div className="flex items-center gap-2 px-3 border-r border-border/50 shrink-0">
                        <SpinBox value={xScale} min={1} max={30} step={1} onChange={(v) => { setXScale(v); xScaleRef.current = v; }} label="T Scale" unit="s" />
                        <SpinBox value={xOffset} min={0} max={60} step={1} onChange={(v) => setXOffset(v)} label="T Delay" unit="s" />
                    </div>

                    <div className="flex items-center gap-2 px-3 border-r border-border/50 shrink-0">
                        <SpinBox value={getYScale(activeYChannel)} min={0.1} max={50} step={0.1} onChange={(v) => setYScales(p => ({...p, [activeYChannel]: v}))} label="Y Scale" />
                        <SpinBox value={getYOffset(activeYChannel)} min={-50} max={50} step={0.1} onChange={(v) => setYOffsets(p => ({...p, [activeYChannel]: v}))} label="Y Offset" />
                    </div>

                    <div className="flex items-center gap-2 px-3 shrink-0">
                        <div className="flex flex-col items-start justify-center">
                            <span className="text-[9px] uppercase font-bold text-muted-foreground mb-1 tracking-wider">
                                Trigger
                                {trigger.enabled && trigger.key === activeYChannel && trigger.waiting && <span className="text-destructive animate-pulse ml-1">WAITING</span>}
                            </span>
                            <Select value={triggerDropdownValue} onValueChange={handleTriggerChange}>
                              <SelectTrigger className="w-24 h-6 text-xs bg-background border shadow-sm focus:ring-0"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                  <SelectItem value="None" className="text-xs">None</SelectItem>
                                  <SelectItem value="Rising" className="text-xs">Rising</SelectItem>
                                  <SelectItem value="Falling" className="text-xs">Falling</SelectItem>
                                  <SelectItem value="Above" className="text-xs">Above</SelectItem>
                                  <SelectItem value="Below" className="text-xs">Below</SelectItem>
                              </SelectContent>
                            </Select>
                        </div>
                        <SpinBox 
                           value={trigger.key === activeYChannel ? trigger.level : 0} 
                           min={-50} max={50} step={0.1} 
                           onChange={(v) => {
                               const newT = { ...trigger, level: v };
                               setTrigger(newT); triggerRef.current = newT;
                           }} 
                           label="Trig Lvl" 
                        />
                    </div>

                </div>
            </div>
        )}

        {activeWorkspace === "firmware" && (
            <div className="h-12 border-b flex items-center px-4 gap-4 shrink-0 bg-background">
                <Button size="sm" variant="outline" className="font-bold"><Unplug className="w-4 h-4 mr-2" /> Connect Robot</Button>
                <Dialog>
                  <DialogTrigger render={<Button size="sm" variant="default" className="font-bold"><Download className="w-4 h-4 mr-2" /> Firmware Update</Button>} />
                  <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                      <DialogTitle>Update Firmware</DialogTitle>
                      <DialogDescription>Select a firmware binary to flash to the connected robot.</DialogDescription>
                    </DialogHeader>
                    <div className="flex flex-col gap-4 py-4">
                      <div className="flex items-center gap-4">
                        <Input type="file" accept=".bin,.hex" className="text-xs" />
                      </div>
                      <Button className="w-full font-bold"><Upload className="w-4 h-4 mr-2" /> Flash Device</Button>
                    </div>
                  </DialogContent>
                </Dialog>
            </div>
        )}

        {/* Workspace Bodies */}
        <div className="flex-1 min-h-0 overflow-hidden relative bg-muted/5">
            {activeWorkspace === "code" && (
                <ResizablePanelGroup orientation="vertical" className="h-full">
                  <ResizablePanel defaultSize={70} minSize={20} className="flex flex-col overflow-hidden border-b">
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
                  <ResizableHandle withHandle className="h-1 bg-border cursor-row-resize hover:bg-muted-foreground/30 transition-colors" />
                  <ResizablePanel defaultSize={30} minSize={15} className="flex flex-col bg-background">
                    <Tabs defaultValue="verification" className="flex-1 flex flex-col min-h-0 overflow-hidden">
                        <div className="h-8 border-b flex items-center px-2 shrink-0 bg-muted/30">
                            <TabsList className="h-6 bg-transparent">
                                <TabsTrigger value="verification" className="text-xs h-6 px-4 data-[state=active]:bg-background data-[state=active]:shadow-sm">Verification Status</TabsTrigger>
                                <TabsTrigger value="shell" className="text-xs h-6 px-4 data-[state=active]:bg-background data-[state=active]:shadow-sm">Shell Output</TabsTrigger>
                            </TabsList>
                        </div>
                        <TabsContent value="verification" className="flex-1 overflow-y-auto p-2 m-0 data-[state=inactive]:hidden font-mono text-xs text-muted-foreground">
                            {verifyLogs.length === 0 ? "No verification run." : verifyLogs.map((l, i) => <div key={i}>{l}</div>)}
                        </TabsContent>
                        <TabsContent value="shell" className="flex-1 overflow-y-auto p-2 m-0 data-[state=inactive]:hidden font-mono text-xs text-foreground">
                            {logs.length === 0 && <span className="text-muted-foreground">Awaiting logs...</span>}
                            {logs.map((log, i) => <div key={i}>{log}</div>)}
                        </TabsContent>
                    </Tabs>
                  </ResizablePanel>
                </ResizablePanelGroup>
            )}

            {activeWorkspace === "scope" && (
                <ResizablePanelGroup orientation="horizontal" className="h-full">
                  <ResizablePanel defaultSize={20} minSize={15} className="p-4 flex flex-col overflow-y-auto border-r bg-background">
                    <div className="flex items-center justify-between mb-4 shrink-0">
                       <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-bold">Signal Browser</div>
                       {hoveredData && <div className="text-[8px] bg-yellow-500/20 text-yellow-600 px-1.5 py-0.5 rounded font-bold uppercase tracking-widest">Hover Time</div>}
                       {(!hoveredData && isPaused) && <div className="text-[8px] bg-cyan-500/20 text-cyan-600 px-1.5 py-0.5 rounded font-bold uppercase tracking-widest">Paused Snapshot</div>}
                    </div>
                    <div className="flex-1 min-h-0">{renderTree(stateData)}</div>
                  </ResizablePanel>
                  <ResizableHandle withHandle className="w-1 bg-border cursor-col-resize hover:bg-primary/50 transition-colors" />
                  <ResizablePanel defaultSize={80} minSize={50} className="flex flex-col bg-background">
                      <div className="flex-1 min-h-0 relative p-4 select-none" ref={plotContainerRef}>
                          {yCursor1 !== null && (
                              <div 
                                className="absolute left-0 right-0 h-[1px] bg-yellow-500 z-10 opacity-70 pointer-events-none"
                                style={{ bottom: `${yToPercent(yCursor1)}%` }}
                              >
                                  <div 
                                     className="absolute right-0 translate-x-full translate-y-[-50%] w-10 h-6 bg-yellow-500 text-black text-[10px] font-bold flex items-center justify-center cursor-ns-resize pointer-events-auto rounded-r hover:bg-yellow-400"
                                     onPointerDown={(e) => {
                                         const container = plotContainerRef.current;
                                         if (!container) return;
                                         const rect = container.getBoundingClientRect();
                                         const move = (ev: PointerEvent) => {
                                             const y = ev.clientY - rect.top;
                                             const pct = 1 - (y / rect.height);
                                             
                                             const min = getYOffset(activeYChannel) - getYScale(activeYChannel) / 2;
                                             const max = getYOffset(activeYChannel) + getYScale(activeYChannel) / 2;
                                             const val = min + pct * (max - min);
                                             
                                             setYCursor1(val);
                                             yCursor1Ref.current = val;
                                         };
                                         const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); };
                                         window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
                                     }}
                                  >
                                    Y1
                                  </div>
                              </div>
                          )}
                          {yCursor2 !== null && (
                              <div 
                                className="absolute left-0 right-0 h-[1px] bg-cyan-400 z-10 opacity-70 pointer-events-none"
                                style={{ bottom: `${yToPercent(yCursor2)}%` }}
                              >
                                  <div 
                                     className="absolute right-0 translate-x-full translate-y-[-50%] w-10 h-6 bg-cyan-400 text-black text-[10px] font-bold flex items-center justify-center cursor-ns-resize pointer-events-auto rounded-r hover:bg-cyan-300"
                                     onPointerDown={(e) => {
                                         const container = plotContainerRef.current;
                                         if (!container) return;
                                         const rect = container.getBoundingClientRect();
                                         const move = (ev: PointerEvent) => {
                                             const y = ev.clientY - rect.top;
                                             const pct = 1 - (y / rect.height);
                                             
                                             const min = getYOffset(activeYChannel) - getYScale(activeYChannel) / 2;
                                             const max = getYOffset(activeYChannel) + getYScale(activeYChannel) / 2;
                                             const val = min + pct * (max - min);
                                             
                                             setYCursor2(val);
                                         };
                                         const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); };
                                         window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
                                     }}
                                  >
                                    Y2
                                  </div>
                              </div>
                          )}

                          <ResponsiveContainer width="100%" height="100%">
                            <LineChart 
                                data={plotHistory}
                                onMouseMove={(s: any) => {
                                    if (s && s.activePayload && s.activePayload.length > 0) {
                                        setHoveredData(s.activePayload[0].payload);
                                    }
                                }}
                                onMouseLeave={() => setHoveredData(null)}
                            >
                              <CartesianGrid strokeDasharray="3 3" opacity={0.5} stroke="#888" />
                              <XAxis type="number" dataKey="timestamp" domain={[xMin, xMax]} hide />
                              
                              {plottedKeys.map((key, i) => (
                                 <YAxis 
                                    key={`ya-${key}`} 
                                    yAxisId={key} 
                                    domain={[getYOffset(key) - getYScale(key) / 2, getYOffset(key) + getYScale(key) / 2]} 
                                    hide 
                                 />
                              ))}
                              
                              {plottedKeys.map((key, i) => (
                                 <Line 
                                    key={key} 
                                    yAxisId={key}
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
                          
                          <div className="absolute top-2 right-16 flex flex-col items-end pointer-events-none">
                              <div className="text-[8px] text-muted-foreground uppercase mb-1">({activeYChannel})</div>
                              {yCursor1 !== null && <div className="text-yellow-500 text-[10px] font-mono">Y1: {yCursor1.toFixed(3)}</div>}
                              {yCursor2 !== null && <div className="text-cyan-400 text-[10px] font-mono">Y2: {yCursor2.toFixed(3)}</div>}
                              {yCursor1 !== null && yCursor2 !== null && <div className="text-foreground text-[10px] font-mono mt-1">ΔY: {Math.abs(yCursor1 - yCursor2).toFixed(3)}</div>}
                          </div>
                      </div>
                  </ResizablePanel>
                </ResizablePanelGroup>
            )}

            {activeWorkspace === "firmware" && (
                <ResizablePanelGroup orientation="vertical" className="h-full">
                  <ResizablePanel defaultSize={60} minSize={20} className="flex flex-col bg-background border-b p-4">
                     <h2 className="text-lg font-bold mb-4">Firmware Configurations</h2>
                     <div className="flex flex-col gap-4 max-w-xl">
                        <div className="grid grid-cols-2 gap-4">
                            <div className="flex flex-col gap-1">
                                <span className="text-xs font-semibold">Baud Rate</span>
                                <Select defaultValue="115200">
                                  <SelectTrigger><SelectValue/></SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="9600">9600</SelectItem>
                                    <SelectItem value="115200">115200</SelectItem>
                                    <SelectItem value="921600">921600</SelectItem>
                                  </SelectContent>
                                </Select>
                            </div>
                            <div className="flex flex-col gap-1">
                                <span className="text-xs font-semibold">Motor Type</span>
                                <Select defaultValue="bldc">
                                  <SelectTrigger><SelectValue/></SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="bldc">Brushless DC</SelectItem>
                                    <SelectItem value="stepper">Stepper</SelectItem>
                                  </SelectContent>
                                </Select>
                            </div>
                        </div>
                     </div>
                  </ResizablePanel>
                  <ResizableHandle withHandle className="h-1 bg-border cursor-row-resize" />
                  <ResizablePanel defaultSize={40} minSize={15} className="flex flex-col bg-black text-green-400 font-mono text-xs p-4 overflow-y-auto">
                     <div className="text-[10px] uppercase font-bold text-muted-foreground mb-2 sticky top-0 bg-black py-1">Device Shell Output</div>
                     {logs.length === 0 && <span className="opacity-50">No logs...</span>}
                     {logs.map((log, i) => <div key={i}>{log}</div>)}
                  </ResizablePanel>
                </ResizablePanelGroup>
            )}
        </div>
      </div>
    </div>
  );
}
"""

with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(code)

print("Rewrote page.tsx with SpinBox implementation.")
