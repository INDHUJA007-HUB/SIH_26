# NiyamFlow frontend verification

## Delivered

An independent public React/TypeScript landing page in `frontend/`, adapted from the user's supplied story-scroll template. Tailwind 4 and shadcn-compatible aliases/components structure are configured. GSAP animates chapter headings on desktop; mobile and reduced-motion layouts use static content. Editorial cream, orange and forest-green sections explain the problem, application lifecycle, role responsibilities and accountability model.

Interactive features include a five-step journey, three role previews, a fictional institution walkthrough in a native dialog, FAQs, responsive navigation and links to the authenticated backend workspace. Illustrative records are labelled. The page does not claim official AICTE endorsement, automated regulatory decisions, production readiness or measured adoption statistics.

## Executed checks

- `npm run build`: strict TypeScript compilation and Vite production build passed.
- `npm audit --audit-level=high`: zero reported vulnerabilities, including development dependencies, at verification time.
- Headless Microsoft Edge browser: desktop and mobile pages rendered without JavaScript page errors.
- Native example dialog opened and dismissed using Escape.
- Journey tabs changed the matching content; arrow-key navigation changed the selected tab.
- Role tabs changed the workspace preview and description.
- FAQ expansion displayed the associated answer.
- Mobile menu opened, navigated to a section and closed.
- No horizontal document overflow at widths 360, 390, 768, 1024 and 1440 pixels.
- Reduced-motion mode left both section containers and chapter headings without GSAP transforms.
- Simulated HTTP 503 on the workspace path displayed the unavailable-service dialog; dismissal and the example walkthrough remained functional.
- Desktop and mobile screenshots were generated and visually inspected. Chapter motion was narrowed to headings after visual review to prevent section content overlap.

Browser verification used local temporary scripts and the bundled Playwright runtime. These are executed checks rather than a committed browser regression suite. Screenshots and local verification scripts remain in ignored `.local/`.

## Boundaries

The backend service was unavailable during the initial frontend checks, so authenticated workspace flows were not retested. The frontend handles this condition with a readable notice. By default, Vite proxies `/niyam` to port 8000; `WB_FRONTEND_PROXY_TARGET` can select another local backend. Production hosting must configure the workspace URL or reverse proxy. The frontend was subsequently deployed to Vercel as recorded below; no GitHub push was performed for this frontend change.

The existing backend and its authentication model are preserved. This landing page does not replace the authenticated workspace, build a new SSO login or expose private case data. Google Fonts has system-font fallbacks; typography may differ if external font loading is blocked. No formal accessibility certification or regulatory compliance certification is claimed.

## Vercel production deployment

- Project: `niyamflow`, ID `prj_hTfYPrCENLcNxeVCpZoEXX7ALZHi`.
- Deployment: `dpl_D6kBEHFRvHd3iZKThn3KaPNi57fg`, state `READY`, target `production`.
- Public URL: https://niyamflow-five.vercel.app/.
- Source: local frontend working tree, uploaded through the authenticated Vercel connector; 15 frontend files. This is not a deployment of a committed Git revision.
- Framework: Vite/React; Node 22; production build approximately 18 seconds.
- The backend, databases, root research documents and local credentials were excluded.
- `VITE_FRONTEND_ONLY=true` is configured for production/preview. Workspace links display the service notice instead of navigating to an undeployed API. An external `VITE_WORKSPACE_URL` can connect a separately hosted backend later.
- Public HTTP 200 verified without an authentication bypass.
- Live Edge browser checks passed for desktop/mobile rendering, example dialog, journey tabs, role tabs, mobile navigation and workspace notice. No JavaScript page errors or mobile horizontal overflow were observed.
- No backend functions, runtime monitoring integrations or log drains were added. This verification covers the deployed static frontend and its browser interactions.
- The supplied credential was not embedded in source or browser assets; deployment used the existing authenticated connector.

## React Bits navigation and cursor update

- Integrated the user-supplied React Bits CardNav and SwarmCursor JavaScript/CSS components, with typed public interfaces. Added the upstream license and attribution to the frontend.
- Replaced the top navigation with three themed cards and preserved section navigation, the example action and the workspace CTA. Collapsed navigation is inert; Escape and outside-click dismissal work.
- Cursor is lazily imported only for widths of at least 1024px, a fine hover pointer and no reduced-motion preference. Touch-only devices do not request the cursor chunk. Resizing or changing the preference unmounts the cursor and releases resources/listeners.
- The fixed canvas does not intercept pointer events or hide the system cursor. Hover targets cover document buttons/links. Explicit context loss on cleanup was removed to support React StrictMode's effect remount.
- Local browser verification: actual WebGL2 context present, not lost, GL error zero; menu open/close, Escape, outside dismissal, anchors and example action passed. Responsive widths 360–1440 had no horizontal overflow. Mobile, touch-only desktop and reduced-motion exclusion passed. Core navigation also passed with WebGL disabled.
- Strict TypeScript/Vite build passed; npm dependency audit reported zero vulnerabilities.
- Updated production deployment: `dpl_DaJ2h7jwnWnZj9sDk3rS56JB6gSt`, state `READY`, same public URL https://niyamflow-five.vercel.app/. Uploaded 23 frontend source/documentation files; backend remains excluded.
