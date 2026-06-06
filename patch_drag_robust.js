const fs = require('fs');
let code = fs.readFileSync('frontend/src/app/page.tsx', 'utf8');

const oldHandlePointerDown = `const handlePointerDown = (e: React.PointerEvent<SVGGElement>) => {
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
    };`;

const newHandlePointerDown = `const handlePointerDown = (e: React.PointerEvent<SVGGElement>) => {
        e.stopPropagation();
        if (onClick) onClick();
        
        const target = e.currentTarget;
        try { target.requestPointerLock(); } catch (err) {}
        
        let isDragging = true;
        
        const moveHandler = (moveEvent: PointerEvent) => {
            if (isDragging) {
                if (onDrag) onDrag(moveEvent.movementY);
            }
        };

        const wheelHandler = (wheelEvent: WheelEvent) => {
            if (isDragging) {
                wheelEvent.preventDefault();
                const direction = wheelEvent.deltaY > 0 ? -1 : 1;
                let multiplier = 1;
                if (wheelEvent.shiftKey) multiplier = 10;
                if (wheelEvent.altKey) multiplier = 0.1;
                if (onScroll) onScroll(direction, multiplier);
            }
        };
        
        const upHandler = () => {
            isDragging = false;
            try { document.exitPointerLock(); } catch (err) {}
            document.removeEventListener('pointermove', moveHandler);
            document.removeEventListener('pointerup', upHandler);
            document.removeEventListener('wheel', wheelHandler);
        };
        
        document.addEventListener('pointermove', moveHandler);
        document.addEventListener('wheel', wheelHandler, { passive: false });
        document.addEventListener('pointerup', upHandler);
    };`;

code = code.replace(oldHandlePointerDown, newHandlePointerDown);
fs.writeFileSync('frontend/src/app/page.tsx', code);
