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
| Completed-onboarding event | NEXT | Engineering | Define the first-value milestone, then emit it from the product rather than counting account creation. |
| Google Search Console | NEXT | Founder | Verify domain property and submit `https://technomateai.com/sitemap.xml`. |
| Microsoft Clarity | BLOCKED | Founder | Create project, add `NEXT_PUBLIC_CLARITY_ID` as a GitHub Actions repository variable, then redeploy. |
| Weekly funnel report | NEXT | Growth | Record sessions, source/medium, landing page, leads, demos, signups, qualified opportunities and pilots every Monday. |
| Security and trust page | DONE | Engineering | `/security/` implemented, linked in the footer and sitemap, and production build verified. |
| Replace unsupported performance claims | DONE | Engineering | Homepage public stats render only from the live platform; empty/unavailable data renders no claim. |
| Founder/team credibility | BLOCKED | Founder | Supply approved founder bio, headshot and real LinkedIn URL. |
| Response-time expectation | NEXT | Founder | Confirm a serviceable sales response SLA before publishing it. |
| Pilot terms | NEXT | Sales + Engineering | Define device limit, duration, success criteria, support scope and exit process. |
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
7. Publish two high-intent articles per month.

## Decision log

- ASTRA is the lead offer; managed services and hardware support the implementation story.
- Booked demo is the primary website conversion; sign-up and lead magnet are secondary.
- No customer logos, testimonials or outcome numbers are published without approval and evidence.
- Paid acquisition starts only after landing-page and conversion tracking are verified.
