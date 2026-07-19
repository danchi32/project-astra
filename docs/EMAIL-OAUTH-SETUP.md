# Email — OAuth setup (Phase 2, run in parallel)

The DNS-verified sending model is **built and shipping now** (Settings → Email). OAuth
("Connect Google Workspace / Microsoft 365") is Phase 2. Its long pole is **Google's
security review**, which can take several weeks — so start the account/app registration
below *now*, in parallel, even though the ASTRA code for it lands later.

Nothing here touches production until we wire the OAuth flows in; these steps just get your
provider apps registered and reviewed so they're ready when the code is.

---

## A. Google Workspace (Gmail API) — start this first (longest lead time)

Goal: ASTRA becomes a verified Google OAuth app allowed to send mail as a customer's mailbox.

1. **Create a Google Cloud project** — https://console.cloud.google.com → new project "ASTRA Email".
2. **Enable the Gmail API** — APIs & Services → Library → *Gmail API* → Enable.
3. **OAuth consent screen** — APIs & Services → OAuth consent screen:
   - User type: **External**
   - App name, support email, **app logo**, app home page, **privacy policy URL**, terms URL
   - Authorized domains: `technomateai.com`
4. **Add the scope** `https://www.googleapis.com/auth/gmail.send` (this is a **restricted** scope — it's what triggers the review).
5. **Create OAuth client credentials** — APIs & Services → Credentials → OAuth client ID → Web application. Add the redirect URI we'll use (placeholder for now):
   `https://api.astra.technomateai.com/api/v1/integrations/google/callback`
   Save the **client ID + secret** (these go in Railway later — do NOT commit them).
6. **Submit for verification** (the slow part). Google requires, for restricted scopes:
   - A **privacy policy** that explains the Gmail data use
   - A **demo video** showing the OAuth grant + how the scope is used
   - Justification for `gmail.send`
   - Likely an annual **third-party security assessment (CASA)** since gmail.send is restricted
   - Turnaround: **days to several weeks.** Start now.

> Faster alternative for a single Workspace (your own or a design-partner customer):
> **domain-wide delegation** with a service account (Google Admin → Security → API controls
> → Domain-wide delegation → add the service account client ID + `gmail.send` scope). This
> avoids per-user consent but is admin-level and per-customer — good for pilots, not for
> self-serve signups.

---

## B. Microsoft 365 (Microsoft Graph) — lighter, do this second

Goal: ASTRA becomes a multi-tenant Entra (Azure AD) app allowed to send mail via Graph.

1. **Register an app** — https://entra.microsoft.com → App registrations → New registration:
   - Name: "ASTRA Email"
   - Supported account types: **Accounts in any organizational directory (multi-tenant)**
   - Redirect URI (Web): `https://api.astra.technomateai.com/api/v1/integrations/microsoft/callback`
2. **API permissions** — Microsoft Graph → add **`Mail.Send`**:
   - *Delegated* (send as the signed-in user) — simplest, and the user consents themselves, or
   - *Application* (send as configured mailboxes) — needs **admin consent** + an **Application Access Policy** to restrict which mailboxes it may send as (recommended so it isn't "send as anyone").
3. **Certificates & secrets** — create a client secret. Save the **client ID + secret + tenant** (Railway later; do NOT commit).
4. **Publisher verification** — verify your Microsoft Partner/publisher identity so the consent screen shows "verified" (reduces admin friction). Much faster than Google's review.
5. Customer admins then click **Connect** and **Grant admin consent** for their tenant — no DNS changes on their side.

---

## C. What ASTRA will add when you're ready (for context)

- `integrations/google/*` and `integrations/microsoft/*` OAuth start + callback routes
- Encrypted refresh-token storage per org (new columns on `email_settings`, method =
  `oauth_google` / `oauth_microsoft`)
- Send paths: Gmail API `users.messages.send` / Graph `sendMail`
- `EmailIntegrationService.resolve_sender()` already exists as the single seam — OAuth just
  becomes another verified sender source, so the asset-email feature won't change

## D. Secrets you'll hand ASTRA later (via Railway variables — never commit)

| Provider | Variables |
|---|---|
| Google | `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` |
| Microsoft | `MS_OAUTH_CLIENT_ID`, `MS_OAUTH_CLIENT_SECRET` |

---

### TL;DR ordering
1. **Today:** register the Google Cloud app + submit consent-screen verification (weeks-long).
2. **Today/soon:** register the Microsoft Entra app + publisher verification.
3. **Meanwhile:** customers use the DNS-verified model (already live).
4. **When Google clears:** tell me, and I'll wire the OAuth routes + token storage — the
   sender resolver is already in place.
