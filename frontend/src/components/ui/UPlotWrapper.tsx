import React, { useEffect, useRef } from 'react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';

interface UPlotWrapperProps {
  options: uPlot.Options;
  data: uPlot.AlignedData;
}

export function UPlotWrapper({ options, data }: UPlotWrapperProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const plotRef = useRef<uPlot | null>(null);

  useEffect(() => {
    if (containerRef.current) {
      if (!plotRef.current) {
        plotRef.current = new uPlot(options, data, containerRef.current);
      } else {
        plotRef.current.setData(data);
      }
    }
    
    // Cleanup on unmount or options change
    return () => {
      // In a real implementation we might just update data
      // but if options change drastically we might need to recreate.
      // For now, we rely on setData.
    };
  }, [options, data]);

  return <div ref={containerRef} className="w-full h-full" />;
}
