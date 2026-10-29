"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { ContactShadows, Float, OrbitControls, RoundedBox } from "@react-three/drei";
import { useRef } from "react";
import * as THREE from "three";

/** The Volt One speaker: fabric body, glowing touch ring, metal base. Drag to spin. */
function Speaker({ color, glow }: { color: string; glow: string }) {
  const ring = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    if (ring.current) (ring.current.material as THREE.MeshStandardMaterial).emissiveIntensity = 1.6 + Math.sin(clock.elapsedTime * 2.4) * 0.8;
  });
  return (
    <Float speed={1.6} rotationIntensity={0.25} floatIntensity={0.6}>
      <group position={[0, -0.1, 0]}>
        {/* Fabric body */}
        <mesh castShadow>
          <cylinderGeometry args={[1, 1.05, 2.3, 96, 1]} />
          <meshStandardMaterial color={color} roughness={0.92} metalness={0.05} />
        </mesh>
        {/* Woven grille lines */}
        {Array.from({ length: 14 }, (_, i) => (
          <mesh key={i} position={[0, -1 + i * 0.15, 0]}>
            <torusGeometry args={[1.012 + i * 0.0035, 0.006, 6, 96]} />
            <meshStandardMaterial color="#000" transparent opacity={0.18} />
          </mesh>
        ))}
        {/* Top cap */}
        <mesh position={[0, 1.16, 0]}>
          <cylinderGeometry args={[1, 1, 0.04, 96]} />
          <meshStandardMaterial color="#111" roughness={0.3} metalness={0.6} />
        </mesh>
        {/* Glowing touch ring */}
        <mesh ref={ring} position={[0, 1.19, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.55, 0.035, 16, 96]} />
          <meshStandardMaterial color={glow} emissive={glow} emissiveIntensity={2} toneMapped={false} />
        </mesh>
        {/* Control buttons */}
        {[-0.18, 0, 0.18].map((x) => (
          <RoundedBox key={x} args={[0.1, 0.03, 0.1]} radius={0.01} position={[x, 1.2, 0]}>
            <meshStandardMaterial color="#2a2a2a" />
          </RoundedBox>
        ))}
        {/* Metal base */}
        <mesh position={[0, -1.2, 0]}>
          <cylinderGeometry args={[1.06, 0.98, 0.14, 96]} />
          <meshStandardMaterial color="#c9ccd3" metalness={0.9} roughness={0.25} />
        </mesh>
      </group>
    </Float>
  );
}

export default function VoltixScene({ color, glow }: { color: string; glow: string }) {
  return (
    <Canvas
      dpr={[1, 1.8]}
      camera={{ position: [0, 0.9, 7.4], fov: 38 }}
      gl={{ antialias: true, alpha: true }}
      style={{ background: "transparent", cursor: "grab" }}
      onCreated={(state) => {
        state.gl.domElement.addEventListener("webglcontextlost", (e) => e.preventDefault(), false);
      }}
    >
      <ambientLight intensity={0.5} />
      <directionalLight position={[4, 6, 5]} intensity={2.4} castShadow />
      <pointLight position={[-4, 1, 3]} intensity={30} color={glow} />
      <pointLight position={[3, -2, -3]} intensity={20} color="#7c3aed" />
      <Speaker color={color} glow={glow} />
      <ContactShadows position={[0, -1.55, 0]} opacity={0.55} scale={7} blur={2.6} far={3} />
      <OrbitControls enableZoom={false} enablePan={false} autoRotate autoRotateSpeed={1.6} minPolarAngle={Math.PI / 3} maxPolarAngle={Math.PI / 1.8} />
    </Canvas>
  );
}
