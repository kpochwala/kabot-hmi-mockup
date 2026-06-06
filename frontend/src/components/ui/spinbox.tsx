"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface SpinBoxProps {
  label?: string;
  unit?: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
  className?: string;
}

export function SpinBox({ label, unit, value, min, max, step, onChange, className }: SpinBoxProps) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const isDragging = React.useRef(false);
  const [internalValue, setInternalValue] = React.useState(value);

  React.useEffect(() => {
    setInternalValue(value);
  }, [value]);

  const handlePointerDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return; // Only left click
    e.preventDefault();
    if (!containerRef.current) return;
    
    isDragging.current = true;
    
  };

  React.useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) return;
      
      const delta = -e.movementY; // negative movementY is moving mouse UP
      if (delta === 0) return;
      
      // Calculate change proportional to step
      // A movement of 5 pixels might equal 1 step, to make it smooth but controllable
      const multiplier = e.shiftKey ? 10 : (e.altKey ? 0.1 : 1);
      const stepsToMove = delta * 0.1 * multiplier; 
      
      setInternalValue((prev) => {
        let next = prev + stepsToMove * step;
        next = Math.round(next / step) * step; // lock to step grid
        next = Math.max(min, Math.min(max, next));
        if (next !== prev) {
            onChange(next);
        }
        return next;
      });
    };

    const handleMouseUp = () => {
      if (isDragging.current) {
        isDragging.current = false;
        
      }
    };

    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
          };
  }, [min, max, step, onChange]);

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const dir = e.deltaY > 0 ? -1 : 1;
    let next = internalValue + dir * step;
    next = Math.round(next / step) * step;
    next = Math.max(min, Math.min(max, next));
    setInternalValue(next);
    onChange(next);
  };

  return (
    <div 
       className={cn("flex flex-col items-center justify-center gap-1", className)}
       title="Drag up/down or use scroll wheel"
    >
      {label && <span className="text-[10px] font-bold uppercase text-muted-foreground tracking-wider">{label}</span>}
      <div 
        ref={containerRef}
        onPointerDown={handlePointerDown}
        onWheel={handleWheel}
        className="h-7 w-20 bg-muted/30 border border-border/50 rounded flex items-center justify-center cursor-ns-resize hover:bg-muted/50 hover:border-primary/50 transition-colors"
      >
        <span className="font-mono text-xs font-medium text-foreground select-none">
            {internalValue.toFixed(step < 1 ? 1 : 0)}
            {unit && <span className="text-[10px] text-muted-foreground ml-1">{unit}</span>}
        </span>
      </div>
    </div>
  );
}
