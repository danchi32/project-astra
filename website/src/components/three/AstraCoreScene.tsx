"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import {
  Float,
  Line,
  MeshDistortMaterial,
  Sparkles,
  Icosahedron,
} from "@react-three/drei";
import { useMemo, useRef } from "react";
import * as THREE from "three";

/* Device nodes orbiting the core. Each rides its own tilted, rotating ring. */
const NODES = [
  { radius: 2.4, speed: 0.22, tilt: 0.35, size: 0.16, color: "#c86ce7" },
  { radius: 3.1, speed: -0.16, tilt: -0.5, size: 0.13, color: "#b246d4" },
  { radius: 2.8, speed: 0.19, tilt: 0.9, size: 0.15, color: "#e04ad0" },
  { radius: 3.5, speed: -0.13, tilt: -0.25, size: 0.12, color: "#d8b4fe" },
  { radius: 2.1, speed: 0.26, tilt: 1.2, size: 0.14, color: "#d946ef" },
  { radius: 3.9, speed: -0.1, tilt: 0.6, size: 0.11, color: "#a855f7" },
  { radius: 2.6, speed: 0.17, tilt: -0.9, size: 0.13, color: "#9a2fbb" },
];

function OrbitNode({
  radius,
  speed,
  tilt,
  size,
  color,
  phase,
}: (typeof NODES)[number] & { phase: number }) {
  const group = useRef<THREE.Group>(null);
  const pulse = useRef<number>(phase);

  useFrame((_, delta) => {
    if (group.current) group.current.rotation.y += delta * speed;
    pulse.current += delta;
  });

  // Line from the core (origin) out to the node's local position.
  const points = useMemo<[number, number, number][]>(
    () => [
      [0, 0, 0],
      [radius, 0, 0],
    ],
    [radius],
  );

  return (
    <group rotation={[tilt, phase, 0]}>
      <group ref={group}>
        <Line
          points={points}
          color={color}
          lineWidth={1}
          transparent
          opacity={0.35}
        />
        <mesh position={[radius, 0, 0]}>
          <icosahedronGeometry args={[size, 0]} />
          <meshStandardMaterial
            color={color}
            emissive={color}
            emissiveIntensity={2.2}
            toneMapped={false}
          />
        </mesh>
      </group>
    </group>
  );
}

function Core() {
  const shell = useRef<THREE.Mesh>(null);
  useFrame((_, delta) => {
    if (shell.current) {
      shell.current.rotation.y += delta * 0.12;
      shell.current.rotation.x += delta * 0.05;
    }
  });

  return (
    <group>
      {/* Distorted glowing core */}
      <Float speed={1.4} rotationIntensity={0.5} floatIntensity={0.6}>
        <mesh>
          <icosahedronGeometry args={[1.15, 4]} />
          <MeshDistortMaterial
            color="#9a2fbb"
            emissive="#7f2599"
            emissiveIntensity={0.6}
            roughness={0.15}
            metalness={0.6}
            distort={0.35}
            speed={2.2}
          />
        </mesh>
        {/* Wireframe halo */}
        <Icosahedron ref={shell} args={[1.45, 1]}>
          <meshBasicMaterial
            color="#c86ce7"
            wireframe
            transparent
            opacity={0.18}
          />
        </Icosahedron>
      </Float>
    </group>
  );
}

/* Whole scene: subtle pointer parallax + auto drift. */
function Scene() {
  const root = useRef<THREE.Group>(null);
  useFrame((state, delta) => {
    if (!root.current) return;
    root.current.rotation.y += delta * 0.04;
    const px = state.pointer.x * 0.25;
    const py = state.pointer.y * 0.2;
    root.current.rotation.x = THREE.MathUtils.lerp(root.current.rotation.x, py, 0.05);
    root.current.position.x = THREE.MathUtils.lerp(root.current.position.x, px, 0.05);
  });

  return (
    <group ref={root}>
      <Core />
      {NODES.map((n, i) => (
        <OrbitNode key={i} {...n} phase={(i / NODES.length) * Math.PI * 2} />
      ))}
      <Sparkles
        count={60}
        scale={9}
        size={2}
        speed={0.3}
        opacity={0.5}
        color="#dd9cf2"
      />
    </group>
  );
}

export default function AstraCoreScene() {
  return (
    <Canvas
      dpr={[1, 1.8]}
      camera={{ position: [0, 0, 7], fov: 45 }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      style={{ background: "transparent" }}
      onCreated={(state) => {
        // Ensure the canvas fills its container even if R3F measured it
        // before layout settled (it can stick at the default 300×150).
        const el = state.gl.domElement.parentElement;
        const apply = () => {
          if (!el) return;
          const r = el.getBoundingClientRect();
          if (r.width > 0 && r.height > 0) state.setSize(r.width, r.height);
        };
        apply();
        requestAnimationFrame(apply);
        setTimeout(apply, 300);

        // Gracefully handle GPU context loss (e.g. during client-side
        // navigation between pages that each mount a WebGL canvas). Calling
        // preventDefault lets the browser restore it instead of throwing.
        state.gl.domElement.addEventListener(
          "webglcontextlost",
          (e) => e.preventDefault(),
          false,
        );
      }}
    >
      <ambientLight intensity={0.6} />
      <pointLight position={[5, 5, 5]} intensity={40} color="#b246d4" />
      <pointLight position={[-5, -3, 2]} intensity={30} color="#e04ad0" />
      <pointLight position={[0, 0, 3]} intensity={12} color="#c86ce7" />
      <Scene />
    </Canvas>
  );
}
