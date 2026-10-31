import type { CSSProperties, ElementType, MouseEvent, ReactNode } from 'react';

export interface NavLink { label: string; href?: string; ariaLabel?: string }
export interface NavItem { label: string; description?: string; bgColor?: string; textColor?: string; links: NavLink[] }
export interface CardNavProps {
  logo?: ReactNode; logoAlt?: string; logoHref?: string; items?: NavItem[];
  cta?: { label: string; href?: string; onClick?: (event: MouseEvent<HTMLAnchorElement>) => void };
  theme?: 'dark' | 'light'; surface?: 'glass' | 'solid'; openOn?: 'click' | 'hover';
  cardEffect?: 'rise' | 'unfold' | 'fade'; stagger?: number; bounce?: number;
  speed?: number; cardHeight?: number; maxWidth?: number; accentColor?: string;
  menuLabel?: boolean; intro?: boolean; defaultOpen?: boolean; open?: boolean;
  onOpenChange?: (open: boolean) => void; linkComponent?: ElementType;
  onLinkClick?: (link: NavLink, item: NavItem, event: MouseEvent) => void;
  ariaLabel?: string; className?: string; style?: CSSProperties;
}
export interface SwarmCursorProps {
  children?: ReactNode; count?: number; size?: number; shape?: 'dot' | 'square' | 'streak';
  color?: string; accentColor?: string; spread?: number; speed?: number; swirl?: number;
  tail?: number; trail?: number; wander?: number; depth?: number; targets?: string;
  idle?: 'roam' | 'gather' | 'hide'; clickEffect?: 'burst' | 'pulse' | 'none';
  hideCursor?: boolean; intro?: boolean; enabled?: boolean; lightMode?: boolean;
  dpr?: number; className?: string; style?: CSSProperties;
}
