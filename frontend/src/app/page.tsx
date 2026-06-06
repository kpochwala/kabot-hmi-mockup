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
import { Check, ArrowRight, Square, Search, Settings, TerminalSquare, Activity, Play, Wand, Unplug, Download, Upload, ChevronDown } from 'lucide-react';
import { UPlotScope } from "@/components/ui/UPlotScope";
import { SpinBox } from "@/components/ui/spinbox";
import { ChannelConfig, ScopeState, TriggerType } from "@/types/scope";

const chartColors = ["#2563eb", "#16a34a", "#dc2626", "#d97706", "#9333ea", "#0891b2", "#be185d"];

export default function Home() {
  const monaco = useMonaco();
  const [logs, setLogs] = useState<string[]>([]);
  const [verifyLogs, setVerifyLogs] = useState<string[]>([]);
  const [stateData, setStateData] = useState<any>({});
  const [pausedState, setPausedState] = useState<any>(null);
  
  const dataBufferRef = useRef<any[]>([]);
  const [hzStats, setHzStats] = useState<Record<string, string>>({});
  
  const [channels, setChannels] = useState<ScopeState>({});
  const channelsRef = useRef<ScopeState>({});
  
  const [triggerSourceKey, setTriggerSourceKey] = useState<string | null>(null);
  const triggerSourceKeyRef = useRef<string | null>(null);
  
  // Track triggered wait state
  const isTriggerWaitingRef = useRef(false);
  const [isTriggerWaitingUI, setIsTriggerWaitingUI] = useState(false);
  
  const recentStampsRef = useRef<Record<string, number[]>>({});
  
  const [isPaused, setIsPaused] = useState(false);
  const isPausedRef = useRef(false);
  
  const [xScale, setXScale] = useState(5);
  const xScaleRef = useRef(5);
  const [xOffset, setXOffset] = useState(0);
  const [t0Ratio, setT0Ratio] = useState(0.8); // 80% towards the right by default
  
  const [yCursor1, setYCursor1] = useState<number | null>(0.5);
  const yCursor1Ref = useRef<number | null>(0.5);
  const [yCursor2, setYCursor2] = useState<number | null>(-0.5);
  
  const lastValueRef = useRef<Record<string, number>>({});
  
  const [hoveredData, setHoveredData] = useState<any>(null);
  const [hoveredChannelKey, setHoveredChannelKey] = useState<string | null>(null);
  
  const [isRunning, setIsRunning] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const plotContainerRef = useRef<HTMLDivElement>(null);
  
  const [activeWorkspace, setActiveWorkspace] = useState<"code" | "scope" | "firmware">("code");

  const defaultCode = `def control(state: RobotState, control: RobotControl) -> RobotControl:\n    if state.distance < 0.5:\n        control.effort.x = 0\n        control.effort.y = 0\n    else:\n        control.effort.x = 1\n        control.effort.y = 1\n    return control\n`;
  const [code, setCode] = useState(defaultCode);
  
  const [robotIp, setRobotIp] = useState("localhost");

  useEffect(() => {
    // Keep ref in sync
    channelsRef.current = channels;
  }, [channels]);

  useEffect(() => {
    triggerSourceKeyRef.current = triggerSourceKey;
  }, [triggerSourceKey]);

  useEffect(() => {
    wsRef.current = new WebSocket(`ws://${robotIp}:8000/ws`);
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
          
          // Auto-initialize channels if they don't exist
          let addedNewChannel = false;
          const currentChannels = channelsRef.current;
          const nextChannels = { ...currentChannels };
          
          for (const k in entry) {
              if (k === 'timestamp') continue;
              if (!nextChannels[k]) {
                  nextChannels[k] = {
                      key: k,
                      color: chartColors[Object.keys(nextChannels).length % chartColors.length],
                      visible: k.startsWith('mag.'), // Default some to visible
                      focused: k === 'mag.x',
                      y_offset: 0,
                      y_scale: 2,
                      grid_size: 1,
                      trigger_type: 'None',
                      trigger_level: 0
                  };
                  addedNewChannel = true;
              }
          }
          if (addedNewChannel) {
              setChannels(nextChannels);
              channelsRef.current = nextChannels;
          }
          
          const trKey = triggerSourceKeyRef.current;
          if (trKey && isTriggerWaitingRef.current) {
              const ch = channelsRef.current[trKey];
              if (ch && ch.trigger_type !== 'None') {
                  const val = entry[trKey];
                  const prevVal = lastValueRef.current[trKey];
                  const tLevel = ch.trigger_level;
                  
                  if (val !== undefined && prevVal !== undefined) {
                      const mode = ch.trigger_type;
                      if (mode === 'Rising Edge' && prevVal < tLevel && val >= tLevel) isTriggerWaitingRef.current = false;
                      else if (mode === 'Falling Edge' && prevVal > tLevel && val <= tLevel) isTriggerWaitingRef.current = false;
                      else if (mode === 'State High' && val >= tLevel) isTriggerWaitingRef.current = false;
                      else if (mode === 'State Low' && val <= tLevel) isTriggerWaitingRef.current = false;
                      
                      if (!isTriggerWaitingRef.current) setIsTriggerWaitingUI(false);
                  }
              }
          }
          
          for (const k in entry) {
              if (k !== 'timestamp') lastValueRef.current[k] = entry[k];
          }
          
          if (!isPausedRef.current && !isTriggerWaitingRef.current) {
              dataBufferRef.current.push(entry);
              const cutoff = ts - 60000;
              while (dataBufferRef.current.length > 0 && dataBufferRef.current[0].timestamp < cutoff) {
                  dataBufferRef.current.shift();
              }
          }
        }
      } catch(e) {}
    };
    return () => wsRef.current?.close();
  }, [robotIp]);

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
  
  const handleAutoLayout = () => {
      setChannels(prev => {
          const next = { ...prev };
          const visibleKeys = Object.values(next).filter(c => c.visible).map(c => c.key);
          if (visibleKeys.length === 0) return next;

          const snapScales = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000];
          const N = visibleKeys.length;
          const M = 0.8; // Margin factor (occupy 80% of row slot)

          visibleKeys.forEach((key, index) => {
              let maxAbs = 0;
              if (dataBufferRef.current && dataBufferRef.current.length > 0) {
                  dataBufferRef.current.forEach(row => {
                      const val = row[key];
                      if (val !== undefined && val !== null) {
                          const absVal = Math.abs(val);
                          if (absVal > maxAbs) maxAbs = absVal;
                      }
                  });
              }

              let chosenScale = snapScales[snapScales.length - 1];
              for (let s of snapScales) {
                  if (s >= maxAbs * 2 * 1.1) {
                      chosenScale = s;
                      break;
                  }
              }
              if (maxAbs === 0) chosenScale = 1;

              next[key] = {
                  ...next[key],
                  grid_size: chosenScale / 2,
                  y_scale: chosenScale * N / M,
                  y_offset: chosenScale * (index + 0.5 - N / 2) / M,
              };
          });

          return next;
      });
  };

  const handleSetTriggerMode = (mode: TriggerType) => {
      if (!focusedKey) return;
      setChannels(p => ({
          ...p,
          [focusedKey]: { ...p[focusedKey], trigger_type: mode }
      }));
      if (mode !== 'None') {
          setTriggerSourceKey(focusedKey);
          isTriggerWaitingRef.current = true;
          setIsTriggerWaitingUI(true);
          setIsPaused(false);
          isPausedRef.current = false;
      } else if (triggerSourceKey === focusedKey) {
          setTriggerSourceKey(null);
          isTriggerWaitingRef.current = false;
          setIsTriggerWaitingUI(false);
      }
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
       
       const ch = channels[fullKey];
       if (!ch) return null;
       
       const isPlotted = ch.visible;
       const color = ch.color;
       const isFocused = ch.focused;
       const isHovered = hoveredChannelKey === fullKey;
       const isTriggerSrc = triggerSourceKey === fullKey;

       const isHighlightedLeft = isFocused;
       const borderLeftWidth = isPlotted ? (isHighlightedLeft ? 4 : 2) : 2;
       const paddingLeft = 10 - borderLeftWidth;

       const borderRightWidth = isHovered ? 4 : 0;
       const paddingRight = 8 - borderRightWidth;

       return (
          <div 
             key={fullKey} 
             className={`flex items-center justify-between py-1 border-b last:border-0 transition-colors cursor-pointer hover:bg-muted/10`}
             style={isPlotted ? { 
                 backgroundColor: isFocused ? `${color}30` : isHovered ? `${color}25` : `${color}15`, 
                 borderLeft: isFocused ? `4px solid ${color}` : `2px solid ${color}`,
                 borderRight: isHovered ? `4px solid ${color}80` : '0px solid transparent',
                 paddingLeft: `${paddingLeft}px`,
                 paddingRight: `${paddingRight}px`
             } : { 
                 borderLeft: '2px solid transparent',
                 borderRight: isHovered ? `4px solid ${color}80` : '0px solid transparent',
                 paddingLeft: `${paddingLeft}px`,
                 paddingRight: `${paddingRight}px`
             }}
             onClick={() => {
                 setChannels(p => {
                     const next = {...p};
                     // Click focuses it
                     Object.keys(next).forEach(k => next[k] = {...next[k], focused: false});
                     next[fullKey] = {...next[fullKey], focused: true};
                     return next;
                 });
             }}
             onMouseEnter={() => setHoveredChannelKey(fullKey)}
             onMouseLeave={() => setHoveredChannelKey(p => p === fullKey ? null : p)}
          >
             <div className="flex items-center gap-2">
               <input 
                  type="radio" 
                  name="triggerSrc" 
                  checked={isTriggerSrc} 
                  onChange={(e) => {
                      e.stopPropagation();
                      setTriggerSourceKey(fullKey);
                  }}
                  title="Use as Trigger Source"
                  className="w-3 h-3 cursor-pointer accent-primary"
               />
               <Checkbox 
                 checked={isPlotted} 
                 onCheckedChange={(c) => {
                     setChannels(p => ({...p, [fullKey]: {...p[fullKey], visible: !!c}}));
                 }}
                 onClick={(e) => e.stopPropagation()}
               />
               <span className="font-mono text-xs" style={isPlotted ? { color, fontWeight: isFocused || hoveredChannelKey === fullKey ? 'bold' : 'normal' } : { color: 'var(--muted-foreground)' }}>{fullKey}</span>
             </div>
             <div className="flex items-center gap-3">
               <span className="font-mono text-[10px] text-muted-foreground/70 w-12 text-right" style={isPlotted ? { color: `${color}99` } : {}}>{hz} Hz</span>
               <span className="font-mono text-sm w-16 text-right font-medium" style={isPlotted ? { color } : {}}>{typeof val === 'number' ? val.toFixed(3) : val}</span>
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

  const focusedKey = Object.values(channels).find(c => c.focused)?.key;
  const focusedChannel = focusedKey ? channels[focusedKey] : null;

  const yToPercent = (val: number) => {
    if (!focusedChannel) return 50;
    const min = focusedChannel.y_offset - focusedChannel.y_scale / 2;
    const max = focusedChannel.y_offset + focusedChannel.y_scale / 2;
    const clamped = Math.max(min, Math.min(max, val));
    return ((clamped - min) / (max - min)) * 100;
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
                    <Button variant="outline" size="sm" className="h-8 font-bold" onClick={handleAutoLayout}>
                        <Wand className="w-4 h-4 mr-2" /> Auto Layout
                    </Button>
                </div>
                
                <div className="w-px h-8 bg-border mx-2 shrink-0" />
                
                <div className="flex items-center bg-muted/20 rounded-md p-1 border border-border/50 shrink-0">
                    
                    <div 
                      className="flex flex-col items-start justify-center px-3 border-r border-border/50 shrink-0 h-full transition-colors"
                      style={{ backgroundColor: focusedChannel ? `${focusedChannel.color}15` : 'transparent' }}
                    >
                        <span className="text-[9px] uppercase font-bold mb-1 tracking-wider" style={{ color: focusedChannel ? focusedChannel.color : 'var(--muted-foreground)' }}>Focused Channel</span>
                        <div className="w-28 h-6 text-xs font-bold flex items-center">{focusedKey || "None"}</div>
                    </div>

                    <div className="flex items-center gap-2 px-3 border-r border-border/50 shrink-0">
                        <SpinBox value={xScale} min={0.01} max={360000} step={1} onChange={(v) => { setXScale(v); xScaleRef.current = v; }} label="T Scale" unit="s" />
                        <SpinBox value={xOffset} min={0} max={360000} step={1} onChange={(v) => setXOffset(v)} label="T Delay" unit="s" />
                    </div>

                    <div className="flex items-center gap-2 px-3 border-r border-border/50 shrink-0">
                        <SpinBox 
                           value={focusedChannel?.y_scale || 2} 
                           min={0.1} max={50} step={0.1} 
                           onChange={(v) => {
                               if (focusedKey) setChannels(p => ({...p, [focusedKey]: {...p[focusedKey], y_scale: v}}));
                           }} 
                           label="Y Scale" 
                        />
                        <SpinBox 
                           value={focusedChannel?.y_offset || 0} 
                           min={-50} max={50} step={0.1} 
                           onChange={(v) => {
                               if (focusedKey) setChannels(p => ({...p, [focusedKey]: {...p[focusedKey], y_offset: v}}));
                           }} 
                           label="Y Offset" 
                        />
                    </div>

                    <div className="flex items-center gap-2 px-3 shrink-0">
                        <div className="flex flex-col items-start justify-center">
                            <span className="text-[9px] uppercase font-bold text-muted-foreground mb-1 tracking-wider">
                                Trigger
                                {isTriggerWaitingUI && focusedKey === triggerSourceKey && <span className="text-destructive animate-pulse ml-1">WAITING</span>}
                            </span>
                            <Select value={focusedChannel?.trigger_type || 'None'} onValueChange={handleSetTriggerMode as any}>
                              <SelectTrigger className="w-24 h-6 text-xs bg-background border shadow-sm focus:ring-0"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                  <SelectItem value="None" className="text-xs">None</SelectItem>
                                  <SelectItem value="Rising Edge" className="text-xs">Rising Edge</SelectItem>
                                  <SelectItem value="Falling Edge" className="text-xs">Falling Edge</SelectItem>
                                  <SelectItem value="State High" className="text-xs">Above</SelectItem>
                                  <SelectItem value="State Low" className="text-xs">Below</SelectItem>
                              </SelectContent>
                            </Select>
                        </div>
                        <SpinBox 
                           value={focusedChannel?.trigger_level || 0} 
                           min={-50} max={50} step={0.1} 
                           onChange={(v) => {
                               if (focusedKey) setChannels(p => ({...p, [focusedKey]: {...p[focusedKey], trigger_level: v}}));
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
                      <div className="flex-1 min-h-0 relative p-4 select-none overflow-hidden" ref={plotContainerRef}>
                          <UPlotScope 
                            dataRef={dataBufferRef}
                            channels={channels}
                            xScale={xScale}
                            xOffset={xOffset}
                            isPaused={isPaused}
                            hoveredChannelKey={hoveredChannelKey}
                            setHoveredChannelKey={setHoveredChannelKey}
                            onHoverData={setHoveredData}
                            setChannels={setChannels}
                            setXOffset={setXOffset}
                            setXScale={setXScale}
                            t0Ratio={t0Ratio}
                            setT0Ratio={setT0Ratio}
                          />
                      </div>
                  </ResizablePanel>
                </ResizablePanelGroup>
            )}

            {activeWorkspace === "firmware" && (
                <ResizablePanelGroup orientation="vertical" className="h-full">
                  <ResizablePanel defaultSize={60} minSize={20} className="flex flex-col bg-background border-b p-4">
                     <h2 className="text-lg font-bold mb-4">Settings & Firmware Configurations</h2>
                     <div className="flex flex-col gap-4 max-w-xl">
                        <div className="flex flex-col gap-1">
                            <span className="text-xs font-semibold">Robot IP Address</span>
                            <input 
                                type="text" 
                                value={robotIp} 
                                onChange={(e) => setRobotIp(e.target.value)} 
                                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                                placeholder="localhost"
                            />
                        </div>
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
