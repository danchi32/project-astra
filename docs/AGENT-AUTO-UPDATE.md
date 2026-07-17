# ASTRA Agent Auto-Update

Installed agents check the backend for a newer release and, when one is available and its
signature verifies, download and apply it automatically — no touch on the endpoint.

## Security model (read this first)

An auto-update channel is a remote-code path to every managed PC. The design keeps the
**signing key off the backend** so that a backend compromise cannot forge a fleet update:

```
  CI (signs, key in GitHub secret)  ──►  GitHub Releases (signed manifest + zip)
                                              │  (backend fetches + relays verbatim)
                                              ▼
  Backend  ──►  GET /api/v1/agent/update  ──►  Agent
                                              │  verifies signature vs PINNED public key
                                              ▼  + SHA-256 of the download
                                          apply, restart service
```

- **The agent trusts only its pinned public key.** Anything that doesn't verify is ignored.
- **The backend is not a signing authority.** It relays the already-signed manifest it fetches
  from the release. The worst a breached backend can do is withhold or replay a *validly signed*
  manifest — it cannot mint a new one.
- **The download is hash-checked** against the signed manifest before it's ever executed.
- **Fail-safe:** with the placeholder public key still in the build, the agent verifies no key
  and simply never updates. The feature turns on only once you pin a real key.
- **Anti-replay floor:** the agent remembers the highest version it has ever seen in a signed
  manifest (and honours an optional signed `min_version`), and refuses anything at or below that
  floor — so a replayed older-but-signed manifest can't roll it back. (Residual: an agent that
  has *never* reached an honest backend since a newer release can still be pointed at an older
  signed release; closing that fully needs a time-based freshness field — a planned follow-up.)
- **Hardened working area:** staging and the apply script live under the admin-only install root
  with an explicit SYSTEM/Administrators-only DACL — never world-writable `ProgramData` — so a
  local unprivileged user can't tamper with files the LocalSystem service then executes.
- **Strict manifest shape:** version/sha256/url are format-validated (`X.Y.Z`, 64-hex, `https://`)
  even behind a valid signature, so nothing unexpected can reach a file path or the apply script.

## One-time setup

### 1. Generate the signing keypair (do this once, keep the private key safe)

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out agent-update-private.pem
openssl rsa -in agent-update-private.pem -pubout -out agent-update-public.pem
```

- **Public key** → paste the contents of `agent-update-public.pem` into
  `agent/src/AstraAgent.Service/Update/update-signing-public.pem`, replacing the placeholder.
  (Public keys are safe to commit.)
- **Private key** → add the contents of `agent-update-private.pem` as the GitHub Actions secret
  **`AGENT_UPDATE_SIGNING_KEY`** (repo → Settings → Secrets and variables → Actions).
  **Never commit it or paste it anywhere else.** If it leaks, anyone can push code to every
  installed agent — rotate immediately (new keypair, new public key in the build, re-release).

### 2. Point the backend at your release channel

Set these on the backend (e.g. Railway variables), replacing `OWNER/REPO`:

```
ASTRA_AGENT_UPDATE_MANIFEST_URL=https://github.com/OWNER/REPO/releases/latest/download/manifest.json
ASTRA_AGENT_UPDATE_SIGNATURE_URL=https://github.com/OWNER/REPO/releases/latest/download/manifest.json.sig
```

Until both are set, `/api/v1/agent/update` reports "no update available" and agents stay put.

## Cutting a release

1. Bump the version in **both** places so they match:
   - `agent/src/AstraAgent.Service/AgentOptions.cs` → `AgentVersion.Current`
   - `agent/src/AstraAgent.Service/AstraAgent.Service.csproj` → `<Version>`
2. Commit, then tag and push:
   ```bash
   git tag agent-v0.2.0
   git push origin agent-v0.2.0
   ```
3. The **Release ASTRA Agent** workflow builds the agent, signs the manifest with your CI key,
   and publishes `AstraAgent.zip` + `manifest.json` + `manifest.json.sig` to a GitHub Release.
   (It fails fast if `AgentVersion.Current` doesn't equal the tag, or if the secret is missing.)

Within one update-check interval (default 60 min), online agents notice the newer version,
verify it, and apply it. The service restarts itself into the new build.

## How the apply step works

A running Windows service holds its own files locked, so the swap can't happen in-process.
The agent stages the verified files, launches a small self-deleting script, and stops the
service; the script waits for the host process to exit, mirrors the new files in (preserving
the local `appsettings.json` with your server URL + enrollment), restarts the service, and
cleans up.

## Scope / follow-up

- **This covers the always-on Windows service.** The tray chat app runs in the user's session
  and can't be safely swapped from a session-0 service mid-use, so it is **not** auto-updated
  yet — redistribute it with the installer when it changes. A dedicated tray self-updater is
  the planned next step.
- The update-check interval is configurable via `Astra:UpdateCheckIntervalMinutes` (min 5).
