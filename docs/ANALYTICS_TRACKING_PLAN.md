# Technomate / ASTRA Analytics Tracking Plan

Updated: 2026-08-30

## Decision framework

The weekly question is whether qualified organizations are progressing from an attributable website visit to an agreed ASTRA pilot. Do not use page views alone as a success metric.

## Production tools

- GA4 property: `G-80HZL6TZGW`, loaded through consent mode
- Microsoft Clarity project: `yarda8bkso`, loaded after consent
- Meta Pixel: optional production environment value
- Search Console: organic query and landing-page measurement

No email address, name, phone number, company name, message text, account ID or device ID may be sent as an analytics event parameter.

## Event contract

| Event | Meaning | Parameters | Trigger | GA4 key event |
|---|---|---|---|---|
| `book_demo_click` | Visitor leaves for the booking flow | first-touch UTMs, landing page, referrer, destination, CTA text, page path | Click on configured booking URL | Yes |
| `signup_click` | Visitor leaves for the ASTRA account flow | first-touch UTMs, landing page, referrer, destination, CTA text, page path | Click on configured app URL | Yes |
| `generate_lead` | Website form or lead magnet completes successfully | lead type/form name plus first-touch attribution | Server-confirmed form success or local resource delivery | Yes |
| `site_assistant_open` | Website assistant opened | none | Open action | No |
| `site_assistant_question` | Assistant returned a response | grounded flag | Successful response | No |
| `site_assistant_handoff` | Assistant sends visitor to contact | destination | Handoff click | No |

First-touch attribution is stored only for the browser session, so a campaign landing visit remains attached after internal navigation. If browser storage is unavailable, the current page context is used. No cross-session profile is created.

## GA4 administration checklist

1. In **Admin+�u���R Data display+�u���R Events**, confirm the three conversion events have arrived.
2. Mark `book_demo_click`, `signup_click` and `generate_lead` as key events.
3. Use **once per session** counting for these lead actions.
4. Create event-scoped custom dimensions only when reporting requires them: `utm_campaign`, `cta_text`, `page_path`, and `lead_type`.
5. Define internal traffic for the Technomate team and exclude it from the reporting view.
6. Keep data retention at 14 months only if it matches the published privacy policy and operational need.

## Weekly funnel report

Run every Monday for the previous Monday-Sunday period.

| Funnel stage | Source | Definition |
|---|---|---|
| Unique visitors | GA4 | Active users, with internal traffic excluded |
| Non-brand search clicks | Search Console | Web clicks where query does not contain Technomate or ASTRA brand terms |
| Leads | GA4 | Users with `generate_lead` |
| Demo bookings | Booking system | Completed booking, reconciled against `book_demo_click` |
| Signups | Product database | Completed accounts, reconciled against `signup_click` |
| Qualified opportunities | Sales tracker/CRM | Organization fits Windows fleet and buyer criteria |
| Pilot starts | Product database | First approved pilot device reports successfully |

Break the first five stages down by source/medium, campaign, and landing page. Report both counts and step-to-step conversion rates. Booking clicks and signup clicks are intent signals, not completed bookings or accounts.

## Data-quality checks

- Test each key event after consent is granted and confirm it in GA4 Realtime/DebugView.
- Confirm one click produces one event and that CTA text/page path are populated.
- Navigate from a UTM landing page to `/pilot/`, convert, and confirm the original UTM values remain.
- Confirm no form values or authenticated product identifiers appear in event parameters.
- Reconcile GA4 intent events with booking, product and sales source-of-truth totals every week.
