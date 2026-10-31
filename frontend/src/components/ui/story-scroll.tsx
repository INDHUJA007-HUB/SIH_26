'use client';

import { Children, useRef, type CSSProperties, type ReactNode } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import { cn } from '@/lib/utils';

gsap.registerPlugin(ScrollTrigger, useGSAP);

export function FlowSection({ children, className, style, id, 'aria-label': label }: {
  children: ReactNode; className?: string; style?: CSSProperties; id?: string; 'aria-label'?: string;
}) {
  return <section id={id} data-flow-section aria-label={label} className={cn('flow-section relative w-full', className)}>
    <div data-flow-inner className="flow-art-container" style={style}>{children}</div>
  </section>;
}

/** Adapted from the supplied story-scroll template; static, readable flow on mobile/reduced motion. */
export default function FlowArt({ children }: { children: ReactNode }) {
  const container = useRef<HTMLElement>(null);
  useGSAP(() => {
    const media = gsap.matchMedia();
    media.add('(min-width: 1000px) and (prefers-reduced-motion: no-preference)', () => {
      const sections = gsap.utils.toArray<HTMLElement>('[data-flow-section]', container.current!);
      sections.forEach((section, index) => {
        const inner = section.querySelector<HTMLElement>('h2');
        if (!inner || index === 0) return;
        gsap.fromTo(inner, { rotation: 3, y: 20, transformOrigin: 'bottom left' }, {
          rotation: 0, y: 0, ease: 'none',
          scrollTrigger: { trigger: section, start: 'top bottom', end: 'top 55%', scrub: true },
        });
      });
    });
    return () => media.revert();
  }, { scope: container, dependencies: [Children.count(children)], revertOnUpdate: true });
  return <main id="main" ref={container}>{children}</main>;
}
