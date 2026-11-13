"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { RoundedBox } from "@react-three/drei";
import { useRef, type MutableRefObject } from "react";
import * as THREE from "three";

/*
 * The SAVIO guide robot in 3D: a small walking character built from primitives.
 * SavioGuide moves the canvas around the page and writes what the robot should be
 * doing into `live` (walking, which way, current gesture). Everything here reads it
 * every frame, so a change never re-renders React.
 */

export type BotPose = "laptop" | "point" | "present" | "wave" | "thumbs" | "cheer" | "sit" | "lie" | "dance";
/**
 * What the robot is doing right now. `t` runs 0→1 through a jump or climb; `greet`
 * makes it wave hello while it walks; `lean` tilts it along its rope while it swings.
 */
export type BotLive = {
  move: "idle" | "walk" | "jump" | "climb" | "ladder" | "swing";
  t: number;
  dir: -1 | 0 | 1;
  pose: BotPose;
  lookRight: boolean;
  greet: boolean;
  lean: number;
};

const BLUE = "#2563eb";
const BLUE_DARK = "#1d4ed8";
const CYAN = "#67e8f9";
const VISOR = "#0b1530";

const damp = (cur: number, to: number, k: number, dt: number) => THREE.MathUtils.damp(cur, to, k, dt);

function Bot({ live }: { live: MutableRefObject<BotLive> }) {
  const root = useRef<THREE.Group>(null);
  const body = useRef<THREE.Group>(null);
  const head = useRef<THREE.Group>(null);
  const eyes = useRef<THREE.Group>(null);
  const armL = useRef<THREE.Group>(null);
  const armR = useRef<THREE.Group>(null);
  const legL = useRef<THREE.Group>(null);
  const legR = useRef<THREE.Group>(null);
  const laptop = useRef<THREE.Group>(null);
  const spark = useRef<THREE.Mesh>(null);
  const phase = useRef(0);

  useFrame((state, dt) => {
    const t = state.clock.elapsedTime;
    const { move, t: mt, dir, pose, lookRight, greet, lean } = live.current;
    const walking = move === "walk";
    const laddering = move === "ladder";
    const swinging = move === "swing";
    const airborne = move === "jump" || move === "climb" || swinging;
    const still = move === "idle";
    if (!root.current || !body.current || !armL.current || !armR.current || !legL.current || !legR.current) return;
    const sitting = still && pose === "sit";
    const lying = still && pose === "lie";
    const dancing = still && pose === "dance";

    // Facing: sideways along the walk, otherwise a quarter-turn toward what it presents.
    // Sitting and lying face the visitor.
    // On a ladder it turns its back to us, like anyone climbing one.
    const yaw = laddering ? Math.PI : walking ? (dir === 0 ? 0 : dir * 1.15) : airborne ? dir * 0.5 : sitting || lying ? 0 : lookRight ? 0.45 : -0.45;
    root.current.rotation.y = damp(root.current.rotation.y, yaw, 7, dt);

    // Walk cycle: legs and arms swing opposite, the body bobs once per step.
    if (walking) phase.current += dt * 9;
    if (laddering) phase.current += dt * 7;
    const swing = walking ? Math.sin(phase.current) : 0;
    // Jump: legs tuck in the air. Climb: they dangle under the hands. Sitting: they
    // hang forward over the card's edge and kick. Dancing: a little side step.
    const legTuck = move === "jump" ? (mt > 0.15 && mt < 0.85 ? -0.9 : 0) : 0;
    const dangle = move === "climb" ? Math.sin(t * 7) * 0.35 : 0;
    let legLx = swing * 0.65 + legTuck + dangle;
    let legRx = -swing * 0.65 + legTuck - dangle;
    if (sitting) {
      legLx = -1.45 + Math.sin(t * 3) * 0.25;
      legRx = -1.45 - Math.sin(t * 3) * 0.25;
    } else if (lying) {
      // Legs crossed, one knee up.
      legLx = -0.25;
      legRx = 0.35;
    } else if (dancing) {
      legLx = Math.max(0, Math.sin(t * 6)) * -0.6;
      legRx = Math.max(0, -Math.sin(t * 6)) * -0.6;
    } else if (laddering) {
      // One foot up a rung, then the other.
      legLx = -0.55 + Math.sin(phase.current) * 0.5;
      legRx = -0.55 - Math.sin(phase.current) * 0.5;
    } else if (swinging) {
      // Feet together, kicking a little with the swing.
      legLx = -0.35 + Math.sin(t * 6) * 0.15;
      legRx = -0.35 + Math.sin(t * 6) * 0.15;
    }
    legL.current.rotation.x = damp(legL.current.rotation.x, legLx, 14, dt);
    legR.current.rotation.x = damp(legR.current.rotation.x, legRx, 14, dt);

    // Squash on take-off and landing, stretch in the air.
    const squash = move === "jump" ? (mt < 0.12 || mt > 0.9 ? 0.82 : 1.08) : 1;
    body.current.scale.y = damp(body.current.scale.y, squash, 18, dt);
    body.current.scale.x = damp(body.current.scale.x, 2 - squash, 18, dt);

    // Whole-body attitude: lie down on its side, sit low, sway to the beat, or swing
    // like a pendulum while hanging from its hands.
    const side = lookRight ? 1 : -1;
    const tiltTo = lying ? side * 1.5 : swinging ? lean : move === "climb" ? Math.sin(t * 7) * 0.12 : dancing ? Math.sin(t * 3) * 0.18 : 0;
    body.current.rotation.z = damp(body.current.rotation.z, tiltTo, 6, dt);
    body.current.position.x = damp(body.current.position.x, lying ? side * 1.55 : 0, 6, dt);
    const bob = walking
      ? Math.abs(Math.sin(phase.current)) * 0.12
      : dancing
        ? Math.abs(Math.sin(t * 6)) * 0.18
        : pose === "cheer" && still
          ? Math.abs(Math.sin(t * 5)) * 0.25
          : Math.sin(t * 2) * 0.03;
    const lift = lying ? 0.62 + Math.sin(t * 1.6) * 0.02 : sitting ? -0.62 : 0; // breathing while it lies there
    body.current.position.y = damp(body.current.position.y, bob + lift, 10, dt);

    // Arms. lz / rz: positive / negative swings that arm out to its own side.
    let lx = 0, lz = 0.18, rx = 0, rz = -0.18;
    if (move === "climb") {
      // Both hands up, pulling itself onto the card above.
      lz = 2.9;
      rz = -2.9;
    } else if (laddering) {
      // Hand over hand up (or down) the rungs.
      lz = 2.55 + Math.sin(phase.current) * 0.35;
      rz = -2.55 + Math.sin(phase.current) * 0.35;
    } else if (swinging) {
      // One hand up on the rope, the other out for balance.
      rz = -2.95;
      lz = 0.95 + Math.sin(t * 5) * 0.15;
    } else if (move === "jump") {
      lz = mt < 0.12 ? 0.6 : 2.2;
      rz = mt < 0.12 ? -0.6 : -2.2;
      lx = mt < 0.12 ? 0.6 : 0;
      rx = mt < 0.12 ? 0.6 : 0;
    } else if (walking) {
      lx = -swing * 0.7;
      rx = swing * 0.7;
      // Saying hello as it goes: the arm on the visitor's side waves.
      if (greet) {
        rx = 0;
        rz = -2.6 + Math.sin(t * 9) * 0.35;
      }
    } else {
      switch (pose) {
        case "laptop":
          lx = -1.1 + Math.sin(t * 14) * 0.08;
          rx = -1.1 + Math.cos(t * 14) * 0.08;
          lz = 0.25;
          rz = -0.25;
          break;
        case "point":
          // Out and down toward the card it stands on, with a little "this one" tap.
          if (lookRight) {
            rz = -1.05 + Math.sin(t * 5) * 0.1;
            rx = -0.45;
          } else {
            lz = 1.05 + Math.sin(t * 5) * 0.1;
            lx = -0.45;
          }
          break;
        case "present":
          lz = 1.0;
          rz = -1.0;
          lx = -0.5;
          rx = -0.5;
          break;
        case "wave":
          rz = -2.5 + Math.sin(t * 8) * 0.35;
          break;
        case "thumbs":
          rx = -1.6;
          rz = -0.35;
          break;
        case "cheer":
          lz = 2.6 + Math.sin(t * 6) * 0.2;
          rz = -2.6 - Math.sin(t * 6) * 0.2;
          break;
        case "sit":
          // Hands resting on its knees, one giving a lazy wave now and then.
          lx = -0.9;
          rx = -0.9;
          if (Math.sin(t * 0.8) > 0.6) {
            rx = 0;
            rz = -2.4 + Math.sin(t * 8) * 0.3;
          }
          break;
        case "lie":
          // Head propped on the lower hand, the other resting along its side.
          if (lookRight) {
            lx = -0.2;
            lz = 2.8;
            rz = -0.1;
          } else {
            rx = -0.2;
            rz = -2.8;
            lz = 0.1;
          }
          break;
        case "dance":
          lz = 1.4 + Math.sin(t * 6) * 1.1;
          rz = -1.4 + Math.sin(t * 6) * 1.1;
          break;
      }
    }
    armL.current.rotation.x = damp(armL.current.rotation.x, lx, 10, dt);
    // In three's frame "out to its own side" is the opposite sign, so flip it here once.
    armL.current.rotation.z = damp(armL.current.rotation.z, -lz, 10, dt);
    armR.current.rotation.x = damp(armR.current.rotation.x, rx, 10, dt);
    armR.current.rotation.z = damp(armR.current.rotation.z, -rz, 10, dt);

    // Head: looks where it goes, bops to the music, and turns up to the visitor when
    // lying on its side. Eyes blink every few seconds and droop sleepily when lying.
    if (head.current) {
      head.current.rotation.y = damp(head.current.rotation.y, walking ? 0 : Math.sin(t * 0.7) * 0.15, 4, dt);
      const headZ = lying ? -side * 1.2 : dancing ? Math.sin(t * 6) * 0.15 : (pose === "wave" && still) || (walking && greet) ? Math.sin(t * 4) * 0.08 : 0;
      head.current.rotation.z = damp(head.current.rotation.z, headZ, 6, dt);
    }
    if (eyes.current) eyes.current.scale.y = lying ? 0.35 : t % 4 < 0.12 ? 0.1 : 1;
    if (spark.current) {
      spark.current.rotation.y = t * 2;
      const s = 1 + Math.sin(t * 4) * 0.15;
      spark.current.scale.setScalar(s);
    }
    if (laptop.current) {
      const show = pose === "laptop" && still;
      laptop.current.scale.setScalar(damp(laptop.current.scale.x, show ? 1 : 0.001, 10, dt));
    }
  });

  const mat = (color: string, extra: Partial<THREE.MeshStandardMaterialParameters> = {}) => (
    <meshStandardMaterial color={color} roughness={0.35} metalness={0.15} {...extra} />
  );

  return (
    <group ref={root} position={[0, -1.25, 0]}>
      <group ref={body}>
        {/* Legs, pivoting at the hips */}
        {[-0.24, 0.24].map((x, i) => (
          <group key={x} ref={i === 0 ? legL : legR} position={[x, 0.95, 0]}>
            <mesh position={[0, -0.32, 0]}>
              <capsuleGeometry args={[0.13, 0.38, 6, 12]} />
              {mat(BLUE_DARK)}
            </mesh>
            <RoundedBox args={[0.3, 0.14, 0.42]} radius={0.06} position={[0, -0.66, 0.06]}>
              {mat("#e2e8f0")}
            </RoundedBox>
          </group>
        ))}

        {/* Torso with the SAVIO spark on its chest */}
        <RoundedBox args={[0.95, 0.85, 0.62]} radius={0.28} smoothness={5} position={[0, 1.35, 0]}>
          {mat(BLUE)}
        </RoundedBox>
        <mesh position={[0, 1.38, 0.32]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.17, 0.17, 0.04, 32]} />
          {mat(VISOR)}
        </mesh>
        <mesh position={[0, 1.38, 0.35]} rotation={[0, 0, Math.PI / 4]}>
          <octahedronGeometry args={[0.1, 0]} />
          <meshStandardMaterial color={CYAN} emissive={CYAN} emissiveIntensity={1.6} toneMapped={false} />
        </mesh>

        {/* Arms, pivoting at the shoulders */}
        {[-0.6, 0.6].map((x, i) => (
          <group key={x} ref={i === 0 ? armL : armR} position={[x, 1.62, 0]}>
            <mesh position={[0, -0.3, 0]}>
              <capsuleGeometry args={[0.11, 0.38, 6, 12]} />
              {mat(BLUE)}
            </mesh>
            <mesh position={[0, -0.62, 0]}>
              <sphereGeometry args={[0.15, 20, 20]} />
              {mat("#e0ecff")}
            </mesh>
          </group>
        ))}

        {/* Head */}
        <group ref={head} position={[0, 2.25, 0]}>
          <RoundedBox args={[1.2, 0.95, 0.9]} radius={0.38} smoothness={6}>
            {mat("#f8fbff", { roughness: 0.2 })}
          </RoundedBox>
          <RoundedBox args={[0.92, 0.55, 0.1]} radius={0.2} position={[0, 0, 0.43]}>
            {mat(VISOR, { roughness: 0.1, metalness: 0.4 })}
          </RoundedBox>
          <group ref={eyes} position={[0, 0.05, 0.5]}>
            {[-0.2, 0.2].map((x) => (
              <mesh key={x} position={[x, 0, 0]}>
                <capsuleGeometry args={[0.07, 0.1, 4, 12]} />
                <meshStandardMaterial color={CYAN} emissive={CYAN} emissiveIntensity={2.2} toneMapped={false} />
              </mesh>
            ))}
          </group>
          <mesh position={[0, -0.14, 0.49]} rotation={[0, 0, Math.PI]}>
            <torusGeometry args={[0.1, 0.022, 8, 24, Math.PI]} />
            <meshStandardMaterial color={CYAN} emissive={CYAN} emissiveIntensity={2} toneMapped={false} />
          </mesh>
          {[-0.64, 0.64].map((x) => (
            <mesh key={x} position={[x, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
              <cylinderGeometry args={[0.13, 0.13, 0.12, 24]} />
              {mat(BLUE)}
            </mesh>
          ))}
          <mesh position={[0, 0.62, 0]}>
            <cylinderGeometry args={[0.03, 0.03, 0.32, 8]} />
            {mat("#93c5fd")}
          </mesh>
          <mesh ref={spark} position={[0, 0.84, 0]}>
            <octahedronGeometry args={[0.12, 0]} />
            <meshStandardMaterial color={CYAN} emissive={CYAN} emissiveIntensity={2.4} toneMapped={false} />
          </mesh>
        </group>

        {/* Laptop for the opening pose */}
        <group ref={laptop} position={[0, 0.95, 0.75]} scale={0.001}>
          <RoundedBox args={[1.1, 0.06, 0.7]} radius={0.02}>
            {mat("#cbd5e1", { metalness: 0.6 })}
          </RoundedBox>
          <group position={[0, 0.02, 0.33]} rotation={[-1.95, 0, 0]}>
            <RoundedBox args={[1.1, 0.7, 0.04]} radius={0.02} position={[0, 0.35, 0]}>
              {mat("#e2e8f0", { metalness: 0.6 })}
            </RoundedBox>
            <mesh position={[0, 0.35, -0.025]}>
              <circleGeometry args={[0.08, 24]} />
              <meshStandardMaterial color={BLUE} emissive={BLUE} emissiveIntensity={1.2} toneMapped={false} />
            </mesh>
          </group>
        </group>
      </group>
    </group>
  );
}

export default function SavioBotScene({ live }: { live: MutableRefObject<BotLive> }) {
  return (
    <Canvas
      dpr={[1, 2]}
      camera={{ position: [0, 0.35, 7.2], fov: 30 }}
      gl={{ antialias: true, alpha: true }}
      style={{ background: "transparent", pointerEvents: "none" }}
      onCreated={(state) => {
        state.gl.domElement.addEventListener("webglcontextlost", (e) => e.preventDefault(), false);
      }}
    >
      <ambientLight intensity={0.75} />
      <directionalLight position={[3, 5, 4]} intensity={2.2} />
      <pointLight position={[-3, 1, 3]} intensity={18} color={CYAN} />
      <Bot live={live} />
    </Canvas>
  );
}
