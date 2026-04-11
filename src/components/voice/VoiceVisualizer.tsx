import { useRef, useEffect, useCallback } from 'react';
import './VoiceVisualizer.css';

interface Props {
  state: 'sleeping' | 'idle' | 'listening' | 'processing' | 'responding';
}

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  opacity: number;
  hue: number;
  life: number;
  maxLife: number;
}

export default function VoiceVisualizer({ state }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<Particle[]>([]);
  const frameRef = useRef<number>(0);
  const timeRef = useRef<number>(0);

  // ── Optimization: Mutation-based pool instead of recreation ──
  const initParticle = useCallback(
    (p: Partial<Particle>, cx: number, cy: number, radius: number): Particle => {
      const angle = Math.random() * Math.PI * 2;
      const dist = radius * (0.6 + Math.random() * 0.4);
      p.x = cx + Math.cos(angle) * dist;
      p.y = cy + Math.sin(angle) * dist;
      p.vx = (Math.random() - 0.5) * 0.4;
      p.vy = (Math.random() - 0.5) * 0.4;
      p.radius = Math.random() * 2.5 + 0.5;
      p.opacity = Math.random() * 0.6 + 0.2;
      p.hue = state === 'listening' ? 180 + Math.random() * 40 : 245 + Math.random() * 20;
      p.life = 0;
      p.maxLife = 120 + Math.random() * 180;
      return p as Particle;
    },
    [state]
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d', { alpha: false }); // Opt-out of alpha for slightly faster clear
    if (!ctx) return;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.scale(dpr, dpr);
    };
    resize();
    window.addEventListener('resize', resize);

    const rect = canvas.getBoundingClientRect();
    const cx = rect.width / 2;
    const cy = rect.height / 2;
    const baseRadius = Math.min(cx, cy) * 0.45;

    // Initialize fixed particle pool
    if (particlesRef.current.length === 0) {
      for (let i = 0; i < 200; i++) {
        particlesRef.current.push(initParticle({}, cx, cy, baseRadius));
      }
    }

    const animate = () => {
      timeRef.current += 0.016;
      const t = timeRef.current;
      
      // ── Intensity & Setup ──
      let intensity = 0.3, ringAlpha = 0.15, pulseSpeed = 0.5, particleSpeed = 0.3;
      switch (state) {
        case 'sleeping': intensity = 0.15; ringAlpha = 0.08; pulseSpeed = 0.3; particleSpeed = 0.1; break;
        case 'idle': intensity = 0.3; ringAlpha = 0.15; pulseSpeed = 0.5; particleSpeed = 0.3; break;
        case 'listening': intensity = 0.8; ringAlpha = 0.35; pulseSpeed = 1.5; particleSpeed = 0.8; break;
        case 'processing': intensity = 0.6; ringAlpha = 0.25; pulseSpeed = 2.0; particleSpeed = 0.6; break;
        case 'responding': intensity = 0.5; ringAlpha = 0.2; pulseSpeed = 0.8; particleSpeed = 0.4; break;
      }

      // ── Clean Clear ──
      ctx.fillStyle = '#050508'; // Match background precisely
      ctx.fillRect(0, 0, rect.width, rect.height);

      // ── Background nebula glow (Optimized Gradients) ──
      const nebulaGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, baseRadius * 2);
      nebulaGrad.addColorStop(0, `hsla(252, 80%, 60%, ${0.06 * intensity})`);
      nebulaGrad.addColorStop(0.5, `hsla(190, 100%, 50%, ${0.03 * intensity})`);
      nebulaGrad.addColorStop(1, 'transparent');
      ctx.fillStyle = nebulaGrad;
      ctx.fillRect(0, 0, rect.width, rect.height);

      // ── Central orb ──
      const breathScale = 1 + Math.sin(t * pulseSpeed) * 0.06 * intensity;
      const orbRadius = baseRadius * 0.25 * breathScale;
      const orbGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, orbRadius);
      orbGrad.addColorStop(0, `rgba(108, 99, 255, ${0.6 * intensity})`);
      orbGrad.addColorStop(0.6, `rgba(0, 229, 255, ${0.2 * intensity})`);
      orbGrad.addColorStop(1, 'transparent');
      ctx.fillStyle = orbGrad;
      ctx.beginPath(); ctx.arc(cx, cy, orbRadius, 0, Math.PI * 2); ctx.fill();

      // ── Orbital rings (Reduced context switches) ──
      ctx.setLineDash([]);
      for (let r = 0; r < 3; r++) {
        const ringRadius = baseRadius * (0.5 + r * 0.22) * breathScale;
        const ringRotation = t * (0.2 + r * 0.1) * (r % 2 === 0 ? 1 : -1);
        ctx.save();
        ctx.translate(cx, cy); ctx.rotate(ringRotation);
        ctx.strokeStyle = `rgba(108, 99, 255, ${ringAlpha * (1 - r * 0.3)})`;
        ctx.lineWidth = 1.5 - r * 0.3;
        ctx.setLineDash([4 + r * 2, 8 + r * 4]);
        ctx.beginPath(); ctx.arc(0, 0, ringRadius, 0, Math.PI * 2); ctx.stroke();
        ctx.restore();
      }

      // ── Audio wave bars ──
      if (state === 'listening' || state === 'processing') {
        const barCount = 48;
        ctx.lineWidth = 2;
        for (let i = 0; i < barCount; i++) {
          const angle = (Math.PI * 2 * i) / barCount;
          const amplitude = (Math.sin(t * 3 + i * 0.4) * 0.5 + 0.5) * (Math.cos(t * 1.7 + i * 0.2) * 0.3 + 0.7) * baseRadius * 0.15 * intensity;
          const innerR = baseRadius * 0.7;
          const x1 = cx + Math.cos(angle) * innerR;
          const y1 = cy + Math.sin(angle) * innerR;
          const x2 = cx + Math.cos(angle) * (innerR + amplitude);
          const y2 = cy + Math.sin(angle) * (innerR + amplitude);
          ctx.strokeStyle = state === 'listening' ? `rgba(0, 229, 255, ${0.3 + (amplitude / (baseRadius * 0.15)) * 0.5})` : `rgba(108, 99, 255, 0.4)`;
          ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
        }
      }

      // ── High Performance Particle System ──
      const particles = particlesRef.current;
      const pull = state === 'listening' ? 0.02 : -0.005;
      
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.life++;
        const dx = cx - p.x; const dy = cy - p.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        p.vx += (dx / dist) * pull * particleSpeed;
        p.vy += (dy / dist) * pull * particleSpeed;
        p.x += p.vx; p.y += p.vy;
        p.vx *= 0.98; p.vy *= 0.98;

        const alpha = p.opacity * (1 - p.life / p.maxLife) * intensity;
        if (alpha > 0) {
          ctx.fillStyle = `hsla(${p.hue}, 80%, 70%, ${alpha})`;
          ctx.beginPath(); ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2); ctx.fill();
        }

        if (p.life > p.maxLife || dist > baseRadius * 3) {
          initParticle(p, cx, cy, baseRadius);
        }
      }

      frameRef.current = requestAnimationFrame(animate);
    };

    frameRef.current = requestAnimationFrame(animate);
    return () => {
      cancelAnimationFrame(frameRef.current);
      window.removeEventListener('resize', resize);
    };
  }, [state, initParticle]);

  const stateLabel = {
    sleeping: 'Sleeping…',
    idle: 'Say "Hey Nova"',
    listening: 'Listening…',
    processing: 'Thinking…',
    responding: 'Speaking…',
  }[state];

  return (
    <div className="voice-visualizer" id="voice-visualizer">
      <canvas ref={canvasRef} className="voice-canvas" />
      <div className={`voice-status voice-status--${state}`}>
        <span className="voice-status-dot" />
        <span className="voice-status-text">{stateLabel}</span>
      </div>
    </div>
  );
}
