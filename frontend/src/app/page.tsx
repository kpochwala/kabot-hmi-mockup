"use client";

import { useEffect, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Check, ArrowRight, Square, Search, Settings, TerminalSquare, Activity, Play, Wand, Unplug, Download, Upload, ChevronDown, ChevronUp, ChevronLeft, Copy } from 'lucide-react';
import { UPlotScope } from "@/components/ui/UPlotScope";
import { SpinBox } from "@/components/ui/spinbox";
import { ChannelConfig, ScopeState, TriggerType } from "@/types/scope";

const chartColors = ["#2563eb", "#16a34a", "#dc2626", "#d97706", "#9333ea", "#0891b2", "#be185d"];
const lockedFunctionSignature = "def control(state: RobotState, control: RobotControl) -> RobotControl:";

type ControlDirection = "up" | "down" | "left" | "right";

const scriptSchema = {
  state: {
    distance: "float",
    effort: { x: "float", y: "float" },
    linear_acceleration: { x: "float", y: "float", z: "float" },
    angular_velocity: { x: "float", y: "float", z: "float" },
    magnetic_field: { x: "float", y: "float", z: "float" },
    light_left: "float",
    light_right: "float",
    current_left: "float",
    bus_voltage_left: "float",
    power_left: "float",
    current_right: "float",
    bus_voltage_right: "float",
    power_right: "float",
    current_supply: "float",
    bus_voltage_supply: "float",
    power_supply: "float",
  },
  control: {
    effort: { x: "float", y: "float" },
  },
} as const;

export default function Home() {
  const [logs, setLogs] = useState<string[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState("firmware");
  const [stateData, setStateData] = useState<any>({});
  const [pausedState, setPausedState] = useState<any>(null);
  
  const dataBufferRef = useRef<any[]>([]);
  const [hzStats, setHzStats] = useState<Record<string, string>>({});
  
  const [channels, setChannels] = useState<ScopeState>({});
  const channelsRef = useRef<ScopeState>(channels);

  // Load saved layout strictly after mount to avoid SSR hydration mismatch
  useEffect(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("plot_layout");
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          setChannels(parsed);
          channelsRef.current = parsed;
        } catch (e) {}
      }
    }
  }, []);

  useEffect(() => {
    if (Object.keys(channels).length > 0) {
      localStorage.setItem("plot_layout", JSON.stringify(channels));
    }
  }, [channels]);
  
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
  const editorRef = useRef<any>(null);
  const plotContainerRef = useRef<HTMLDivElement>(null);
  const codeLogsEndRef = useRef<HTMLDivElement>(null);
  const firmwareLogsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (activeWorkspace === "code") {
      codeLogsEndRef.current?.scrollIntoView();
    } else if (activeWorkspace === "firmware") {
      firmwareLogsEndRef.current?.scrollIntoView();
    }
  }, [logs, activeWorkspace]);
  
  const defaultCode = `${lockedFunctionSignature}\n    if state.distance < 0.5:\n        control.effort.x = 0\n        control.effort.y = 0\n    else:\n        control.effort.x = 1\n        control.effort.y = 1\n    return control\n`;
  const [code, setCode] = useState(defaultCode);
  const [scriptName, setScriptName] = useState("control.py");
  
  const [robotIp, setRobotIp] = useState("localhost");
  const [backendPort, setBackendPort] = useState<number>(8000);

  useEffect(() => {
    if (typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__) {
      import("@tauri-apps/api/core").then((module) => {
        module.invoke("get_backend_port").then((port) => {
          if (typeof port === "number") {
            setBackendPort(port);
          }
        }).catch(console.error);
      });
    }
  }, []);
  const [connectedRobot, setConnectedRobot] = useState<any>(null);
  const [discoveredRobots, setDiscoveredRobots] = useState<any[]>([]);
  const [selectedRobotSerial, setSelectedRobotSerial] = useState<string>("");
  const [isScanning, setIsScanning] = useState(false);
  const [backendConnected, setBackendConnected] = useState(false);
  const [robotConnectionStatus, setRobotConnectionStatus] = useState<'connected' | 'warning' | 'disconnected'>('disconnected');
  const [scriptsPath, setScriptsPath] = useState("backend/scripts");
  const manualDirectionsRef = useRef<Set<ControlDirection>>(new Set());
  const [manualDirectionsUI, setManualDirectionsUI] = useState<Set<ControlDirection>>(new Set());
  const lastManualControlRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const [copiedPath, setCopiedPath] = useState<string | null>(null);

  const getEditorCode = () => {
    if (editorRef.current) {
      return editorRef.current.getValue();
    }
    return code;
  };

  const setEditorCode = (nextCode: string) => {
    setCode(nextCode);
    if (editorRef.current) {
      editorRef.current.setValue(nextCode);
    }
  };

  const sendScriptsPath = (path: string) => {
    const normalized = path.trim();
    if (!normalized) return;
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "set_scripts_path", path: normalized }));
    }
  };

  const requestScriptsList = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "list_scripts" }));
    }
  };

  const saveCurrentScript = async () => {
    if (typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__) {
      try {
        const { save } = await import('@tauri-apps/plugin-dialog');
        const filePath = await save({
          filters: [{ name: 'Python script', extensions: ['py'] }],
          defaultPath: scriptName,
        });
        if (filePath && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: "save_script", path: filePath, code: getEditorCode() }));
        }
      } catch (e) {
        console.error("Save script error", e);
      }
    } else {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "save_script", name: scriptName, code: getEditorCode() }));
      }
    }
  };

  const loadScript = async () => {
    if (typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__) {
      try {
        const { open } = await import('@tauri-apps/plugin-dialog');
        const filePath = await open({
          multiple: false,
          directory: false,
          filters: [{ name: 'Python script', extensions: ['py'] }]
        });
        if (filePath && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: "load_script", path: filePath as string }));
        }
      } catch (e) {
        console.error("Load script error", e);
      }
    } else {
      const name = prompt("Enter script name to load:");
      if (name && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "load_script", name }));
      }
    }
  };

  useEffect(() => {
    // Keep ref in sync
    channelsRef.current = channels;
  }, [channels]);

  useEffect(() => {
    triggerSourceKeyRef.current = triggerSourceKey;
  }, [triggerSourceKey]);

  useEffect(() => {
    let reconnectTimeout: ReturnType<typeof setTimeout>;
    let isComponentMounted = true;

    const connectWs = () => {
      if (!isComponentMounted) return;
      wsRef.current = new WebSocket(`ws://${robotIp}:${backendPort}/ws`);
      wsRef.current.onopen = () => {
        setBackendConnected(true);
      };
      wsRef.current.onclose = () => {
        setBackendConnected(false);
        setIsRunning(false);
        setIsScanning(false);
        if (isComponentMounted) {
          reconnectTimeout = setTimeout(connectWs, 2000);
        }
      };
      wsRef.current.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "log") {
          setLogs(prev => [...prev.slice(-10000), msg.data]);
          if (msg.data.includes("Runtime Error:") || msg.data.includes("Stopped user script.")) setIsRunning(false);
          if (msg.data.includes("Discovery sweep finished. No robots found.")) setIsScanning(false);
        } else if (msg.type === "robots_discovered") {
          setIsScanning(false);
          setDiscoveredRobots(msg.robots);
          
          const alreadyClaimedByUs = msg.robots.find((r: any) => r.is_claimed_by_us);
          if (alreadyClaimedByUs && !connectedRobot) {
            setConnectedRobot(alreadyClaimedByUs);
            setRobotConnectionStatus('connected');
            setSelectedRobotSerial(`${alreadyClaimedByUs.serial}_${alreadyClaimedByUs.ip}`);
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                wsRef.current.send(JSON.stringify({ 
                    type: 'claim_robot', 
                    ip: alreadyClaimedByUs.ip, 
                    port: alreadyClaimedByUs.port 
                }));
                wsRef.current.send(JSON.stringify({ 
                    type: 'request_current_script'
                }));
            }
          } else if (msg.robots.length === 0) {
            setSelectedRobotSerial("");
          } else if (msg.robots.length === 1 && !selectedRobotSerial) {
            setSelectedRobotSerial(`${msg.robots[0].serial}_${msg.robots[0].ip}`);
          }
        } else if (msg.type === "claim_accepted") {
          setDiscoveredRobots(prev => prev.map(r => 
            r.ip === msg.ip ? { ...r, is_claimed: true } : r
          ));
        } else if (msg.type === "run_result") {
          if (msg.ok) {
            setIsRunning(true);
          } else {
            setIsRunning(false);
          }
        } else if (msg.type === "runtime_status") {
          setIsRunning(!!msg.active);
        } else if (msg.type === "scripts_config") {
          if (typeof msg.path === "string" && msg.path.trim()) {
            setScriptsPath(msg.path);
          }
        } else if (msg.type === "script_saved") {
          if (typeof msg.name === "string" && msg.name.trim()) {
            setScriptName(msg.name);
          }
        } else if (msg.type === "script_loaded") {
          if (typeof msg.name === "string" && msg.name.trim()) {
            setScriptName(msg.name);
          }
          if (typeof msg.code === "string") {
            setEditorCode(msg.code);
          }
        } else if (msg.type === "robot_connected") {
          setConnectedRobot(msg.robot);
          setRobotConnectionStatus('connected');
          setIsScanning(false);
        } else if (msg.type === "robot_connection_status") {
          setRobotConnectionStatus(msg.status);
        } else if (msg.type === "robot_disconnected") {
          setConnectedRobot(null);
          setRobotConnectionStatus('disconnected');
          setSelectedRobotSerial("");
          setDiscoveredRobots(prev => prev.filter(r => r.ip !== msg.ip));
        } else if (msg.type === "robot_released") {
          setConnectedRobot(null);
          setRobotConnectionStatus('disconnected');
          setSelectedRobotSerial("");
          setDiscoveredRobots(prev => prev.map(r => 
            (msg.ip ? r.ip === msg.ip : true) ? { ...r, is_claimed: false, is_claimed_by_us: false } : r
          ));
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
                  const deltaMs = history[history.length - 1] - history[0];
                  if (deltaMs > 0) newHz[key] = ((history.length - 1) * 1e3 / deltaMs).toFixed(1);
                  else newHz[key] = "0.0";
              } else newHz[key] = "0.0";
          }
          setHzStats(newHz);
          
            const ts = Date.now();
            const entry: any = { timestamp: ts };
            const flattenNumeric = (value: any, path: string[] = []) => {
              if (typeof value === 'number' && Number.isFinite(value)) {
                entry[path.join('.')] = value;
                return;
              }
              if (value && typeof value === 'object') {
                for (const key of Object.keys(value)) {
                  flattenNumeric(value[key], [...path, key]);
                }
              }
            };
            flattenNumeric(d);
          
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
                      visible: k.startsWith('effort.') || k === 'distance' || k.startsWith('gyro.'),
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
    };

    connectWs();
    return () => {
      isComponentMounted = false;
      clearTimeout(reconnectTimeout);
      if (wsRef.current) {
          wsRef.current.onclose = null;
          wsRef.current.close();
      }
    };
  }, [robotIp, backendPort]);

  const handleEditorMount = (editor: any, monaco: any) => {
    editorRef.current = editor;
    editor.setValue(code);

    if (typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__) {
      editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyV, async () => {
        try {
          const { readText } = await import('@tauri-apps/plugin-clipboard-manager');
          const text = await readText();
          if (text) {
            editor.trigger('keyboard', 'type', { text });
          }
        } catch (e) {
          console.error("Failed to paste from Tauri clipboard", e);
        }
      });
    }
  };

  const sendManualControl = (x: number, y: number, force = false) => {
    if (!force && lastManualControlRef.current.x === x && lastManualControlRef.current.y === y) {
      return;
    }
    lastManualControlRef.current = { x, y };
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "control", effort: { x, y } }));
    }
  };

  const computeManualVector = (dirs: Set<ControlDirection>) => {
    const vectors: Record<ControlDirection, { x: number; y: number }> = {
      up: { x: 1, y: 1 },
      down: { x: -1, y: -1 },
      left: { x: -1, y: 1 },
      right: { x: 1, y: -1 },
    };
    let x = 0;
    let y = 0;
    for (const dir of dirs) {
      x += vectors[dir].x;
      y += vectors[dir].y;
    }
    return {
      x: Math.max(-1, Math.min(1, x)),
      y: Math.max(-1, Math.min(1, y)),
    };
  };

  const updateManualDirections = (updater: (next: Set<ControlDirection>) => void) => {
    const next = new Set(manualDirectionsRef.current);
    updater(next);
    manualDirectionsRef.current = next;
    setManualDirectionsUI(next);
    const vector = computeManualVector(next);
    sendManualControl(vector.x, vector.y);
  };

  useEffect(() => {
    if (manualDirectionsUI.size === 0) return;
    const intervalId = setInterval(() => {
      const vector = computeManualVector(manualDirectionsUI);
      sendManualControl(vector.x, vector.y, true);
    }, 100);
    return () => clearInterval(intervalId);
  }, [manualDirectionsUI]);

  const handleManualDirectionPress = (direction: ControlDirection) => {
    updateManualDirections((next) => next.add(direction));
  };

  const handleManualDirectionRelease = (direction: ControlDirection) => {
    updateManualDirections((next) => next.delete(direction));
  };

  const clearManualDirections = () => {
    updateManualDirections((next) => next.clear());
  };

  const copyPath = async (path: string) => {
    try {
      if (typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__) {
        const { writeText } = await import('@tauri-apps/plugin-clipboard-manager');
        await writeText(path);
      } else {
        await navigator.clipboard.writeText(path);
      }
      setCopiedPath(path);
      setTimeout(() => setCopiedPath((prev) => (prev === path ? null : prev)), 1000);
    } catch (err) {
      console.error(err);
    }
  };

  const renderScriptTree = (node: any, parentPath = "", depth = 0): React.ReactNode => {
    return Object.entries(node).map(([key, value]) => {
      const path = parentPath ? `${parentPath}.${key}` : key;
      if (typeof value === "string") {
        return (
          <div
            key={path}
            className="flex items-center justify-between gap-2 py-1"
            style={{ paddingLeft: `${depth * 12}px` }}
          >
            <div className="flex items-center gap-2 min-w-0">
              <span className="font-mono text-xs truncate">{path}</span>
              <span className="text-[10px] text-muted-foreground shrink-0">{value}</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="h-5 px-1.5 shrink-0"
              onClick={() => copyPath(path)}
              title={`Copy ${path}`}
            >
              <Copy className="w-3 h-3 mr-1" />
              <span className="text-[10px]">{copiedPath === path ? "Copied" : "Copy"}</span>
            </Button>
          </div>
        );
      }

      return (
        <div key={path} className="py-1" style={{ paddingLeft: `${depth * 12}px` }}>
          <div className="text-[10px] uppercase font-bold tracking-wide text-muted-foreground">{path}</div>
          <div>{renderScriptTree(value, path, depth + 1)}</div>
        </div>
      );
    });
  };

  useEffect(() => {
    const keyToDirection: Record<string, ControlDirection> = {
      ArrowUp: "up",
      ArrowDown: "down",
      ArrowLeft: "left",
      ArrowRight: "right",
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (activeWorkspace !== "scope") return;
      const direction = keyToDirection[event.key];
      if (!direction) return;
      event.preventDefault();
      if (!manualDirectionsRef.current.has(direction)) {
        handleManualDirectionPress(direction);
      }
    };

    const onKeyUp = (event: KeyboardEvent) => {
      const direction = keyToDirection[event.key];
      if (!direction) return;
      event.preventDefault();
      if (manualDirectionsRef.current.has(direction)) {
        handleManualDirectionRelease(direction);
      }
    };

    const onWindowBlur = () => {
      clearManualDirections();
    };

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    window.addEventListener("blur", onWindowBlur);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      window.removeEventListener("blur", onWindowBlur);
    };
  }, [activeWorkspace]);

  useEffect(() => {
    if (activeWorkspace !== "scope") {
      clearManualDirections();
    }
  }, [activeWorkspace]);

  const handleRun = () => {
    const runtimeCode = getEditorCode();
    const body = runtimeCode.split("\n").slice(1).join("\n").trim();
    if (!body) {
      return;
    }
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "run", code: runtimeCode }));
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
          <button 
            onClick={() => setActiveWorkspace("firmware")} 
            className={`p-2 rounded-lg transition-colors ${activeWorkspace === "firmware" ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"}`}
            title="Settings"
          >
            <Settings className="w-5 h-5" />
          </button>
      </div>

      <div className="flex-1 flex flex-col min-w-0 min-h-0 relative">
        
        {/* Contextual Toolbar */}
        {activeWorkspace === "code" && (
            <div className="h-12 border-b flex items-center px-4 gap-4 shrink-0 bg-background">
                {!isRunning ? (
                  <Button size="sm" variant="default" className="font-bold w-[140px]" onClick={handleRun} disabled={isRunning} title="Run script"><Play className="w-4 h-4 mr-2" /> Run script</Button>
                ) : (
                  <Button size="sm" variant="destructive" className="font-bold animate-pulse w-[140px]" onClick={handleStop} title="Stop"><Square className="w-4 h-4 mr-2 fill-current" /> Stop ({hzStats['state'] || '0.0'} Hz)</Button>
                )}
                <div className="w-px h-6 bg-border mx-2" />
                <Input
                  value={scriptName}
                  onChange={(e) => {
                    setScriptName(e.target.value);
                  }}
                  className="w-44 h-8 text-xs font-mono"
                  placeholder="script name"
                  title="Script file name"
                />
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8"
                  onClick={saveCurrentScript}
                  title="Save script to disk"
                >
                  Save
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8"
                  onClick={loadScript}
                  title="Load script from disk"
                >
                  Load
                </Button>
                <div className="flex items-center gap-2">
                  <Select 
                    value={selectedRobotSerial} 
                    onValueChange={(val) => setSelectedRobotSerial(val || "")}
                  >
                    <SelectTrigger className="w-80 h-8 text-xs border-0 bg-muted/50 focus:ring-0">
                      <SelectValue placeholder="Select Robot">
                        {(() => {
                          const r = discoveredRobots.find(r => `${r.serial}_${r.ip}` === selectedRobotSerial);
                          if (r) return `${r.ip}${r.is_claimed ? ` claimed by ${r.is_claimed_by_us ? 'us' : r.claimed_by_ip}` : ''}`;
                          if (selectedRobotSerial) return selectedRobotSerial.split('_')[1] || selectedRobotSerial;
                          return "Select Robot";
                        })()}
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                      {discoveredRobots.map(r => {
                        const uniqueId = `${r.serial}_${r.ip}`;
                        return (
                          <SelectItem key={uniqueId} value={uniqueId} className="text-xs">
                            {r.ip}{r.is_claimed ? ` claimed by ${r.is_claimed_by_us ? 'us' : r.claimed_by_ip}` : ''}
                          </SelectItem>
                        );
                      })}
                    </SelectContent>
                  </Select>
                  <Button
                    size="sm"
                    variant="default"
                    className="h-8 px-2"
                    disabled={
                      !selectedRobotSerial || 
                      discoveredRobots.find(r => `${r.serial}_${r.ip}` === selectedRobotSerial)?.is_claimed
                    }
                    onClick={() => {
                      const robot = discoveredRobots.find(r => `${r.serial}_${r.ip}` === selectedRobotSerial);
                      if (robot && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                        setConnectedRobot(robot);
                        wsRef.current.send(JSON.stringify({ 
                          type: "claim_robot", 
                          ip: robot.ip, 
                          port: robot.port 
                        }));
                      }
                    }}
                    title="Claim Selected Robot"
                  >
                    Claim
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 px-2"
                    disabled={!connectedRobot}
                    onClick={() => {
                      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                        setConnectedRobot(null);
                        wsRef.current.send(JSON.stringify({ type: "release_robot" }));
                      }
                    }}
                    title="Release Claimed Robot"
                  >
                    Unclaim
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 px-2"
                    disabled={isScanning}
                    onClick={() => {
                      setIsScanning(true);
                      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                        wsRef.current.send(JSON.stringify({ type: "scan_robots" }));
                      }
                    }}
                    title="Scan for Robots"
                  >
                    <Search className={`w-4 h-4 ${isScanning ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
            </div>
        )}

        {activeWorkspace === "scope" && (
            <div className="h-16 border-b flex items-center px-4 gap-4 bg-background shrink-0 overflow-x-auto overflow-y-visible">
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

                    <div className="flex items-center gap-2 px-3 border-l border-border/50 shrink-0">
                        <div className="flex items-center gap-1.5">
                            <span className="text-[9px] uppercase font-bold text-muted-foreground tracking-wider">Manual</span>
                            <Button
                              variant={manualDirectionsUI.has("up") ? "default" : "outline"}
                              size="icon"
                              className="h-5 w-5"
                              title="Forward (Arrow Up)"
                              onMouseDown={() => handleManualDirectionPress("up")}
                              onMouseUp={() => handleManualDirectionRelease("up")}
                              onMouseLeave={() => handleManualDirectionRelease("up")}
                            >
                              <ChevronUp className="w-2.5 h-2.5" />
                            </Button>
                            <Button
                              variant={manualDirectionsUI.has("left") ? "default" : "outline"}
                              size="icon"
                              className="h-5 w-5"
                              title="Left (Arrow Left)"
                              onMouseDown={() => handleManualDirectionPress("left")}
                              onMouseUp={() => handleManualDirectionRelease("left")}
                              onMouseLeave={() => handleManualDirectionRelease("left")}
                            >
                              <ChevronLeft className="w-2.5 h-2.5" />
                            </Button>
                            <Button
                              variant="outline"
                              size="icon"
                              className="h-5 w-5"
                              title="Release"
                              onClick={clearManualDirections}
                            >
                              <Square className="w-2 h-2" />
                            </Button>
                            <Button
                              variant={manualDirectionsUI.has("right") ? "default" : "outline"}
                              size="icon"
                              className="h-5 w-5"
                              title="Right (Arrow Right)"
                              onMouseDown={() => handleManualDirectionPress("right")}
                              onMouseUp={() => handleManualDirectionRelease("right")}
                              onMouseLeave={() => handleManualDirectionRelease("right")}
                            >
                              <ArrowRight className="w-2.5 h-2.5" />
                            </Button>
                            <Button
                              variant={manualDirectionsUI.has("down") ? "default" : "outline"}
                              size="icon"
                              className="h-5 w-5"
                              title="Backward (Arrow Down)"
                              onMouseDown={() => handleManualDirectionPress("down")}
                              onMouseUp={() => handleManualDirectionRelease("down")}
                              onMouseLeave={() => handleManualDirectionRelease("down")}
                            >
                              <ChevronDown className="w-2.5 h-2.5" />
                            </Button>
                        </div>
                    </div>

                </div>
            </div>
        )}

        {activeWorkspace === "firmware" && (
            <div className="h-12 border-b flex items-center px-4 gap-4 shrink-0 bg-background">
                <Button size="sm" variant="outline" className="font-bold" onClick={() => alert("This functionality will be available soon. Sorry.")}><Unplug className="w-4 h-4 mr-2" /> Connect Robot</Button>
                <Button size="sm" variant="default" className="font-bold" onClick={() => alert("This functionality will be available soon. Sorry.")}><Download className="w-4 h-4 mr-2" /> Firmware Update</Button>
            </div>
        )}

        {/* Workspace Bodies */}
        <div className="flex-1 min-h-0 overflow-hidden relative bg-muted/5">
            <div className={activeWorkspace === "code" ? "h-full" : "hidden h-full"}>
                <ResizablePanelGroup orientation="vertical" className="h-full">
                  <ResizablePanel defaultSize={70} minSize={20} className="flex flex-col overflow-hidden border-b">
                    <ResizablePanelGroup orientation="horizontal" className="h-full">
                      <ResizablePanel defaultSize={74} minSize={45} className="flex flex-col overflow-hidden border-r">
                        <div className="flex-1 min-h-0 overflow-hidden relative">
                          <Editor
                            height="100%"
                            defaultLanguage="python"
                            defaultValue={code}
                            onMount={handleEditorMount}
                            options={{ fontFamily: '"Hack", monospace', minimap: { enabled: false }, roundedSelection: false, scrollBeyondLastLine: false }}
                          />
                        </div>
                      </ResizablePanel>
                      <ResizableHandle withHandle className="w-1 bg-border cursor-col-resize hover:bg-primary/50 transition-colors" />
                      <ResizablePanel defaultSize={26} minSize={18} className="bg-background overflow-hidden">
                        <div className="h-full flex flex-col">
                          <div className="h-8 border-b px-3 flex items-center justify-between shrink-0">
                            <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground">Script Paths</span>
                            <span className="text-[10px] text-muted-foreground">RobotState and RobotControl</span>
                          </div>
                          <div className="flex-1 min-h-0 overflow-y-auto p-2">
                            {renderScriptTree(scriptSchema)}
                          </div>
                        </div>
                      </ResizablePanel>
                    </ResizablePanelGroup>
                  </ResizablePanel>
                  <ResizableHandle withHandle className="h-1 bg-border cursor-row-resize hover:bg-muted-foreground/30 transition-colors" />
                  <ResizablePanel defaultSize={30} minSize={15} className="flex flex-col bg-background">
                    <Tabs defaultValue="shell" className="flex-1 flex flex-col min-h-0 overflow-hidden">
                        <div className="h-8 border-b flex items-center px-2 shrink-0 bg-muted/30">
                            <TabsList className="h-6 bg-transparent">
                                <TabsTrigger value="shell" className="text-xs h-6 px-4 data-[state=active]:bg-background data-[state=active]:shadow-sm">Shell Output</TabsTrigger>
                            </TabsList>
                        </div>
                        <TabsContent value="shell" className="flex-1 overflow-y-auto p-2 m-0 data-[state=inactive]:hidden font-mono text-xs text-foreground">
                            {logs.length === 0 && <span className="text-muted-foreground">Awaiting logs...</span>}
                            {logs.map((log, i) => <div key={i}>{log}</div>)}
                            <div ref={codeLogsEndRef} />
                        </TabsContent>
                    </Tabs>
                  </ResizablePanel>
                </ResizablePanelGroup>
              </div>

            {activeWorkspace === "scope" && (
                <ResizablePanelGroup orientation="horizontal" className="h-full">
                  <ResizablePanel defaultSize={30} minSize={20} className="p-4 flex flex-col overflow-y-auto border-r bg-background">
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
                     <h2 className="text-xl font-bold mb-6">Settings</h2>
                     <div className="flex flex-col gap-8 max-w-2xl">
                        
                        {/* HMI Status */}
                        <div className="flex flex-col gap-3">
                            <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground border-b pb-1">HMI Status</h3>
                            <div className="grid grid-cols-2 gap-4 text-sm">
                                <div className="flex flex-col">
                                    <span className="text-muted-foreground text-xs">Backend Connection</span>
                                    <div className="flex items-center gap-2 mt-1">
                                        <div className={`w-2 h-2 rounded-full ${backendConnected ? 'bg-green-500' : 'bg-red-500'}`} />
                                        <span className="font-medium">{backendConnected ? 'Connected' : 'Disconnected'}</span>
                                    </div>
                                </div>
                                <div className="flex flex-col">
                                    <span className="text-muted-foreground text-xs">Robot Connection</span>
                                    <div className="flex items-center gap-2 mt-1">
                                        <div className={`w-2 h-2 rounded-full ${robotConnectionStatus === 'connected' ? 'bg-green-500' : robotConnectionStatus === 'warning' ? 'bg-yellow-500' : 'bg-red-500'}`} />
                                        <span className="font-medium">{robotConnectionStatus === 'connected' ? 'Connected' : robotConnectionStatus === 'warning' ? 'Connection Lost' : 'Disconnected'}</span>
                                    </div>
                                </div>
                                <div className="flex flex-col">
                                    <span className="text-muted-foreground text-xs">HMI Version</span>
                                    <span className="font-medium mt-1">v1.0.0-mockup</span>
                                </div>
                                <div className="flex flex-col">
                                    <span className="text-muted-foreground text-xs">Links</span>
                                    <div className="flex flex-col mt-1 gap-1">
                                        <a href="https://github.com/kabot-io/kabot-zephyr" target="_blank" rel="noreferrer" className="text-blue-500 hover:underline font-medium">Firmware repo</a>
                                        <a href="https://github.com/kpochwala/kabot-hmi-mockup" target="_blank" rel="noreferrer" className="text-blue-500 hover:underline font-medium">HMI repo</a>
                                        <a href="https://discord.com/channels/1080485717970518126/1080485718624841770" target="_blank" rel="noreferrer" className="text-blue-500 hover:underline font-medium">Discord channel</a>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Robot Status */}
                        <div className="flex flex-col gap-3">
                            <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground border-b pb-1">Robot Status</h3>
                            {connectedRobot ? (
                                <div className="grid grid-cols-2 gap-4 text-sm">
                                    <div className="flex flex-col">
                                        <span className="text-muted-foreground text-xs">IP Address</span>
                                        <span className="font-medium mt-1 font-mono">{connectedRobot.ip}</span>
                                    </div>
                                    <div className="flex flex-col">
                                        <span className="text-muted-foreground text-xs">Serial Number</span>
                                        <span className="font-medium mt-1 font-mono">{connectedRobot.serial}</span>
                                    </div>
                                    <div className="flex flex-col">
                                        <span className="text-muted-foreground text-xs">Human Name</span>
                                        <span className="font-medium mt-1">{connectedRobot.human_name || "N/A"}</span>
                                    </div>
                                    <div className="flex flex-col">
                                        <span className="text-muted-foreground text-xs">Firmware Version</span>
                                        <span className="font-medium mt-1">{connectedRobot.firmware_version || "N/A"}</span>
                                    </div>
                                    <div className="flex flex-col">
                                        <span className="text-muted-foreground text-xs">Control Port</span>
                                        <span className="font-medium mt-1">{connectedRobot.port}</span>
                                    </div>
                                    <div className="flex flex-col">
                                        <span className="text-muted-foreground text-xs">Claimed Status</span>
                                        <span className="font-medium mt-1">
                                            {connectedRobot.is_claimed_by_us ? "Claimed by us" : 
                                             connectedRobot.is_claimed ? `Claimed by ${connectedRobot.claimed_by_ip}` : "Unclaimed"}
                                        </span>
                                    </div>
                                </div>
                            ) : (
                                <div className="text-sm text-muted-foreground italic">No robot is currently connected.</div>
                            )}
                        </div>

                        {/* Robot Override Details */}
                        <div className="flex flex-col gap-3">
                            <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground border-b pb-1">Configurations</h3>
                            <div className="flex flex-col gap-4 max-w-sm">
                                <div className="flex flex-col gap-1">
                                    <span className="text-xs font-semibold">Robot IP Override</span>
                                    <input 
                                        type="text" 
                                        value={robotIp} 
                                        onChange={(e) => setRobotIp(e.target.value)} 
                                        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                                        placeholder="Auto-discovered"
                                    />
                                    <span className="text-[10px] text-muted-foreground mt-1">Leave empty to use auto-discovery.</span>
                                </div>
                                <div className="flex flex-col gap-1">
                                    <span className="text-xs font-semibold">Scripts Folder Path</span>
                                    <input
                                        type="text"
                                        value={scriptsPath}
                                        onChange={(e) => setScriptsPath(e.target.value)}
                                        onBlur={() => sendScriptsPath(scriptsPath)}
                                        onKeyDown={(e) => {
                                          if (e.key === "Enter") {
                                            e.preventDefault();
                                            sendScriptsPath(scriptsPath);
                                          }
                                        }}
                                        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                                        placeholder="backend/scripts"
                                    />
                                </div>
                            </div>
                        </div>

                     </div>
                  </ResizablePanel>
                </ResizablePanelGroup>
            )}
        </div>
      </div>
    </div>
  );
}
