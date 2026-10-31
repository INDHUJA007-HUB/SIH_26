import { useRef, useState, type KeyboardEvent, type MouseEvent } from 'react';
import { ArrowDown, ArrowDownRight, ArrowRight, ArrowUpRight, Check, CheckCheck, ChevronDown, CircleCheck, Clock3, FileCheck2, Fingerprint, GraduationCap, Layers3, ListChecks, LockKeyhole, MoveUpRight, ScanLine, ShieldCheck, Sparkles, UsersRound, X } from 'lucide-react';
import CardNav from '@/components/ui/CardNav';
import DesktopCursor from '@/components/desktop-cursor';
import FlowArt, { FlowSection } from '@/components/ui/story-scroll';

const journey = [
  { name: 'Submit', title: 'One application. Everything attached.', description: 'An institution submits its application and supporting documents. Evidence stays connected to the case, so reviewers can see what was submitted and when.', owner: 'Institution', action: 'Application received', detail: 'Documents linked · Receipt recorded', icon: FileCheck2 },
  { name: 'Review', title: 'A clear next step for every case.', description: 'A published process pack decides the review route for that application category. Officers examine the evidence and record a reason when asking for a correction.', owner: 'Processing officer', action: 'Scrutiny in progress', detail: 'Assigned reviewer · Published route', icon: ScanLine },
  { name: 'Coordinate', title: 'Bring the right people together.', description: 'When a route requires an Expert Visit Committee (EVC), officers plan a visit using an authorized roster. Confirmation checks member availability and overlapping bookings.', owner: 'Officer & committee', action: 'Visit ready to confirm', detail: 'Availability checked · Conflicts checked', icon: UsersRound },
  { name: 'Decide', title: 'People decide. The record explains.', description: 'The configured route can include hearings and appeals. The competent authority records the final decision; the system preserves the history and prepares communication drafts.', owner: 'Authorized decision-maker', action: 'Awaiting authority decision', detail: 'Human authorization · Recorded reasons', icon: ShieldCheck },
  { name: 'Monitor', title: 'Approval is a milestone, not the end.', description: 'Undertakings, expiring documents and renewals remain visible after a case closes. In-app reminders flag due dates, and an officer verifies new evidence before closing an obligation.', owner: 'Institution & reviewing officer', action: 'Compliance watch active', detail: 'Renewal tracked · Verification required', icon: Clock3 },
];
const roles = [
  { name: 'Institutions', icon: GraduationCap, headline: 'Know what is needed. See what is next.', text: 'Keep your application, evidence and continuing obligations connected. Respond to review requests with the right context.', items: ['Follow application progress', 'Respond with supporting evidence', 'Track document validity and renewals'], view: 'Institution view', rows: [['Application review', 'In scrutiny'], ['Document renewal', 'Response needed'], ['Submitted evidence', 'Available for review']] },
  { name: 'Officers', icon: ListChecks, headline: 'A work queue with context, not guesswork.', text: 'See assigned cases, review supporting evidence and coordinate the next action within a governed process.', items: ['Review assigned applications', 'Plan committee appointments', 'Verify compliance responses'], view: 'Officer view', rows: [['Assigned application', 'Ready for review'], ['Committee appointment', 'Check availability'], ['Renewal response', 'Verify evidence']] },
  { name: 'Authorities', icon: ShieldCheck, headline: 'Make an informed, accountable decision.', text: 'Follow case history and recorded reasons before acting. Decisions require the appropriate, explicit authority.', items: ['Inspect the case history', 'Review hearing and appeal stages', 'Record authorized decisions'], view: 'Authority view', rows: [['Case history', 'Ready to inspect'], ['Review recommendation', 'Recorded'], ['Final decision', 'Authorization required']] },
];
const questions = [
  ['What is NiyamFlow, in simple terms?', 'It is a shared digital workspace for handling technical-education approval applications. Instead of tracking documents, reviewers, visits and deadlines in separate places, a case keeps those steps connected and makes the next action visible.'],
  ['Who is this built for?', 'Institutions submitting applications, officers reviewing them, committees carrying out visits, and authorities responsible for decisions. Each role gets access appropriate to its assignment or authorized delegation.'],
  ['Does AI approve or reject an institution?', 'No. Published rules guide the route and automation assists with coordination, reminders and communication drafts. Authorized people review evidence and make regulatory decisions. AI predictions and automatic legal interpretation are not implemented in this prototype.'],
  ['Is this the official AICTE portal?', 'No. NiyamFlow is an independent SIH26262 development prototype. The included process pack and the examples on this page are illustrative. Official policy validation, production identity integration and deployment qualification are still required.'],
  ['What can I try today?', 'Use the interactive example on this page without signing in. The separate workspace connects to the implemented backend and requires a valid access token. It includes case queues, compliance, EVC planning, process packs, alerts and reports.'],
];

function Brand({ light = false }: { light?: boolean }) { return <a href="#home" aria-label="NiyamFlow home" className={`brand ${light ? 'brand-light' : ''}`}><span className="brand-icon"><Layers3 size={22} strokeWidth={2.2} /></span>Niyam<span className="brand-flow">Flow</span><span className="brand-dot" aria-hidden="true">✳</span></a>; }
function SectionLabel({ number, children }: { number: string; children: React.ReactNode }) { return <div className="section-label"><span>{number} /</span>{children}<span className="label-line" /></div>; }

export default function App() {
  const [step, setStep] = useState(0);
  const [role, setRole] = useState(0);
  const [openFaq, setOpenFaq] = useState<number | null>(0);
  const dialog = useRef<HTMLDialogElement>(null);
  const workspaceDialog = useRef<HTMLDialogElement>(null);
  const stepRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const roleRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const workspace = import.meta.env.VITE_WORKSPACE_URL || '/niyam';
  async function openWorkspace(event: MouseEvent<HTMLAnchorElement>) {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const target = new URL(workspace, window.location.href);
    if (target.origin !== window.location.origin) return;
    event.preventDefault();
    if (import.meta.env.VITE_FRONTEND_ONLY === 'true') {
      if (!workspaceDialog.current?.open) workspaceDialog.current?.showModal();
      return;
    }
    try {
      const response = await fetch(target.href, { signal: AbortSignal.timeout(5000), headers: { Accept: 'text/html' } });
      if (!response.ok) throw new Error('Workspace unavailable');
      window.location.assign(target.href);
    } catch { if (!workspaceDialog.current?.open) workspaceDialog.current?.showModal(); }
  }
  const current = journey[step];
  const CurrentIcon = current.icon;
  const currentRole = roles[role];
  function tabKeys(event: KeyboardEvent, index: number, count: number, select: (n: number) => void, refs: (HTMLButtonElement | null)[]) {
    let next = index;
    if (event.key === 'ArrowRight') next = (index + 1) % count;
    else if (event.key === 'ArrowLeft') next = (index + count - 1) % count;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = count - 1;
    else return;
    event.preventDefault(); select(next); refs[next]?.focus();
  }
  return <>
    <a className="skip-link" href="#main">Skip to content</a>
    <DesktopCursor />
    <header className="card-header">
      <CardNav
        logo={<span className="brand"><span className="brand-icon"><Layers3 size={22} /></span>Niyam<span className="brand-flow">Flow</span></span>}
        logoAlt="NiyamFlow home" logoHref="#home"
        theme="light" surface="solid" maxWidth={1160} cardHeight={185}
        accentColor="#253329" intro={false} cardEffect="rise" bounce={0.15}
        ariaLabel="Main navigation"
        cta={{ label: 'Open workspace ↗', href: workspace, onClick: openWorkspace }}
        items={[
          { label: 'Discover', description: 'A clearer path for technical education.', bgColor: '#ed592e', textColor: '#fff8ed', links: [{ label: 'The idea', href: '#idea' }, { label: 'How it works', href: '#journey' }] },
          { label: 'Your workspace', description: 'Different roles. One shared direction.', bgColor: '#e4e8da', textColor: '#253329', links: [{ label: 'Built for you', href: '#roles' }, { label: 'Explore an example', ariaLabel: 'Open example from navigation' }] },
          { label: 'Trust & clarity', description: 'People stay responsible for decisions.', bgColor: '#253329', textColor: '#f4f1e9', links: [{ label: 'Built for accountability', href: '#trust' }, { label: 'FAQs', href: '#faq' }] },
        ]}
        onLinkClick={link => { if (!link.href) dialog.current?.showModal(); }}
      />
    </header>
    <FlowArt>
      <FlowSection id="home" className="hero" aria-label="Introducing NiyamFlow">
        <div className="hero-topline"><span className="eyebrow"><span className="status-dot" /> A CLEARER PATH FOR TECHNICAL EDUCATION</span><span className="edition">SIH26262 / THE APPROVAL WORKSPACE</span></div>
        <div className="hero-grid">
          <div className="hero-copy"><h1>Every step.<br /><span>In the clear.</span><span className="heading-star" aria-hidden="true">✳</span></h1>
            <p>From the first application to the next renewal. One connected workspace for AICTE approval reviews, compliance and the people moving them forward.</p>
            <div className="hero-actions"><a className="button button-dark" href="#journey">See how it works <ArrowDownRight size={19} /></a><button className="text-button" onClick={() => dialog.current?.showModal()}>Explore an example <span className="circle-arrow"><ArrowUpRight size={17} /></span></button></div>
            <div className="hero-caption"><span className="mini-mark"><CheckCheck size={17} /></span> Clear ownership. Connected evidence. Human decisions.</div>
          </div>
          <div className="hero-art" aria-label="Illustrative application review preview">
            <div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="art-axis" />
            <span className="art-coordinate">CONNECTED BY DESIGN ↘</span>
            <div className="floating-tag"><span className="status-dot" /> Every action has a trail</div>
            <div className="case-preview"><div className="preview-top"><span><span className="small-logo">N</span> Application overview</span><span>↗</span></div>
              <div className="preview-title"><span className="micro">ILLUSTRATIVE CASE / NF–2026–014</span><h3>A clearer path<br />to the next step.</h3><span className="pill"><span className="status-dot" /> In review</span></div>
              <div className="preview-route">{['Submitted', 'Scrutiny', 'Committee', 'Decision'].map((name, i) => <div className={`route-node ${i < 2 ? 'done' : ''}`} key={name}><span>{i === 0 ? <Check size={13} /> : String(i + 1).padStart(2, '0')}</span><small>{name}</small></div>)}</div>
              <div className="preview-task"><span className="task-icon"><FileCheck2 size={22} /></span><div><strong>Evidence, in context.</strong><small>Attached to the application record</small></div><ArrowUpRight size={17} /></div>
              <div className="preview-bottom"><span><UsersRound size={14} /> Assigned officer</span><span>Next: evidence review</span></div>
            </div>
            <div className="floating-confirm"><span><ShieldCheck size={22} /></span><div><strong>People stay in control.</strong><small>Authority required for decisions</small></div></div>
            <span className="art-note">A SINGLE CASE. A SHARED PICTURE.</span>
          </div>
        </div>
        <div className="hero-footer"><a href="#idea"><span className="scroll-circle"><ArrowDown size={15} /></span> A better way forward</a><span>APPLICATION → REVIEW → DECISION → COMPLIANCE</span><span className="page-number">01 — 06</span></div>
      </FlowSection>

      <FlowSection id="idea" className="idea-section" aria-label="The problem and the idea">
        <SectionLabel number="01">THE BIG PICTURE</SectionLabel>
        <div className="idea-grid"><h2>Less chasing.<br />More <em>clarity.</em></h2><div className="idea-explanation"><span className="eyebrow">GOOD EDUCATION NEEDS GOOD PROCESSES.</span><p>Technical institutions need approval to operate and make certain changes. That means evidence to check, people to coordinate and conditions to keep meeting.</p><p>When those steps live in separate files and follow-ups, it becomes hard to see who owns the next action. <strong>NiyamFlow brings the journey together.</strong></p></div></div>
        <div className="principle-grid">{[
          { icon: Layers3, title: 'One connected case', text: 'Keep the application, evidence and review history together.' },
          { icon: UsersRound, title: 'A clear next owner', text: 'Move work through a published route with assigned responsibilities.' },
          { icon: Clock3, title: 'Deadlines in sight', text: 'Follow continuing conditions, expiring documents and renewals.' },
        ].map(({ icon: Icon, title, text }, i) => <article key={title}><div className="principle-top"><Icon size={27} strokeWidth={1.5} /><span>0{i + 1}</span></div><h3>{title}</h3><p>{text}</p></article>)}</div>
        <div className="plain-note"><Sparkles size={18} /><span>In plain terms: everyone sees the right information, and every step has a place.</span></div>
      </FlowSection>

      <FlowSection id="journey" className="journey-section" aria-label="Explore the approval journey">
        <SectionLabel number="02">FROM APPLICATION TO ACCOUNTABILITY</SectionLabel>
        <div className="section-heading"><h2>A process you<br />can <span className="serif">follow.</span></h2><p>Five connected moments. One traceable journey.<br />Select a step to see how the work moves.</p></div>
        <div className="journey-tabs" role="tablist" aria-label="Approval journey">{journey.map((item, index) => <button key={item.name} ref={el => { stepRefs.current[index] = el; }} id={`step-${index}`} role="tab" aria-controls="journey-panel" aria-selected={step === index} tabIndex={step === index ? 0 : -1} onKeyDown={event => tabKeys(event, index, journey.length, setStep, stepRefs.current)} onClick={() => setStep(index)}><span>0{index + 1}</span>{item.name}<ArrowUpRight size={18} /></button>)}</div>
        <div className="journey-content" id="journey-panel" role="tabpanel" aria-labelledby={`step-${step}`} tabIndex={0}>
          <div className="journey-text"><span className="chapter-small">STEP 0{step + 1} / {current.owner}</span><h3>{current.title}</h3><p>{current.description}</p><button className="text-button" onClick={() => setStep((step + 1) % journey.length)}>{step === 4 ? 'Back to the beginning' : 'Explore the next step'} <ArrowRight size={19} /></button></div>
          <div className="journey-visual"><div className="visual-top"><span className="micro">EXAMPLE WORKFLOW</span><span className="live-chip">Illustrative</span></div><div className="step-orbit"><CurrentIcon size={42} strokeWidth={1.3} /><span className="step-badge">0{step + 1}</span></div><h4>{current.action}</h4><p>{current.detail}</p><div className="visual-owner"><span>RESPONSIBLE</span><strong>{current.owner}</strong><CircleCheck size={19} /></div></div>
        </div>
        <p className="section-footnote">Routes vary by application category and published policy. Visits, hearings and appeals apply where the configured route requires them.</p>
      </FlowSection>

      <FlowSection id="roles" className="roles-section" aria-label="Workspaces for every responsibility">
        <SectionLabel number="03">DIFFERENT ROLES. SHARED DIRECTION.</SectionLabel>
        <div className="section-heading"><h2>Your work.<br /><em>Your perspective.</em></h2><p>The right context for each responsibility.<br />Access follows assignment and authorization.</p></div>
        <div className="roles-layout"><div><div className="role-tabs" role="tablist" aria-label="Workspace roles">{roles.map(({ name, icon: Icon }, i) => <button role="tab" id={`role-${i}`} aria-controls="role-panel" aria-selected={role === i} tabIndex={role === i ? 0 : -1} ref={el => { roleRefs.current[i] = el; }} key={name} onKeyDown={event => tabKeys(event, i, roles.length, setRole, roleRefs.current)} onClick={() => setRole(i)}><Icon size={17} />{name}</button>)}</div><div role="tabpanel" id="role-panel" aria-labelledby={`role-${role}`} tabIndex={0} className="role-copy"><h3>{currentRole.headline}</h3><p>{currentRole.text}</p><ul>{currentRole.items.map(item => <li key={item}><Check size={17} />{item}</li>)}</ul><a href={workspace} onClick={openWorkspace} className="text-button">Open the workspace <ArrowUpRight size={19} /></a></div></div>
          <div className="workspace-preview"><aside><span className="small-logo">N</span><Layers3 size={19} /><ListChecks size={19} /><UsersRound size={19} /><Clock3 size={19} /><span className="sidebar-bottom"><LockKeyhole size={17} /></span></aside><div className="workspace-main"><div className="workspace-bar"><span>WORKSPACE PREVIEW</span><span className="tiny-avatar">NF</span></div><h4>{currentRole.view}</h4><p>Every next action, in context.</p><div className="workspace-summary"><span><FileCheck2 size={21} /><strong>A shared record</strong></span><small>Evidence and history<br />connected to the case</small></div><div className="workspace-table-head"><span>ITEM</span><span>NEXT ACTION / STATUS</span></div>{currentRole.rows.map(([label, state], i) => <div className="workspace-row" key={label}><span><i className={`row-dot dot-${i}`} />{label}</span><small>{state}</small></div>)}<div className="workspace-notice"><ShieldCheck size={16} /><span>Only authorized information is visible.</span></div><span className="preview-disclaimer">Sample interface · Synthetic records</span></div></div>
        </div>
      </FlowSection>

      <FlowSection id="trust" className="trust-section" aria-label="Designed for accountable decisions">
        <SectionLabel number="04">TRUST IS PART OF THE PROCESS</SectionLabel>
        <div className="trust-layout"><div><span className="trust-symbol" aria-hidden="true">✳</span><h2>Built to assist.<br /><span className="serif">Designed to<br />be accountable.</span></h2><p>Automation moves the work forward.<br />People remain responsible for decisions.</p></div><div className="trust-list">{[
          [Fingerprint, 'A history you can follow', 'Case actions, recorded reasons and evidence references stay connected to the review history.'],
          [LockKeyhole, 'Access with boundaries', 'Assignments and scoped delegations control who can see information and take action.'],
          [FileCheck2, 'Rules with a published version', 'A case follows a published process pack. Draft policy changes require independent approval before publication.'],
          [ShieldCheck, 'Human judgment, protected', 'Reminders and communication drafts support the process. Final decisions require explicit competent authority.'],
        ].map(([Icon, title, text]) => { const TrustIcon = Icon as typeof Fingerprint; return <article key={String(title)}><TrustIcon size={23} strokeWidth={1.5} /><div><h3>{String(title)}</h3><p>{String(text)}</p></div><ArrowUpRight size={17} /></article>; })}</div></div>
        <div className="prototype-note"><span className="pill">WHERE WE ARE TODAY</span><p>An independent development prototype for SIH26262. Sample policies are illustrative; official policy validation, production integrations and deployment qualification remain ahead.</p></div>
      </FlowSection>

      <FlowSection id="faq" className="faq-section" aria-label="Frequently asked questions">
        <SectionLabel number="05">A LITTLE MORE CLARITY</SectionLabel>
        <div className="faq-layout"><div><h2>Good questions.<br /><em>Clear answers.</em></h2><p>New to approval workflows?<br />Start here.</p><ArrowDownRight className="faq-arrow" size={76} strokeWidth={1} /></div><div className="faq-items">{questions.map(([question, answer], i) => <article className={openFaq === i ? 'faq-item open' : 'faq-item'} key={question}><h3><button aria-expanded={openFaq === i} aria-controls={`answer-${i}`} id={`question-${i}`} onClick={() => setOpenFaq(openFaq === i ? null : i)}><span><small>0{i + 1}</small>{question}</span><ChevronDown size={19} /></button></h3><div id={`answer-${i}`} role="region" aria-labelledby={`question-${i}`} hidden={openFaq !== i}><p>{answer}</p></div></article>)}</div></div>
      </FlowSection>
    </FlowArt>
    <footer><div className="footer-cta"><div><span className="eyebrow">LESS FRICTION. MORE FORWARD.</span><h2>See the bigger picture.<br /><span>Then take the next step.</span></h2></div><a href={workspace} onClick={openWorkspace} className="footer-cta-link" aria-label="Open NiyamFlow workspace"><MoveUpRight size={55} strokeWidth={1.2} /><span>Open workspace</span></a></div><div className="footer-bottom"><Brand light /><span>Approval. Compliance. Clarity.</span><a href="#home">Back to top ↑</a></div><div className="legal-line"><span>© {new Date().getFullYear()} NiyamFlow · SIH26262 development prototype</span><span>Independent project. Not an official AICTE service.</span></div></footer>
    <dialog ref={workspaceDialog} className="example-dialog" aria-labelledby="workspace-dialog-title" onClick={event => { if (event.target === event.currentTarget) workspaceDialog.current?.close(); }}><div className="dialog-head"><span className="eyebrow">SECURE WORKSPACE</span><button autoFocus aria-label="Close workspace notice" onClick={() => workspaceDialog.current?.close()}><X size={22} /></button></div><h2 id="workspace-dialog-title">The workspace is<br />temporarily unavailable.</h2><p>The connected application service is not responding right now. You can still explore the approval journey and see how NiyamFlow works.</p><p className="dialog-note" style={{ marginTop: 16 }}>The secure workspace requires the backend service and an authorized account. The walkthrough uses illustrative examples and is available without signing in.</p><a href="#journey" className="button button-dark" onClick={() => workspaceDialog.current?.close()}>Explore the journey <ArrowRight size={17} /></a></dialog>
    <dialog ref={dialog} aria-label="Fictional institution application walkthrough" className="example-dialog" onClick={event => { if (event.target === event.currentTarget) dialog.current?.close(); }}><div className="dialog-head"><span className="eyebrow">THE JOURNEY, MADE SIMPLE</span><button autoFocus aria-label="Close example" onClick={() => dialog.current?.close()}><X size={22} /></button></div><span className="pill">Fictional example</span><h2>Meet Kavya,<br />an institution officer.</h2><p>Kavya is preparing an application for her institution. Here is how NiyamFlow helps keep everyone aligned.</p><ol>{[['Prepare & submit', 'Kavya submits the application with its evidence. The receipt and submitted version are recorded.'], ['Review & respond', 'An assigned officer reviews the case. If a correction is needed, Kavya sees the request and responds with evidence.'], ['Coordinate & decide', 'Where required, a committee visit is arranged. The authorized decision-maker reviews the record and records a decision.'], ['Keep meeting conditions', 'Kavya follows any continuing undertakings or renewals. An officer verifies responses before an obligation is closed.']].map(([title, text], i) => <li key={title}><span>0{i + 1}</span><div><h3>{title}</h3><p>{text}</p></div></li>)}</ol><p className="dialog-note">This example does not prescribe an official approval route or timeline.</p><a className="button button-dark" href="#journey" onClick={() => dialog.current?.close()}>Explore each step <ArrowRight size={17} /></a></dialog>
  </>;
}
