"use client";

import { useId } from "react";

/**
 * Ambient "live telemetry" layer for otherwise empty section backgrounds.
 *
 * A sparse device network whose links carry data, packets travelling between nodes and a
 * heartbeat running along the bottom — the same story the SAVIO mark tells, at wallpaper
 * strength. It is masked to the edges so the middle of a section, where the copy sits, stays
 * clean: it fills the space around the content, never the space behind it.
 *
 * Pure SVG + CSS, no canvas and no JS loop. The CSS animations are switched off by the global
 * prefers-reduced-motion rule; the SMIL packets are hidden there too (.tf-motion).
 * Drop it as the first child of a section that has `relative isolate overflow-hidden`.
 */

// Node layout on a 1200×600 board, kept to the left and right thirds on purpose.
const NODES: [number, number][] = [
  [60, 80], [190, 150], [110, 300], [250, 360], [70, 500], [210, 530], [330, 250],
  [1140, 90], [1010, 170], [1090, 320], [950, 380], [1130, 500], [990, 540], [870, 230],
];
const LINKS: [number, number][] = [
  [0, 1], [1, 2], [2, 3], [3, 5], [4, 5], [1, 6], [3, 6], [2, 4],
  [7, 8], [8, 9], [9, 10], [10, 12], [11, 12], [8, 13], [10, 13], [9, 11],
];
// Links a packet rides along: [link index, duration seconds, begin offset].
const PACKETS: [number, number, number][] = [[1, 4.5, 0], [6, 5, 1.2], [9, 4, 0.6], [14, 5.5, 2], [3, 4.2, 2.6]];
const HEARTBEAT =
  "M0 560 H300 L320 560 L335 520 L350 590 L365 540 L378 560 H700 L718 560 L732 515 L748 595 L762 545 L775 560 H1200";

export function TelemetryField({ flip = false, className = "" }: { flip?: boolean; className?: string }) {
  const id = useId().replace(/:/g, "");
  return (
    <div
      aria-hidden
      className={`pointer-events-none absolute inset-0 -z-10 ${className}`}
      style={{
        maskImage: "radial-gradient(ellipse 60% 70% at 50% 45%, transparent 35%, black 80%)",
        WebkitMaskImage: "radial-gradient(ellipse 60% 70% at 50% 45%, transparent 35%, black 80%)",
      }}
    >
      <svg
        className="h-full w-full"
        viewBox="0 0 1200 600"
        preserveAspectRatio="xMidYMid slice"
        style={flip ? { transform: "scaleX(-1)" } : undefined}
      >
        <defs>
          <linearGradient id={`${id}beat`} x1="0" x2="1">
            <stop offset="0" stopColor="#1d4ed8" />
            <stop offset="0.5" stopColor="#3b82f6" />
            <stop offset="1" stopColor="#22d3ee" />
          </linearGradient>
        </defs>

        {/* links — dashed so the flow animation reads as data moving */}
        <g stroke="var(--accent)" strokeOpacity="0.22" strokeWidth="1.2" strokeDasharray="4 7" className="tf-flow">
          {LINKS.map(([a, b], i) => (
            <line key={i} x1={NODES[a][0]} y1={NODES[a][1]} x2={NODES[b][0]} y2={NODES[b][1]} />
          ))}
        </g>

        {/* nodes, each with a slow halo pulse at its own phase */}
        {NODES.map(([x, y], i) => (
          <g key={i}>
            <circle cx={x} cy={y} r="10" fill="#3b82f6" opacity="0.08" className="tf-halo" style={{ animationDelay: `${(i % 5) * 0.7}s` }} />
            <circle cx={x} cy={y} r="3.2" fill={i % 3 === 0 ? "#22d3ee" : "var(--accent)"} opacity="0.55" />
          </g>
        ))}

        {/* packets travelling along a few links */}
        <g className="tf-motion">
          {PACKETS.map(([li, dur, begin], i) => {
            const [a, b] = LINKS[li];
            return (
              <circle key={i} r="3" fill="#22d3ee" opacity="0.9">
                <animateMotion
                  dur={`${dur}s`}
                  begin={`${begin}s`}
                  repeatCount="indefinite"
                  path={`M${NODES[a][0]} ${NODES[a][1]} L${NODES[b][0]} ${NODES[b][1]}`}
                />
              </circle>
            );
          })}
        </g>

        {/* heartbeat: a faint track with a bright pulse running along it */}
        <path d={HEARTBEAT} fill="none" stroke="var(--accent)" strokeOpacity="0.12" strokeWidth="1.5" />
        <path
          d={HEARTBEAT}
          fill="none"
          stroke={`url(#${id}beat)`}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray="160 1500"
          className="tf-beat"
        />
      </svg>
    </div>
  );
}
