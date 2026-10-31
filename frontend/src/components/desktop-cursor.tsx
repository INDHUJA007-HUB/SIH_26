import { lazy, Suspense, useEffect, useState } from 'react';

const SwarmCursor = lazy(() => import('./ui/SwarmCursor'));
const DESKTOP_POINTER = '(min-width: 1024px) and (hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)';

export default function DesktopCursor() {
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    const query = window.matchMedia(DESKTOP_POINTER);
    const update = () => setEnabled(query.matches);
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  if (!enabled) return null;
  return <Suspense fallback={null}><SwarmCursor
    className="desktop-swarm" count={280} size={1.8} spread={42} swirl={0.45}
    color="#ed592e" accentColor="#71845c" lightMode idle="hide" intro={false}
    hideCursor={false} tail={0.35} trail={0.35} wander={0.25} depth={0.35} dpr={1.5}
    clickEffect="burst"
  /></Suspense>;
}
