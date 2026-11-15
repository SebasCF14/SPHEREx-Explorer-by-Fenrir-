
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Stars } from '@react-three/drei'
import * as THREE from 'three'

import './DiwoHero.css'

// =============================================
// ANIMATED STAR SHADERS
// =============================================

const starVertexShader = `
  varying vec3 vPosition;
  varying vec3 vNormal;

  void main() {
    vPosition = position;
    vNormal = normalize(normalMatrix * normal);

    gl_Position =
      projectionMatrix *
      modelViewMatrix *
      vec4(position, 1.0);
  }
`

const starFragmentShader = `
  uniform float uTime;

  varying vec3 vPosition;
  varying vec3 vNormal;

  void main() {
    float waves =
      sin(
        vPosition.y * 13.0 +
        uTime * 0.7 +
        sin(vPosition.x * 9.0 + uTime * 0.4)
      ) *
      sin(
        vPosition.x * 17.0 -
        uTime * 0.45 +
        sin(vPosition.z * 12.0)
      );

    float granules =
      sin(vPosition.x * 35.0 + uTime * 0.5) *
      sin(vPosition.y * 32.0 - uTime * 0.7) *
      sin(vPosition.z * 31.0);

    float pattern = clamp(
      0.5 + 0.22 * waves + 0.14 * granules,
      0.0,
      1.0
    );

    vec3 orange = vec3(1.0, 0.35, 0.07);
    vec3 yellow = vec3(1.0, 0.90, 0.42);

    vec3 color = mix(orange, yellow, pattern);

    float limb = pow(
      max(
        dot(normalize(vNormal), vec3(0.0, 0.0, 1.0)),
        0.0
      ),
      0.5
    );

    color *= 0.7 + 0.3 * limb;

    gl_FragColor = vec4(color, 1.0);
  }
`

// =============================================
// PROCEDURAL CORONA TEXTURE
// =============================================

function createCoronaTexture() {
  const canvas = document.createElement('canvas')

  canvas.width = 256
  canvas.height = 256

  const ctx = canvas.getContext('2d')

  const gradient = ctx.createRadialGradient(
    128, 128, 25,
    128, 128, 128
  )

  gradient.addColorStop(0, 'rgba(255,225,130,0.95)')
  gradient.addColorStop(0.25, 'rgba(255,160,45,0.48)')
  gradient.addColorStop(0.55, 'rgba(255,105,20,0.14)')
  gradient.addColorStop(1, 'rgba(255,80,10,0)')

  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, 256, 256)

  return new THREE.CanvasTexture(canvas)
}

// =============================================
// PROCEDURAL EXOPLANET TEXTURE
// =============================================

function createPlanetTexture() {
  const canvas = document.createElement('canvas')

  canvas.width = 1024
  canvas.height = 512

  const ctx = canvas.getContext('2d')

  ctx.fillStyle = '#647f9b'
  ctx.fillRect(0, 0, 1024, 512)

  // Atmospheric bands
  for (let y = 0; y < 512; y += 5) {
    const variation =
      Math.sin(y * 0.047) * 22 +
      Math.sin(y * 0.13) * 13

    const r = Math.round(95 + variation)
    const g = Math.round(122 + variation)
    const b = Math.round(148 + variation)

    ctx.fillStyle = `rgb(${r},${g},${b})`
    ctx.fillRect(0, y, 1024, 5)
  }

  // Atmospheric details
  for (let i = 0; i < 1400; i++) {
    const x = (i * 73.17) % 1024
    const y = (i * 41.53) % 512

    ctx.fillStyle =
      i % 2 === 0
        ? 'rgba(235,242,255,0.06)'
        : 'rgba(16,35,65,0.06)'

    ctx.beginPath()

    ctx.ellipse(
      x,
      y,
      3 + (i % 9),
      1 + (i % 3),
      0,
      0,
      Math.PI * 2
    )

    ctx.fill()
  }

  // Illustrative atmospheric storm
  ctx.fillStyle = 'rgba(220,228,230,0.25)'
  ctx.beginPath()

  ctx.ellipse(
    690, 310, 70, 25,
    -0.12, 0, Math.PI * 2
  )

  ctx.fill()

  const texture = new THREE.CanvasTexture(canvas)

  texture.colorSpace = THREE.SRGBColorSpace
  texture.wrapS = THREE.RepeatWrapping

  return texture
}

// =============================================
// DÌWÖ — HOST STAR
// =============================================

function DiwoStar({ animated, onSelect }) {
  const shaderRef = useRef(null)
  const starRef = useRef(null)

  const corona = useMemo(createCoronaTexture, [])

  useEffect(() => {
    return () => corona.dispose()
  }, [corona])

  useFrame((_, delta) => {
    if (!animated) return

    if (shaderRef.current) {
      shaderRef.current.uniforms.uTime.value += delta
    }

    if (starRef.current) {
      starRef.current.rotation.y += delta * 0.035
    }
  })

  return (
    <group>

      {/* Stellar glow */}
      <sprite scale={[5.4, 5.4, 1]} renderOrder={0}>
        <spriteMaterial
          map={corona}
          transparent
          opacity={0.72}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </sprite>

      {/* Interactive star */}
      <mesh
        ref={starRef}
        renderOrder={1}
        onClick={(event) => {
          event.stopPropagation()
          onSelect('diwo')
        }}
        onPointerOver={() => {
          document.body.style.cursor = 'pointer'
        }}
        onPointerOut={() => {
          document.body.style.cursor = 'auto'
        }}
      >
        <sphereGeometry args={[1.12, 96, 64]} />

        <shaderMaterial
          ref={shaderRef}
          vertexShader={starVertexShader}
          fragmentShader={starFragmentShader}
          uniforms={{
            uTime: { value: 0 }
          }}
        />
      </mesh>

      <pointLight
        color="#ffd49b"
        intensity={65}
        distance={30}
        decay={2}
      />

    </group>
  )
}

// =============================================
// DITSÖ̀ — EXOPLANET
// =============================================

function DitsoPlanet({ animated, onSelect }) {
  const orbitRef = useRef(null)
  const planetRef = useRef(null)

  const texture = useMemo(createPlanetTexture, [])

  useEffect(() => {
    return () => texture.dispose()
  }, [texture])

  useFrame((_, delta) => {
    if (!animated) return

    if (orbitRef.current) {
      orbitRef.current.rotation.y += delta * 0.24
    }

    if (planetRef.current) {
      planetRef.current.rotation.y += delta * 0.32
    }
  })

  return (
    <group ref={orbitRef}>

      <mesh
        ref={planetRef}
        position={[3.2, 0, 0]}
        onClick={(event) => {
          event.stopPropagation()
          onSelect('ditso')
        }}
        onPointerOver={() => {
          document.body.style.cursor = 'pointer'
        }}
        onPointerOut={() => {
          document.body.style.cursor = 'auto'
        }}
      >
        <sphereGeometry args={[0.38, 64, 48]} />

        <meshStandardMaterial
          map={texture}
          roughness={0.95}
          metalness={0}
        />
      </mesh>

    </group>
  )
}

// =============================================
// ORBITAL PATH
// =============================================

function OrbitalPath() {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]}>

      <ringGeometry args={[3.195, 3.205, 192]} />

      <meshBasicMaterial
        color="#74bfff"
        transparent
        opacity={0.35}
        side={THREE.DoubleSide}
        depthWrite={false}
      />

    </mesh>
  )
}

// =============================================
// COMPLETE 3D SCENE
// =============================================

function SpaceScene({ animated, onSelect }) {
  return (
    <>
      <ambientLight intensity={0.22} />

      <hemisphereLight
        args={['#b6d9ff', '#15213b', 0.4]}
      />

      <Stars
        radius={80}
        depth={50}
        count={3500}
        factor={3.2}
        saturation={0}
        fade
        speed={animated ? 0.45 : 0}
      />

      <OrbitalPath />

      <DiwoStar
        animated={animated}
        onSelect={onSelect}
      />

      <DitsoPlanet
        animated={animated}
        onSelect={onSelect}
      />

      <OrbitControls
        enablePan={false}
        enableZoom
        enableRotate
        enableDamping
        dampingFactor={0.06}
        minDistance={5.2}
        maxDistance={14}
        minPolarAngle={0.25}
        maxPolarAngle={Math.PI * 0.8}
        target={[0, 0, 0]}
      />
    </>
  )
}

// =============================================
// SCIENTIFIC AND CULTURAL INFORMATION
// =============================================

const celestialInformation = {
  diwo: {
    category: 'HOST STAR',
    title: 'Dìwö',
    identifier: 'WASP-17',

    description:
      'Dìwö is a star located in the constellation Scorpius. Its name was proposed by Costa Rica as part of the International Astronomical Union naming initiative.',

    meaningTitle: 'Meaning in the Bribri language',

    meaning:
      'Dìwö refers to the Sun — greater than the Sun we know, one that never goes out.',

    culturalNote:
      'The name comes from the Bribri language of Costa Rica, connecting astronomical exploration with Indigenous cultural heritage.',

    detail:
      'Dìwö hosts the gas giant exoplanet Ditsö̀, also known as WASP-17 b.'
  },

  ditso: {
    category: 'EXOPLANET',
    title: 'Ditsö̀',
    identifier: 'WASP-17 b',

    description:
      'Ditsö̀ is a gas giant exoplanet orbiting the star Dìwö. It belongs to the class of planets known as hot Jupiters.',

    meaningTitle: 'Meaning in Bribri tradition',

    meaning:
      'Ditsö̀ is the name that Sibö̀, a central deity in Bribri tradition, gave to the first Bribri people.',

    culturalNote:
      'The name honors the cultural heritage and origin traditions of the Bribri people of Costa Rica.',

    detail:
      'The planet orbits very close to its host star. The visualization is artistic and is not physically to scale.'
  }
}

// =============================================
// MAIN LANDING PAGE
// =============================================

function DiwoHero() {
  const [animated, setAnimated] = useState(true)
  const [selection, setSelection] = useState(null)

  const infoPanelRef = useRef(null)

  const selectedObject = selection
    ? celestialInformation[selection]
    : null

  useEffect(() => {
    return () => {
      document.body.style.cursor = 'auto'
    }
  }, [])

  // Close information when clicking outside
  // the information panel.
  function handleOutsidePointerDown(event) {
    if (infoPanelRef.current?.contains(event.target)) {
      return
    }

    setSelection(null)
  }

  return (
    <div
      className={`diwo-page ${
        animated ? '' : 'diwo-paused'
      }`}
      onPointerDownCapture={handleOutsidePointerDown}
    >

      {/* CINEMATIC BACKGROUND */}

      <div
        className="diwo-cinematic-background"
        aria-hidden="true"
      >
        <div className="diwo-nebula-one" />
        <div className="diwo-nebula-two" />
        <div className="diwo-background-grid" />
      </div>

      {/* HEADER */}

      <header className="diwo-header">

        <Link to="/" className="diwo-logo">
          <span className="diwo-logo-symbol">✦</span>

          <span>
            SPHEREx
            <strong> EXPLORER</strong>
          </span>
        </Link>

        <div className="diwo-header-actions">

          <span className="diwo-header-caption">
            INTERACTIVE COSMIC OBSERVATORY
          </span>

          <button
            type="button"
            className="diwo-pause-button"
            onClick={() => {
              setAnimated(value => !value)
            }}
            aria-pressed={!animated}
          >
            {animated
              ? '⏸ Pause animation'
              : '▶ Resume animation'}
          </button>

        </div>
      </header>

      {/* MAIN CONTENT */}

      <main className="diwo-main">

        {/* INTRODUCTION */}

        <section className="diwo-introduction">

          <div className="diwo-eyebrow">
            <span className="diwo-live-dot" />
            ASTRONOMICAL EXPLORATION
          </div>

          <h1>
            The universe
            <span> is waiting.</span>
          </h1>

          <p className="diwo-description">
            Discover the cosmos from a new perspective.
            Explore the sky, visualize the universe,
            and uncover the mysteries that lie
            beyond the visible.
          </p>

          <div className="diwo-buttons">

            <Link
              to="/observador"
              className="diwo-primary-button"
            >
              <span>Explore the universe</span>
              <span>↗</span>
            </Link>

            <Link
              to="/investigador"
              className="diwo-secondary-button"
            >
              Researcher access
            </Link>

          </div>

          <div className="diwo-information-line" />

          <div className="diwo-metadata">

            <div>
              <span>FEATURED STAR</span>
              <strong>Dìwö · WASP-17</strong>
            </div>

            <div>
              <span>CONSTELLATION</span>
              <strong>Scorpius</strong>
            </div>

            <div>
              <span>NAME ORIGIN</span>
              <strong>Costa Rica · Bribri</strong>
            </div>

          </div>
        </section>

        {/* INTERACTIVE 3D OBSERVATORY */}

        <section className="diwo-observatory">

          <div className="diwo-observatory-top">

            <div className="diwo-observatory-title">
              <span className="diwo-live-dot" />
              DÌWÖ SYSTEM
            </div>

            <span className="diwo-observatory-id">
              WASP-17 SYSTEM
            </span>

          </div>

          <div className="diwo-canvas-container">

            <Canvas
              camera={{
                position: [0, 3.6, 9.4],
                fov: 42,
                near: 0.1,
                far: 200
              }}
              dpr={[1, 1.8]}
              gl={{
                antialias: true,
                alpha: true
              }}
              onPointerMissed={() => {
                setSelection(null)
              }}
              fallback={
                <p className="diwo-webgl-error">
                  Your browser does not support WebGL.
                </p>
              }
            >
              <SpaceScene
                animated={animated}
                onSelect={setSelection}
              />
            </Canvas>

            <div className="diwo-scene-label diwo-scene-label-star">
              <span>01 / STAR</span>
              <strong>DÌWÖ</strong>
              <small>WASP-17</small>
            </div>

            <div className="diwo-scene-label diwo-scene-label-planet">
              <span>02 / EXOPLANET</span>
              <strong>DITSÖ̀</strong>
              <small>WASP-17 b</small>
            </div>

            <div className="diwo-interaction-hint">
              <span>↔ Drag to rotate</span>
              <span>⊕ Scroll to zoom</span>
              <span>Click an object to learn more</span>
            </div>

          </div>

          {/* INTERACTIVE INFORMATION PANEL */}

          {selectedObject && (
            <aside
              ref={infoPanelRef}
              className="diwo-info-panel"
              aria-label={`${selectedObject.title} information`}
            >

              <button
                type="button"
                className="diwo-close-panel"
                onClick={() => setSelection(null)}
                aria-label="Close information panel"
              >
                ×
              </button>

              <span className="diwo-info-category">
                {selectedObject.category}
              </span>

              <h2>{selectedObject.title}</h2>

              <span className="diwo-info-id">
                {selectedObject.identifier}
              </span>

              <p>{selectedObject.description}</p>

              <div className="diwo-etymology">
                <h3>{selectedObject.meaningTitle}</h3>
                <p>{selectedObject.meaning}</p>
              </div>

              <p>{selectedObject.culturalNote}</p>

              <p>{selectedObject.detail}</p>

            </aside>
          )}

          <div className="diwo-observatory-bottom">

            <span>
              ● INTERACTIVE 3D SIMULATION
            </span>

            <span>
              Conceptual representation · Not to scale
            </span>

          </div>

        </section>

      </main>

      {/* FOOTER */}

      <footer className="diwo-footer">

        <span>
          SPHEREx Explorer · 2026
        </span>

        <span>
          Science, exploration and Costa Rican heritage
        </span>

        <span>
          COSTA RICA
        </span>

      </footer>

    </div>
  )
}

export default DiwoHero
