import { cn } from "@/lib/utils";

/**
 * Technomate mark — a flowing mesh "wave" of rounded tiles that fan out to the
 * right and dissolve into trailing lines, in the brand purple gradient.
 * Deterministic layout (no randomness) so it is hydration-safe.
 */
export function Logo({ className }: { className?: string }) {
  const cols = 5;
  const rows = 4;
  const tiles: {
    x: number;
    y: number;
    w: number;
    h: number;
    rot: number;
    op: number;
  }[] = [];

  for (let c = 0; c < cols; c++) {
    const t = c / (cols - 1); // 0..1 left→right
    for (let r = 0; r < rows; r++) {
      const cx = 22 + c * 20;
      const cy = 80 - c * 8 - r * 12; // rise to the right, stack upward
      const w = 14 - c * 1.8;
      const h = 12 - c * 1.2;
      tiles.push({
        x: cx,
        y: cy,
        w,
        h,
        rot: -6 - c * 4, // increasing tilt → sense of flow
        op: 1 - t * 0.45,
      });
    }
  }

  return (
    <svg
      viewBox="0 0 128 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn(className)}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="tm-mark" x1="10" y1="95" x2="130" y2="15">
          <stop offset="0%" stopColor="#7f2599" />
          <stop offset="45%" stopColor="#b246d4" />
          <stop offset="100%" stopColor="#e04ad0" />
        </linearGradient>
      </defs>

      <g>
        {tiles.map((tile, i) => (
          <rect
            key={i}
            x={tile.x - tile.w / 2}
            y={tile.y - tile.h / 2}
            width={tile.w}
            height={tile.h}
            rx={tile.w * 0.28}
            fill="url(#tm-mark)"
            opacity={tile.op}
            transform={`rotate(${tile.rot} ${tile.x} ${tile.y})`}
          />
        ))}

        {/* Trailing flow lines that the mesh dissolves into */}
        <path
          d="M100 20 C 116 24, 124 34, 116 48"
          stroke="url(#tm-mark)"
          strokeWidth="3"
          strokeLinecap="round"
          fill="none"
          opacity="0.7"
        />
        <path
          d="M104 34 C 118 38, 124 46, 119 58"
          stroke="url(#tm-mark)"
          strokeWidth="2.4"
          strokeLinecap="round"
          fill="none"
          opacity="0.5"
        />
      </g>
    </svg>
  );
}
