import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { Box, Maximize2, RotateCcw, ScanLine } from "lucide-react";
import { fmt, type Parameters, type SceneData } from "../domain/types";

export interface Layers {
  soil: boolean;
  concrete: boolean;
  casing: boolean;
  steel: boolean;
  water: boolean;
  grid: boolean;
}
export function Viewer({
  parameters: p,
  scene: data,
  layers,
}: {
  parameters: Parameters;
  scene?: SceneData;
  layers: Layers;
}) {
  const host = useRef<HTMLDivElement>(null);
  const commands = useRef<(v: string) => void>(() => {});
  const [error, setError] = useState("");
  const [view, setView] = useState("iso");
  const D = p.camisa.usar
    ? (p.camisa.DN || 1.2) + 2 * (p.camisa.espessura || 0.09)
    : p.geometria.D || 1.2;
  const L = p.geometria.L || 3;
  useEffect(() => {
    const container = host.current!;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    } catch {
      setError(
        "A visualização 3D não está disponível neste dispositivo. O corte e os resultados continuam disponíveis após o cálculo.",
      );
      return;
    }
    setError("");
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.8));
    renderer.setClearColor("#eef1f6");
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(-5, 5, 5, -5, 0.01, 500);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = false;
    controls.minZoom = 0.25;
    controls.maxZoom = 8;
    controls.target.set(0, -L * 0.4, 0);
    const render = () => renderer.render(scene, camera);
    controls.addEventListener("change", render);
    scene.add(new THREE.HemisphereLight(0xffffff, 0xb8c2d8, 2.3));
    const light = new THREE.DirectionalLight(0xffffff, 2.8);
    light.position.set(4, 8, 5);
    scene.add(light);
    const radius = D / 2,
      dc = p.camisa.usar && !p.camisa.estrutural ? p.camisa.DN || D : D;
    const mat = (color: THREE.ColorRepresentation, opacity = 1) =>
      new THREE.MeshStandardMaterial({
        color,
        roughness: 0.75,
        metalness: 0.05,
        transparent: opacity < 1,
        opacity,
        depthWrite: opacity === 1,
        side: THREE.DoubleSide,
      });
    const concrete = mat("#c2cee3", layers.steel && data ? 0.18 : 0.56),
      casing = mat("#c0c8d4", 0.3),
      steel = mat("#dc7e3d");
    const mesh = (
      geometry: THREE.BufferGeometry,
      material: THREE.Material,
      x = 0,
      y = 0,
      z = 0,
    ) => {
      const o = new THREE.Mesh(geometry, material);
      o.position.set(x, y, z);
      scene.add(o);
      return o;
    };
    const cylinder = (
      r: number,
      h: number,
      y: number,
      material: THREE.Material,
    ) => mesh(new THREE.CylinderGeometry(r, r, h, 64), material, 0, y, 0);
    const ring = (
      r: number,
      y: number,
      thickness: number,
      material: THREE.Material,
    ) => {
      const o = mesh(
        new THREE.TorusGeometry(r, thickness, 6, 64),
        material,
        0,
        y,
        0,
      );
      o.rotation.x = Math.PI / 2;
    };
    const segment = (
      a: THREE.Vector3,
      b: THREE.Vector3,
      r: number,
      material: THREE.Material,
    ) => {
      const direction = b.clone().sub(a);
      const o = mesh(
        new THREE.CylinderGeometry(r, r, direction.length(), 8),
        material,
      );
      o.position.copy(a).add(b).multiplyScalar(0.5);
      o.quaternion.setFromUnitVectors(
        new THREE.Vector3(0, 1, 0),
        direction.normalize(),
      );
    };
    if (layers.grid) {
      const grid = new THREE.GridHelper(
        Math.max(D * 6, L * 2),
        24,
        0xc6cedd,
        0xdce2eb,
      );
      grid.position.y = -L - 0.08;
      scene.add(grid);
    }
    if (layers.concrete) {
      cylinder(dc / 2, L, -L / 2, concrete);
      const outline = new THREE.LineSegments(
        new THREE.EdgesGeometry(
          new THREE.CylinderGeometry(dc / 2, dc / 2, L, 32),
        ),
        new THREE.LineBasicMaterial({
          color: "#5d729a",
          transparent: true,
          opacity: 0.45,
        }),
      );
      outline.position.y = -L / 2;
      scene.add(outline);
      cylinder(
        radius + 0.08,
        Math.max(0.02, p.lastro.espessura),
        -L - p.lastro.espessura / 2,
        mat("#a4afc0"),
      );
    }
    if (layers.casing && p.camisa.usar) {
      cylinder(radius, L, -L / 2, casing);
      const material = mat("#8595af");
      for (let y = 0; y <= L + 0.001; y += Math.max(0.1, p.camisa.altura))
        ring(radius, -Math.min(y, L), 0.009, material);
    }
    if (p.apoio.tipo !== "nenhum") {
      const h = Math.max(0.6, Math.min(p.apoio.h_aplicacao || 0.9, L * 0.35));
      const material = mat("#9ba9c0", 0.95);
      if (p.apoio.tipo === "poste" || p.apoio.secao === "circular")
        cylinder(
          p.apoio.tipo === "poste"
            ? Math.sqrt(Math.max(0.01, p.apoio.area_secao) / Math.PI)
            : p.apoio.d / 2,
          h,
          h / 2,
          material,
        );
      else
        mesh(
          new THREE.BoxGeometry(p.apoio.a, h, p.apoio.b),
          material,
          p.apoio.ex,
          h / 2,
          p.apoio.ey,
        );
    }
    if (layers.steel && data) {
      for (const rebar of [data.armadura, data.montagem]) {
        if (!rebar) continue;
        const r = rebar.raio || dc / 2 - p.materiais.cobrimento;
        const length = Math.min(L, rebar.z_fim || L);
        for (let j = 0; j < rebar.n; j++) {
          const angle = (2 * Math.PI * j) / rebar.n;
          segment(
            new THREE.Vector3(r * Math.cos(angle), -0.04, r * Math.sin(angle)),
            new THREE.Vector3(
              r * Math.cos(angle),
              -length,
              r * Math.sin(angle),
            ),
            Math.max(0.006, rebar.bitola / 2000),
            steel,
          );
        }
      }
      for (const rebar of [data.estribos, data.fretagem]) {
        if (!rebar) continue;
        for (let j = 0; j < rebar.n; j++) {
          const y =
            (rebar.z1 || 0.05) +
            (j * ((rebar.z2 || L) - (rebar.z1 || 0.05))) /
              Math.max(1, rebar.n - 1);
          ring(rebar.raio, -y, Math.max(0.005, rebar.bitola / 2000), steel);
        }
      }
      if (data.grelha)
        for (let i = 0; i < data.grelha.n_camadas; i++) {
          const y = -data.grelha.z1 - i * data.grelha.s_camadas;
          for (const bar of data.grelha.grampos) {
            const a =
              bar.dir === "X"
                ? new THREE.Vector3(-Math.abs(bar.bx), y, bar.by)
                : new THREE.Vector3(bar.bx, y, -Math.abs(bar.by));
            const b =
              bar.dir === "X"
                ? new THREE.Vector3(Math.abs(bar.bx), y, bar.by)
                : new THREE.Vector3(bar.bx, y, Math.abs(bar.by));
            segment(a, b, Math.max(0.006, data.grelha.bitola / 2000), steel);
          }
        }
    }
    if (layers.soil && data) {
      const top = p.geometria.cota_topo;
      const colors: Record<string, string> = {
        Granular: "#c8b997",
        Coesivo: "#bda28e",
        Intermediário: "#a6b8a7",
      };
      for (const c of data.perfis[0]?.camadas || []) {
        const y1 = Math.min(0.05, c.topo - top),
          y2 = Math.max(-L - 0.4, c.base - top);
        if (y1 <= y2) continue;
        const shape = new THREE.Shape();
        shape.absarc(0, 0, D * 1.25, 0, Math.PI, false);
        shape.lineTo(-radius * 1.06, 0);
        shape.absarc(0, 0, radius * 1.06, Math.PI, 0, true);
        shape.closePath();
        const geom = new THREE.ExtrudeGeometry(shape, {
          depth: y1 - y2,
          bevelEnabled: false,
          curveSegments: 40,
        });
        const o = mesh(geom, mat(colors[c.familia] || "#c6b697", 0.45));
        o.rotation.x = Math.PI / 2;
        o.position.y = y1;
      }
    }
    if (layers.water && data?.na != null) {
      const y = data.na - p.geometria.cota_topo;
      if (y >= -L - 0.5 && y <= 0.5) {
        const o = mesh(
          new THREE.CircleGeometry(D * 1.3, 64),
          mat("#459ac6", 0.22),
          0,
          y,
          0,
        );
        o.rotation.x = -Math.PI / 2;
      }
    }
    const arrows = [
      [new THREE.Vector3(1, 0, 0), 0xd36862],
      [new THREE.Vector3(0, 1, 0), 0x537dd0],
      [new THREE.Vector3(0, 0, 1), 0x4e9b85],
    ] as const;
    for (const [dir, color] of arrows)
      scene.add(
        new THREE.ArrowHelper(
          dir,
          new THREE.Vector3(-D * 1.45, -L, D * 0.9),
          D * 0.3,
          color,
          D * 0.055,
          D * 0.03,
        ),
      );
    const reset = (type: string) => {
      const size = Math.max(L, D * 2);
      controls.target.set(0, -L * 0.4, 0);
      camera.zoom = 1;
      camera.position.set(
        ...((type === "front"
          ? [0, -L * 0.4, size * 3]
          : type === "top"
            ? [0, size * 3, 0.001]
            : [size * 1.6, size * 1.1, size * 2]) as [number, number, number]),
      );
      camera.lookAt(controls.target);
      camera.updateProjectionMatrix();
      controls.update();
      render();
    };
    commands.current = reset;
    const resize = () => {
      const w = container.clientWidth,
        h = container.clientHeight;
      if (!w || !h) return;
      const range = Math.max(L * 0.78, D * 1.7);
      camera.left = (-range * w) / h;
      camera.right = (range * w) / h;
      camera.top = range;
      camera.bottom = -range;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
      render();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();
    reset(view);
    return () => {
      observer.disconnect();
      controls.dispose();
      scene.traverse((o) => {
        const m = o as THREE.Mesh;
        m.geometry?.dispose();
        const materials = Array.isArray(m.material)
          ? m.material
          : m.material
            ? [m.material]
            : [];
        materials.forEach((x) => x.dispose());
      });
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
      commands.current = () => {};
    };
  }, [p, data, layers, D, L]);
  return (
    <div className="viewer">
      <div className="three-host" ref={host} />
      <div className="viewport-heading">
        <span className="eyebrow">MODELO ESPACIAL</span>
        <h2>{p.nome}</h2>
        <span>
          {data
            ? "Geometria da solução calculada"
            : "Prévia da geometria · calcule para obter resultados"}
        </span>
      </div>
      <div className="view-tools">
        {[
          ["iso", "Isométrica", Box],
          ["front", "Frente", ScanLine],
          ["top", "Planta", Maximize2],
        ].map(([v, label, Icon]) => {
          const I = Icon as typeof Box;
          return (
            <button
              key={String(v)}
              title={String(label)}
              aria-label={String(label)}
              className={view === v ? "active" : ""}
              onClick={() => {
                setView(String(v));
                commands.current(String(v));
              }}
            >
              <I size={17} />
              <span>{String(label)}</span>
            </button>
          );
        })}
        <button
          title="Ajustar vista"
          aria-label="Ajustar vista"
          onClick={() => commands.current(view)}
        >
          <RotateCcw size={17} />
        </button>
      </div>
      {error && <div className="viewer-error">{error}</div>}
      <div className="dimension-tag">
        <b>Ø {fmt(D)} m</b>
        <span>L = {fmt(L)} m</span>
        <span>Base: {fmt(p.geometria.cota_topo - L)} m</span>
      </div>
      <div className="viewport-caption">
        Arraste para orbitar · roda para aproximar · botão direito para deslocar
        <br />
        Apoio esquemático · modelo sem base alargada
      </div>
      <div className="axis-legend">
        <i className="x">X</i>
        <i className="y">Y</i>
        <i className="z">Z ↑</i>
      </div>
    </div>
  );
}
