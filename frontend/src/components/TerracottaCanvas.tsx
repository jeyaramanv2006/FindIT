import React, { useEffect, useRef } from 'react';

interface TerracottaCanvasProps {
  isSearching?: boolean;
  pulseTrigger?: number;
}

export const TerracottaCanvas: React.FC<TerracottaCanvasProps> = ({ isSearching, pulseTrigger }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const pulseRef = useRef<number>(0);

  useEffect(() => {
    if (pulseTrigger) {
      pulseRef.current = 1.0;
    }
  }, [pulseTrigger]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width = 0;
    let height = 0;
    let dpr = 1;
    let animationFrameId: number;
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

    function resize() {
      if (!canvas || !ctx) return;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    window.addEventListener('resize', resize);
    resize();

    const mouse = {
      x: width * 0.5,
      y: height * 0.5,
      targetX: width * 0.5,
      targetY: height * 0.5,
    };

    const handleMouseMove = (e: MouseEvent) => {
      mouse.targetX = e.clientX;
      mouse.targetY = e.clientY;
    };
    window.addEventListener('mousemove', handleMouseMove, { passive: true });

    let speedMultiplier = 1.0;
    const targetSpeedMultiplier = isSearching ? 1.8 : 1.0;
    let t = 0;

    // Marching squares algorithm for smooth organic serpentine contours
    function getSegments(field: Float32Array, nx: number, ny: number, cellW: number, cellH: number, iso: number) {
      const segments: [[number, number], [number, number]][] = [];
      for (let j = 0; j < ny - 1; j++) {
        for (let i = 0; i < nx - 1; i++) {
          const v0 = field[j * nx + i] >= iso ? 1 : 0;
          const v1 = field[j * nx + (i + 1)] >= iso ? 1 : 0;
          const v2 = field[(j + 1) * nx + (i + 1)] >= iso ? 1 : 0;
          const v3 = field[(j + 1) * nx + i] >= iso ? 1 : 0;
          const code = (v0 << 3) | (v1 << 2) | (v2 << 1) | v3;
          if (code === 0 || code === 15) continue;

          const val0 = field[j * nx + i];
          const val1 = field[j * nx + (i + 1)];
          const val2 = field[(j + 1) * nx + (i + 1)];
          const val3 = field[(j + 1) * nx + i];

          const topT = Math.max(0, Math.min(1, (iso - val0) / (val1 - val0 || 0.0001)));
          const rightT = Math.max(0, Math.min(1, (iso - val1) / (val2 - val1 || 0.0001)));
          const bottomT = Math.max(0, Math.min(1, (iso - val3) / (val2 - val3 || 0.0001)));
          const leftT = Math.max(0, Math.min(1, (iso - val0) / (val3 - val0 || 0.0001)));

          const pTop: [number, number] = [(i + topT) * cellW, j * cellH];
          const pRight: [number, number] = [(i + 1) * cellW, (j + rightT) * cellH];
          const pBottom: [number, number] = [(i + bottomT) * cellW, (j + 1) * cellH];
          const pLeft: [number, number] = [i * cellW, (j + leftT) * cellH];

          switch (code) {
            case 1: segments.push([pLeft, pBottom]); break;
            case 2: segments.push([pBottom, pRight]); break;
            case 3: segments.push([pLeft, pRight]); break;
            case 4: segments.push([pTop, pRight]); break;
            case 5: segments.push([pTop, pLeft], [pBottom, pRight]); break;
            case 6: segments.push([pTop, pBottom]); break;
            case 7: segments.push([pTop, pLeft]); break;
            case 8: segments.push([pTop, pLeft]); break;
            case 9: segments.push([pTop, pBottom]); break;
            case 10: segments.push([pTop, pRight], [pLeft, pBottom]); break;
            case 11: segments.push([pTop, pRight]); break;
            case 12: segments.push([pLeft, pRight]); break;
            case 13: segments.push([pBottom, pRight]); break;
            case 14: segments.push([pLeft, pBottom]); break;
          }
        }
      }
      return segments;
    }

    const isoLevels = [
      { iso: -1.35, color: 'rgba(237, 227, 212, 0.55)', width: 8.5 },
      { iso: -0.85, color: 'rgba(184, 74, 57, 0.18)', width: 5.5 },
      { iso: -0.40, color: 'rgba(158, 47, 43, 0.28)', width: 3.2 },
      { iso:  0.00, color: 'rgba(184, 74, 57, 0.24)', width: 4.8 },
      { iso:  0.45, color: 'rgba(237, 227, 212, 0.65)', width: 9.0 },
      { iso:  0.85, color: 'rgba(158, 47, 43, 0.26)', width: 3.5 },
      { iso:  1.30, color: 'rgba(184, 74, 57, 0.20)', width: 5.0 },
    ];

    function draw() {
      if (!ctx) return;
      ctx.clearRect(0, 0, width, height);

      // Warm ivory base background
      ctx.fillStyle = '#F8F4EC';
      ctx.fillRect(0, 0, width, height);

      speedMultiplier += (targetSpeedMultiplier - speedMultiplier) * 0.05;
      mouse.x += (mouse.targetX - mouse.x) * 0.05;
      mouse.y += (mouse.targetY - mouse.y) * 0.05;

      if (pulseRef.current > 0.001) {
        pulseRef.current *= 0.94;
      } else {
        pulseRef.current = 0;
      }

      if (!prefersReducedMotion.matches) {
        t += 0.0042 * speedMultiplier;
      }

      const cellW = 28;
      const cellH = 28;
      const nx = Math.ceil(width / cellW) + 2;
      const ny = Math.ceil(height / cellH) + 2;
      const field = new Float32Array(nx * ny);

      const mxNorm = mouse.x / width;
      const myNorm = mouse.y / height;

      for (let j = 0; j < ny; j++) {
        const y = (j * cellH) / 190;
        for (let i = 0; i < nx; i++) {
          const x = (i * cellW) / 190;

          let v = Math.sin(x * 1.15 + t * 0.7) * Math.cos(y * 1.15 - t * 0.55);
          v += Math.sin((x + y) * 0.88 + t * 0.5) * 0.85;
          v += Math.cos(x * 0.75 - y * 1.05 + t * 0.62) * 0.75;
          v += Math.sin(Math.sqrt(x * x + y * y) * 1.1 - t * 0.9) * 0.45;

          const dx = (i * cellW) / width - mxNorm;
          const dy = (j * cellH) / height - myNorm;
          const distSq = dx * dx + dy * dy;
          if (distSq < 0.16) {
            const factor = 1 - Math.sqrt(distSq) / 0.4;
            v += Math.sin(factor * Math.PI) * 0.35;
          }

          if (pulseRef.current > 0.001) {
            v += Math.sin(x * 2.0 + y * 2.0 - t * 4.0) * 0.3 * pulseRef.current;
          }

          field[j * nx + i] = v;
        }
      }

      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';

      isoLevels.forEach((lvl) => {
        const segs = getSegments(field, nx, ny, cellW, cellH, lvl.iso);
        if (segs.length === 0) return;

        ctx.beginPath();
        for (let s = 0; s < segs.length; s++) {
          const p0 = segs[s][0];
          const p1 = segs[s][1];
          ctx.moveTo(p0[0], p0[1]);
          ctx.lineTo(p1[0], p1[1]);
        }
        ctx.strokeStyle = lvl.color;
        ctx.lineWidth = lvl.width;
        ctx.stroke();
      });

      animationFrameId = requestAnimationFrame(draw);
    }

    animationFrameId = requestAnimationFrame(draw);

    return () => {
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', handleMouseMove);
      cancelAnimationFrame(animationFrameId);
    };
  }, [isSearching]);

  return (
    <>
      <canvas
        ref={canvasRef}
        id="kinetic-terracotta-canvas"
        aria-hidden="true"
        className="fixed inset-0 pointer-events-none z-0 w-full h-full"
      />
      {/* Radial Warm Ivory Reading Veil for center contrast */}
      <div
        aria-hidden="true"
        className="fixed inset-0 pointer-events-none z-0"
        style={{
          background:
            'radial-gradient(circle at 50% 50%, rgba(248, 244, 236, 0.95) 0%, rgba(248, 244, 236, 0.88) 28%, rgba(248, 244, 236, 0.52) 60%, rgba(248, 244, 236, 0.15) 100%)',
        }}
      />
    </>
  );
};
