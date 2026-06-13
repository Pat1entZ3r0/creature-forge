import { Suspense, useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Grid, useGLTF, useAnimations } from "@react-three/drei";
import * as THREE from "three";
import { clone as cloneSkinned } from "three/examples/jsm/utils/SkeletonUtils.js";
import { makePs1Material, type Ps1Material } from "./ps1Material";

const MODEL_URL = `${import.meta.env.BASE_URL}spider_alien.glb`;
const ACCENT = "#7CFF9B";

useGLTF.preload(MODEL_URL);

type SpiderProps = {
  clip: string;
  ps1: boolean;
  wireframe: boolean;
  spin?: boolean;
  onFinished?: (clip: string) => void;
};

function Spider({ clip, ps1, wireframe, spin, onFinished }: SpiderProps) {
  const { scene, animations } = useGLTF(MODEL_URL);
  const model = useMemo(() => cloneSkinned(scene), [scene]);
  const material = useMemo<Ps1Material>(() => makePs1Material(), []);
  const { actions, mixer } = useAnimations(animations, model);
  const group = useRef<THREE.Group>(null);

  // gentle turntable for the hero — independent of OrbitControls
  useFrame((_, dt) => {
    if (spin && group.current) group.current.rotation.y += dt * 0.28;
  });

  // graft the PS1 material onto every mesh of the clone
  useMemo(() => {
    model.traverse((o) => {
      if ((o as THREE.Mesh).isMesh) {
        (o as THREE.Mesh).material = material;
        o.castShadow = true;
      }
    });
  }, [model, material]);

  // live toggles
  useEffect(() => {
    material.wireframe = wireframe;
    material.userData.ps1.uPS1.value = ps1 ? 1 : 0;
  }, [material, wireframe, ps1]);

  // play / crossfade the selected clip
  useEffect(() => {
    const action = actions[clip];
    if (!action) return;
    const isLoop = clip.endsWith("-loop");
    action.reset();
    action.setLoop(isLoop ? THREE.LoopRepeat : THREE.LoopOnce, Infinity);
    action.clampWhenFinished = !isLoop;
    action.fadeIn(0.18).play();
    return () => {
      action.fadeOut(0.18);
    };
  }, [clip, actions]);

  // one-shot states return to idle at end — death is terminal and holds its pose
  useEffect(() => {
    const handler = () => {
      if (clip !== "death" && !clip.endsWith("-loop")) onFinished?.("idle-loop");
    };
    mixer.addEventListener("finished", handler);
    return () => mixer.removeEventListener("finished", handler);
  }, [mixer, clip, onFinished]);

  return (
    <group ref={group}>
      <primitive object={model} />
    </group>
  );
}

export type SpiderCanvasProps = {
  clip: string;
  ps1?: boolean;
  wireframe?: boolean;
  controls?: boolean;
  autoRotate?: boolean;
  onFinished?: (clip: string) => void;
  className?: string;
};

export function SpiderCanvas({
  clip,
  ps1 = true,
  wireframe = false,
  controls = false,
  autoRotate = false,
  onFinished,
  className,
}: SpiderCanvasProps) {
  const ref = useRef<HTMLDivElement>(null);
  return (
    <div ref={ref} className={className}>
      <Canvas
        shadows
        dpr={[1, 2]}
        camera={{ position: [0.85, 0.55, 1.15], fov: 38, near: 0.05, far: 50 }}
        gl={{ antialias: false }}
      >
        <color attach="background" args={["#0b0913"]} />
        <fog attach="fog" args={["#0b0913", 2.2, 6.5]} />

        <hemisphereLight args={["#3a3450", "#080610", 0.55]} />
        <directionalLight
          position={[2.5, 4, 2]}
          intensity={2.1}
          color="#cfd4ff"
          castShadow
          shadow-mapSize={[1024, 1024]}
          shadow-bias={-0.0005}
        />
        <pointLight position={[-0.6, 0.5, -0.8]} intensity={3} distance={3} color={ACCENT} />

        <Suspense fallback={null}>
          <Spider clip={clip} ps1={ps1} wireframe={wireframe} spin={autoRotate} onFinished={onFinished} />
        </Suspense>

        <Grid
          position={[0, 0, 0]}
          args={[12, 12]}
          cellSize={0.18}
          cellThickness={0.6}
          cellColor="#241d3a"
          sectionSize={0.9}
          sectionThickness={1}
          sectionColor={ACCENT}
          fadeDistance={6}
          fadeStrength={1.6}
          infiniteGrid
        />

        <OrbitControls
          enabled={controls}
          enablePan={false}
          minDistance={0.7}
          maxDistance={3.2}
          minPolarAngle={0.2}
          maxPolarAngle={Math.PI / 2 - 0.05}
          target={[0, 0.24, 0]}
        />
      </Canvas>
    </div>
  );
}
