# Technomate Marketing Execution Tracker

Updated: 2026-08-30

Status legend: `DONE`, `IN PROGRESS`, `NEXT`, `BLOCKED`, `LATER`

## North-star outcome

Qualified organizations that start an agreed ASTRA pilot. Supporting conversions are booked demos, completed product sign-ups and qualified lead-magnet downloads.

## Weeks 1-2: measurement and trust

| Work item | Status | Owner | Evidence / next action |
|---|---|---|---|
| GA4 base tag | DONE | Engineering | Production measurement ID is wired through consent mode. |
| Track demo clicks | DONE | Engineering | `book_demo_click` includes attribution and destination. |
| Track signup clicks | DONE | Engineering | `signup_click` maps to Meta `StartTrial`. |
| Track contact and lead-magnet leads | DONE | Engineering | `generate_lead` fires after contact success and lead-magnet delivery. |
| Mark GA4 events as key events | NEXT | Founder | In GA4 Admin, mark `book_demo_click`, `signup_click` and `generate_lead` as key events. |
| Completed-onboarding event | IN PROGRESS | Engineering | First successful device reporting is the proposed milestone. Portal tracking needs a privacy-safe server-side design before implementation. |
| Google Search Console | NEXT | Founder | Verify domain property and submit `https://technomateai.com/sitemap.xml`. |
| Microsoft Clarity | DONE | Founder + Engineering | Project `yarda8bkso` configured as a repository variable, deployed and verified in the live bundle. |
| First-touch campaign attribution | DONE | Engineering | Session-scoped attribution now survives internal navigation; conversion events include CTA text and page path without PII. |
| Weekly funnel report | IN PROGRESS | Growth | Measurement definitions, sources, reconciliation rules and Monday cadence documented in `docs/ANALYTICS_TRACKING_PLAN.md`; first baseline awaits source data. |
| Security and trust page | DONE | Engineering | `/security/` implemented, linked in the footer and sitemap, and production build verified. |
| Replace unsupported performance claims | DONE | Engineering | Homepage public stats render only from the live platform; empty/unavailable data renders no claim. |
| Founder/team credibility | BLOCKED | Founder | Supply approved founder bio, headshot and real LinkedIn URL. |
| Response-time expectation | DONE | Founder | Immediate automated acknowledgement/execution may be stated for eligible online-device actions; no instant human-response guarantee. |
| Pilot terms | DONE | Sales + Engineering | 10-device, free guided, 14-day controlled pilot approved; public `/pilot/` page built and production build verified. |
| Google Business Profile | DONE | Founder | Profile created and core fields completed. Continue weekly posts, photos and review requests. |

## First four weekly funnel rows

| Week starting | Unique visitors | Non-brand search clicks | Leads | Demo bookings | Signups | Qualified opportunities | Pilot starts | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 2026-08-31 |  |  |  |  |  |  |  | Baseline |
| 2026-09-07 |  |  |  |  |  |  |  |  |
| 2026-09-14 |  |  |  |  |  |  |  |  |
| 2026-09-21 |  |  |  |  |  |  |  |  |

## Weeks 3-6 queue

1. AI IT support India landing page. - DONE; production build verified.
2. Windows endpoint automation landing page. - DONE; production build verified.
3. Self-healing IT landing page. - DONE; production build verified.
4. Managed IT services Noida / Greater Noida landing page. - LATER; local-only positioning deprioritized in favor of pan-India software reach.
5. IT support for organizations with 50-500 employees landing page. - DONE; India-wide ASTRA software positioning and production build verified.
6. Intune and ManageEngine comparison pages with dated sources. - DONE; official sources reviewed 30 August 2026 and production build verified.
7. Publish two high-intent articles per month. - DONE for August; buyer guide and endpoint automation pilot checklist added and production build verified.

## India-wide acquisition execution

| Work item | Status | Owner | Evidence / next action |
|---|---|---|---|
| B2B ICP and scoring model | DONE | Growth | India-wide 25-500 Windows endpoint ICP, buying signals, disqualifiers and 100-point qualification rubric documented. |
| Compliance-safe prospect tracker | DONE | Growth | CSV template captures source lineage, verification, lawful basis, opt-out and deletion date. |
| Cold outreach sequence | DONE | Growth + Sales | Five-touch, 24-day sequence created without fabricated proof; first-touch CTA asks for a reply. |
| LinkedIn organic campaign | DONE | Founder + Growth | Five posts and unique UTM links ready for founder/company publishing. |
| First 25 verified accounts | IN PROGRESS | Growth | Batches 1-3 contain 15 sourced candidates across technology, manufacturing, engineering and GCC operations. No account is Hot until Windows fit, buyer and deliverability gates pass. |
| First controlled outreach batch | NEXT | Founder | Send to a maximum of 10 newly verified contacts per business day; stop on deliverability or complaint warnings. |

## Decision log

- ASTRA is the lead offer; managed services and hardware support the implementation story.
- Booked demo is the primary website conversion; sign-up and lead magnet are secondary.
- No customer logos, testimonials or outcome numbers are published without approval and evidence.
- Paid acquisition starts only after landing-page and conversion tracking are verified.
