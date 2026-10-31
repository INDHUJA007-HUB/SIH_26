# NiyamFlow frontend

Production frontend: https://niyamflow-five.vercel.app/ — Vercel project `niyamflow`. Only this frontend is deployed. The Vercel production/preview setting `VITE_FRONTEND_ONLY=true` makes workspace links show the service notice until a backend is connected. To connect a separately hosted backend workspace later, set `VITE_WORKSPACE_URL` to its HTTPS URL and rebuild.

React + TypeScript + Vite, Tailwind CSS 4, Lucide icons and GSAP. The supplied story-scroll component is adapted in `src/components/ui/story-scroll.tsx`. It keeps the oversized editorial typography, contrasting chapters and scroll rotation, with readable normal flow and reduced-motion/mobile fallbacks. GSAP contexts clean up on resize and unmount.

## Start

Requires Node 20.19+ (or a supported newer LTS).

```powershell
cd C:\Users\indhu\SIH_26\frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. The landing page works independently of the backend. Its case cards, role previews and interactive journey are explicitly illustrative. The example dialog contains fictional records. No landing-page content fetches or exposes authenticated case data.

`Open workspace` links to the existing `/niyam` authenticated application. Vite proxies that path to `http://127.0.0.1:8000` by default. Start the backend using the repository's existing setup to use it; it needs a valid access token. To use another local backend port, set `WB_FRONTEND_PROXY_TARGET` before starting Vite. Do not put credentials in frontend environment variables.

If the same-origin workspace is unavailable, the page displays a dismissible notice and offers the walkthrough. A separate production workspace host handles its own availability and authentication.

```powershell
$env:WB_FRONTEND_PROXY_TARGET = 'http://127.0.0.1:8009'
npm run dev
```

For separate production hosts, set `VITE_WORKSPACE_URL` to the deployed workspace URL **at build time**, or configure a same-origin reverse proxy for `/niyam` and its backend API routes. This frontend build does not change or deploy the backend.

## Build

```powershell
npm run build
npm run preview
```

The build type-checks the application and outputs static assets to ignored `dist/`. Deploy those assets with an appropriate static host. Google Fonts is optional at runtime; local system fonts provide fallbacks if unavailable.

## Components and styles

Reusable UI components live in `src/components/ui`, application content in `src/App.tsx`, styles in `src/index.css`, and class helpers in `src/lib/utils.ts`. The root `components.json` configures the shadcn aliases and Tailwind 4 stylesheet, so future shadcn components can share a predictable import path (`@/components/ui`). No separate Tailwind configuration is required for Tailwind 4.

## Interaction and accessibility

React Bits CardNav now provides the expanding three-card navigation, adapted to NiyamFlow's palette and section links. SwarmCursor is loaded as a separate chunk only at desktop widths (1024px+) with a fine hover pointer and no reduced-motion preference. The overlay keeps the system cursor, does not intercept clicks, supports document-wide button hover targets and unmounts when the device/media conditions change. No cursor chunk is requested on touch-only devices. Component notices and the upstream license are included in `THIRD_PARTY_NOTICES.md` and `react-bits-LICENSE.md`.

- Card navigation links jump to sections; the expanding menu has labelled controls, inert collapsed content, outside-click dismissal and Escape dismissal with focus restoration.
- Journey and role tabs support Left/Right, Home and End, labelled panels and roving tab focus.
- The native example dialog supports focus containment, Escape, backdrop dismissal and return focus.
- FAQs use real buttons with expanded state and associated answer regions.
- Reduced-motion preferences disable scroll transforms. All core content remains readable without animation.
- Product messaging distinguishes the independent prototype, illustrative policy and human decision-making from official AICTE services.

The existing authenticated workspace remains separate. This change adds the public frontend and does not claim a completed SSO redesign or replacement of every authenticated domain form.
