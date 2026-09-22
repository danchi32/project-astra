"use client";
import { useEffect, useRef, useState } from "react";
import { ScreenShare, X, Loader2, ShieldCheck, Hourglass, ExternalLink } from "lucide-react";
import {
  requestRemoteSession, getRemoteSession, endRemoteSession,
  MIN_REASON_LENGTH, type RemoteSession,
} from "@/lib/api/remote-control";
import { apiErrorMessage } from "@/lib/utils";

/**
 * Ask for someone's screen, wait for them to answer, then show it.
 *
 * Three states, and the middle one is the point. Between asking and seeing there is a
 * person deciding, and this component's job is to represent that honestly — a countdown
 * the server owns, and an outcome that says what actually happened rather than rounding
 * everything to "denied".
 */

const POLL_MS = 2000;

/** What the technician is told, per outcome. */
const OUTCOME: Record<string, { title: string; body: string; tone: "bad" | "warn" }> = {
  declined: {
    title: "They said no",
    // An answer, and a final one. Asking again immediately is pestering somebody who has
    // already told you what they want.
    body: "They declined the session. Ask them directly before requesting again.",
    tone: "bad",
  },
  no_response: {
    title: "No answer",
    // NOT a refusal. Treating it as one is the exact mistake this wording exists to stop.
    body: "The prompt timed out — they may be away from the machine or missed it behind another window. Try again, or contact them first.",
    tone: "warn",
  },
  expired: {
    title: "Session expired",
    body: "They agreed, but the session wasn't opened in time. Request it again.",
    tone: "warn",
  },
  failed: {
    title: "Couldn't connect",
    body: "The remote service couldn't start the session. This is not something they did.",
    tone: "bad",
  },
};

export function RemoteControlButton({
  deviceId, hostname, iconOnly = true,
}: { deviceId: string; hostname: string; iconOnly?: boolean }) {
  const [phase, setPhase] = useState<"idle" | "asking" | "waiting" | "viewing" | "done">("idle");
  const [reason, setReason] = useState("");
  const [session, setSession] = useState<RemoteSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // `poll` re-arms itself from inside a closure, so it would read whatever `phase` was
  // when that closure was made. The ref is always current.
  const phaseRef = useRef(phase);
  useEffect(() => { phaseRef.current = phase; }, [phase]);

  // The viewer URL, FROZEN the first time it appears. The backend mints a fresh one (new
  // cookie, new IV) on every GET, so re-reading it each poll would hand back a different
  // link; captured once, it stays put and the poll still updates `session` for status.
  const viewerUrlRef = useRef<string | null>(null);

  // The remote desktop opens as its OWN top-level browser tab, not an embedded iframe. In
  // the portal's iframe the relay's desktop connection churns and dies every 15-40s and
  // reconnects — proven by isolating it: the identical viewer URL opened as a normal tab
  // runs rock-solid for minutes. So we hold that tab's window here to point it at the link,
  // refocus it, and close it on disconnect. Opened inside the click that asks (see `ask`),
  // never from an async callback, or the browser blocks it as an unsolicited popup.
  const viewerWindowRef = useRef<Window | null>(null);

  // Stop polling when the component goes away — a device page left in a background tab
  // should not keep asking the server about a session nobody is watching.
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  function reset() {
    if (timer.current) clearTimeout(timer.current);
    if (viewerWindowRef.current && !viewerWindowRef.current.closed) viewerWindowRef.current.close();
    viewerWindowRef.current = null;
    viewerUrlRef.current = null;
    setPhase("idle"); setReason(""); setSession(null); setError(null); setBusy(false);
  }

  // Point the already-open tab at the desktop (no user gesture needed to navigate a window
  // we own), or open one if it was blocked or the person closed it. The fallback only
  // succeeds from a user gesture — which "Reopen" is, and the async poll is not, so a tab
  // opened up front in `ask` is what makes the seamless case work.
  function pointViewerAt(url: string) {
    const win = viewerWindowRef.current;
    if (win && !win.closed) { win.location.href = url; win.focus(); }
    else { viewerWindowRef.current = window.open(url, "_blank"); }
  }

  async function ask() {
    if (reason.trim().length < MIN_REASON_LENGTH) return;
    // Open the desktop's tab NOW, synchronously inside this click, so the browser treats it
    // as user-initiated and does not block it. It starts blank and gets pointed at the link
    // the moment one is minted. It must be its own top-level tab, not an iframe — see the
    // note on viewerWindowRef for why an embedded frame will not hold the connection.
    viewerWindowRef.current = window.open("about:blank", "_blank");
    setBusy(true); setError(null);
    try {
      const created = await requestRemoteSession({ device_id: deviceId, reason: reason.trim() });
      setSession(created);
      // The link is issued with the pending session, because opening it is what puts the
      // prompt on the person's screen — there is no separate step to wait through. The relay
      // holds the stream until they allow it and shows its own waiting state in the tab.
      if (created.viewer_url) {
        viewerUrlRef.current = created.viewer_url;   // freeze it once
        pointViewerAt(created.viewer_url);
        setPhase("viewing");
      } else {
        setPhase("waiting");   // keep the blank tab; the poll points it once a link appears
      }
      poll(created.id);
    } catch (e) {
      // No session — do not leave an empty tab sitting open.
      if (viewerWindowRef.current && !viewerWindowRef.current.closed) viewerWindowRef.current.close();
      viewerWindowRef.current = null;
      setError(apiErrorMessage(e, "Couldn't reach the server."));
    } finally {
      setBusy(false);
    }
  }

  function poll(id: string) {
    timer.current = setTimeout(async () => {
      try {
        const next = await getRemoteSession(id);
        setSession(next);
        // Keep polling THROUGH the viewing state. The frame shows what is happening on
        // the screen; this tells us what happened to the request — and a refusal has to
        // close the frame, or the technician sits watching a viewer that will never fill.
        if (["declined", "no_response", "expired", "failed", "ended"].includes(next.status)) {
          setPhase("done"); return;
        }
        // First time a link appears, freeze it and point the waiting tab at it. Never
        // re-point — the next poll's link is a different cookie for the same session, and
        // navigating the tab again would reload the desktop mid-session.
        if (next.viewer_url && !viewerUrlRef.current) {
          viewerUrlRef.current = next.viewer_url;
          pointViewerAt(next.viewer_url);
          setPhase("viewing");
        }
        poll(id);
      } catch (e) {
        setError(apiErrorMessage(e, "Couldn't reach the server."));
        setPhase("done");
      }
    }, POLL_MS);
  }

  async function finish() {
    if (session) { try { await endRemoteSession(session.id); } catch { /* already ended */ } }
    reset();
  }

  const label = "Remote control";

  return (
    <>
      <button
        onClick={() => { setPhase("asking"); setError(null); }}
        title={`${label} — asks the person at ${hostname} for permission first`}
        aria-label={label}
        className={iconOnly
          ? "inline-flex items-center justify-center w-7 h-7 rounded-lg shrink-0"
          : "inline-flex items-center gap-2 px-3 h-9 rounded-lg text-sm font-medium"}
        style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
      >
        <ScreenShare size={iconOnly ? 13 : 15} />
        {!iconOnly && label}
      </button>

      {/* Ask ------------------------------------------------------------ */}
      {phase === "asking" && (
        <Overlay onClose={() => !busy && reset()}>
          <Head title={`Request remote control — ${hostname}`} onClose={() => !busy && reset()} />
          <p className="text-sm mb-3" style={{ color: "var(--text-secondary)" }}>
            The person using this machine will be asked to allow it, and will see your
            name and the reason below. Nothing happens unless they agree.
          </p>
          <label className="block text-xs mb-1" style={{ color: "var(--text-secondary)" }}>
            Why do you need to connect?
          </label>
          <textarea
            id="remote-control-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            placeholder="Outlook keeps crashing and the restart didn't help"
            className="w-full rounded-lg px-3 py-2 text-sm"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          />
          <div className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
            They read this. {reason.trim().length < MIN_REASON_LENGTH
              ? `At least ${MIN_REASON_LENGTH} characters.`
              : " "}
          </div>
          {error && <Error text={error} />}
          <Actions>
            <Ghost onClick={reset} disabled={busy}>Cancel</Ghost>
            <Primary onClick={ask} disabled={busy || reason.trim().length < MIN_REASON_LENGTH}>
              {busy ? "Asking…" : "Ask permission"}
            </Primary>
          </Actions>
        </Overlay>
      )}

      {/* Wait ----------------------------------------------------------- */}
      {phase === "waiting" && (
        <Overlay onClose={finish}>
          <Head title={`Waiting for ${hostname}`} onClose={finish} />
          <div className="flex items-center gap-3 py-2">
            <Loader2 size={18} className="animate-spin" style={{ color: "var(--accent)" }} />
            <div className="text-sm" style={{ color: "var(--text-primary)" }}>
              Asking the person at the machine…
              {/* The countdown comes from the server, because the server is what enforces
                  it. A timer running locally would drift and show "10s left" on a request
                  that had already lapsed. */}
              {session?.expires_in_seconds != null && (
                <span style={{ color: "var(--text-secondary)" }}>
                  {" "}{session.expires_in_seconds}s left to answer
                </span>
              )}
            </div>
          </div>
          <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
            They can take their time — you'll see their screen the moment they allow it.
          </p>
          {error && <Error text={error} />}
          <Actions>
            <Ghost onClick={finish}>Cancel request</Ghost>
          </Actions>
        </Overlay>
      )}

      {/* View — the desktop runs in its own tab; this panel tracks and ends it -------- */}
      {phase === "viewing" && viewerUrlRef.current && (
        <Overlay onClose={finish}>
          <Head title={`Connected to ${hostname}`} onClose={finish} />
          <div className="flex items-start gap-3 py-1">
            <ShieldCheck size={16} className="mt-0.5 shrink-0" style={{ color: "#10b981" }} />
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              The remote desktop opened in a new browser tab. Keep that tab open while you
              work — the person can end the session at any time. If it didn't open, or you
              closed it, reopen it below.
            </p>
          </div>
          {error && <Error text={error} />}
          <Actions>
            <Ghost onClick={() => viewerUrlRef.current && pointViewerAt(viewerUrlRef.current)}>
              <span className="inline-flex items-center gap-1.5"><ExternalLink size={14} /> Reopen desktop</span>
            </Ghost>
            <Primary onClick={finish}>Disconnect</Primary>
          </Actions>
        </Overlay>
      )}

      {/* Outcome -------------------------------------------------------- */}
      {phase === "done" && (
        <Overlay onClose={reset}>
          {(() => {
            const o = OUTCOME[session?.status ?? ""] ?? {
              title: "Session ended",
              body: session?.duration_seconds
                ? `The session lasted ${Math.round(session.duration_seconds / 60)} minute(s).`
                : "The session has ended.",
              tone: "warn" as const,
            };
            return (
              <>
                <Head title={o.title} onClose={reset} />
                <div className="flex items-start gap-3 py-1">
                  <Hourglass size={16} className="mt-0.5 shrink-0"
                    style={{ color: o.tone === "bad" ? "#ef4444" : "#f59e0b" }} />
                  <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{o.body}</p>
                </div>
                {error && <Error text={error} />}
                <Actions>
                  <Ghost onClick={reset}>Close</Ghost>
                  {(session?.status === "no_response" || session?.status === "expired") && (
                    <Primary onClick={() => { setSession(null); setPhase("asking"); }}>
                      Ask again
                    </Primary>
                  )}
                </Actions>
              </>
            );
          })()}
        </Overlay>
      )}
    </>
  );
}

/* ── small local pieces, so the states above read as states ─────────── */

function Overlay({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.5)" }} onClick={onClose}>
      <div className="w-full max-w-md rounded-xl p-5" onClick={(e) => e.stopPropagation()}
        style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        {children}
      </div>
    </div>
  );
}

function Head({ title, onClose }: { title: string; onClose: () => void }) {
  return (
    <div className="flex items-start justify-between gap-3 mb-3">
      <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>{title}</h2>
      <button onClick={onClose} aria-label="Close" className="shrink-0"
        style={{ color: "var(--text-secondary)" }}><X size={16} /></button>
    </div>
  );
}

function Actions({ children }: { children: React.ReactNode }) {
  return <div className="flex items-center justify-end gap-2 mt-4">{children}</div>;
}

function Ghost({ children, onClick, disabled }: {
  children: React.ReactNode; onClick: () => void; disabled?: boolean;
}) {
  return (
    <button onClick={onClick} disabled={disabled}
      className="px-3 h-9 rounded-lg text-sm disabled:opacity-50"
      style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
      {children}
    </button>
  );
}

function Primary({ children, onClick, disabled }: {
  children: React.ReactNode; onClick: () => void; disabled?: boolean;
}) {
  return (
    <button onClick={onClick} disabled={disabled}
      className="px-3 h-9 rounded-lg text-sm font-medium disabled:opacity-50"
      style={{ background: "var(--accent)", color: "#fff", border: "1px solid var(--accent)" }}>
      {children}
    </button>
  );
}

function Error({ text }: { text: string }) {
  return (
    <div className="text-sm mt-3 px-3 py-2 rounded-lg"
      style={{ background: "rgba(239,68,68,0.12)", color: "#ef4444" }}>{text}</div>
  );
}
