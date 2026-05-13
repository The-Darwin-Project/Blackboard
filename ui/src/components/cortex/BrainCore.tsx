// BlackBoard/ui/src/components/cortex/BrainCore.tsx
// @ai-rules:
// 1. [Pattern]: Three.js canvas as background layer (z-0) behind Sigma graph (z-10).
// 2. [Constraint]: Uses alpha:true for transparent background so Sigma nodes render on top.
// 3. [Gotcha]: Two WebGL contexts -- Three.js and Sigma. Keep Three.js minimal to avoid GPU contention.
// 4. [Pattern]: Uses THREE.Timer (not deprecated Clock) -- call timer.update() before timer.getElapsed().
// 5. [Pattern]: brain.glb loaded from /brain.glb (public dir). Fallback: empty scene.
// 6. [Gotcha]: Uses ResizeObserver (not window resize) so sidebar collapse/expand triggers reflow.
import { useEffect, useRef, type FC } from 'react';

const BrainCore: FC<{ className?: string }> = ({ className }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let disposed = false;

    (async () => {
      const THREE = await import('three');
      const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js');
      const { EffectComposer } = await import('three/addons/postprocessing/EffectComposer.js');
      const { RenderPass } = await import('three/addons/postprocessing/RenderPass.js');
      const { UnrealBloomPass } = await import('three/addons/postprocessing/UnrealBloomPass.js');

      if (disposed) return;

      const w = container.clientWidth;
      const h = container.clientHeight;

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 100);
      camera.position.set(0, 1.8, 6.5);

      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setSize(w, h);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setClearColor(0x000000, 0);
      container.appendChild(renderer.domElement);

      // Lighting
      scene.add(new THREE.AmbientLight(0xffffff, 0.4));
      const light1 = new THREE.DirectionalLight(0x22d3ee, 2.5);
      light1.position.set(5, 5, -5);
      scene.add(light1);
      const light2 = new THREE.DirectionalLight(0x3b82f6, 1.5);
      light2.position.set(-5, -5, 5);
      scene.add(light2);

      // Bloom
      const composer = new EffectComposer(renderer);
      composer.addPass(new RenderPass(scene, camera));
      composer.addPass(new UnrealBloomPass(
        new THREE.Vector2(w, h), 0.8, 0.4, 0.2
      ));

      // Swarm orbs
      const orbs: InstanceType<typeof THREE.Mesh>[] = [];
      const orbGeo = new THREE.SphereGeometry(0.03, 12, 12);
      const orbMat = new THREE.MeshBasicMaterial({ color: 0x22d3ee });
      for (let i = 0; i < 60; i++) {
        const orb = new THREE.Mesh(orbGeo, orbMat);
        const radius = 1.5 + Math.random() * 2;
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(Math.random() * 2 - 1);
        orb.position.set(
          radius * Math.sin(phi) * Math.cos(theta),
          radius * Math.sin(phi) * Math.sin(theta),
          radius * Math.cos(phi),
        );
        orb.userData = { angle: theta, speed: 0.003 + Math.random() * 0.01, radius, yOff: orb.position.y };
        scene.add(orb);
        orbs.push(orb);
      }

      // Lightning arcs
      const arcMat = new THREE.LineBasicMaterial({ color: 0xa5f3fc, transparent: true, opacity: 0 });
      const arcs: InstanceType<typeof THREE.Line>[] = [];
      for (let i = 0; i < 4; i++) {
        const line = new THREE.Line(new THREE.BufferGeometry(), arcMat.clone());
        scene.add(line);
        arcs.push(line);
      }

      // Load brain model
      const loader = new GLTFLoader();
      let brainModel: InstanceType<typeof THREE.Object3D> | null = null;
      try {
        const gltf = await loader.loadAsync('/brain.glb');
        brainModel = gltf.scene;
        brainModel.traverse((child: any) => {
          if (child.isMesh) {
            child.material = new THREE.MeshStandardMaterial({
              color: 0x0891b2,
              transparent: true,
              opacity: 0.35,
              roughness: 0.2,
              metalness: 0.5,
            });
          }
        });
        brainModel.scale.setScalar(1.0);
        scene.add(brainModel);
      } catch {
        // brain.glb not available -- render orbs only
      }

      const timer = new THREE.Timer();
      let animId = 0;

      function animate() {
        if (disposed) return;
        animId = requestAnimationFrame(animate);
        timer.update();
        const t = timer.getElapsed();

        if (brainModel) {
          brainModel.rotation.y += 0.002;
          brainModel.position.y = Math.sin(t * 1.5) * 0.15;
        }

        for (const orb of orbs) {
          orb.userData.angle += orb.userData.speed;
          orb.position.x = Math.cos(orb.userData.angle) * orb.userData.radius;
          orb.position.z = Math.sin(orb.userData.angle) * orb.userData.radius;
          orb.position.y = orb.userData.yOff + Math.sin(t * 2 + orb.userData.angle) * 0.2;
        }

        for (const arc of arcs) {
          if (Math.random() > 0.98 && (arc.material as any).opacity <= 0) {
            const a = orbs[Math.floor(Math.random() * orbs.length)].position;
            const b = orbs[Math.floor(Math.random() * orbs.length)].position;
            const mid = new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5);
            mid.x += (Math.random() - 0.5) * 0.5;
            mid.y += (Math.random() - 0.5) * 0.5;
            mid.z += (Math.random() - 0.5) * 0.5;
            arc.geometry.setFromPoints([a, mid, b]);
            (arc.material as any).opacity = 0.8;
          } else if ((arc.material as any).opacity > 0) {
            (arc.material as any).opacity -= 0.04;
          }
        }

        composer.render();
      }
      animate();

      const onResize = () => {
        const nw = container.clientWidth;
        const nh = container.clientHeight;
        if (nw === 0 || nh === 0) return;
        camera.aspect = nw / nh;
        camera.updateProjectionMatrix();
        renderer.setSize(nw, nh);
        composer.setSize(nw, nh);
      };

      const ro = new ResizeObserver(onResize);
      ro.observe(container);

      cleanupRef.current = () => {
        disposed = true;
        cancelAnimationFrame(animId);
        ro.disconnect();
        renderer.dispose();
        composer.dispose();
        container.removeChild(renderer.domElement);
      };
    })();

    return () => {
      disposed = true;
      cleanupRef.current?.();
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className={`absolute inset-0 pointer-events-none ${className ?? ''}`}
      style={{ zIndex: 0 }}
    />
  );
};

export default BrainCore;
