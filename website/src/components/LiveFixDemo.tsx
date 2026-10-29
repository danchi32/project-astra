"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  Activity, BookOpen, BrainCircuit, CheckCircle2, Folder, Globe, LifeBuoy, Loader2, Mail, MessagesSquare,
  Monitor, Send, ShieldCheck, Trash2, Wifi, Wrench,
} from "lucide-react";
import { SavioMark } from "@/components/SavioMark";

/**
 * The SAVIO page's hero demo: someone types an IT problem, SAVIO works it through its loop
 * and fixes it. Visitors can type their own problem or pick one; idle, it plays the
 * scenarios on its own.
 *
 * It is a simulation and says so on the card. What it must not do is show anything the
 * product does not do: every fix below is a real action in the remediation registry
 * (backend/app/services/remediation/actions.py) at its real tier, the approval case really
 * waits for a human, and anything the scenarios don't cover is ESCALATED with evidence —
 * never "fixed" — because that is what the product does with a problem it can't solve.
 */

type Tone = "brand" | "cyan" | "amber" | "green" | "slate";
type Step = {
  icon: typeof Activity;
  tone: Tone;
  text: string;
  detail?: string;
  metrics?: [string, number][];
  /** "run" shows a progress bar; "approval" waits for an admin before continuing. */
  wait?: "run" | "approval";
};
/** The employee with the problem. Invented people — initials, a first name and a team. */
type Person = { name: string; team: string; color: string };
type Scenario = { chip: string; issue: string; keywords: string[]; device: string; who: Person; steps: Step[] };

const YOU: Person = { name: "You", team: "", color: "bg-slate-600" };

const think = (text: string): Step => ({ icon: BrainCircuit, tone: "brand", text });
const kb = (detail: string): Step => ({ icon: BookOpen, tone: "brand", text: "Searched the knowledge base", detail });

const SCENARIOS: Scenario[] = [
  {
    chip: "Outlook keeps crashing",
    issue: "Outlook keeps crashing every time I open it",
    keywords: ["outlook", "mail", "email", "crash"],
    device: "DESIGN-WS-07",
    who: { name: "Riya", team: "Design", color: "bg-pink-500" },
    steps: [
      think("Understood: Outlook closes on launch"),
      kb("Matched a known fix for a hung Outlook profile"),
      { icon: Activity, tone: "cyan", text: "Collected live telemetry", detail: "Event 1000 · OUTLOOK.EXE faulted 3× today", metrics: [["CPU", 38], ["RAM", 71], ["Disk", 54]] },
      { icon: Wrench, tone: "green", text: "Fix: Restart Outlook", detail: "Automatic tier · runs without approval", wait: "run" },
      { icon: CheckCircle2, tone: "green", text: "Verified — Outlook opens normally", detail: "Recorded in the audit log" },
    ],
  },
  {
    chip: "Internet is very slow",
    issue: "Websites are not loading, internet is very slow",
    keywords: ["internet", "slow", "website", "browser", "dns", "network", "wifi", "load"],
    device: "SALES-LT-14",
    who: { name: "Arjun", team: "Sales", color: "bg-amber-500" },
    steps: [
      think("Understood: pages time out, connection itself is up"),
      kb("Matched: stale DNS cache after a network change"),
      { icon: Activity, tone: "cyan", text: "Collected live telemetry", detail: "Adapter up · DNS lookups failing", metrics: [["CPU", 22], ["RAM", 48], ["Disk", 61]] },
      { icon: Wrench, tone: "green", text: "Fix: Flush DNS cache", detail: "Automatic tier · runs without approval", wait: "run" },
      { icon: CheckCircle2, tone: "green", text: "Verified — sites resolve and load", detail: "Recorded in the audit log" },
    ],
  },
  {
    chip: "C: drive is full",
    issue: "My C drive is full and the laptop is very slow",
    keywords: ["disk", "drive", "storage", "space", "full", "c:"],
    device: "FIN-LT-03",
    who: { name: "Meera", team: "Finance", color: "bg-emerald-500" },
    steps: [
      think("Understood: low disk space slowing the device"),
      kb("Matched: temporary files filling the system drive"),
      { icon: Activity, tone: "cyan", text: "Collected live telemetry", detail: "C: 96% used · 11 GB in temp folders", metrics: [["CPU", 64], ["RAM", 77], ["Disk", 96]] },
      { icon: Wrench, tone: "green", text: "Fix: Clear temporary files", detail: "Automatic tier · runs without approval", wait: "run" },
      { icon: CheckCircle2, tone: "green", text: "Verified — C: back to 58% used", detail: "Recorded in the audit log" },
    ],
  },
  {
    chip: "No sound in Teams",
    issue: "No sound in my Teams call, others can't hear me either",
    keywords: ["sound", "audio", "speaker", "mic", "microphone", "teams", "hear"],
    device: "HR-WS-02",
    who: { name: "Kabir", team: "HR", color: "bg-orange-500" },
    steps: [
      think("Understood: audio dead in and out of calls"),
      kb("Matched: Windows audio service stuck after sleep"),
      { icon: Activity, tone: "cyan", text: "Collected live telemetry", detail: "Audiosrv not responding · devices present", metrics: [["CPU", 31], ["RAM", 58], ["Disk", 47]] },
      { icon: Wrench, tone: "green", text: "Fix: Recover the audio stack", detail: "Automatic tier · runs without approval", wait: "run" },
      { icon: CheckCircle2, tone: "green", text: "Verified — speaker and mic detected", detail: "Recorded in the audit log" },
    ],
  },
  {
    chip: "VPN won't connect",
    issue: "VPN won't connect since this morning",
    keywords: ["vpn", "connect", "remote", "tunnel"],
    device: "OPS-LT-21",
    who: { name: "Sana", team: "Operations", color: "bg-cyan-600" },
    steps: [
      think("Understood: VPN fails to establish a tunnel"),
      kb("Matched: corrupted network stack after an update"),
      { icon: Activity, tone: "cyan", text: "Collected live telemetry", detail: "Winsock errors · VPN adapter in a bad state", metrics: [["CPU", 27], ["RAM", 52], ["Disk", 63]] },
      { icon: ShieldCheck, tone: "amber", text: "Fix: Reset network stack", detail: "Approval required · asking IT admin", wait: "approval" },
      { icon: Wrench, tone: "green", text: "Applying approved fix", wait: "run" },
      { icon: CheckCircle2, tone: "green", text: "Verified — VPN connected", detail: "Approver and result in the audit log" },
    ],
  },
];

// Anything the scenarios don't match goes where the product sends it: to a human, with evidence.
const escalation = (issue: string): Scenario => ({
  chip: "",
  issue,
  keywords: [],
  device: "YOUR-PC",
  who: YOU,
  steps: [
    think("Understood your request"),
    kb("No safe automatic fix for this one"),
    { icon: Activity, tone: "cyan", text: "Collected evidence from the device", detail: "Logs, recent events and system state attached", metrics: [["CPU", 35], ["RAM", 60], ["Disk", 55]] },
    { icon: LifeBuoy, tone: "slate", text: "Escalated to your IT team", detail: "Ticket raised with all the evidence — nobody starts from zero" },
  ],
});

function match(text: string): Scenario {
  const t = text.toLowerCase();
  let best: Scenario | null = null;
  let score = 0;
  for (const s of SCENARIOS) {
    const n = s.keywords.filter((k) => t.includes(k)).length;
    if (n > score) { best = s; score = n; }
  }
  return best ?? escalation(text);
}

const TONE: Record<Tone, string> = {
  brand: "bg-brand-500/10 text-brand-500",
  cyan: "bg-cyan-500/10 text-cyan-500",
  amber: "bg-amber-500/10 text-amber-500",
  green: "bg-emerald-500/10 text-emerald-500",
  slate: "bg-slate-500/10 text-secondary-token",
};

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function Avatar({ who }: { who: Person }) {
  return (
    <span className={`grid h-5 w-5 shrink-0 place-items-center rounded-full text-[8px] font-bold text-white ${who.color}`}>
      {who.name === "You" ? "You" : who.name[0]}
    </span>
  );
}

export function LiveFixDemo() {
  const reduce = useReducedMotion();
  const [typed, setTyped] = useState("");
  const [shown, setShown] = useState<Step[]>([]);
  const [phase, setPhase] = useState<"idle" | "composing" | "typing" | "working" | "approval" | "running" | "done">("idle");
  const [progress, setProgress] = useState(0);
  const [device, setDevice] = useState("");
  const [who, setWho] = useState<Person>(YOU);
  const [input, setInput] = useState("");
  const [userDriven, setUserDriven] = useState(false);
  const [visitorTyping, setVisitorTyping] = useState(false);
  const keyTimer = useRef<number | undefined>(undefined);
  const run = useRef(0);

  // The hands follow the visitor's own keystrokes too, and stop shortly after they do.
  function keystroke() {
    setVisitorTyping(true);
    window.clearTimeout(keyTimer.current);
    keyTimer.current = window.setTimeout(() => setVisitorTyping(false), 450);
  }
  const scroller = useRef<HTMLDivElement>(null);

  async function play(s: Scenario, issueText = s.issue, person = s.who) {
    const id = ++run.current;
    const live = () => run.current === id;
    setShown([]); setProgress(0); setDevice(s.device); setTyped(""); setWho(person);
    // "Riya is typing…" first, the way a real chat shows someone composing.
    if (person !== YOU && !reduce) {
      setPhase("composing");
      await sleep(1300);
      if (!live()) return;
    }
    setPhase("typing");
    if (reduce) setTyped(issueText);
    else for (let i = 1; i <= issueText.length; i++) {
      if (!live()) return;
      setTyped(issueText.slice(0, i));
      await sleep(28);
    }
    await sleep(400);
    for (const step of s.steps) {
      if (!live()) return;
      setPhase("working");
      await sleep(reduce ? 150 : 900);
      if (!live()) return;
      setShown((prev) => [...prev, step]);
      if (step.wait === "approval") {
        setPhase("approval");
        await sleep(reduce ? 300 : 2200);
      } else if (step.wait === "run") {
        setPhase("running");
        for (let p = 0; p <= 100; p += 5) {
          if (!live()) return;
          setProgress(p);
          await sleep(reduce ? 5 : 55);
        }
      }
    }
    if (!live()) return;
    setPhase("done");
  }

  // Autoplay through the scenarios until a visitor takes over.
  useEffect(() => {
    if (userDriven) return;
    let i = 0;
    let stopped = false;
    (async () => {
      while (!stopped) {
        await play(SCENARIOS[i % SCENARIOS.length]);
        if (stopped) return;
        await sleep(3200);
        i += 1;
      }
    })();
    // Only stop the loop here: when a visitor takes over, their own play() has already
    // superseded the autoplay run, and bumping `run` now would cancel theirs instead.
    return () => { stopped = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userDriven]);

  // Cancel whatever is playing when the card unmounts.
  useEffect(() => () => { run.current += 1; }, []);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: reduce ? "auto" : "smooth" });
  }, [shown, phase, reduce]);

  function ask(text: string) {
    const t = text.trim();
    if (!t) return;
    setUserDriven(true);
    setInput("");
    play(match(t), t, YOU);
  }

  const lastApproval = phase === "approval";
  // The hands type while the employee's message is being written, or while the visitor types.
  const handsTyping = phase === "typing" || visitorTyping;
  const busy = phase !== "idle" && phase !== "done";

  return (
    <div className="relative w-full max-w-[600px]">
      {/* ── the laptop lid: thin bezel, camera, a 16:10 Windows desktop ── */}
      <div className="relative z-10 rounded-[18px] bg-ink-900 px-[1.6%] pb-[1.6%] pt-[2.6%] shadow-2xl ring-1 ring-black/10 dark:ring-white/10">
        <span className="absolute left-1/2 top-[1%] h-1.5 w-1.5 -translate-x-1/2 rounded-full bg-slate-600" />
        <div className="relative aspect-[16/10] overflow-hidden rounded-[6px] bg-gradient-to-br from-[#1e3a8a] via-[#2563eb] to-[#0891b2]">
          <Wallpaper />
          <DesktopIcons />

          {/* The SAVIO tray chat — the size the real tray window opens at, above its tray icon,
              not the whole screen. */}
          <motion.div
            className="absolute bottom-[10%] right-[1.5%] flex h-[86%] w-[94%] flex-col overflow-hidden rounded-lg border border-white/20 bg-surface shadow-2xl sm:w-[58%]"
            initial={{ opacity: 0, y: 12, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.4, delay: 0.3 }}
          >
            {/* window chrome */}
            <div className="flex items-center justify-between border-b border-token px-2.5 py-1.5">
              <div className="flex items-center gap-1.5">
                <SavioMark size={20} />
                <div>
                  <p className="text-[11px] font-bold leading-none">SAVIO Assistant</p>
                  <p className="mt-0.5 flex items-center gap-1 text-[9px] text-muted-token">
                    <span className="h-1 w-1 animate-pulse rounded-full bg-emerald-500" />
                    Online{device && <> · {device}</>}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 text-[10px] text-muted-token">
                <span className="rounded-full border border-token px-1.5 py-px text-[8px] font-semibold uppercase tracking-wide">Demo</span>
                <span>—</span><span>✕</span>
              </div>
            </div>

            {/* conversation */}
            <div ref={scroller} className="mini-scroll min-h-0 flex-1 space-y-2 overflow-y-auto px-2.5 py-2">
              {phase === "composing" && (
                <div className="flex items-end justify-end gap-1.5">
                  <div className="flex items-center gap-1.5 rounded-xl rounded-br-sm border border-token bg-app px-2 py-1 text-[10px] text-muted-token">
                    <span>{who.name} is typing</span>
                    <span className="flex gap-0.5">
                      {[0, 1, 2].map((d) => (
                        <motion.span
                          key={d}
                          className="h-1 w-1 rounded-full bg-brand-500"
                          animate={{ y: [0, -2, 0], opacity: [0.4, 1, 0.4] }}
                          transition={{ duration: 0.9, repeat: Infinity, delay: d * 0.15 }}
                        />
                      ))}
                    </span>
                  </div>
                  <Avatar who={who} />
                </div>
              )}
              {typed && (
                <div className="flex items-end justify-end gap-1.5">
                  <div className="max-w-[82%]">
                    <p className="mb-0.5 text-right text-[9px] text-muted-token">
                      {who.name}{who.team && <> · {who.team}</>}
                    </p>
                    <div className="rounded-xl rounded-br-sm bg-brand-600 px-2.5 py-1.5 text-[11px] leading-snug text-white">
                      {typed}
                      {phase === "typing" && <span className="ml-0.5 inline-block h-3 w-px animate-pulse bg-white align-middle" />}
                    </div>
                  </div>
                  <Avatar who={who} />
                </div>
              )}

              <AnimatePresence initial={false}>
                {shown.map((s, i) => {
                  const Icon = s.icon;
                  const isLast = i === shown.length - 1;
                  return (
                    <motion.div
                      key={`${device}-${i}`}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.25 }}
                      className="flex gap-2"
                    >
                      <span className={`mt-px grid h-5 w-5 shrink-0 place-items-center rounded-md ${TONE[s.tone]}`}>
                        <Icon className="h-3 w-3" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-[11px] font-semibold leading-snug">{s.text}</p>
                        {s.detail && <p className="text-[10px] leading-snug text-muted-token">{s.detail}</p>}
                        {s.metrics && (
                          <div className="mt-1 grid grid-cols-3 gap-1.5">
                            {s.metrics.map(([label, v]) => (
                              <div key={label}>
                                <div className="flex justify-between text-[8.5px] text-muted-token"><span>{label}</span><span>{v}%</span></div>
                                <div className="mt-px h-1 overflow-hidden rounded-full bg-surface-2">
                                  <motion.div
                                    className={`h-full rounded-full ${v > 90 ? "bg-red-500" : v > 70 ? "bg-amber-500" : "bg-cyan-500"}`}
                                    initial={{ width: 0 }}
                                    animate={{ width: `${v}%` }}
                                    transition={{ duration: 0.8 }}
                                  />
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                        {s.wait === "approval" && (
                          <div className="mt-1 flex items-center gap-1.5 text-[10px]">
                            {isLast && lastApproval ? (
                              <><Loader2 className="h-3 w-3 animate-spin text-amber-500" /> Waiting for IT admin…</>
                            ) : (
                              <span className="rounded bg-emerald-500/10 px-1.5 py-px font-semibold text-emerald-500">Approved by IT admin</span>
                            )}
                          </div>
                        )}
                        {s.wait === "run" && (
                          <div className="mt-1 h-1 overflow-hidden rounded-full bg-surface-2">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-brand-600 to-cyan-500 transition-[width] duration-100"
                              style={{ width: `${isLast && phase === "running" ? progress : 100}%` }}
                            />
                          </div>
                        )}
                      </div>
                    </motion.div>
                  );
                })}
              </AnimatePresence>

              {phase === "working" && (
                <div className="flex items-center gap-1.5 pl-0.5 text-[10px] text-muted-token">
                  <Loader2 className="h-3 w-3 animate-spin" /> SAVIO is working…
                </div>
              )}
            </div>

            {/* the tray app's own input */}
            <form
              onSubmit={(e) => { e.preventDefault(); ask(input); }}
              className="flex items-center gap-1.5 border-t border-token px-2 py-1.5"
            >
              <input
                value={input}
                onChange={(e) => { setInput(e.target.value); keystroke(); }}
                placeholder="Describe an IT problem…"
                aria-label="Describe an IT problem for the demo"
                maxLength={120}
                className="min-w-0 flex-1 rounded-md bg-app px-2 py-1 text-[11px] outline-none placeholder:text-muted-token"
              />
              <button type="submit" aria-label="Send to SAVIO" className="grid h-6 w-6 place-items-center rounded-md bg-brand-600 text-white">
                <Send className="h-3 w-3" />
              </button>
            </form>
          </motion.div>

          <Taskbar busy={busy} />
        </div>
      </div>

      <KeyboardDeck typing={handsTyping} />

      {/* try-it prompts, outside the laptop */}
      <div className="relative z-20 -mt-2 flex flex-wrap items-center justify-center gap-1.5">
        <span className="mr-0.5 text-[11px] font-semibold uppercase tracking-wide text-muted-token">Try:</span>
        {SCENARIOS.map((s) => (
          <button
            key={s.chip}
            type="button"
            onClick={() => ask(s.issue)}
            className="rounded-full border border-token bg-surface px-2.5 py-1 text-[11px] font-medium text-secondary-token shadow-sm transition-colors hover:border-brand-500/50 hover:text-brand-500"
          >
            {s.chip}
          </button>
        ))}
      </div>
    </div>
  );
}

/* ───────────────────────── the desktop around the tray chat ───────────────────────── */

function Wallpaper() {
  return (
    <svg aria-hidden className="absolute inset-0 h-full w-full" viewBox="0 0 160 100" preserveAspectRatio="none">
      <defs>
        <radialGradient id="wp-glow" cx="0.2" cy="0.15" r="0.7">
          <stop offset="0" stopColor="#93c5fd" stopOpacity="0.55" />
          <stop offset="1" stopColor="#93c5fd" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="160" height="100" fill="url(#wp-glow)" />
      {[0, 1, 2, 3].map((i) => (
        <path
          key={i}
          d={`M-10 ${70 + i * 6} C 40 ${50 + i * 6}, 90 ${95 + i * 4}, 170 ${60 + i * 6}`}
          fill="none"
          stroke="#e0f2fe"
          strokeOpacity={0.18 - i * 0.03}
          strokeWidth="0.8"
        />
      ))}
    </svg>
  );
}

function DesktopIcons() {
  const icons = [
    { Icon: Monitor, label: "This PC" },
    { Icon: Mail, label: "Outlook" },
    { Icon: Globe, label: "Chrome" },
    { Icon: Trash2, label: "Recycle Bin" },
  ];
  return (
    <div aria-hidden className="absolute left-[2%] top-[4%] hidden flex-col gap-[6%] sm:flex" style={{ height: "80%" }}>
      {icons.map(({ Icon, label }) => (
        <div key={label} className="flex w-12 flex-col items-center gap-0.5">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-white/15 text-white ring-1 ring-white/20">
            <Icon className="h-3.5 w-3.5" />
          </span>
          <span className="text-center text-[8px] leading-tight text-white drop-shadow">{label}</span>
        </div>
      ))}
    </div>
  );
}

function Taskbar({ busy }: { busy: boolean }) {
  const [now, setNow] = useState("");
  useEffect(() => {
    const tick = () => setNow(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    tick();
    const id = window.setInterval(tick, 30_000);
    return () => window.clearInterval(id);
  }, []);
  return (
    <div aria-hidden className="absolute inset-x-0 bottom-0 flex h-[8%] items-center gap-1.5 bg-slate-900/80 px-2 backdrop-blur">
      {/* start */}
      <span className="grid h-3 w-3 grid-cols-2 gap-px">
        {[0, 1, 2, 3].map((i) => <span key={i} className="rounded-[1px] bg-sky-400" />)}
      </span>
      <span className="ml-1 hidden h-3 w-16 rounded-full bg-white/15 sm:block" />
      {[Folder, Mail, Globe, MessagesSquare].map((Icon, i) => (
        <Icon key={i} className="h-3 w-3 text-white/80" />
      ))}
      <span className="flex-1" />
      {/* system tray: SAVIO's icon, glowing while it works */}
      <span className="relative grid place-items-center">
        {busy && <span className="absolute h-4 w-4 animate-ping rounded-full bg-cyan-400/50" />}
        <SavioMark size={13} />
      </span>
      <Wifi className="h-3 w-3 text-white/80" />
      <span className="text-[8px] font-medium tabular-nums text-white/90">{now}</span>
    </div>
  );
}

/* ───────────────────────── the laptop base and the hands ───────────────────────── */

const KEY_COUNT = 42;
function KeyboardDeck({ typing }: { typing: boolean }) {
  const [hot, setHot] = useState<number[]>([]);
  useEffect(() => {
    if (!typing) { setHot([]); return; }
    const id = window.setInterval(
      () => setHot([Math.floor(Math.random() * KEY_COUNT), Math.floor(Math.random() * KEY_COUNT)]),
      120,
    );
    return () => window.clearInterval(id);
  }, [typing]);

  return (
    <div aria-hidden className="relative mx-auto -mt-1 w-[106%] -translate-x-[2.8%]" style={{ perspective: "700px" }}>
      <div className="mx-auto h-2 w-[94%] rounded-b-md bg-slate-400 dark:bg-slate-700" />
      <div
        className="origin-top rounded-b-[26px] bg-gradient-to-b from-slate-200 to-slate-300 px-[7%] pb-12 pt-4 shadow-xl dark:from-slate-800 dark:to-slate-900"
        style={{ transform: "rotateX(42deg)" }}
      >
        <div className="grid gap-1" style={{ gridTemplateColumns: "repeat(14, minmax(0, 1fr))" }}>
          {Array.from({ length: KEY_COUNT }, (_, i) => (
            <span
              key={i}
              className={`h-3.5 rounded-[3px] transition-colors duration-100 ${
                hot.includes(i)
                  ? "translate-y-px bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.8)]"
                  : "bg-white shadow-[0_1px_0_rgba(15,23,42,0.18)] dark:bg-slate-700"
              }`}
            />
          ))}
          <span className="mx-auto mt-0.5 h-3.5 w-1/2 rounded-[3px] bg-white shadow-[0_1px_0_rgba(15,23,42,0.18)] dark:bg-slate-700" style={{ gridColumn: "1 / -1" }} />
        </div>
        <div className="mx-auto mt-3 h-6 w-1/3 rounded-md bg-slate-300/80 dark:bg-slate-700/70" />
      </div>
      <Hand side="left" typing={typing} />
      <Hand side="right" typing={typing} />
    </div>
  );
}

/** One hand seen from behind, resting on the keys; it drifts and its fingers strike while typing. */
function Hand({ side, typing }: { side: "left" | "right"; typing: boolean }) {
  const left = side === "left";
  const skin = "#e5ad82";
  const shade = "#cf9168";
  return (
    <svg
      viewBox="0 0 120 230"
      className="absolute top-[4%] w-[22%]"
      style={{
        [left ? "left" : "right"]: "22%",
        transform: left ? undefined : "scaleX(-1)",
        maskImage: "linear-gradient(to bottom, black 62%, transparent 92%)",
        WebkitMaskImage: "linear-gradient(to bottom, black 62%, transparent 92%)",
      }}
    >
      {/* sleeve — long, so the arm runs off the bottom of the laptop toward the person */}
      <rect x="28" y="96" width="64" height="140" rx="16" fill="#2563eb" />
      <rect x="28" y="96" width="64" height="12" rx="6" fill="#1d4ed8" />
      <motion.g
        animate={typing ? { x: [0, 4, -3, 2, 0], y: [0, -2, 0, -1, 0] } : { x: 0, y: 0 }}
        transition={{ duration: 1.2, repeat: typing ? Infinity : 0, ease: "easeInOut", delay: left ? 0 : 0.3 }}
      >
        <ellipse cx="60" cy="78" rx="29" ry="25" fill={skin} />
        {[34, 47, 60, 73].map((x, i) => (
          <motion.g
            key={x}
            animate={typing ? { y: [0, 8, 0] } : { y: 0 }}
            transition={{ duration: 0.26, repeat: typing ? Infinity : 0, repeatDelay: 0.18 + i * 0.05, delay: ((i * 0.11) + (left ? 0 : 0.06)) % 0.35 }}
          >
            <rect x={x - 5} y={i === 0 || i === 3 ? 40 : 33} width="11" height="35" rx="5.5" fill={skin} />
            {/* nail */}
            <rect x={x - 3} y={i === 0 || i === 3 ? 42 : 35} width="7" height="6" rx="3" fill="#f6d2b8" />
            {/* knuckle crease */}
            <rect x={x - 3} y={i === 0 || i === 3 ? 58 : 51} width="7" height="1.6" rx="0.8" fill={shade} opacity="0.6" />
          </motion.g>
        ))}
        <rect x="80" y="66" width="11" height="26" rx="5.5" fill={shade} transform="rotate(-35 85 79)" />
        <ellipse cx="60" cy="86" rx="20" ry="11" fill={shade} opacity="0.3" />
      </motion.g>
    </svg>
  );
}
