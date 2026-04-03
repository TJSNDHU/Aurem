/**
 * ProductViewer3D.jsx
 * ─────────────────────────────────────────────────────────────
 * REROOTS.CA — AURA-GEN 3D Product Viewer
 * Brand owner: Reroots Aesthetics Inc.
 *
 * THEMES:
 * theme="light" → reroots.ca website (cream/ivory)
 * theme="dark"  → mobile app (obsidian black)
 *
 * PRODUCTS:
 * model="auragen-serum" → ARC Active Recovery Serum 30mL
 * model="auragen-cream" → ACRC Rich Cream 35mL
 *
 * USAGE:
 * Website: <ProductViewer3D model="auragen-serum" theme="light" />
 * App:     <ProductViewer3D model="auragen-serum" theme="dark" />
 * ─────────────────────────────────────────────────────────────
 */

import React, { Suspense, useRef, useState, useEffect } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, ContactShadows, useGLTF } from "@react-three/drei";

// ── Theme tokens ──────────────────────────────────
const THEMES = {
  light: {
    bg: "#F7F4EF",
    bgCard: "#FFFFFF",
    border: "rgba(184,146,42,0.18)",
    shadow: "0 8px 40px rgba(0,0,0,0.07), 0 0 0 1px rgba(184,146,42,0.12)",
    accent: "#B8922A",
    accentGlow: "rgba(184,146,42,0.07)",
    accentRing: "rgba(184,146,42,0.22)",
    textPrimary: "#1A1714",
    textSecondary: "#6B6459",
    textMuted: "rgba(26,23,20,0.32)",
    tagBg: "rgba(184,146,42,0.05)",
    tagBorder: "rgba(184,146,42,0.18)",
    tagColor: "#8B6E1A",
    divider: "rgba(0,0,0,0.05)",
    hintColor: "rgba(26,23,20,0.28)",
    canvasH: "360px",
    cardMaxW: "480px",
  },
  dark: {
    bg: "#08080A",
    bgCard: "#0D0D12",
    border: "rgba(200,169,106,0.14)",
    shadow: "0 0 80px rgba(200,169,106,0.07), 0 24px 48px rgba(0,0,0,0.65)",
    accent: "#C8A96A",
    accentGlow: "rgba(200,169,106,0.1)",
    accentRing: "rgba(200,169,106,0.28)",
    textPrimary: "#F2EBD9",
    textSecondary: "rgba(242,235,217,0.52)",
    textMuted: "rgba(242,235,217,0.22)",
    tagBg: "rgba(200,169,106,0.05)",
    tagBorder: "rgba(200,169,106,0.18)",
    tagColor: "#C8A96A",
    divider: "rgba(200,169,106,0.09)",
    hintColor: "rgba(255,255,255,0.22)",
    canvasH: "320px",
    cardMaxW: "400px",
  },
};

// ── Product data ──────────────────────────────────
const PRODUCTS = {
  "auragen-serum": {
    name: "ARC Active Recovery Serum",
    volume: "30mL",
    badge: "STEP 01 · PM",
    tagline: "Clinical Recovery. Nightly.",
    description:
      "PDRN-powered cellular repair serum. Targets redness, uneven tone, and fine lines from night one.",
    tags: ["PDRN", "TXA 2%", "Argireline", "Niacinamide"],
    isSerum: true,
  },
  "auragen-cream": {
    name: "ACRC Rich Cream",
    volume: "35mL",
    badge: "STEP 02 · AM/PM",
    tagline: "Barrier Repair. Daily.",
    description:
      "Triple ceramide barrier cream. Seals and amplifies the serum's active recovery complex.",
    tags: ["Ceramide NP+AP+EOP", "PDRN", "Ectoin", "Squalane"],
    isSerum: false,
  },
};

// ── Fallback bottle (shows if no .glb file exists) ──
function FallbackBottle({ theme, isSerum }) {
  const groupRef = useRef();
  const T = THEMES[theme];

  useFrame((_, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * 0.38;
    }
  });

  const bottleColor = theme === "light" ? "#ddd8cc" : "#16162a";

  return (
    <group ref={groupRef}>
      {/* Main body */}
      <mesh position={[0, 0, 0]}>
        <cylinderGeometry
          args={isSerum ? [0.3, 0.34, 2.4, 64] : [0.52, 0.56, 1.7, 64]}
        />
        <meshPhysicalMaterial
          color={bottleColor}
          metalness={0.55}
          roughness={0.18}
          transparent
          opacity={0.9}
          transmission={0.2}
        />
      </mesh>

      {/* Gold cap */}
      <mesh position={[0, isSerum ? 1.44 : 1.05, 0]}>
        <cylinderGeometry
          args={isSerum ? [0.14, 0.14, 0.68, 32] : [0.54, 0.54, 0.22, 64]}
        />
        <meshPhysicalMaterial
          color="#C8A96A"
          metalness={0.95}
          roughness={0.04}
        />
      </mesh>

      {/* Gold label band */}
      <mesh position={[0, isSerum ? -0.2 : -0.1, 0]}>
        <cylinderGeometry
          args={isSerum ? [0.31, 0.35, 0.55, 64] : [0.53, 0.57, 0.45, 64]}
        />
        <meshStandardMaterial
          color="#C8A96A"
          metalness={0.75}
          roughness={0.35}
          transparent
          opacity={0.55}
        />
      </mesh>

      {/* Base ring */}
      <mesh position={[0, isSerum ? -1.26 : -0.93, 0]}>
        <cylinderGeometry
          args={isSerum ? [0.36, 0.32, 0.14, 64] : [0.58, 0.54, 0.14, 64]}
        />
        <meshPhysicalMaterial
          color="#C8A96A"
          metalness={0.92}
          roughness={0.08}
        />
      </mesh>
    </group>
  );
}

// ── GLB model (used when .glb file exists) ────────
// Error boundary for Three.js model loading
function GLBModelErrorBoundary({ children, fallback }) {
  const [hasError, setHasError] = useState(false);
  
  if (hasError) {
    return fallback;
  }
  
  return (
    <ErrorBoundary onError={() => setHasError(true)} fallback={fallback}>
      {children}
    </ErrorBoundary>
  );
}

// Simple error boundary component
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.warn('[ProductViewer3D] Model loading error:', error.message);
    if (this.props.onError) {
      this.props.onError(error);
    }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || null;
    }
    return this.props.children;
  }
}

function GLBModel({ path }) {
  const groupRef = useRef();
  const { scene } = useGLTF(path);

  useFrame((_, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * 0.38;
    }
  });

  return (
    <group ref={groupRef} scale={[2.6, 2.6, 2.6]}>
      <primitive object={scene} />
    </group>
  );
}

// ── Scene ─────────────────────────────────────────
function Scene({ modelPath, theme, isSerum, onLoaded }) {
  const [hasGLB, setHasGLB] = useState(false);
  const T = THEMES[theme];

  useEffect(() => {
    // Check if model file exists by fetching headers
    // If it returns 404 or HTML content type, fallback to generated bottle
    fetch(modelPath, { method: "HEAD" })
      .then((r) => {
        const contentType = r.headers.get("content-type") || "";
        // Only use GLB if status is OK and content type is binary/gltf
        if (r.ok && (contentType.includes("model") || contentType.includes("octet-stream") || contentType.includes("gltf"))) {
          setHasGLB(true);
        }
        onLoaded();
      })
      .catch(() => onLoaded());
  }, [modelPath, onLoaded]);

  return (
    <>
      <ambientLight intensity={theme === "light" ? 0.75 : 0.2} />
      <directionalLight
        position={[4, 8, 4]}
        intensity={theme === "light" ? 1.6 : 1.3}
        color="#ffffff"
      />
      <pointLight position={[-3, 2, 3]} intensity={0.9} color={T.accent} />
      <pointLight
        position={[3, -1, -3]}
        intensity={0.4}
        color={theme === "light" ? "#fffaef" : "#C8A96A"}
      />
      <spotLight
        position={[0, 6, 0]}
        intensity={theme === "light" ? 0.35 : 0.75}
        color={T.accent}
        angle={0.5}
        penumbra={0.9}
      />

      {hasGLB ? (
        <ErrorBoundary fallback={<FallbackBottle theme={theme} isSerum={isSerum} />}>
          <GLBModel path={modelPath} />
        </ErrorBoundary>
      ) : (
        <FallbackBottle theme={theme} isSerum={isSerum} />
      )}

      <ContactShadows
        position={[0, -1.5, 0]}
        opacity={theme === "light" ? 0.15 : 0.55}
        scale={4}
        blur={2.5}
        color={T.accent}
      />

      <OrbitControls
        enableZoom
        enablePan={false}
        minDistance={3}
        maxDistance={7}
        minPolarAngle={Math.PI / 4}
        maxPolarAngle={Math.PI / 1.8}
        autoRotate
        autoRotateSpeed={1.4}
      />
    </>
  );
}

// ── Main export ───────────────────────────────────
export default function ProductViewer3D({
  model = "auragen-serum",
  theme = "light",
}) {
  const T = THEMES[theme];
  const product = PRODUCTS[model] || PRODUCTS["auragen-serum"];
  const modelPath = `/models/${model}.glb`;

  const [isLoading, setIsLoading] = useState(true);
  const [activeTag, setActiveTag] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setReady(true), 250);
    return () => clearTimeout(t);
  }, []);

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;1,400&family=DM+Sans:wght@300;400;500&display=swap');
        @keyframes ag3d-spin { to { transform: rotate(360deg); } }
        @keyframes ag3d-in { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }
        .ag3d-tag { transition: all 0.15s ease; }
        .ag3d-tag:hover { opacity: 1 !important; }
      `}</style>

      <div
        style={{
          background: T.bgCard,
          borderRadius: theme === "light" ? "10px" : "16px",
          overflow: "hidden",
          width: "100%",
          maxWidth: T.cardMaxW,
          margin: "0 auto",
          fontFamily: "'DM Sans', sans-serif",
          border: `1px solid ${T.border}`,
          boxShadow: T.shadow,
        }}
      >
        {/* Top badge bar */}
        <div
          style={{
            padding: "9px 20px",
            background: T.accentGlow,
            borderBottom: `1px solid ${T.divider}`,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span
            style={{
              fontSize: "8.5px",
              letterSpacing: "0.28em",
              color: T.accent,
              textTransform: "uppercase",
              fontWeight: 500,
            }}
          >
            AURA-GEN · Reroots Aesthetics Inc.
          </span>
          <span
            style={{
              fontSize: "8.5px",
              letterSpacing: "0.2em",
              color: T.textMuted,
              textTransform: "uppercase",
            }}
          >
            {product.badge}
          </span>
        </div>

        {/* Canvas area */}
        <div
          style={{
            width: "100%",
            height: T.canvasH,
            position: "relative",
            background: T.bg,
            cursor: "grab",
          }}
        >
          {/* Background glow */}
          <div
            style={{
              position: "absolute",
              top: "45%",
              left: "50%",
              transform: "translate(-50%,-50%)",
              width: "160px",
              height: "160px",
              borderRadius: "50%",
              background: `radial-gradient(circle, ${T.accentGlow} 0%, transparent 70%)`,
              pointerEvents: "none",
              zIndex: 0,
            }}
          />

          {/* Loader */}
          {isLoading && (
            <div
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: "14px",
                background: T.bg,
                zIndex: 10,
              }}
            >
              <div
                style={{
                  width: "38px",
                  height: "38px",
                  borderRadius: "50%",
                  border: `1.5px solid ${T.accentRing}`,
                  borderTopColor: T.accent,
                  animation: "ag3d-spin 0.85s linear infinite",
                }}
              />
              <span
                style={{
                  fontSize: "9px",
                  letterSpacing: "0.25em",
                  color: T.accent,
                  textTransform: "uppercase",
                  opacity: 0.65,
                }}
              >
                Loading
              </span>
            </div>
          )}

          {/* Three.js Canvas */}
          {ready && (
            <Suspense fallback={null}>
              <Canvas
                camera={{ position: [0, 0.5, 5], fov: 38 }}
                gl={{ antialias: true, alpha: true }}
                dpr={[1, 2]}
                style={{
                  position: "absolute",
                  inset: 0,
                  background: "transparent",
                }}
              >
                <Scene
                  modelPath={modelPath}
                  theme={theme}
                  isSerum={product.isSerum}
                  onLoaded={() => setIsLoading(false)}
                />
              </Canvas>
            </Suspense>
          )}

          {/* Drag hint */}
          {!isLoading && (
            <div
              style={{
                position: "absolute",
                bottom: "12px",
                left: "50%",
                transform: "translateX(-50%)",
                fontSize: "9px",
                letterSpacing: "0.2em",
                color: T.hintColor,
                textTransform: "uppercase",
                pointerEvents: "none",
                whiteSpace: "nowrap",
                animation: "ag3d-in 0.4s ease",
              }}
            >
              Drag to rotate · Scroll to zoom
            </div>
          )}
        </div>

        {/* Info panel */}
        <div
          style={{
            padding: "20px 22px 24px",
            borderTop: `1px solid ${T.divider}`,
            background: T.bgCard,
          }}
        >
          <div
            style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: theme === "light" ? "19px" : "17px",
              fontWeight: 500,
              color: T.textPrimary,
              lineHeight: 1.2,
              marginBottom: "3px",
            }}
          >
            {product.name}
          </div>

          <div
            style={{
              fontSize: "9.5px",
              letterSpacing: "0.14em",
              color: T.textMuted,
              textTransform: "uppercase",
              marginBottom: "10px",
            }}
          >
            {product.volume} · AURA-GEN Combo · CAD $149
          </div>

          <div
            style={{
              fontFamily: "'Playfair Display', serif",
              fontStyle: "italic",
              fontSize: "13px",
              color: T.textSecondary,
              marginBottom: "13px",
            }}
          >
            {product.tagline}
          </div>

          <div
            style={{
              fontSize: "12px",
              lineHeight: 1.7,
              color: T.textSecondary,
              marginBottom: "16px",
            }}
          >
            {product.description}
          </div>

          {/* Tags */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
            {product.tags.map((tag) => (
              <button
                key={tag}
                className="ag3d-tag"
                onClick={() =>
                  setActiveTag(activeTag === tag ? null : tag)
                }
                style={{
                  padding: "4px 10px",
                  borderRadius: "2px",
                  fontSize: "8.5px",
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  border: `1px solid ${
                    activeTag === tag ? T.accent : T.tagBorder
                  }`,
                  color: activeTag === tag ? T.accent : T.tagColor,
                  background:
                    activeTag === tag ? T.accentGlow : T.tagBg,
                  cursor: "pointer",
                  fontFamily: "'DM Sans', sans-serif",
                  outline: "none",
                }}
              >
                {tag}
              </button>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
