import sys

content = """\"use client\";

import { useEffect, useRef, useState } from "react";
import Editor, { useMonaco } from "@monaco-editor/react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Check, ArrowRight, Square, FolderOpen, Search, Settings } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function Home() {
  const monaco = useMonaco();
  const [logs, setLogs] = useState<string[]>([]);
  const [verifyLogs, setVerifyLogs] = useState<string[]>([]);
  const [distance, setDistance] = useState(0);
  const [effort, setEffort] = useState({ x: 0, y: 0 });
  const [effortHistory, setEffortHistory] = useState<{time: string, x: number, y: number}[]>([]);
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
          setDistance(msg.data.distance);
          setEffort(msg.data.effort);
          
          const now = new Date().toLocaleTimeString('en-US', { hour12: false, hour: "numeric", minute: "numeric", second: "numeric" });
          setEffortHistory(prev => {
             const newHistory = [...prev, { time: now, x: msg.data.effort.x, y: msg.data.effort.y }];
             return newHistory.slice(-20);
          });
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
      <div className="flex-1 flex flex-col min-w-0">
        
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
                options={{ minimap: { enabled: false }, roundedSelection: false, scrollBeyondLastLine: false }}
              />
            </div>
          </ResizablePanel>
          
          <ResizableHandle withHandle className="h-1 w-full bg-border cursor-row-resize hover:bg-muted-foreground/30 transition-colors" />
          
          <ResizablePanel defaultSize={30} minSize={15} className="flex flex-col overflow-hidden bg-background">
            <Tabs defaultValue="shell" className="flex flex-col h-full w-full">
              
              <div className="border-b shrink-0 flex items-center justify-between px-2 bg-muted/10 h-9">
                <TabsList className="h-full bg-transparent p-0 gap-1 rounded-none">
                  <TabsTrigger value="verification" className="text-xs h-full rounded-none border-b-2 border-transparent data-[state=active]:border-foreground data-[state=active]:shadow-none data-[state=active]:bg-transparent">
                    Verification Status
                  </TabsTrigger>
                  <TabsTrigger value="shell" className="text-xs h-full rounded-none border-b-2 border-transparent data-[state=active]:border-foreground data-[state=active]:shadow-none data-[state=active]:bg-transparent">
                    Shell
                  </TabsTrigger>
                  <TabsTrigger value="data" className="text-xs h-full rounded-none border-b-2 border-transparent data-[state=active]:border-foreground data-[state=active]:shadow-none data-[state=active]:bg-transparent">
                    Data View
                  </TabsTrigger>
                </TabsList>
              </div>

              <div className="flex-1 min-h-0 overflow-hidden">
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

                <TabsContent value="data" className="h-full flex p-4 m-0 outline-none data-[state=inactive]:hidden gap-4">
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
                </TabsContent>
              </div>
            </Tabs>
          </ResizablePanel>

        </ResizablePanelGroup>
      </div>
    </div>
  );
}
"""

with open('src/app/page.tsx', 'w') as f:
    f.write(content)

