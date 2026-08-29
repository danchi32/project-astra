# n8n workflows

Import-ready JSON for the marketing automation. n8n orchestrates; it does not decide.

## What n8n owns, and what it does not

n8n runs the steps that belong **outside the visitor's request path** — the model scoring
pass, the CRM sync, retries, and follow-up sequences. It does not own lead state, and it
is not required for a lead to be captured, scored, acknowledged or alerted: all four
happen in the service before this workflow is even called.

That division is deliberate. A workflow is a JSON blob edited live in a browser, so it
cannot be the thing that decides whether something happens — it is the thing that makes
already-decided work happen reliably. The same rule the product applies to remediation
tiers: enforced in code, never in a canvas.

**The acknowledgement email is not here.** It stays inline in the service. Moving it out
was the original plan, on the strength of an 8-second intake measured from a laptop in
India; production measures 2.9 seconds, well inside `contact.php`'s 6-second timeout. The
~2 s saved was not worth making the single most valuable message in the funnel depend on
n8n being up.

## Setup

### 1. Credentials

Create three credentials in n8n, then **re-select each one in the node's UI after import**.

Do not skip that step, and do not assume the import carried it. The workflow JSON ships
`"id": "REPLACE_WITH_CREDENTIAL_ID"`, and a node pointing at an id that does not exist
does not fail loudly — **n8n sends the request with no auth header at all**. On this
service that is an ordinary 401, indistinguishable at a glance from a wrong token, so the
natural reaction is to go and check the token, which is fine, which wastes the afternoon.

This happened. Every scheduled sweep 401'd from the moment the workflows were activated,
along with `Rescore with the model` and `Sync to Bigin` in workflow 01 — three nodes, one
missing credential. The service now logs which of the three possible mistakes it was
(`no Authorization header was sent` / wrong scheme / wrong token), so the next occurrence
is a one-line diagnosis:

```bash
gcloud logging read 'resource.type="cloud_run_revision"
  AND resource.labels.service_name="astra-marketing"
  AND (logName:"stderr" OR logName:"stdout")
  AND textPayload:"admin request refused"' --limit=5 --freshness=1h
```

Nodes that need `ASTRA admin token` attached: `Sync anything pending` (workflow 02),
`Rescore with the model` and `Sync to Bigin` (workflow 01).

| Credential | Type | Value |
|---|---|---|
| `ASTRA webhook token` | Header Auth | Name `X-Astra-Webhook-Token`, value = `ASTRA_MKT_N8N_WEBHOOK_SECRET` |
| `ASTRA admin token` | Header Auth | Name `Authorization`, value `Bearer <ASTRA_MKT_ADMIN_TOKEN>` |
| `ASTRA marketing bot` | Telegram | The bot token from BotFather |

The webhook is protected by n8n's built-in Header Auth rather than an HMAC check in a Code
node: the Code node's crypto access is sandboxed on n8n Cloud, and this hop is already
server-to-server over TLS and not publicly reachable. HMAC is used where it earns its
keep — the public `contact.php` → service hop, where replay protection matters. The
service sends both headers, so either check is available.

### 2. Environment variables

In n8n → Settings → Variables:

| Variable | Value |
|---|---|
| `ASTRA_MKT_URL` | `https://astra-marketing-fmuizr4sda-as.a.run.app` |
| `ASTRA_TELEGRAM_CHAT_ID` | the same chat id the service alerts |

### 3. Import and activate

Workflows → Import from File → pick the JSON → **Activate**. n8n then shows the
production webhook URL for `01-lead-pipeline`.

### 4. Point the service at it

Set that URL as `ASTRA_MKT_N8N_LEAD_WEBHOOK_URL`, and any shared secret as
`ASTRA_MKT_N8N_WEBHOOK_SECRET`, in Secret Manager. Until both are set the dispatcher is
inert — the service captures, scores, acknowledges and alerts exactly as it does now, and
simply does not call out. Nothing breaks by leaving this unconfigured.

## Workflows

| File | Trigger | Does |
|---|---|---|
| `01-lead-pipeline.json` | Webhook from the service | Model rescore → Bigin sync → Telegram on failure |
| `02-crm-sweeper.json` | Every 30 minutes | `POST /leads/sync-pending` — the backstop for anything workflow 01 missed |
| `03-error-alerts.json` | n8n error trigger | Telegram on any failed execution |

Set **03 as the error workflow** for 01 and 02: each workflow's Settings → Error Workflow.
It is not automatic, and without it a failed execution is a red row in a list nobody
opens — an automation that fails silently is worse than one that was never built, because
it is trusted.

Two deliberate choices about noise:

- **The sweeper says nothing on a clean run.** It fires 48 times a day and will find
  nothing almost every time. A message per run trains the reader to ignore the channel,
  which is exactly when the one that matters arrives.
- **Thirty minutes, not five.** This is a backstop; workflow 01 syncs within seconds. A
  tighter interval mostly wakes a scaled-to-zero Cloud Run instance to be told there is
  nothing to do.

Planned: tier-based follow-up sequences.

## Notes that will save time

- **`responseMode: onReceived`.** The service does not wait for this workflow and treats a
  slow response as a failed dispatch. Answering immediately keeps `dispatched_at` honest.
- **Both HTTP nodes use `neverError` + `continueRegularOutput`,** so the run always reaches
  the failure check. Without it a 502 from Bigin ends the execution early and the alert
  never fires — a green-looking failure.
- **`Sync to Bigin` reads `lead_id` from the `Lead fields` node,** not from the previous
  node's output, which is the rescore response.
- **The failure alert says what did *not* fail.** Capture, the acknowledgement and the
  Telegram alert all happened before this workflow ran; a bare "pipeline failed" at 2am
  reads as a lost lead when nothing was lost.
