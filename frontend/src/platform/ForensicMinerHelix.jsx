/**
 * ForensicMinerHelix — 3D Copper Helix Visualization
 * Each discovered domain = a node on a rotating helix spiral.
 * Health score drives node color: red (0-40) → amber (41-70) → green (71-100)
 * Click node → expand detail panel (emails, social, outreach status)
 */
import React, { useRef, useMemo, useState, useCallback } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Text, Billboard } from '@react-three/drei';
import * as THREE from 'three';

const COPPER = '#B87333';
const GOLD = '#D4AF37';

function getHealthColor(score) {
  if (score >= 71) return '#22c55e';
  if (score >= 41) return '#f59e0b';
  return '#ef4444';
}

function HelixSpine({ count }) {
  const points = useMemo(() => {
    const pts = [];
    for (let i = 0; i <= count * 8; i++) {
      const t = i / (count * 8);
      const angle = t * Math.PI * 2 * (count / 2.5);
      const y = (t - 0.5) * count * 1.2;
      pts.push(new THREE.Vector3(Math.cos(angle) * 2.2, y, Math.sin(angle) * 2.2));
    }
    return pts;
  }, [count]);

  const curve = useMemo(() => new THREE.CatmullRomCurve3(points), [points]);
  const tubeGeo = useMemo(() => new THREE.TubeGeometry(curve, 200, 0.03, 8, false), [curve]);

  return (
    <mesh geometry={tubeGeo}>
      <meshStandardMaterial color={COPPER} metalness={0.85} roughness={0.25} />
    </mesh>
  );
}

function DomainNode({ store, index, total, onSelect, isSelected, outreachStatus }) {
  const meshRef = useRef();
  const t = total > 1 ? index / (total - 1) : 0.5;
  const angle = t * Math.PI * 2 * (total / 2.5);
  const y = (t - 0.5) * total * 1.2;
  const x = Math.cos(angle) * 2.2;
  const z = Math.sin(angle) * 2.2;
  const score = store.score || 0;
  const color = getHealthColor(score);

  const status = outreachStatus?.[store.domain] ? 'outreach' : store.emails?.length > 0 ? 'email' : 'scanned';
  const ringColor = status === 'outreach' ? '#22c55e' : status === 'email' ? GOLD : '#3b82f6';

  useFrame((state) => {
    if (meshRef.current) {
      const scale = isSelected ? 1.4 : 1.0;
      const pulse = isSelected ? 0.1 * Math.sin(state.clock.elapsedTime * 3) : 0;
      meshRef.current.scale.setScalar(scale + pulse);
    }
  });

  return (
    <group position={[x, y, z]}>
      {/* Outer ring (status indicator) */}
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.35, 0.025, 8, 32]} />
        <meshStandardMaterial color={ringColor} metalness={0.7} roughness={0.3} emissive={ringColor} emissiveIntensity={0.3} />
      </mesh>
      {/* Core sphere */}
      <mesh ref={meshRef} onClick={(e) => { e.stopPropagation(); onSelect(store); }} style={{ cursor: 'pointer' }}>
        <sphereGeometry args={[0.22, 24, 24]} />
        <meshStandardMaterial color={color} metalness={0.6} roughness={0.3} emissive={color} emissiveIntensity={isSelected ? 0.5 : 0.15} />
      </mesh>
      {/* Domain label */}
      <Billboard follow={true} lockX={false} lockY={false} lockZ={false}>
        <Text position={[0, 0.5, 0]} fontSize={0.18} color="#e0e0e0" anchorX="center" anchorY="middle"
          font="https://fonts.gstatic.com/s/jetbrainsmono/v18/tDbY2o-flEEny0FZhsfKu5WU4zr3E_BX0PnT8RD8yKxTOlOTk6OThhvA.woff"
          outlineWidth={0.015} outlineColor="#000000">
          {(store.domain || '').length > 18 ? store.domain.slice(0, 16) + '..' : store.domain}
        </Text>
        <Text position={[0, 0.32, 0]} fontSize={0.13} color={color} anchorX="center" anchorY="middle"
          outlineWidth={0.01} outlineColor="#000000">
          {score}/100
        </Text>
      </Billboard>
    </group>
  );
}

function HelixScene({ stores, onSelect, selectedDomain, outreachStatus }) {
  const groupRef = useRef();

  useFrame((state) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += 0.002;
    }
  });

  const count = stores?.length || 0;

  return (
    <>
      <ambientLight intensity={0.4} />
      <pointLight position={[5, 8, 5]} intensity={1.2} color="#ffe4c4" />
      <pointLight position={[-5, -3, -5]} intensity={0.6} color={COPPER} />
      <spotLight position={[0, 10, 0]} angle={0.3} intensity={0.8} color={GOLD} penumbra={0.5} />

      <group ref={groupRef}>
        {count > 1 && <HelixSpine count={count} />}
        {stores?.map((store, i) => (
          <DomainNode
            key={store.domain || i}
            store={store}
            index={i}
            total={count}
            onSelect={onSelect}
            isSelected={selectedDomain === store.domain}
            outreachStatus={outreachStatus}
          />
        ))}
      </group>

      <OrbitControls enablePan={false} minDistance={3} maxDistance={15} autoRotate={false} />
    </>
  );
}

function DetailPanel({ store, outreachStatus, onQueueOutreach, queuingDomain, onClose }) {
  if (!store) return null;
  const score = store.score || 0;
  const color = getHealthColor(score);
  const status = outreachStatus?.[store.domain] ? 'Outreach Sent' : store.emails?.length > 0 ? 'Email Found' : 'Scanned';
  const statusColor = status === 'Outreach Sent' ? '#22c55e' : status === 'Email Found' ? GOLD : '#3b82f6';

  return (
    <div className="absolute right-3 top-3 bottom-3 w-72 rounded-2xl overflow-y-auto z-10"
      style={{ background: 'rgba(20,18,22,0.95)', border: '1px solid rgba(184,115,51,0.3)', backdropFilter: 'blur(20px)' }}
      data-testid="helix-detail-panel">
      <div className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full" style={{ background: `${statusColor}18`, color: statusColor }}>{status}</span>
          <button onClick={onClose} className="text-[#888] hover:text-white text-xs">&times;</button>
        </div>
        <div>
          <h3 className="text-sm font-black" style={{ color: '#F5F5F5' }}>{store.domain}</h3>
          {store.organization && <p className="text-[10px]" style={{ color: '#999' }}>{store.organization}</p>}
        </div>
        <div className="flex items-center gap-2">
          <div className="text-2xl font-black" style={{ color }}>{score}</div>
          <span className="text-[10px]" style={{ color: '#999' }}>/100 Health</span>
        </div>

        {store.emails?.length > 0 && (
          <div>
            <p className="text-[9px] font-bold mb-1" style={{ color: '#888' }}>EMAILS</p>
            {store.emails.map((e, i) => (
              <p key={i} className="text-[10px] font-mono" style={{ color: '#D4AF37' }}>{e.email || e}</p>
            ))}
          </div>
        )}
        {store.phones?.length > 0 && (
          <div>
            <p className="text-[9px] font-bold mb-1" style={{ color: '#888' }}>PHONES</p>
            {store.phones.map((p, i) => <p key={i} className="text-[10px]" style={{ color: '#ccc' }}>{p}</p>)}
          </div>
        )}
        {Object.keys(store.social || {}).length > 0 && (
          <div>
            <p className="text-[9px] font-bold mb-1" style={{ color: '#888' }}>SOCIAL</p>
            {Object.entries(store.social).map(([k, v]) => (
              <p key={k} className="text-[10px]" style={{ color: '#ccc' }}><span style={{ color: COPPER }}>{k}:</span> @{v}</p>
            ))}
          </div>
        )}
        {store.issues?.length > 0 && (
          <div>
            <p className="text-[9px] font-bold mb-1" style={{ color: '#888' }}>ISSUES</p>
            <div className="flex flex-wrap gap-1">
              {store.issues.map((issue, j) => (
                <span key={j} className="text-[8px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(239,68,68,0.12)', color: '#ef4444' }}>{issue.replace(/_/g, ' ')}</span>
              ))}
            </div>
          </div>
        )}

        {status !== 'Outreach Sent' && store.emails?.length > 0 && (
          <button onClick={() => onQueueOutreach(store)} disabled={queuingDomain === store.domain}
            data-testid="helix-queue-outreach"
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold mt-2 transition-all hover:opacity-80"
            style={{ background: 'linear-gradient(135deg, #D4AF37, #B87333)', color: '#141216' }}>
            {queuingDomain === store.domain ? 'Queuing...' : 'Queue Outreach'}
          </button>
        )}
      </div>
    </div>
  );
}

export default function ForensicMinerHelix({ stores, outreachStatus, onQueueOutreach, queuingDomain }) {
  const [selected, setSelected] = useState(null);

  const handleSelect = useCallback((store) => {
    setSelected(prev => prev?.domain === store.domain ? null : store);
  }, []);

  if (!stores || stores.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 rounded-2xl" style={{ background: 'rgba(20,18,22,0.6)', border: '1px solid rgba(184,115,51,0.15)' }}>
        <p className="text-xs" style={{ color: '#888' }}>Run a scan to visualize domains on the Copper Helix</p>
      </div>
    );
  }

  return (
    <div className="relative rounded-2xl overflow-hidden" style={{ height: 420, background: 'radial-gradient(ellipse at center, #1a1520 0%, #0a0810 100%)', border: '1px solid rgba(184,115,51,0.2)' }}
      data-testid="forensic-miner-helix">
      {/* Legend */}
      <div className="absolute top-3 left-3 z-10 flex gap-3">
        {[{ c: '#ef4444', l: '0-40' }, { c: '#f59e0b', l: '41-70' }, { c: '#22c55e', l: '71-100' }].map(({ c, l }) => (
          <div key={l} className="flex items-center gap-1">
            <div className="size-2 rounded-full" style={{ background: c }} />
            <span className="text-[9px] font-bold" style={{ color: '#888' }}>{l}</span>
          </div>
        ))}
      </div>
      <div className="absolute bottom-3 left-3 z-10">
        <span className="text-[9px] font-bold px-2 py-1 rounded-lg" style={{ background: 'rgba(184,115,51,0.15)', color: COPPER }}>{stores.length} domains</span>
      </div>

      <Canvas camera={{ position: [0, 2, 8], fov: 50 }} gl={{ antialias: true }}>
        <HelixScene stores={stores} onSelect={handleSelect} selectedDomain={selected?.domain} outreachStatus={outreachStatus} />
      </Canvas>

      <DetailPanel
        store={selected}
        outreachStatus={outreachStatus}
        onQueueOutreach={onQueueOutreach}
        queuingDomain={queuingDomain}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}
