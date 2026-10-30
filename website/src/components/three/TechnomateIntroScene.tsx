"use client";

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Sparkles } from "@react-three/drei";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

/*
 * The about-page intro: the real Technomate logo (public/logo.png, or
 * logo-dark.png in dark mode) assembling itself in 3D.
 *
 * Rather than re-modelling the mark — which never quite matches — the PNG is
 * cut into its own connected shapes: every tile of the mark, every letter of
 * the wordmark and of the tagline. Each shape becomes a thin extruded piece
 * that flies in and lands exactly where it sits in the image, so the final
 * frame IS the logo, pixel for pixel. Plays once, then calls onDone.
 */
export const INTRO_SECONDS = 3.6;

const WORLD_W = 7; // logo width in world units
const LAYERS = 5; // stacked copies that give each piece its thickness
const LAYER_GAP = 0.012;
const CORE_ALPHA = 140; // pixels at least this opaque decide where shapes split

type Piece = {
  tex: THREE.CanvasTexture;
  x: number; // world centre
  y: number;
  w: number; // world size
  h: number;
  band: number; // 0 mark, 1 wordmark, 2 tagline
  order: number; // 0..1 left → right within its band
  u: number; // 0..1 left → right across the whole logo
};

// Sliced once per image: a replay starts at once instead of re-cutting the PNG.
const sliced = new Map<string, Promise<{ pieces: Piece[]; aspect: number }>>();
function slice(src: string) {
  if (!sliced.has(src)) sliced.set(src, cut(src));
  return sliced.get(src)!;
}

/** Split the logo image into its connected shapes, one texture per shape. */
async function cut(src: string): Promise<{ pieces: Piece[]; aspect: number }> {
  const img = new Image();
  img.src = src;
  await img.decode();
  const W = img.naturalWidth;
  const H = img.naturalHeight;
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const g = canvas.getContext("2d", { willReadFrequently: true })!;
  g.drawImage(img, 0, 0);
  const px = g.getImageData(0, 0, W, H).data;
  const alpha = (p: number) => px[p * 4 + 3];

  // 1. Label solid cores (4-connected, so touching antialiased edges don't merge tiles).
  const lab = new Int32Array(W * H);
  const sizes = [0];
  for (let p = 0, n = 0; p < W * H; p++) {
    if (lab[p] || alpha(p) < CORE_ALPHA) continue;
    n++;
    let count = 0;
    const stack = [p];
    lab[p] = n;
    while (stack.length) {
      const q = stack.pop()!;
      count++;
      const x = q % W;
      for (const r of [q - W, q + W, x > 0 ? q - 1 : -1, x < W - 1 ? q + 1 : -1]) {
        if (r >= 0 && r < W * H && !lab[r] && alpha(r) >= CORE_ALPHA) {
          lab[r] = n;
          stack.push(r);
        }
      }
    }
    sizes.push(count);
  }

  // 2. Grow each shape into its soft antialiased rim so edges stay smooth.
  for (let pass = 0; pass < 3; pass++) {
    const prev = lab.slice();
    for (let p = 0; p < W * H; p++) {
      if (prev[p] || alpha(p) === 0) continue;
      const x = p % W;
      const r =
        (p >= W && prev[p - W]) ||
        (p < W * (H - 1) && prev[p + W]) ||
        (x > 0 && prev[p - 1]) ||
        (x < W - 1 && prev[p + 1]) ||
        0;
      if (r) lab[p] = r;
    }
  }

  // 3. Bounding boxes, and horizontal bands (mark / wordmark / tagline) from empty rows.
  const n = sizes.length - 1;
  const box = Array.from({ length: n + 1 }, () => [W, H, -1, -1]);
  const rowUsed = new Uint8Array(H);
  for (let p = 0; p < W * H; p++) {
    const l = lab[p];
    if (!l || sizes[l] < 6) continue; // drop stray specks
    const x = p % W;
    const y = (p / W) | 0;
    const b = box[l];
    if (x < b[0]) b[0] = x;
    if (y < b[1]) b[1] = y;
    if (x > b[2]) b[2] = x;
    if (y > b[3]) b[3] = y;
    rowUsed[y] = 1;
  }
  const bands: [number, number][] = [];
  for (let y = 0, s = -1; y <= H; y++) {
    if (y < H && rowUsed[y] && s < 0) s = y;
    if ((y === H || !rowUsed[y]) && s >= 0) {
      bands.push([s, y - 1]);
      s = -1;
    }
  }
  const bandOf = (cy: number) => Math.min(2, Math.max(0, bands.findIndex(([a, b]) => cy >= a && cy <= b)));

  const k = WORLD_W / W;
  const raw: (Omit<Piece, "order" | "u"> & { px0: number })[] = [];
  for (let l = 1; l <= n; l++) {
    const [x0, y0, x1, y1] = box[l];
    if (x1 < 0) continue;
    const w = x1 - x0 + 1;
    const h = y1 - y0 + 1;
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    const cg = c.getContext("2d")!;
    const out = cg.createImageData(w, h);
    for (let y = y0; y <= y1; y++) {
      for (let x = x0; x <= x1; x++) {
        const p = y * W + x;
        if (lab[p] !== l) continue;
        const o = ((y - y0) * w + (x - x0)) * 4;
        out.data[o] = px[p * 4];
        out.data[o + 1] = px[p * 4 + 1];
        out.data[o + 2] = px[p * 4 + 2];
        out.data[o + 3] = px[p * 4 + 3];
      }
    }
    cg.putImageData(out, 0, 0);
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 4;
    raw.push({
      tex,
      x: (x0 + w / 2 - W / 2) * k,
      y: -(y0 + h / 2 - H / 2) * k,
      w: w * k,
      h: h * k,
      band: bandOf((y0 + y1) / 2),
      px0: x0,
    });
  }

  const minX = Math.min(...raw.map((r) => r.x));
  const maxX = Math.max(...raw.map((r) => r.x));
  const pieces = raw.map(({ px0: _px0, ...r }) => {
    const same = raw.filter((o) => o.band === r.band);
    const lo = Math.min(...same.map((o) => o.x));
    const hi = Math.max(...same.map((o) => o.x));
    return { ...r, order: hi > lo ? (r.x - lo) / (hi - lo) : 0, u: (r.x - minX) / (maxX - minX || 1) };
  });
  return { pieces, aspect: H / W };
}

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
const easeOutCubic = (x: number) => 1 - (1 - x) ** 3;
const easeOutBack = (x: number) => 1 + 1.9 * (x - 1) ** 3 + 0.9 * (x - 1) ** 2;
const hash = (i: number, s: number) => {
  const v = Math.sin(i * 127.1 + s * 311.7) * 43758.5453;
  return v - Math.floor(v);
};

// When each band starts, how long it staggers across, and each piece's flight time.
const BASE = [0, 0.75, 1.5];
const SPAN = [0.75, 0.8, 0.5];
const FLIGHT = [1.2, 1.0, 0.8];

function PieceMesh({ piece, index, clock }: { piece: Piece; index: number; clock: React.MutableRefObject<number> }) {
  const group = useRef<THREE.Group>(null);
  const { front, side } = useMemo(
    () => ({
      front: new THREE.MeshBasicMaterial({ map: piece.tex, transparent: true, alphaTest: 0.02, toneMapped: false }),
      side: new THREE.MeshBasicMaterial({
        map: piece.tex,
        transparent: true,
        alphaTest: 0.35,
        color: new THREE.Color(0.32, 0.42, 0.68),
        toneMapped: false,
      }),
    }),
    [piece.tex],
  );

  const start = useMemo(() => {
    const a = hash(index, 1);
    const b = hash(index, 2);
    const c = hash(index, 3);
    if (piece.band === 0) {
      // Tiles of the mark: in from a wide scattered cloud.
      const ang = index * 2.39996;
      return {
        pos: new THREE.Vector3(Math.cos(ang) * (5 + a * 3), Math.sin(ang) * (3 + b * 2), -6 + c * 8),
        rot: new THREE.Euler(a * 6, b * 6, c * 6),
      };
    }
    if (piece.band === 1) {
      // Wordmark letters: rise from below, flipping up into place.
      return {
        pos: new THREE.Vector3(piece.x + (a - 0.5) * 2, piece.y - 2.5 - b * 1.5, 1.5 + c * 2),
        rot: new THREE.Euler(-Math.PI * 0.6, (a - 0.5) * 1.2, (b - 0.5) * 0.8),
      };
    }
    // Tagline: drops in from just above, tipping forward.
    return {
      pos: new THREE.Vector3(piece.x, piece.y + 0.8, -1.2),
      rot: new THREE.Euler(Math.PI * 0.5, 0, 0),
    };
  }, [piece, index]);

  // The stacked back layers as one geometry, so each piece costs two draw calls, not LAYERS.
  const sides = useMemo(
    () =>
      mergeGeometries(
        Array.from({ length: LAYERS - 1 }, (_, l) =>
          new THREE.PlaneGeometry(piece.w, piece.h).translate(0, 0, -(l + 1) * LAYER_GAP),
        ),
      ),
    [piece],
  );

  const qa = useMemo(() => new THREE.Quaternion().setFromEuler(start.rot), [start]);
  const qb = useMemo(() => new THREE.Quaternion(), []);
  const target = useMemo(() => new THREE.Vector3(piece.x, piece.y, 0), [piece]);

  useFrame(() => {
    const g = group.current;
    if (!g) return;
    const t = clock.current;
    const p = clamp01((t - BASE[piece.band] - piece.order * SPAN[piece.band]) / FLIGHT[piece.band]);
    const e = piece.band === 0 ? easeOutBack(p) : easeOutCubic(p);
    g.position.lerpVectors(start.pos, target, e);
    g.quaternion.slerpQuaternions(qa, qb, clamp01(e));
    g.scale.setScalar(0.4 + 0.6 * clamp01(e));
    const fade = clamp01(p * 4);
    // Light sweep left → right once everything has landed.
    const shine = 1 + 0.9 * Math.exp(-(((t - 2.55 - piece.u * 0.6) / 0.09) ** 2));
    front.opacity = fade;
    side.opacity = fade;
    front.color.setScalar(shine);
  });

  return (
    <group ref={group}>
      <mesh material={front} renderOrder={2}>
        <planeGeometry args={[piece.w, piece.h]} />
      </mesh>
      <mesh geometry={sides} material={side} renderOrder={1} />
    </group>
  );
}

function Stage({
  pieces,
  aspect,
  onStart,
  onDone,
}: {
  pieces: Piece[];
  aspect: number;
  onStart: () => void;
  onDone: () => void;
}) {
  const clock = useRef(0);
  const origin = useRef<number | null>(null);
  const done = useRef(false);
  const root = useRef<THREE.Group>(null);
  const { camera, size } = useThree();

  useFrame(() => {
    const now = performance.now() / 1000;
    // The clock starts on the first rendered frame, and so does the progress bar.
    if (origin.current === null) {
      origin.current = now;
      onStart();
    }
    const t = now - origin.current;
    clock.current = t;

    // Fit the logo to ~80% of the width (and well inside the height), dollying in as it forms.
    const persp = camera as THREE.PerspectiveCamera;
    const tan = Math.tan(THREE.MathUtils.degToRad(persp.fov / 2));
    const view = size.width / size.height;
    const fitW = WORLD_W / (0.8 * 2 * tan * view);
    const fitH = (WORLD_W * aspect) / (0.62 * 2 * tan);
    const z = Math.max(fitW, fitH);
    persp.position.z = z * (1 + 0.25 * (1 - easeOutCubic(clamp01(t / 3))));

    if (root.current) {
      const e = easeOutCubic(clamp01(t / 2.7));
      // Lands dead flat and centred: TechnomateIntro swaps in the PNG at exactly this spot.
      root.current.rotation.y = -0.7 * (1 - e);
      root.current.rotation.x = 0.35 * (1 - e);
    }

    if (!done.current && t >= INTRO_SECONDS) {
      done.current = true;
      onDone();
    }
  });

  return (
    <group ref={root}>
      {pieces.map((p, i) => (
        <PieceMesh key={i} piece={p} index={i} clock={clock} />
      ))}
    </group>
  );
}

export default function TechnomateIntroScene({
  src,
  onReady,
  onDone,
}: {
  src: string;
  onReady: () => void;
  onDone: () => void;
}) {
  const [data, setData] = useState<{ pieces: Piece[]; aspect: number } | null>(null);

  useEffect(() => {
    let live = true;
    slice(src)
      .then((d) => live && setData(d))
      .catch(() => live && onDone());
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src]);

  if (!data) return null;
  return (
    <Canvas
      dpr={[1, 1.5]}
      camera={{ position: [0, 0, 10], fov: 35 }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      style={{ background: "transparent" }}
      onCreated={(state) => {
        // Same guards as AstraCoreScene: re-measure once layout settles, and
        // let a lost GPU context restore instead of throwing.
        const el = state.gl.domElement.parentElement;
        const apply = () => {
          if (!el) return;
          const r = el.getBoundingClientRect();
          if (r.width > 0 && r.height > 0) state.setSize(r.width, r.height);
        };
        apply();
        requestAnimationFrame(apply);
        state.gl.domElement.addEventListener("webglcontextlost", (e) => e.preventDefault(), false);
      }}
    >
      <Stage pieces={data.pieces} aspect={data.aspect} onStart={onReady} onDone={onDone} />
      <Sparkles count={80} scale={[14, 8, 6]} size={2.4} speed={0.4} opacity={0.7} color="#93c5fd" />
    </Canvas>
  );
}
