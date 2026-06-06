import React, { useRef, useState, useEffect } from "react";
import { cn } from "@/lib/utils";

interface KnobProps {
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (val: number) => void;
  label: string;
  unit?: string;
  className?: string;
}

export function Knob({ value, min, max, step = 1, onChange, label, unit, className }: KnobProps) {
  const knobRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const startYRef = useRef(0);
  const startValRef = useRef(0);

  useEffect(() => {
    const handlePointerMove = (e: PointerEvent) => {
      if (!isDragging) return;
      const deltaY = startYRef.current - e.clientY;
      const range = max - min;
      let val = startValRef.current + (deltaY / 100) * range;
      if (step) val = Math.round(val / step) * step;
      val = Math.max(min, Math.min(max, val));
      onChange(val);
    };

    const handlePointerUp = () => {
      if (isDragging) {
        setIsDragging(false);
        document.body.style.cursor = 'default';
      }
    };

    if (isDragging) {
      window.addEventListener("pointermove", handlePointerMove);
      window.addEventListener("pointerup", handlePointerUp);
    }
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, [isDragging, min, max, step, onChange]);

  const percentage = (value - min) / (max - min);
  const degrees = -135 + percentage * 270;

  return (
    <div className={cn("flex flex-col items-center gap-1 select-none", className)}>
      <div 
        ref={knobRef}
        className="w-10 h-10 rounded-full border-2 border-border bg-muted relative shadow-sm cursor-ns-resize touch-none active:scale-95 transition-transform"
        onPointerDown={(e) => {
          setIsDragging(true);
          startYRef.current = e.clientY;
          startValRef.current = value;
          document.body.style.cursor = 'ns-resize';
        }}
        onWheel={(e) => {
          e.preventDefault();
          const dir = Math.sign(e.deltaY);
          let val = value - (dir * step);
          val = Math.max(min, Math.min(max, val));
          onChange(val);
        }}
      >
        <div 
          className="absolute w-1 h-3 bg-primary rounded-full left-1/2 top-1 origin-[50%_16px]"
          style={{ transform: `translateX(-50%) rotate(${degrees}deg)` }}
        />
      </div>
      <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">{label}</div>
      <div className="text-xs font-mono font-medium">
        {value.toFixed(step < 1 ? 2 : 0)}{unit ? ` ${unit}` : ''}
      </div>
    </div>
  );
}
