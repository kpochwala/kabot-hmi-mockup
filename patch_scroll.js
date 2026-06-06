const fs = require('fs');
let code = fs.readFileSync('frontend/src/app/page.tsx', 'utf8');

const oldArrowLabel = `const CustomArrowLabel = (props: any) => {
    const { viewBox, color, isActive, text, onClick, onDrag } = props;
    if (!viewBox) return null;
    const { x, y } = viewBox;

    const handlePointerDown = (e: React.PointerEvent<SVGGElement>) => {
        e.stopPropagation();
        if (onClick) onClick();
        
        const target = e.currentTarget;
        target.requestPointerLock();
        
        const moveHandler = (moveEvent: PointerEvent) => {
            if (document.pointerLockElement === target) {
                if (onDrag) onDrag(moveEvent.movementY);
            }
        };
        
        const upHandler = () => {
            document.exitPointerLock();
            document.removeEventListener('pointermove', moveHandler);
            document.removeEventListener('pointerup', upHandler);
        };
        
        document.addEventListener('pointermove', moveHandler);
        document.addEventListener('pointerup', upHandler);
    };

    return (
       <g transform={\`translate(\${x - 30}, \${y - 8})\`} onPointerDown={handlePointerDown} style={{ cursor: 'ns-resize', pointerEvents: 'auto' }}>
          {isActive ? (
             <polygon points="0,0 16,0 22,8 16,16 0,16" fill={color} />
          ) : (
             <polygon points="0,0 16,0 22,8 16,16 0,16" fill="var(--background)" stroke={color} strokeWidth={1.5} />
          )}
          <text x={9} y={11} fill={isActive ? '#000' : color} fontSize={9} fontWeight="bold" textAnchor="middle" style={{ pointerEvents: 'none' }}>
              {text.split('.').pop().substring(0, 2).toUpperCase()}
          </text>
       </g>
    );
};`;

const newArrowLabel = `const CustomArrowLabel = (props: any) => {
    const { viewBox, color, isActive, text, onClick, onDrag, onScroll } = props;
    if (!viewBox) return null;
    const { x, y } = viewBox;

    const handlePointerDown = (e: React.PointerEvent<SVGGElement>) => {
        e.stopPropagation();
        if (onClick) onClick();
        
        const target = e.currentTarget;
        target.requestPointerLock();
        
        const moveHandler = (moveEvent: PointerEvent) => {
            if (document.pointerLockElement === target) {
                if (onDrag) onDrag(moveEvent.movementY);
            }
        };

        const wheelHandler = (wheelEvent: WheelEvent) => {
            if (document.pointerLockElement === target) {
                wheelEvent.preventDefault();
                const direction = wheelEvent.deltaY > 0 ? -1 : 1;
                let multiplier = 1;
                if (wheelEvent.shiftKey) multiplier = 10;
                if (wheelEvent.altKey) multiplier = 0.1;
                if (onScroll) onScroll(direction, multiplier);
            }
        };
        
        const upHandler = () => {
            document.exitPointerLock();
            document.removeEventListener('pointermove', moveHandler);
            document.removeEventListener('pointerup', upHandler);
            document.removeEventListener('wheel', wheelHandler);
        };
        
        document.addEventListener('pointermove', moveHandler);
        document.addEventListener('wheel', wheelHandler, { passive: false });
        document.addEventListener('pointerup', upHandler);
    };

    return (
       <g transform={\`translate(\${x - 30}, \${y - 8})\`} onPointerDown={handlePointerDown} style={{ cursor: 'ns-resize', pointerEvents: 'auto' }}>
          {isActive ? (
             <polygon points="0,0 16,0 22,8 16,16 0,16" fill={color} />
          ) : (
             <polygon points="0,0 16,0 22,8 16,16 0,16" fill="var(--background)" stroke={color} strokeWidth={1.5} />
          )}
          <text x={9} y={11} fill={isActive ? '#000' : color} fontSize={9} fontWeight="bold" textAnchor="middle" style={{ pointerEvents: 'none' }}>
              {text.split('.').pop().substring(0, 2).toUpperCase()}
          </text>
       </g>
    );
};`;

code = code.replace(oldArrowLabel, newArrowLabel);

const oldRefLine = `label={<CustomArrowLabel color={color} isActive={isActive} text={key} onClick={() => setActiveYChannel(key)} onDrag={(dy: number) => setYOffset(p => ({...p, [key]: (p[key] || 0) + dy * 0.05}))} />}`;

const newRefLine = `label={<CustomArrowLabel color={color} isActive={isActive} text={key} onClick={() => setActiveYChannel(key)} onDrag={(dy: number) => setYOffset(p => ({...p, [key]: (p[key] || 0) + dy * 0.05}))} onScroll={(dir: number, mult: number) => setYScale(p => ({...p, [key]: Math.max(0.001, (p[key] ?? 1) + dir * 0.1 * mult)}))} />}`;

code = code.replace(oldRefLine, newRefLine);

fs.writeFileSync('frontend/src/app/page.tsx', code);
