import React, { useRef, useState, useEffect, useMemo, useCallback, Suspense } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Environment, Text, RoundedBox } from '@react-three/drei';
import * as THREE from 'three';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const OBSIDIAN = '#1a1a2e';
const COPPER = '#b87333';
const COPPER_LIGHT = '#d4a574';
const COPPER_DARK = '#8b5e3c';

function deg2rad(d) { return d * Math.PI / 180; }

function ArmSegment({ length, radius, position, rotation, children }) {
  return (
    <group position={position} rotation={rotation}>
      <mesh castShadow>
        <capsuleGeometry args={[radius, length, 8, 16]} />
        <meshStandardMaterial color={OBSIDIAN} metalness={0.9} roughness={0.15} />
      </mesh>
      <mesh position={[0, length / 2 + radius, 0]} castShadow>
        <sphereGeometry args={[radius * 1.3, 16, 16]} />
        <meshStandardMaterial color={COPPER} metalness={0.95} roughness={0.1} envMapIntensity={1.5} />
      </mesh>
      {children}
    </group>
  );
}

function GripperFinger({ side, openAngle }) {
  const angle = side === 'left' ? deg2rad(openAngle) : deg2rad(-openAngle);
  return (
    <group rotation={[0, 0, angle]}>
      <mesh position={[side === 'left' ? -0.02 : 0.02, 0.04, 0]} castShadow>
        <boxGeometry args={[0.008, 0.06, 0.015]} />
        <meshStandardMaterial color={COPPER_DARK} metalness={0.85} roughness={0.2} />
      </mesh>
    </group>
  );
}

function RoboticArm({ joints = [0, 0, 0, 0, 0, 0] }) {
  const groupRef = useRef();
  const targetJoints = useRef(joints);
  const currentJoints = useRef([0, 0, 0, 0, 0, 0]);

  useEffect(() => { targetJoints.current = joints; }, [joints]);

  useFrame(() => {
    for (let i = 0; i < 6; i++) {
      currentJoints.current[i] += (targetJoints.current[i] - currentJoints.current[i]) * 0.08;
    }
  });

  const L = [0.12, 0.18, 0.16, 0.06, 0.04, 0.03];
  const R = [0.035, 0.025, 0.02, 0.015, 0.012, 0.01];

  return (
    <group ref={groupRef} position={[0, -0.25, 0]}>
      {/* Base platform */}
      <mesh position={[0, -0.01, 0]} receiveShadow>
        <cylinderGeometry args={[0.08, 0.1, 0.02, 32]} />
        <meshStandardMaterial color={OBSIDIAN} metalness={0.95} roughness={0.1} />
      </mesh>
      <mesh position={[0, 0.005, 0]}>
        <torusGeometry args={[0.075, 0.004, 8, 32]} />
        <meshStandardMaterial color={COPPER} metalness={0.95} roughness={0.1} emissive={COPPER} emissiveIntensity={0.2} />
      </mesh>

      {/* Joint 0: Base rotation */}
      <group rotation={[0, deg2rad(currentJoints.current[0]), 0]}>
        <ArmSegment length={L[0]} radius={R[0]} position={[0, L[0] / 2, 0]} rotation={[0, 0, 0]}>
          {/* Joint 1: Shoulder */}
          <group position={[0, L[0] / 2 + R[0], 0]} rotation={[deg2rad(currentJoints.current[1]), 0, 0]}>
            <ArmSegment length={L[1]} radius={R[1]} position={[0, L[1] / 2, 0]} rotation={[0, 0, 0]}>
              {/* Joint 2: Elbow */}
              <group position={[0, L[1] / 2 + R[1], 0]} rotation={[deg2rad(currentJoints.current[2]), 0, 0]}>
                <ArmSegment length={L[2]} radius={R[2]} position={[0, L[2] / 2, 0]} rotation={[0, 0, 0]}>
                  {/* Joint 3: Wrist pitch */}
                  <group position={[0, L[2] / 2 + R[2], 0]} rotation={[deg2rad(currentJoints.current[3]), 0, 0]}>
                    <ArmSegment length={L[3]} radius={R[3]} position={[0, L[3] / 2, 0]} rotation={[0, 0, 0]}>
                      {/* Joint 4: Wrist roll */}
                      <group position={[0, L[3] / 2 + R[3], 0]} rotation={[0, deg2rad(currentJoints.current[4]), 0]}>
                        <mesh castShadow>
                          <cylinderGeometry args={[R[4], R[4], L[4], 12]} />
                          <meshStandardMaterial color={COPPER_LIGHT} metalness={0.9} roughness={0.15} />
                        </mesh>
                        {/* Gripper */}
                        <group position={[0, L[4] / 2, 0]}>
                          <GripperFinger side="left" openAngle={currentJoints.current[5]} />
                          <GripperFinger side="right" openAngle={currentJoints.current[5]} />
                        </group>
                      </group>
                    </ArmSegment>
                  </group>
                </ArmSegment>
              </group>
            </ArmSegment>
          </group>
        </ArmSegment>
      </group>
    </group>
  );
}

function GridFloor() {
  return (
    <group>
      <gridHelper args={[1, 20, COPPER_DARK, '#111']} position={[0, -0.27, 0]} />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.271, 0]} receiveShadow>
        <planeGeometry args={[1, 1]} />
        <meshStandardMaterial color="#0a0a15" metalness={0.5} roughness={0.8} transparent opacity={0.8} />
      </mesh>
    </group>
  );
}

function StatusHUD({ status, sequenceName, progress }) {
  return (
    <group position={[0, 0.45, 0]}>
      <Text fontSize={0.025} color={COPPER} anchorX="center" anchorY="middle" font="/fonts/inter-bold.woff">
        {sequenceName || 'IDLE'}
      </Text>
      <Text fontSize={0.015} color="#666" anchorX="center" anchorY="middle" position={[0, -0.035, 0]}>
        {status === 'executing' ? `${Math.round(progress * 100)}%` : 'STANDBY'}
      </Text>
    </group>
  );
}

function Scene({ joints, status, sequenceName, progress }) {
  return (
    <>
      <ambientLight intensity={0.15} />
      <directionalLight position={[3, 5, 2]} intensity={0.8} color="#fff5e6" castShadow shadow-mapSize={1024} />
      <pointLight position={[-2, 3, -1]} intensity={0.3} color={COPPER} />
      <pointLight position={[1, 0.5, 2]} intensity={0.2} color="#4a90d9" />
      <spotLight position={[0, 4, 0]} angle={0.3} penumbra={0.5} intensity={0.4} color={COPPER_LIGHT} castShadow />
      <RoboticArm joints={joints} />
      <GridFloor />
      <OrbitControls enablePan={false} enableZoom={true} minDistance={0.3} maxDistance={1.2} autoRotate autoRotateSpeed={0.3} maxPolarAngle={Math.PI / 1.8} />
    </>
  );
}

export default function RobotViewport({ token }) {
  const [armState, setArmState] = useState({ joints: [0, 0, 0, 0, 0, 0], status: 'idle', sequence_name: 'Idle', progress: 0 });
  const [connected, setConnected] = useState(false);
  const [taskLog, setTaskLog] = useState([]);
  const wsRef = useRef(null);
  const pollRef = useRef(null);

  // WebSocket connection for real-time joint streaming
  useEffect(() => {
    const wsUrl = (API_URL || window.location.origin).replace(/^http/, 'ws') + '/api/robotics/ws';
    let ws;
    try {
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type === 'joint_state') {
            setArmState(data);
          } else if (data.type === 'sequence_start') {
            setTaskLog(prev => [{ ...data, time: new Date().toLocaleTimeString() }, ...prev].slice(0, 5));
          }
        } catch {}
      };
      ws.onclose = () => setConnected(false);
      ws.onerror = () => setConnected(false);
    } catch { setConnected(false); }

    return () => { if (ws) ws.close(); };
  }, []);

  // Fallback polling when WS fails
  useEffect(() => {
    if (connected) { if (pollRef.current) clearInterval(pollRef.current); return; }
    if (!token) return;
    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch(`${API_URL}/api/robotics/state`, { headers: { Authorization: `Bearer ${token}` } });
        if (r.ok) setArmState(await r.json());
      } catch {}
    }, 500);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [connected, token]);

  // Idle breathing animation when no task is running
  const [idleTime, setIdleTime] = useState(0);
  useEffect(() => {
    if (armState.status !== 'idle') return;
    const iv = setInterval(() => setIdleTime(t => t + 0.05), 50);
    return () => clearInterval(iv);
  }, [armState.status]);

  const displayJoints = useMemo(() => {
    if (armState.status === 'executing') return armState.joints;
    const t = idleTime;
    return [
      Math.sin(t * 0.5) * 5,
      Math.sin(t * 0.3) * 3,
      Math.cos(t * 0.4) * 2,
      Math.sin(t * 0.6) * 2,
      0,
      0,
    ];
  }, [armState.status, armState.joints, idleTime]);

  const triggerSequence = useCallback(async (seqId) => {
    if (!token) return;
    try {
      await fetch(`${API_URL}/api/robotics/trigger`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ sequence_id: seqId, trigger: 'manual' }),
      });
    } catch {}
  }, [token]);

  return (
    <div data-testid="robot-viewport" style={{
      position: 'relative',
      borderRadius: 16,
      overflow: 'hidden',
      background: 'linear-gradient(135deg, rgba(26,26,46,0.85) 0%, rgba(15,15,30,0.95) 100%)',
      backdropFilter: 'blur(24px)',
      WebkitBackdropFilter: 'blur(24px)',
      border: '1px solid rgba(184,115,51,0.2)',
      boxShadow: '0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(184,115,51,0.1)',
    }}>
      {/* Header */}
      <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid rgba(184,115,51,0.15)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: connected ? '#22c55e' : armState.status === 'executing' ? COPPER : '#666', boxShadow: connected ? '0 0 8px #22c55e' : 'none' }} />
          <span style={{ color: COPPER, fontSize: 11, fontWeight: 700, letterSpacing: 2, fontFamily: "'Montserrat', sans-serif" }}>SOVEREIGN ARM</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ color: '#666', fontSize: 9, letterSpacing: 1.5, fontFamily: 'monospace' }}>
            [{armState.status === 'executing' ? 'ACTIVE' : 'SIMULATED'}]
          </span>
          <span style={{ color: COPPER_DARK, fontSize: 9, letterSpacing: 1 }}>Sovereign Ops</span>
        </div>
      </div>

      {/* 3D Canvas */}
      <div style={{ height: 260 }}>
        <Canvas shadows camera={{ position: [0.5, 0.4, 0.6], fov: 40 }} gl={{ antialias: true, alpha: true }} style={{ background: 'transparent' }}>
          <Suspense fallback={null}>
            <Scene joints={displayJoints} status={armState.status} sequenceName={armState.sequence_name} progress={armState.progress} />
          </Suspense>
        </Canvas>
      </div>

      {/* Control Bar */}
      <div style={{ padding: '8px 12px', display: 'flex', gap: 6, borderTop: '1px solid rgba(184,115,51,0.15)', flexWrap: 'wrap' }}>
        {['pick_and_pack', 'point_and_scan', 'quality_inspect', 'wave_greeting'].map(seq => (
          <button
            key={seq}
            data-testid={`trigger-${seq}`}
            onClick={() => triggerSequence(seq)}
            style={{
              flex: 1, minWidth: 70, padding: '5px 8px', border: '1px solid rgba(184,115,51,0.3)',
              borderRadius: 8, background: 'rgba(184,115,51,0.08)', color: COPPER_LIGHT,
              fontSize: 9, fontWeight: 600, letterSpacing: 0.5, cursor: 'pointer',
              fontFamily: "'Montserrat', sans-serif", transition: 'all 0.2s',
            }}
            onMouseOver={e => { e.target.style.background = 'rgba(184,115,51,0.2)'; e.target.style.borderColor = COPPER; }}
            onMouseOut={e => { e.target.style.background = 'rgba(184,115,51,0.08)'; e.target.style.borderColor = 'rgba(184,115,51,0.3)'; }}
          >
            {seq.replace(/_/g, ' ').toUpperCase()}
          </button>
        ))}
      </div>

      {/* Task Log */}
      {taskLog.length > 0 && (
        <div style={{ padding: '6px 12px 10px', maxHeight: 60, overflow: 'hidden' }}>
          {taskLog.slice(0, 2).map((t, i) => (
            <div key={i} style={{ fontSize: 9, color: '#888', fontFamily: 'monospace', lineHeight: 1.6 }}>
              <span style={{ color: COPPER }}>{t.time}</span> {t.name} <span style={{ color: '#555' }}>({t.trigger})</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
