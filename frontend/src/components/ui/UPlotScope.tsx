import React, { useEffect, useRef, useState } from 'react';
import uPlot from 'uplot';
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '@/components/ui/resizable';
import 'uplot/dist/uPlot.min.css';
import { ScopeState } from '@/types/scope';

const hexToRgb = (hex: string) => {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? { r: parseInt(result[1], 16), g: parseInt(result[2], 16), b: parseInt(result[3], 16) } : { r: 0, g: 0, b: 0 };
};

function interpolateValue(ts: number, timestamps: ArrayLike<number>, dataValues: ArrayLike<number | null | undefined>): number | null {
    if (!timestamps || !timestamps.length || !dataValues) return null;
    let lo = 0, hi = timestamps.length - 1;
    while (lo <= hi) {
        let mid = (lo + hi) >> 1;
        if (timestamps[mid] < ts) lo = mid + 1;
        else if (timestamps[mid] > ts) hi = mid - 1;
        else return dataValues[mid] ?? null;
    }
    if (hi < 0) return dataValues[0] ?? null;
    if (lo >= timestamps.length) return dataValues[timestamps.length - 1] ?? null;
    
    const t0 = timestamps[hi];
    const t1 = timestamps[lo];
    const v0 = dataValues[hi];
    const v1 = dataValues[lo];
    if (v0 == null || v1 == null) return v0 ?? v1 ?? null;
    
    const pct = (ts - t0) / (t1 - t0);
    return v0 + (v1 - v0) * pct;
}

interface UPlotScopeProps {
  dataRef: React.MutableRefObject<any[]>;
  channels: ScopeState;
  xScale: number;
  xOffset: number;
  isPaused: boolean;
  hoveredChannelKey: string | null;
  setHoveredChannelKey: React.Dispatch<React.SetStateAction<string | null>>;
  onHoverData: (data: any | null) => void;
  setChannels: React.Dispatch<React.SetStateAction<ScopeState>>;
  setXOffset: React.Dispatch<React.SetStateAction<number>>;
  setXScale: React.Dispatch<React.SetStateAction<number>>;
  t0Ratio: number;
  setT0Ratio: React.Dispatch<React.SetStateAction<number>>;
}

export function UPlotScope({
  dataRef,
  channels,
  xScale,
  xOffset,
  isPaused,
  hoveredChannelKey,
  setHoveredChannelKey,
  onHoverData,
  setChannels,
  setXOffset,
  setXScale,
  t0Ratio,
  setT0Ratio
}: UPlotScopeProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const plotRef = useRef<uPlot | null>(null);
  const scrubberContainerRef = useRef<HTMLDivElement>(null);
  const scrubberPlotRef = useRef<uPlot | null>(null);
  const scrubberOverlayRef = useRef<HTMLDivElement>(null);
  const t0LabelRef = useRef<HTMLDivElement>(null);
  const hoverTooltipRef = useRef<HTMLDivElement>(null);
  const hoverTooltipTextRef = useRef<HTMLSpanElement>(null);
  const hoverRightArrowRef = useRef<HTMLDivElement>(null);
  const hoverRightArrowTextRef = useRef<HTMLSpanElement>(null);
  const hoverTimeLabelRef = useRef<HTMLDivElement>(null);
  const wasPanningRef = useRef(false);
  const lastMousePos = useRef<{x: number, y: number} | null>(null);
  const isDraggingLabelRef = useRef(false);
  
  const visibleKeys = Object.values(channels).filter(c => c.visible).map(c => c.key);
  const configHash = visibleKeys.join('|');
  
  useEffect(() => {
     const moveHandler = (e: MouseEvent) => {
         lastMousePos.current = { x: e.clientX, y: e.clientY };
     };
     document.addEventListener('mousemove', moveHandler);
     return () => document.removeEventListener('mousemove', moveHandler);
  }, []);
  
  const domainsRef = useRef({ xScale, xOffset, isPaused, channels, hoveredChannelKey, t0Ratio, isDraggingT0: false, lastClick: { time: 0, x: 0, y: 0 } });
  useEffect(() => {
     domainsRef.current = { xScale, xOffset, isPaused, channels, hoveredChannelKey, t0Ratio, isDraggingT0: domainsRef.current.isDraggingT0, lastClick: domainsRef.current.lastClick };
  }, [xScale, xOffset, isPaused, channels, hoveredChannelKey, t0Ratio]);

  useEffect(() => {
    if (!containerRef.current) return;

    const series: uPlot.Series[] = [
      { label: "Time" },
      ...visibleKeys.map((k) => {
         const ch = channels[k];
         return {
             show: true,
             spanGaps: false,
             label: k,
             scale: k,
             stroke: ch.color,
             width: ch.focused ? 2.5 : 1.5,
         } as uPlot.Series;
      })
    ];

    const scales: Record<string, uPlot.Scale> = {
      x: { time: false },
    };

    visibleKeys.forEach(k => {
      scales[k] = { time: false, auto: false, range: [0, 1] }; 
    });

    const drawReferenceLines: uPlot.Plugin = {
       hooks: {
          draw: (u) => {
             const ctx = u.ctx;
             ctx.save();
             ctx.beginPath();
             ctx.rect(u.bbox.left, u.bbox.top, u.bbox.width, u.bbox.height);
             ctx.clip();

             const chState = domainsRef.current.channels;

             visibleKeys.forEach(k => {
                 const ch = chState[k];
                 if (!ch) return;
                 
                 const y0 = u.valToPos(0, k, true);
                 const yMax = u.valToPos(ch.grid_size || 1, k, true);
                 const yMin = u.valToPos(-(ch.grid_size || 1), k, true);

                 ctx.lineWidth = 1;

                 const isHovered = (k === domainsRef.current.hoveredChannelKey);
                 const isFocused = ch.focused;

                 ctx.fillStyle = isFocused ? `${ch.color}1A` : isHovered ? `${ch.color}0E` : `${ch.color}08`;
                 ctx.fillRect(u.bbox.left, Math.min(yMin, yMax), u.bbox.width, Math.abs(yMin - yMax));
                 
                 ctx.font = "9px Inter, sans-serif";
                 ctx.textBaseline = "bottom";
                 ctx.textAlign = "left";
                 const textPadding = 2;

                 const drawLabel = (txt: string, x: number, y: number, baseline: CanvasTextBaseline) => {
                     ctx.textBaseline = baseline;
                     ctx.font = isFocused ? "bold 10px Inter, sans-serif" : "9px Inter, sans-serif";
                     ctx.fillStyle = isFocused ? ch.color : isHovered ? ch.color : `${ch.color}99`;
                     ctx.fillText(txt, x, y);
                 };

                 if (yMax >= u.bbox.top && yMax <= u.bbox.top + u.bbox.height) {
                     ctx.beginPath();
                     ctx.strokeStyle = `${ch.color}50`;
                     ctx.setLineDash([4, 4]);
                     ctx.moveTo(u.bbox.left, yMax);
                     ctx.lineTo(u.bbox.left + u.bbox.width, yMax);
                     ctx.stroke();
                     drawLabel(`+${(ch.grid_size || 1).toFixed(2)}`, u.bbox.left + textPadding, yMax + textPadding, "top");
                 }

                 if (yMin >= u.bbox.top && yMin <= u.bbox.top + u.bbox.height) {
                     ctx.beginPath();
                     ctx.strokeStyle = `${ch.color}50`;
                     ctx.setLineDash([4, 4]);
                     ctx.moveTo(u.bbox.left, yMin);
                     ctx.lineTo(u.bbox.left + u.bbox.width, yMin);
                     ctx.stroke();
                     drawLabel(`-${(ch.grid_size || 1).toFixed(2)}`, u.bbox.left + textPadding, yMin - textPadding, "bottom");
                 }

                 if (y0 >= u.bbox.top && y0 <= u.bbox.top + u.bbox.height) {
                     ctx.beginPath();
                     ctx.strokeStyle = ch.focused ? `${ch.color}CC` : `${ch.color}80`;
                     ctx.setLineDash([5, 5]);
                     ctx.lineWidth = ch.focused ? 1.5 : 1;
                     ctx.moveTo(u.bbox.left, y0);
                     ctx.lineTo(u.bbox.left + u.bbox.width, y0);
                     ctx.stroke();
                     drawLabel('0.00', u.bbox.left + textPadding, y0, "middle");
                 }
             });
             
             const { t0Ratio } = domainsRef.current;
             const xPos = u.bbox.left + t0Ratio * u.bbox.width;
             const ts = u.posToVal(xPos, 'x');
             const timestamps = u.data[0];
             
             if (timestamps && timestamps.length > 0) {
                 visibleKeys.forEach((k, seriesIdx) => {
                     const ch = chState[k];
                     if (!ch) return;
                     const val = interpolateValue(ts, timestamps, u.data[seriesIdx + 1]);
                     if (val == null) return;
                     
                     const yPos = u.valToPos(val, k, true);
                     if (yPos >= u.bbox.top && yPos <= u.bbox.top + u.bbox.height) {
                         ctx.beginPath();
                         ctx.arc(xPos, yPos, 4, 0, 2 * Math.PI);
                         ctx.fillStyle = ch.color;
                         ctx.fill();
                         
                         ctx.font = "bold 11px monospace";
                         ctx.textAlign = "left";
                         ctx.textBaseline = "middle";
                         
                         const text = val.toFixed(2);
                         const m = ctx.measureText(text);
                         const rgb = hexToRgb(ch.color);
                         
                         ctx.fillStyle = `rgba(${rgb.r * 0.3}, ${rgb.g * 0.3}, ${rgb.b * 0.3}, 0.95)`;
                         ctx.fillRect(xPos + 6, yPos - 9, m.width + 8, 13);
                         
                         ctx.fillStyle = ch.color;
                         ctx.fillRect(xPos + 6, yPos - 9, 2, 13);
                         
                         ctx.fillStyle = '#ffffff';
                         ctx.fillText(text, xPos + 10, yPos);
                     }
                 });
             }

             ctx.restore();
          }
       }
    };

    const opts: uPlot.Options = {
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
      padding: [10, 90, 20, 10],
      series,
      axes: [ { show: false }, ...visibleKeys.map(k => ({ show: false, scale: k })) ],
      scales,
      cursor: {
         points: { show: false },
         drag: { x: false, y: false },
         sync: { key: 'scope' },
      },
      legend: { show: false },
      plugins: [drawReferenceLines],
      hooks: {
         setCursor: [
             (u) => {
                if (domainsRef.current.isDraggingT0) {
                    if (hoverTooltipRef.current) hoverTooltipRef.current.style.display = 'none';
                    if (hoverTimeLabelRef.current) hoverTimeLabelRef.current.style.display = 'none';
                    if (hoverRightArrowRef.current) hoverRightArrowRef.current.style.display = 'none';
                    return;
                }
                let foundKey: string | null = null;
                if (u.cursor.top !== undefined && u.cursor.top !== null && u.cursor.top >= 0) {
                    const yPhysical = u.cursor.top;
                    const chState = domainsRef.current.channels;
                    for (let i = 0; i < visibleKeys.length; i++) {
                        const k = visibleKeys[i];
                        const ch = chState[k];
                        if (!ch) continue;
                        const yMax = u.valToPos(ch.grid_size || 1, k, true);
                        const yMin = u.valToPos(-(ch.grid_size || 1), k, true);
                        const topY = Math.min(yMin, yMax);
                        const botY = Math.max(yMin, yMax);
                        if (yPhysical >= topY && yPhysical <= botY) {
                            foundKey = k;
                            break;
                        }
                    }
                }
                
                if (foundKey !== domainsRef.current.hoveredChannelKey) {
                    domainsRef.current.hoveredChannelKey = foundKey;
                    setHoveredChannelKey(foundKey);
                }

                if (u.cursor.idx == null || u.cursor.idx < 0) {
                    onHoverData(null);
                    if (hoverTooltipRef.current) hoverTooltipRef.current.style.display = 'none';
                    if (hoverTimeLabelRef.current) hoverTimeLabelRef.current.style.display = 'none';
                    if (hoverRightArrowRef.current) hoverRightArrowRef.current.style.display = 'none';
                } else {
                    const ts = u.data[0][u.cursor.idx];
                    const orig = dataRef.current.find(d => d.timestamp === ts);
                   onHoverData(orig || null);
                   
                   if (hoverTimeLabelRef.current && u.cursor.left != null) {
                       hoverTimeLabelRef.current.style.display = 'block';
                       hoverTimeLabelRef.current.style.left = `${u.bbox.left + u.cursor.left}px`;
                       const d = new Date(ts);
                       hoverTimeLabelRef.current.innerText = d.toISOString().substring(11, 23);
                   }
                   
                    // Update hover tooltip
                       if (hoverTooltipRef.current && u.cursor.left != null && u.cursor.left >= 0) {
                           const { channels: currentChannels } = domainsRef.current;
                           const k = foundKey;
                           const tsHover = u.posToVal(u.cursor.left || 0, 'x');
                           
                           if (k) {
                               if (hoverRightArrowRef.current) {
                                   hoverRightArrowRef.current.style.display = 'flex';
                                   hoverRightArrowRef.current.style.left = `${u.bbox.left + u.bbox.width}px`;
                                   hoverRightArrowRef.current.style.top = `${u.cursor.top}px`;
                                   hoverRightArrowRef.current.style.setProperty('--tooltip-color', currentChannels[k].color);
                                   
                                   const rgb = hexToRgb(currentChannels[k].color);
                                   hoverRightArrowRef.current.style.setProperty('--tooltip-bg', `rgba(${rgb.r * 0.3}, ${rgb.g * 0.3}, ${rgb.b * 0.3}, 0.95)`);
                                   
                                   const textVal = u.posToVal(u.cursor.top || 0, k).toFixed(2);
                                   if (hoverRightArrowTextRef.current) hoverRightArrowTextRef.current.textContent = textVal;
                               }
                           } else {
                               if (hoverRightArrowRef.current) hoverRightArrowRef.current.style.display = 'none';
                           }
                           
                           const seriesIdx = visibleKeys.indexOf(k || '');
                           const val = k && seriesIdx >= 0 ? interpolateValue(tsHover, u.data[0], u.data[seriesIdx + 1]) : null;
                           
                           if (k && val != null) {
                               const yVal = u.valToPos(val, k, true);
                               
                               hoverTooltipRef.current.style.display = 'block';
                               hoverTooltipRef.current.style.left = `${u.bbox.left + u.cursor.left}px`;
                               hoverTooltipRef.current.style.top = `${yVal}px`;
                               
                               const rgb = hexToRgb(currentChannels[k].color);
                               hoverTooltipRef.current.style.setProperty('--tooltip-color', currentChannels[k].color);
                               hoverTooltipRef.current.style.setProperty('--tooltip-bg', `rgba(${rgb.r * 0.3}, ${rgb.g * 0.3}, ${rgb.b * 0.3}, 0.95)`);
                               
                               if (hoverTooltipTextRef.current) {
                                   hoverTooltipTextRef.current.textContent = val.toFixed(2);
                               }
                           } else {
                               hoverTooltipRef.current.style.display = 'none';
                           }
                       }
                   }
               }
         ]
      }
    };

    if (plotRef.current) plotRef.current.destroy();
    plotRef.current = new uPlot(opts, [[], ...visibleKeys.map(()=>[])], containerRef.current);

    // Scrubber Init
    const scrubberSeries: uPlot.Series[] = [
      { label: "Time" },
      ...visibleKeys.map((k) => ({
         show: true, spanGaps: false, label: k, scale: k, stroke: channels[k].color, width: 1.5
      } as uPlot.Series))
    ];
    
    const scrubberScales: Record<string, uPlot.Scale> = { x: { time: false } };
    visibleKeys.forEach(k => {
        scrubberScales[k] = {
            time: false, auto: true,
            range: (u: uPlot, min: number, max: number) => {
               const maxAbs = Math.max(Math.abs(min), Math.abs(max));
               return maxAbs === 0 ? [-1, 1] : [-maxAbs * 1.1, maxAbs * 1.1];
            }
        };
    });

    const scrubberOpts: uPlot.Options = {
       width: scrubberContainerRef.current?.clientWidth || 0,
       height: scrubberContainerRef.current?.clientHeight || 60,
       padding: [10, 90, 10, 10], // top, right, bottom, left
       series: scrubberSeries,
       axes: [{ show: false }, ...visibleKeys.map(k => ({ show: false, scale: k }))],
       scales: scrubberScales,
       cursor: { show: false },
       legend: { show: false }
    };
    
    if (scrubberPlotRef.current) scrubberPlotRef.current.destroy();
    if (scrubberContainerRef.current) scrubberPlotRef.current = new uPlot(scrubberOpts, [[], ...visibleKeys.map(()=>[])], scrubberContainerRef.current);

    const ro = new ResizeObserver(entries => {
      for (const entry of entries) {
         if (entry.target === containerRef.current && plotRef.current) {
             plotRef.current.setSize({ width: entry.contentRect.width, height: entry.contentRect.height });
         } else if (entry.target === scrubberContainerRef.current && scrubberPlotRef.current) {
             scrubberPlotRef.current.setSize({ width: entry.contentRect.width, height: entry.contentRect.height });
         }
      }
    });
    if (containerRef.current) ro.observe(containerRef.current);
    if (scrubberContainerRef.current) ro.observe(scrubberContainerRef.current);

    const handleWheel = (e: WheelEvent) => {
        if (isDraggingLabelRef.current) return;
        const target = e.target as HTMLElement;
        if (target.classList.contains('u-over') || target.tagName.toLowerCase() === 'canvas') {
            e.preventDefault();
            const dir = e.deltaY > 0 ? 1 : -1;
            let mult = 1;
            if (e.shiftKey) mult = 10;
            if (e.altKey) mult = 0.1;
            
            const data = dataRef.current;
            let maxScale = Infinity;
            if (data && data.length > 1) {
                maxScale = Math.max(0.01, (data[data.length - 1].timestamp - data[0].timestamp) / 1000);
            }
            const factor = (dir > 0 ? 1.05 : 0.95) * (mult > 1 ? 2 : mult < 1 ? 0.5 : 1);
            setXScale(prev => Math.min(maxScale, Math.max(0.01, prev * factor)));
        }
    };
    containerRef.current.addEventListener('wheel', handleWheel, { passive: false });

    return () => {
      ro.disconnect();
      if (containerRef.current) {
          containerRef.current.removeEventListener('wheel', handleWheel);
      }
      if (plotRef.current) plotRef.current.destroy();
      plotRef.current = null;
      if (scrubberPlotRef.current) scrubberPlotRef.current.destroy();
      scrubberPlotRef.current = null;
    };
  }, [configHash]); // recreate when visible channels or their focused/colors change

  useEffect(() => {
    if (!plotRef.current) return;
    visibleKeys.forEach((k, idx) => {
        const ch = channels[k];
        if (ch) {
            const s = plotRef.current!.series[idx + 1];
            if (s) {
                s.width = ch.focused ? 2.5 : 1.5;
            }
        }
    });
  }, [channels, visibleKeys.join('|')]);

  useEffect(() => {
    let animId: number;
    const loop = () => {
       if (plotRef.current && dataRef.current) {
          const data = dataRef.current;
          const { xScale, xOffset, isPaused, channels: chState, t0Ratio } = domainsRef.current;
          
          if (data.length > 0) {
             const now = Date.now();
             const maxTs = data[data.length - 1].timestamp;
             const targetTs = (isPaused ? maxTs : now) - xOffset * 1000;
             const xMin = targetTs - t0Ratio * xScale * 1000;
             const xMax = targetTs + (1 - t0Ratio) * xScale * 1000;
             
             if (t0LabelRef.current) {
                 const d = new Date(targetTs);
                 t0LabelRef.current.innerText = d.toISOString().substring(11, 23); // HH:MM:SS.mmm
             }
             
             plotRef.current.setScale('x', { min: xMin, max: xMax });
             visibleKeys.forEach(k => {
                 const ch = chState[k];
                 if (!ch) return;
                 const ys = ch.y_scale;
                 const yo = ch.y_offset;
                 plotRef.current!.setScale(k, { min: yo - ys/2, max: yo + ys/2 });
             });

             const cols: number[][] = [ [] ];
             const scrubberCols: number[][] = [ [] ];
             visibleKeys.forEach(() => {
                 cols.push([]);
                 scrubberCols.push([]);
             });

             for (let i = 0; i < data.length; i++) {
                const d = data[i];
                const inView = d.timestamp >= xMin - 1000 && d.timestamp <= xMax + 1000;
                
                scrubberCols[0].push(d.timestamp);
                if (inView) cols[0].push(d.timestamp);
                
                for (let j = 0; j < visibleKeys.length; j++) {
                   const val = d[visibleKeys[j]];
                   const safeVal = val !== undefined ? val : null as unknown as number;
                   
                   scrubberCols[j + 1].push(safeVal);
                   if (inView) cols[j + 1].push(safeVal);
                }
             }
             plotRef.current.setData(cols as uPlot.AlignedData);
             if (scrubberPlotRef.current && scrubberCols[0].length > 0) {
                 const sMin = scrubberCols[0][0];
                 const sMax = isPaused ? maxTs : now;
                 
                 scrubberPlotRef.current.setScale('x', { min: sMin, max: sMax });
                 scrubberPlotRef.current.setData(scrubberCols as uPlot.AlignedData);
                 
                 // Update overlay
                 if (scrubberOverlayRef.current) {
                     const globalRange = sMax - sMin;
                     if (globalRange > 0) {
                         const leftPct = Math.max(0, (xMin - sMin) / globalRange) * 100;
                         const rightPct = Math.min(1, (xMax - sMin) / globalRange) * 100;
                         const widthPct = Math.max(0, rightPct - leftPct);
                         
                         scrubberOverlayRef.current.style.left = `${leftPct}%`;
                         scrubberOverlayRef.current.style.width = `${widthPct}%`;
                     }
                 }
             }
             if (lastMousePos.current && containerRef.current) {
                 const over = containerRef.current.querySelector('.u-over');
                 if (over) {
                     const rect = over.getBoundingClientRect();
                     if (
                         lastMousePos.current.x >= rect.left && lastMousePos.current.x <= rect.right &&
                         lastMousePos.current.y >= rect.top && lastMousePos.current.y <= rect.bottom
                     ) {
                         over.dispatchEvent(new MouseEvent('mousemove', {
                             clientX: lastMousePos.current.x,
                             clientY: lastMousePos.current.y,
                             bubbles: true
                         }));
                     }
                 }
             }
          }
       }
       animId = requestAnimationFrame(loop);
    };
    animId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animId);
  }, [visibleKeys.join(',')]);

  const [isDraggingT0, setIsDraggingT0] = useState(false);

  useEffect(() => {
     domainsRef.current.isDraggingT0 = isDraggingT0;
  }, [isDraggingT0]);

  return (
    <div className="flex flex-col w-full h-full relative p-2 pt-0 bg-background text-foreground overflow-hidden">
      <ResizablePanelGroup orientation="vertical" className="h-full w-full">
        <ResizablePanel defaultSize={85} minSize={50} className="relative flex flex-col overflow-hidden border-b">
          <div 
             ref={containerRef} 
             className={`w-full h-full relative ${isDraggingT0 ? '[&_.u-cursor-x]:hidden [&_.u-cursor-y]:hidden' : ''}`}
             onPointerDown={(e) => {
               const target = e.target as HTMLElement;
               if (target.classList.contains('u-over') || target.tagName.toLowerCase() === 'canvas') {
                   const container = containerRef.current;
                   if (!container) return;
                   
                   const startX = e.clientX;
                   const startOffset = domainsRef.current.xOffset;
                   let isDragging = false;
                   
                   container.setPointerCapture(e.pointerId);
                   
                   const move = (ev: PointerEvent) => {
                       const dx = ev.clientX - startX;
                       if (Math.abs(dx) > 8) {
                           isDragging = true;
                           wasPanningRef.current = true;
                       }
                       if (isDragging) {
                           const shiftSeconds = (dx / container.clientWidth) * domainsRef.current.xScale;
                           setXOffset(Math.max(0, startOffset + shiftSeconds));
                       }
                   };
                   
                   const up = (ev: PointerEvent) => {
                        container.removeEventListener('pointermove', move);
                        container.removeEventListener('pointerup', up);
                        container.releasePointerCapture(ev.pointerId);
                        
                        if (!isDragging) {
                            const now = Date.now();
                            const last = domainsRef.current.lastClick || { time: 0, x: 0, y: 0 };
                            const isDbl = (now - last.time < 400) && 
                                          Math.abs(ev.clientX - last.x) < 10 && 
                                          Math.abs(ev.clientY - last.y) < 10;
                            
                            if (isDbl) {
                                const rect = container.getBoundingClientRect();
                                const dataX = (ev.clientX - rect.left) - 10;
                                const dataWidth = rect.width - 100;
                                const pct = Math.max(0.01, Math.min(0.99, dataX / dataWidth));
                                const startRatio = domainsRef.current.t0Ratio;
                                setT0Ratio(pct);
                                setXOffset(startOffset + (startRatio - pct) * domainsRef.current.xScale);
                                domainsRef.current.lastClick = { time: 0, x: 0, y: 0 };
                            } else {
                                domainsRef.current.lastClick = { time: now, x: ev.clientX, y: ev.clientY };
                                const k = domainsRef.current.hoveredChannelKey;
                                if (k) {
                                    setChannels(prev => {
                                        const next = { ...prev };
                                        Object.keys(next).forEach(key => next[key] = { ...next[key], focused: false });
                                        next[k] = { ...next[k], focused: true };
                                        return next;
                                    });
                                }
                            }
                        } else {
                            setTimeout(() => { wasPanningRef.current = false; }, 100);
                        }
                   };
                   
                   container.addEventListener('pointermove', move);
                   container.addEventListener('pointerup', up);
               }
             }}
          >
         {/* T0 Center Line for Main Plot */}
         <div 
             className="absolute top-0 bottom-0 w-[1px] border-l-2 border-dashed border-primary/50 z-20 flex flex-col items-center cursor-ew-resize pointer-events-auto"
             style={{ left: `calc(10px + ${t0Ratio} * calc(100% - 100px))` }}
                 onPointerDown={(e) => {
                 e.stopPropagation();
                 const target = e.target as HTMLElement;
                 target.setPointerCapture(e.pointerId);
                 
                 const startRatio = domainsRef.current.t0Ratio;
                 const startOffset = domainsRef.current.xOffset;
                 
                 setIsDraggingT0(true);
                 
                 const move = (ev: React.PointerEvent | PointerEvent) => {
                     if (!containerRef.current) return;
                     const rect = containerRef.current.getBoundingClientRect();
                     const dataX = (ev.clientX - rect.left) - 10;
                     const dataWidth = rect.width - 100;
                     const pct = Math.max(0.01, Math.min(0.99, dataX / dataWidth));
                     setT0Ratio(pct);
                     setXOffset(startOffset + (startRatio - pct) * domainsRef.current.xScale);
                 };
                 
                 const moveGlobal = (ev: PointerEvent) => move(ev);
                 const up = (ev: PointerEvent) => {
                     target.releasePointerCapture(ev.pointerId);
                     target.removeEventListener('pointermove', moveGlobal);
                     target.removeEventListener('pointerup', up);
                     setIsDraggingT0(false);
                 };
                 target.addEventListener('pointermove', moveGlobal);
                 target.addEventListener('pointerup', up);
             }}
         >
            <div ref={t0LabelRef} className="absolute bottom-1 bg-black text-white text-[10px] px-1 py-[2px] rounded-sm font-mono font-bold whitespace-nowrap shadow-sm border border-primary/20 select-none -translate-x-[50%]">T0</div>
         </div>
         
         {/* Hover Timestamp Label (Top) */}
         <div 
             ref={hoverTimeLabelRef} 
             className={`absolute hidden top-1 z-30 bg-black text-white text-[10px] px-1 py-[2px] rounded-sm font-mono font-bold whitespace-nowrap shadow-sm border border-primary/20 -translate-x-[50%] select-none pointer-events-none ${isDraggingT0 ? 'opacity-0' : ''}`}
         />
         
         {/* Hover Tooltip */}
         <div 
             ref={hoverTooltipRef} 
             className={`absolute hidden z-30 pointer-events-none ${isDraggingT0 ? 'opacity-0' : ''}`}
         >
             <div className="absolute w-2 h-2 rounded-full -translate-x-[4px] -translate-y-[4px]" style={{ backgroundColor: 'var(--tooltip-color)' }} />
             <div className="absolute left-[6px] -translate-y-[50%] px-1 py-[2px] text-white text-[11px] font-mono font-bold shadow whitespace-nowrap" 
                  style={{ backgroundColor: 'var(--tooltip-bg)', borderLeft: '2px solid var(--tooltip-color)' }}>
                 <span ref={hoverTooltipTextRef}></span>
             </div>
         </div>
         
         {/* Hover Right Arrow Y-Label */}
         <div 
             ref={hoverRightArrowRef} 
             className={`absolute hidden z-30 pointer-events-none items-center -translate-y-[50%] ${isDraggingT0 ? 'opacity-0' : ''}`}
         >
             <div className="w-0 h-0 border-y-[6px] border-y-transparent border-r-[6px]" style={{ borderRightColor: 'var(--tooltip-bg)' }} />
             <div className="px-1 py-[2px] text-white text-[10px] font-mono font-bold shadow-sm rounded-r-sm whitespace-nowrap" style={{ backgroundColor: 'var(--tooltip-bg)', borderLeft: '2px solid var(--tooltip-color)' }}>
                 <span ref={hoverRightArrowTextRef}></span>
             </div>
         </div>
         
         {visibleKeys.map((k) => {
           const ch = channels[k];
           const scale = ch.y_scale;
           const offset = ch.y_offset;
           const min = offset - scale / 2;
           const max = offset + scale / 2;
           
           // Where does Y=0 fall on the screen physically?
           // min maps to 0% (bottom of screen), max maps to 100% (top of screen).
           // However, css bottom is used.
           // Value 0 is at percentage: (0 - min) / (max - min)
           const pct = max === min ? 0.5 : (0 - min) / (max - min);
           if (pct < -1 || pct > 2) return null; 
           const bottom = pct * 100;

           return (
              <div key={k} className="absolute left-0 right-0 h-[1px] pointer-events-none z-10" style={{ bottom: `${bottom}%` }}>
                 <div 
                      className="absolute left-[-30px] translate-y-[8px] pointer-events-auto cursor-ns-resize"
                      onWheel={(ev) => {
                          ev.stopPropagation();
                          ev.preventDefault();
                          const dir = ev.deltaY > 0 ? -1 : 1;
                          let mult = 1;
                          if (ev.shiftKey) mult = 10;
                          if (ev.altKey) mult = 0.1;
                          
                          // Channel scale zooming 5x slower (2% change instead of 10%)
                          const factor = (dir < 0 ? 1.02 : 0.98) * (mult > 1 ? 1.5 : mult < 1 ? 0.75 : 1);
                          setChannels(prev => {
                              const oldScale = prev[k].y_scale;
                              const newScale = Math.max(0.0001, oldScale * factor);
                              return {
                                  ...prev,
                                  [k]: {
                                      ...prev[k],
                                      y_scale: newScale,
                                      y_offset: (prev[k].y_offset / oldScale) * newScale
                                  }
                              };
                          });
                      }}
                      onPointerDown={(e) => {
                          e.stopPropagation();
                          setChannels(prev => {
                              const next = {...prev};
                              Object.keys(next).forEach(key => next[key] = {...next[key], focused: false});
                              next[k] = {...next[k], focused: true};
                              return next;
                          });
                          
                          let isDragging = true;
                          isDraggingLabelRef.current = true;
                          const move = (ev: PointerEvent) => { 
                              if(isDragging) {
                                  const H = containerRef.current?.clientHeight || 400;
                                  const chLive = domainsRef.current.channels[k];
                                  const dyUnits = (ev.movementY / H) * chLive.y_scale;
                                  setChannels(prev => ({
                                      ...prev,
                                      [k]: { ...prev[k], y_offset: prev[k].y_offset + dyUnits }
                                  }));
                              }
                          };
                          const up = () => {
                              isDragging = false;
                              isDraggingLabelRef.current = false;
                              document.removeEventListener('pointermove', move);
                              document.removeEventListener('pointerup', up);
                          };
                          document.addEventListener('pointermove', move);
                          document.addEventListener('pointerup', up);
                      }}
                      onMouseEnter={() => setHoveredChannelKey(k)}
                      onMouseLeave={() => setHoveredChannelKey(prev => prev === k ? null : prev)}>
                      <svg width="22" height="16" style={{ transform: 'translateY(-16px)' }}>
                         {ch.focused ? (
                            <polygon points="0,0 16,0 22,8 16,16 0,16" fill={ch.color} />
                         ) : (
                            <polygon points="0,0 16,0 22,8 16,16 0,16" fill="var(--background)" stroke={ch.color} strokeWidth={1.5} />
                         )}
                         <text x={9} y={11} fill={ch.focused ? '#000' : ch.color} fontSize={9} fontWeight="bold" textAnchor="middle" style={{ pointerEvents: 'none' }}>
                             {k.split('.').pop()?.substring(0, 2).toUpperCase()}
                         </text>
                      </svg>
                 </div>
               </div>
            );
        })}
      </div>
      </ResizablePanel>
        
        <ResizableHandle withHandle className="h-1 bg-border cursor-row-resize hover:bg-muted-foreground/30 transition-colors shrink-0" />
        
        {/* Scrubber Plot */}
        <ResizablePanel defaultSize={15} minSize={10} className="relative flex flex-col bg-background">
          <div 
             className="w-full h-full shrink-0 bg-muted/20 relative rounded overflow-hidden" 
             onPointerDown={(e) => {
                 e.preventDefault();
                 const target = e.target as HTMLElement;
                 target.setPointerCapture(e.pointerId);
                 
                 const move = (ev: React.PointerEvent | PointerEvent) => {
                     if (!scrubberContainerRef.current || !dataRef.current || dataRef.current.length === 0) return;
                     const rect = scrubberContainerRef.current.getBoundingClientRect();
                     const pct = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width));
                     
                     const globalMinTs = dataRef.current[0].timestamp;
                     const globalMaxTs = dataRef.current[dataRef.current.length - 1].timestamp;
                     const globalRange = globalMaxTs - globalMinTs;
                     
                     const targetCenterTs = globalMinTs + pct * globalRange;
                     const { isPaused } = domainsRef.current;
                     const now = Date.now();
                     const maxTs = isPaused ? globalMaxTs : now;
                     
                     const newOffset = (maxTs - targetCenterTs) / 1000;
                     setXOffset(Math.max(0, newOffset));
                 };
                 move(e);
                 
                 const moveGlobal = (ev: PointerEvent) => move(ev);
                 const up = (ev: PointerEvent) => {
                     target.releasePointerCapture(ev.pointerId);
                     target.removeEventListener('pointermove', moveGlobal);
                     target.removeEventListener('pointerup', up);
                 };
                 target.addEventListener('pointermove', moveGlobal);
                 target.addEventListener('pointerup', up);
             }}
             onWheel={(e) => {
                 e.preventDefault();
                 // Zoom out if wheel down, zoom in if wheel up
                 const dir = e.deltaY > 0 ? 1 : -1;
                 let mult = 1;
                 if (e.shiftKey) mult = 10;
                 if (e.altKey) mult = 0.1;
                 
                 // Scale zoom factor
                 const data = dataRef.current;
                 let maxScale = Infinity;
                 if (data && data.length > 1) {
                     maxScale = Math.max(0.01, (data[data.length - 1].timestamp - data[0].timestamp) / 1000);
                 }
                 const factor = (dir > 0 ? 1.05 : 0.95) * (mult > 1 ? 2 : mult < 1 ? 0.5 : 1);
                 setXScale(prev => Math.min(maxScale, Math.max(0.01, prev * factor)));
             }}
          >
             <div ref={scrubberContainerRef} className="w-full h-full relative pointer-events-none" />
             {/* Viewport Overlay */}
             <div 
                 ref={scrubberOverlayRef} 
                 className="absolute top-0 bottom-0 bg-primary/20 border-x-2 border-primary/50 pointer-events-none transition-none shadow-[0_0_0_9999px_rgba(0,0,0,0.5)]" 
             >
                 {/* T0 Center Line for Scrubber */}
                 <div className="absolute top-0 bottom-0 w-[1px] border-l border-dashed border-primary/70" style={{ left: `calc(10px + ${t0Ratio} * calc(100% - 100px))` }} />
             </div>
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}
