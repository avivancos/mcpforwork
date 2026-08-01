import Link from "next/link";
import { CopyButton } from "@/components/CopyButton";
import { Logo } from "@/components/Logo";
import { FAQ_FLAT } from "@/content/faq";
import styles from "./landing.module.css";

const HOW = [
  {
    num: "01 · Hunt",
    title: "It browses real portals in your browser",
    sub: "Regional packs teach it how each portal works — any sector, any country.",
  },
  {
    num: "02 · Review",
    title: "Scored against your hard constraints",
    sub: "Visa, salary floor, language, remote — filters you set once, applied every time.",
  },
  {
    num: "03 · Draft",
    title: "In your voice, only from your facts",
    sub: "A facts inventory means it never claims what you didn't prove. Gaps are acknowledged, not stuffed.",
  },
  {
    num: "04 · Apply & track",
    title: "You click Submit. Everything is logged.",
    sub: "Every application audited and deduplicated. Autopilot only if you turn it on.",
  },
];

const USE_CASES = [
  {
    title: "ICU nurse → Dublin",
    sub: "Cross-border move, registration in progress, salary floor private.",
    pack: "healthcare-ie",
  },
  {
    title: "Logistics coordinator → Hamburg",
    sub: "German portals, German cover letters — in their voice, both languages.",
    pack: "logistics-de",
  },
  {
    title: "Frontend dev → remote LATAM",
    sub: "Remote boards + timezone filters; dedup across the reposting flood.",
    pack: "tech-remote-latam",
  },
  {
    title: "Marketing manager → London",
    sub: "High-volume market; scoring and caps keep quality over quantity.",
    pack: "general-uk",
  },
];

const QUOTES = [
  {
    quote: "“The cover letter sounded like me on a good day — not like a robot pretending to be me.”",
    who: "ICU nurse, relocating Madrid → Dublin",
  },
  {
    quote: "“I stopped applying twice to the same reposted job. The dedup alone is worth $5.”",
    who: "Logistics coordinator, Hamburg",
  },
  {
    quote: "“Autopilot with a daily cap and an allowlist is the first automation I actually trust.”",
    who: "Frontend developer, remote LATAM",
  },
];

const ATS = [
  { label: "invasive ventilation", chip: "covered", cls: "chip--green" },
  { label: "haemofiltration", chip: "synonym: CRRT", cls: "chip--blue" },
  { label: "BLS instructor", chip: "you have this — add it", cls: "chip--amber" },
  { label: "paediatric ICU", chip: "gap — acknowledge", cls: "chip--red" },
];

export default function LandingPage() {
  return (
    <div className={styles.page}>
      <div className={styles.container}>
        {/* nav */}
        <nav className={styles.nav}>
          <Logo size={16} />
          <div className={styles.navLinks}>
            <a href="#how">How it works</a>
            <Link href="/pricing">Pricing</Link>
            <a href="#faq">FAQ</a>
            <a href="https://github.com/mcpforwork">GitHub</a>
            <Link href="/pipeline" className={styles.ctaSecondary} style={{ padding: "8px 16px", fontSize: 13.5 }}>
              Dashboard
            </Link>
            <Link href="/connect" className={styles.ctaPrimary} style={{ padding: "8px 16px", fontSize: 13.5 }}>
              Connect to Claude
            </Link>
          </div>
        </nav>

        {/* hero */}
        <header className={styles.hero}>
          <div className={styles.heroCopy}>
            <span className="eyebrow eyebrow--accent">Open source · Apache-2.0 · MCP-first</span>
            <h1 className={styles.h1}>
              Your AI already knows how to job-hunt. <em>Give it hands.</em>
            </h1>
            <p className={styles.heroSub}>
              mcpfor.work connects the Claude or ChatGPT you already pay for to real job portals —
              in your browser, in your voice, under your control. Zero server-side LLM calls. You
              click Submit.
            </p>
            <div className={styles.ctaRow}>
              <Link href="/connect" className={styles.ctaPrimary}>
                Connect to Claude
              </Link>
              <Link href="/pipeline" className={styles.ctaSecondary}>
                Dashboard
              </Link>
            </div>
            <div className={styles.installRow}>
              <span>
                <span style={{ color: "var(--term-muted)" }}>$</span> uvx mcpforwork
              </span>
              <CopyButton text="uvx mcpforwork" className={styles.installCopy} />
            </div>
            <div className={styles.trustLine}>
              <span>Apache-2.0</span>
              <span className={styles.sep}>·</span>
              <span>Zero server-side LLM calls</span>
              <span className={styles.sep}>·</span>
              <span>You click Submit</span>
            </div>
          </div>

          {/* hero visual — browser + chat, Sofía loop (CSS-cycled) */}
          <div className={styles.visual} aria-hidden>
            <div className={styles.browser}>
              <div className={styles.browserBar}>
                <span className={styles.dots}>
                  <span />
                  <span />
                  <span />
                </span>
                <span className={styles.urlBar}>careers.materprivate.ie/apply/icu-staff-nurse</span>
              </div>
              <div className={styles.browserBody}>
                <div className={`${styles.pane} ${styles.paneA}`}>
                  <span className={styles.paneLabel}>12 matches · 3 new · pack healthcare-ie</span>
                  <div className={`${styles.matchRow} ${styles.matchRowTop}`}>
                    <div>
                      <div className={styles.matchName}>ICU Staff Nurse</div>
                      <div className={styles.matchWhere}>Mater Private Hospital · Dublin · Full-time</div>
                    </div>
                    <span className={`${styles.matchScore} ${styles.matchScoreTop}`}>91</span>
                  </div>
                  <div className={styles.matchRow}>
                    <div>
                      <div className={styles.matchName}>Staff Nurse, Critical Care</div>
                      <div className={styles.matchWhere}>St Vincent&rsquo;s University Hospital · Dublin</div>
                    </div>
                    <span className={styles.matchScore}>86</span>
                  </div>
                  <div className={styles.matchRow}>
                    <div>
                      <div className={styles.matchName}>ICU Nurse, Nights</div>
                      <div className={styles.matchWhere}>Beacon Hospital · Sandyford</div>
                    </div>
                    <span className={styles.matchScore}>82</span>
                  </div>
                </div>
                <div className={`${styles.pane} ${styles.paneB}`}>
                  <span className={styles.paneLabel}>Application — ICU Staff Nurse</span>
                  <div className={styles.formFields}>
                    <span className={styles.formField}>Sofía Reyes</span>
                    <span className={styles.formField} style={{ color: "var(--ink-2)" }}>
                      s.reyes@…
                    </span>
                  </div>
                  <div className={styles.resumeChip}>
                    ⎘ resume—mater—icu.pdf{" "}
                    <span style={{ color: "var(--ink-3)" }}>tailored · facts-checked</span>
                  </div>
                  <div className={styles.coverText}>
                    Dear Ms Whelan — after six years in intensive care at Hospital La Paz in Madrid,
                    including two leading the ventilator-weaning…
                    <span className={styles.caret} />
                  </div>
                  <span className={styles.submitBtn}>Submit</span>
                </div>
                <div className={styles.pauseBadge}>
                  <span className={styles.pauseDot} /> Paused — Sofía clicks Submit
                </div>
              </div>
            </div>
            <div className={styles.chat}>
              <div className={styles.chatBar}>
                <span className={styles.chatDot} /> Claude · mcpfor.work
              </div>
              <div className={styles.chatBody}>
                <span className={styles.msgUser}>/hunt icu nurse dublin</span>
                <span className={styles.msgBot}>
                  Drafting in your voice — two achievements from your bank. Nothing you haven&rsquo;t
                  proven.
                </span>
                <span className={styles.msgBot}>Ready to submit — approve?</span>
                <span className={styles.msgApprove}>Approve</span>
              </div>
            </div>
          </div>
        </header>

        {/* steps strip */}
        <div className={styles.steps} aria-hidden>
          {["Hunt", "Review", "Draft", "You submit"].map((s) => (
            <span key={s} className={styles.stepItem}>
              <span className={styles.stepDot} />
              {s}
            </span>
          ))}
        </div>

        {/* works with */}
        <div className={styles.worksWith}>
          <span className={styles.worksWithLabel}>Works with</span>
          <b>Claude</b>
          <span className={styles.sep}>·</span>
          <b>Claude Desktop</b>
          <span className={styles.sep}>·</span>
          <b>Claude Code</b>
          <span className={styles.sep}>·</span>
          <b>ChatGPT</b>
          <span className={styles.sep}>·</span>
          <b>Codex CLI</b>
        </div>

        {/* how it works */}
        <section className={styles.section} id="how">
          <div className={styles.sectionHead}>
            <span className="eyebrow eyebrow--accent">How it works</span>
            <h2 className={styles.h2}>Four verbs. Your AI does the typing, you make the calls.</h2>
          </div>
          <div className={styles.grid4}>
            {HOW.map((card, i) => (
              <div key={card.num} className={styles.howCard}>
                <span className={styles.howNum}>{card.num}</span>
                <span className={styles.howTitle}>{card.title}</span>
                <span className={styles.howSub}>{card.sub}</span>
                {i === 0 && (
                  <div className={styles.howTermDemo}>
                    <span>
                      <span style={{ color: "var(--term-muted)" }}>›</span> /hunt icu nurse dublin
                    </span>
                    <span style={{ color: "var(--term-accent)" }}>12 found · 3 new · 1 duplicate skipped</span>
                  </div>
                )}
                {i === 1 && (
                  <div className={styles.howDemo}>
                    <div className={styles.kvRow}>
                      <span style={{ fontSize: 12.5, fontWeight: 600 }}>ICU Staff Nurse · Mater Private</span>
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--accent)", fontWeight: 500 }}>
                        91
                      </span>
                    </div>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      {["visa ✓", "€52k ✓", "EN C1 ✓"].map((c) => (
                        <span key={c} className="chip chip--green" style={{ borderRadius: 5 }}>
                          {c}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {i === 2 && (
                  <div className={styles.howDemo}>
                    {[
                      { l: "invasive ventilation", c: "covered", cls: "chip--green" },
                      { l: "BLS instructor", c: "you have this", cls: "chip--amber" },
                      { l: "paediatric ICU", c: "gap — don't stuff", cls: "chip--red" },
                    ].map((r) => (
                      <div key={r.l} className={styles.kvRow}>
                        <span className={styles.kvLabel}>{r.l}</span>
                        <span className={`chip ${r.cls}`} style={{ borderRadius: 5, fontSize: 10 }}>
                          {r.c}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
                {i === 3 && (
                  <div className={styles.howDemo}>
                    {[
                      { l: "Mater Private", c: "awaiting you", cls: "chip--amber" },
                      { l: "St Vincent's", c: "submitted", cls: "chip--indigo" },
                      { l: "Beacon Hospital", c: "verified", cls: "chip--green" },
                    ].map((r) => (
                      <div key={r.l} className={styles.kvRow}>
                        <span className={styles.kvLabel} style={{ fontSize: 11.5 }}>
                          {r.l}
                        </span>
                        <span className={`chip ${r.cls}`} style={{ fontSize: 10 }}>
                          {r.c}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* live demo */}
        <section className={`${styles.section} ${styles.sectionWhite}`}>
          <div className={styles.sectionHead}>
            <span className="eyebrow eyebrow--accent">A real session</span>
            <h2 className={styles.h2}>What Sofía&rsquo;s hunt actually looks like</h2>
            <span className={styles.sectionSub}>
              ICU nurse, Madrid → Dublin. Every tool call shown is real MCP surface. Example data.
            </span>
          </div>
          <div className={styles.demo}>
            <div className={styles.transcript}>
              <div className={styles.transcriptBar}>
                <span className={styles.chatDot} /> Claude · mcpfor.work connector
              </div>
              <div className={styles.transcriptBody}>
                <span className={styles.msgUser} style={{ fontSize: 12.5, padding: "8px 13px" }}>
                  /hunt icu nurse dublin
                </span>
                <span className={styles.toolCall}>
                  <span className={styles.toolName}>hunt_plan</span> 3 sources · pack healthcare-ie v14
                </span>
                <span className={styles.toolCall}>
                  <span className={styles.toolName}>check_seen</span> 1 duplicate skipped — seen 12 days ago on IrishJobs
                </span>
                <span className={styles.msgBot} style={{ fontSize: 13.5 }}>
                  Found 12 roles, 3 new. Top match:
                </span>
                <div className={styles.matchCardBig}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 15 }}>ICU Staff Nurse — Mater Private Hospital</div>
                      <div style={{ fontSize: 12.5, color: "var(--ink-3)", display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                        Dublin · Full-time · <span className={styles.packChip} style={{ margin: 0 }}>healthcare-ie</span>
                      </div>
                    </div>
                    <span className={styles.fitRing}>91</span>
                  </div>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {["EU work rights ✓", "salary floor ✓", "English C1 ✓", "relocation ✓"].map((c) => (
                      <span key={c} className="chip chip--green" style={{ borderRadius: 5, fontSize: 11 }}>
                        {c}
                      </span>
                    ))}
                  </div>
                  <span style={{ fontSize: 12, color: "var(--ink-3)" }}>
                    Not seen before — checked against 214 tracked postings.
                  </span>
                </div>
                <span className={styles.msgUser} style={{ fontSize: 12.5, padding: "8px 13px" }}>
                  /apply
                </span>
                <span className={styles.toolCall}>
                  <span className={styles.toolName}>get_generation_brief</span> facts inventory + style profile loaded
                </span>
                <span className={styles.toolCall}>
                  <span className={styles.toolName}>ats_coverage_check</span> 11 covered · 2 synonyms · 1 addable · 1 genuine gap
                </span>
                <span className={styles.toolCall}>
                  <span className={styles.toolName}>request_submit</span> consent level L0 — human required
                </span>
                <div className={styles.pausedBanner}>
                  <span className={styles.pauseDot} style={{ background: "#d97706" }} />
                  <span>
                    <strong style={{ fontWeight: 600 }}>Paused.</strong> Sofía reads the draft and clicks Submit herself —
                    nothing is sent without her.
                  </span>
                </div>
              </div>
            </div>

            <div className={styles.sidebarCards}>
              <div className={styles.factsCard}>
                <div className={styles.factsTitle}>Facts inventory</div>
                <div className={styles.factsBody}>
                  {[
                    { fact: "6 years ICU, Hospital La Paz (Madrid)", src: "CV" },
                    { fact: "Cut ventilator-associated events 23% in 12 months", src: "Achievement #2" },
                    { fact: "NMBI registration in progress — decision Aug", src: "Confirmed answer" },
                  ].map((f) => (
                    <div key={f.src} className={styles.factItem}>
                      <span>{f.fact}</span>
                      <span>
                        <span className="chip" style={{ borderRadius: 5, fontSize: 10.5 }}>
                          {f.src}
                        </span>
                      </span>
                    </div>
                  ))}
                </div>
                <div className={styles.factsFoot}>Drafts may only claim what&rsquo;s on this card.</div>
              </div>
              <div className={styles.atsCard}>
                <span style={{ fontWeight: 600, fontSize: 13.5 }}>ATS coverage</span>
                <div className={styles.atsRows}>
                  {ATS.map((r) => (
                    <div key={r.label} className={styles.kvRow}>
                      <span style={{ color: "var(--ink-label)" }}>{r.label}</span>
                      <span className={`chip ${r.cls}`} style={{ borderRadius: 5, fontSize: 10 }}>
                        {r.chip}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* differentiators */}
        <section className={styles.section}>
          <h2 className={styles.h2} style={{ maxWidth: 560 }}>
            Built on four promises
          </h2>
          <div className={styles.grid2}>
            <div className={styles.promiseCard}>
              <span className={styles.promiseTitle}>It never fabricates</span>
              <span className={styles.promiseSub}>
                Every claim in every draft traces to your facts inventory — CV, achievements,
                confirmed answers. Genuine gaps are acknowledged, never stuffed with keywords.
              </span>
            </div>
            <div className={styles.promiseCard}>
              <span className={styles.promiseTitle}>It&rsquo;s always your call</span>
              <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                {[
                  { l: "L0", cls: "chip--green", t: "Supervised — you click Submit. The default." },
                  { l: "L1", cls: "chip--amber", t: "One-click approve — it fills, you confirm each one." },
                  { l: "L2", cls: "chip--indigo", t: "Autopilot — min score, daily cap, allowlisted sites. Interruptible, fully audited." },
                ].map((lvl) => (
                  <span key={lvl.l} className={styles.levelRow}>
                    <span className={`chip ${lvl.cls}`}>{lvl.l}</span>
                    {lvl.t}
                  </span>
                ))}
              </div>
            </div>
            <div className={styles.promiseCard}>
              <span className={styles.promiseTitle}>$5 is infrastructure, not token resale</span>
              <span className={styles.promiseSub}>
                Your Claude or ChatGPT subscription does all the thinking. We run zero server-side
                LLM calls — that&rsquo;s why it costs $5, not $50.
              </span>
            </div>
            <div className={styles.promiseCard}>
              <span className={styles.promiseTitle}>Your data leaves when you do</span>
              <span className={styles.promiseSub}>
                Self-host on SQLite and it never leaves your machine. Hosted: export everything as
                JSON or delete your account, any time. Salary floor stays private, always.
              </span>
            </div>
          </div>
        </section>

        {/* use cases */}
        <section className={`${styles.section} ${styles.sectionWhite}`}>
          <div className={styles.sectionHead}>
            <span className="eyebrow eyebrow--accent">Any sector, any country</span>
            <h2 className={styles.h2}>Packs teach your AI each portal. The community keeps them fresh.</h2>
          </div>
          <div className={styles.grid4}>
            {USE_CASES.map((u) => (
              <div key={u.pack} className={styles.useCard}>
                <span className={styles.useTitle}>{u.title}</span>
                <span className={styles.useSub}>{u.sub}</span>
                <span className={styles.packChip}>{u.pack}</span>
              </div>
            ))}
          </div>
          <span className={styles.contribute}>
            New portals ship as community pull requests — coverage grows every week, no app update
            needed. <a href="https://github.com/mcpforwork">Contribute a pack →</a>
          </span>
        </section>

        {/* pricing */}
        <section className={`${styles.section} ${styles.pricing}`} id="pricing">
          <div className={styles.sectionHead} style={{ alignItems: "center", textAlign: "center" }}>
            <span className="eyebrow eyebrow--accent">Pricing</span>
            <h2 className={styles.h2}>Same product. You bring the AI in both.</h2>
          </div>
          <div className={styles.pricingGrid}>
            <div className={styles.priceCard}>
              <span className={styles.priceName}>Self-host</span>
              <div className={styles.priceLine}>
                <span className={styles.priceValue}>Free</span>
                <span className={styles.priceNote}>forever · Apache-2.0</span>
              </div>
              <div className={styles.priceChecks}>
                <span className={styles.priceCheck}>
                  <b>✓</b>The full product — open-core parity
                </span>
                <span className={styles.priceCheck}>
                  <b>✓</b>Your machine, SQLite, your data
                </span>
                <span className={styles.priceCheck}>
                  <b>✓</b>All packs, all consent levels, digest via CLI
                </span>
              </div>
              <div className={styles.priceTermRow}>
                <span style={{ color: "var(--term-muted)" }}>$</span> uvx mcpforwork
              </div>
            </div>
            <div className={`${styles.priceCard} ${styles.priceCardHero}`}>
              <span className={styles.priceBadge}>Hosted</span>
              <span className={styles.priceName}>Hosted</span>
              <div className={styles.priceLine}>
                <span className={styles.priceValue}>$5</span>
                <span className={styles.priceNote}>/month flat · one plan, no tiers</span>
              </div>
              <div className={styles.priceChecks}>
                <span className={styles.priceCheck}>
                  <b>✓</b>Nothing to install — connect from claude.ai
                </span>
                <span className={styles.priceCheck}>
                  <b>✓</b>Sync, backups, live pack updates
                </span>
                <span className={styles.priceCheck}>
                  <b>✓</b>Web dashboard + daily digest email
                </span>
              </div>
              <Link href="/connect" className={styles.priceCta}>
                Connect to Claude
              </Link>
            </div>
          </div>
          <span className={styles.pricingFoot}>
            No seats. No token markup. Magic-link sign-in — no password, ever.
          </span>
        </section>

        {/* digest */}
        <section className={`${styles.section} ${styles.sectionWhite} ${styles.digest}`}>
          <div className={styles.digestCopy}>
            <span className="eyebrow eyebrow--accent">Daily digest</span>
            <h2 className={styles.h2}>Your pipeline comes to you — actionable from your inbox</h2>
            <span className={styles.sectionSub} style={{ maxWidth: 480 }}>
              A plain, templated snapshot — never generated prose, never a tracking pixel. Every
              item carries a copy-paste prompt that hands the action to your own AI. The email
              itself can&rsquo;t execute anything.
            </span>
            <div className={styles.trustLine}>
              <span>No images</span>
              <span className={styles.sep}>·</span>
              <span>No salary, ever</span>
              <span className={styles.sep}>·</span>
              <span>One-click unsubscribe</span>
            </div>
          </div>
          <div className={styles.digestCard}>
            <div className={styles.digestHead}>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>
                <span style={{ color: "var(--accent)" }}>mcp</span>for.work
              </span>
              <span style={{ color: "var(--ink-3)", fontSize: 11.5 }}>Tue 7 Jul · daily digest</span>
            </div>
            <div className={styles.digestBody}>
              <div className={styles.digestSection}>
                <span className={styles.digestLabel} style={{ color: "var(--warn)" }}>
                  Waiting on you (1)
                </span>
                <div className={`${styles.digestItem} ${styles.digestItemWarn}`}>
                  <span>ICU Staff Nurse — Mater Private · awaiting your submit</span>
                  <span className={styles.digestPrompt}>Resume application app_8K3D</span>
                </div>
              </div>
              <div className={styles.digestSection}>
                <span className={styles.digestLabel} style={{ color: "var(--accent)" }}>
                  New matches (3)
                </span>
                <div className={styles.digestItem}>
                  <span>Staff Nurse, Critical Care — St Vincent&rsquo;s · fit 86</span>
                  <span className={styles.digestPrompt}>Review match m_7Q2F</span>
                </div>
              </div>
              <span className={styles.digestFoot}>
                You get this because digest is on · Settings · Unsubscribe
              </span>
            </div>
          </div>
        </section>

        {/* testimonials (pre-launch) */}
        <section className={styles.section}>
          <span className={styles.preLaunch}>Illustrative examples — mcpfor.work is pre-launch</span>
          <div className={styles.grid3}>
            {QUOTES.map((q) => (
              <div key={q.who} className={styles.quoteCard}>
                <span className={styles.quote}>{q.quote}</span>
                <span className={styles.quoteWho}>{q.who}</span>
              </div>
            ))}
          </div>
        </section>

        {/* FAQ */}
        <section className={`${styles.section} ${styles.sectionWhite} ${styles.faq}`} id="faq">
          <h2 className={styles.h2}>Fair questions</h2>
          <div>
            <div className={styles.faqList}>
              {FAQ_FLAT.map((f) => (
                <div key={f.q} className={styles.faqItem}>
                  <span className={styles.faqQ}>{f.q}</span>
                  <span className={styles.faqA}>{f.a}</span>
                </div>
              ))}
            </div>
            <Link
              href="/faq"
              style={{ display: "inline-block", marginTop: 20, color: "var(--accent)", fontWeight: 500, fontSize: 14 }}
            >
              Read the full FAQ →
            </Link>
          </div>
        </section>

        {/* final CTA + footer */}
        <footer className={styles.footerCta}>
          <div className={styles.footerCtaInner}>
            <h2 className={styles.footerH2}>Job hunting is brutal. You shouldn&rsquo;t do it alone.</h2>
            <span className={styles.footerSub}>Two minutes to connect. Your AI, your browser, your rules.</span>
            <div className={styles.ctaRow} style={{ justifyContent: "center" }}>
              <Link href="/connect" className={styles.ctaPrimary} style={{ padding: "13px 24px" }}>
                Connect to Claude
              </Link>
              <a href="https://github.com/mcpforwork" className={styles.footerBtnGhost}>
                Self-host free{" "}
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "#78716c" }}>★ 1</span>
              </a>
            </div>
          </div>
          <div className={styles.footerBar}>
            <span style={{ fontFamily: "var(--font-mono)" }}>
              <span style={{ color: "#6366f1" }}>mcp</span>
              <span style={{ color: "#d6d3d1" }}>for.work</span> · Apache-2.0
            </span>
            <div className={styles.footerLinks}>
              <a href="https://github.com/mcpforwork">GitHub</a>
              <Link href="/docs">Docs</Link>
              <Link href="/faq">FAQ</Link>
              <Link href="/privacy">Privacy</Link>
              <Link href="/terms">Terms</Link>
              <Link href="/security">Security</Link>
              <a href="mailto:hello@mcpfor.work">Contact</a>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
