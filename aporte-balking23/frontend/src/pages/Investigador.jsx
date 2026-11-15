
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
  onAuthStateChanged,
  sendPasswordResetEmail,
  sendEmailVerification,
  reload
} from 'firebase/auth'

import { auth } from '../firebase'
import DashboardInvestigador from './DashboardInvestigador'

function Investigador() {

  // =====================================
  // 1. ESTADOS DEL FORMULARIO
  // =====================================

  const [modo, setModo] = useState('login')
  const [correo, setCorreo] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [confirmacion, setConfirmacion] = useState('')
  const [mostrarContrasena, setMostrarContrasena] = useState(false)

  // =====================================
  // 2. ESTADOS DE AUTENTICACIÓN
  // =====================================

  const [usuario, setUsuario] = useState(null)
  const [verificado, setVerificado] = useState(false)
  const [verificando, setVerificando] = useState(true)
  const [cargando, setCargando] = useState(false)

  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')

  const esRegistro = modo === 'registro'

  // =====================================
  // 3. OBSERVAR LA SESIÓN DE FIREBASE
  // =====================================

  useEffect(() => {

    const cancelar = onAuthStateChanged(
      auth,

      usuarioActual => {
        setUsuario(usuarioActual)

        setVerificado(
          Boolean(usuarioActual?.emailVerified)
        )

        setVerificando(false)
      },

      () => {
        setError('No se pudo comprobar la sesión.')
        setVerificando(false)
      }
    )

    return () => cancelar()

  }, [])

  // =====================================
  // 4. CAMBIAR ENTRE LOGIN Y REGISTRO
  // =====================================

  function cambiarModo(nuevoModo) {
    setModo(nuevoModo)
    setContrasena('')
    setConfirmacion('')
    setMensaje('')
    setError('')
  }

  // =====================================
  // 5. INTERPRETAR ERRORES DE FIREBASE
  // =====================================

  function interpretarError(codigo) {

    switch (codigo) {

      case 'auth/email-already-in-use':
        return 'Este correo ya está registrado. Intenta iniciar sesión.'

      case 'auth/invalid-email':
        return 'El correo electrónico no es válido.'

      case 'auth/weak-password':
        return 'La contraseña no cumple los requisitos de seguridad.'

      case 'auth/invalid-credential':
        return 'No se pudo iniciar sesión. Revisa tus credenciales.'

      case 'auth/too-many-requests':
        return 'Demasiados intentos. Intenta nuevamente más tarde.'

      case 'auth/network-request-failed':
        return 'No se pudo conectar con Firebase.'

      case 'auth/unauthorized-domain':
        return 'El dominio no está autorizado en Firebase.'

      case 'auth/operation-not-allowed':
        return 'El método de autenticación no está habilitado.'

      case 'auth/requires-recent-login':
        return 'Por seguridad, cierra sesión e inicia nuevamente.'

      default:
        return `Error de Firebase: ${codigo || 'desconocido'}`
    }
  }

  // =====================================
  // 6. REGISTRO E INICIO DE SESIÓN
  // =====================================

  async function manejarEnvio(evento) {

    evento.preventDefault()

    if (cargando) return

    setError('')
    setMensaje('')

    if (esRegistro && contrasena !== confirmacion) {
      setError('Las contraseñas no coinciden.')
      return
    }

    if (esRegistro && contrasena.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres.')
      return
    }

    setCargando(true)

    try {

      if (esRegistro) {

        const resultado = await createUserWithEmailAndPassword(
          auth,
          correo.trim(),
          contrasena
        )

        setUsuario(resultado.user)
        setVerificado(Boolean(resultado.user.emailVerified))

        setMensaje('Cuenta creada correctamente.')

        // Enviar verificación del correo
        try {

          await sendEmailVerification(resultado.user)

          setMensaje(
            'Cuenta creada. Enviamos un enlace de verificación a tu correo.'
          )

        } catch (errorEnvio) {

          setError(
            'La cuenta se creó, pero no se pudo enviar el correo: ' +
            interpretarError(errorEnvio.code)
          )
        }

      } else {

        const resultado = await signInWithEmailAndPassword(
          auth,
          correo.trim(),
          contrasena
        )

        setUsuario(resultado.user)

        // Actualizar el estado de verificación
        await reload(resultado.user)

        setVerificado(
          Boolean(resultado.user.emailVerified)
        )

        setMensaje('Sesión iniciada correctamente.')
      }

      setContrasena('')
      setConfirmacion('')

    } catch (err) {

      setError(interpretarError(err.code))

    } finally {

      setCargando(false)
    }
  }

  // =====================================
  // 7. REENVIAR VERIFICACIÓN
  // =====================================

  async function reenviarVerificacion() {

    if (!usuario || cargando) return

    setError('')
    setMensaje('')
    setCargando(true)

    try {

      await sendEmailVerification(usuario)

      setMensaje(
        'Correo de verificación enviado. Revisa tu bandeja de entrada y spam.'
      )

    } catch (err) {

      setError(interpretarError(err.code))

    } finally {

      setCargando(false)
    }
  }

  // =====================================
  // 8. COMPROBAR VERIFICACIÓN
  // =====================================

  async function comprobarVerificacion() {

    if (!auth.currentUser || cargando) return

    setError('')
    setMensaje('')
    setCargando(true)

    try {

      await reload(auth.currentUser)

      const estaVerificado = Boolean(
        auth.currentUser.emailVerified
      )

      setVerificado(estaVerificado)

      if (estaVerificado) {

        setMensaje('¡Correo verificado correctamente!')

      } else {

        setMensaje(
          'Tu correo todavía no aparece como verificado. Abre el enlace recibido e intenta nuevamente.'
        )
      }

    } catch (err) {

      setError(interpretarError(err.code))

    } finally {

      setCargando(false)
    }
  }

  // =====================================
  // 9. RECUPERAR CONTRASEÑA
  // =====================================

  async function recuperarContrasena() {

    if (cargando) return

    setError('')
    setMensaje('')

    if (!correo.trim()) {

      setError('Primero introduce tu correo electrónico.')
      return
    }

    setCargando(true)

    try {

      await sendPasswordResetEmail(
        auth,
        correo.trim()
      )

      setMensaje(
        'Si existe una cuenta asociada, recibirás un correo de recuperación.'
      )

    } catch (err) {

      setError(interpretarError(err.code))

    } finally {

      setCargando(false)
    }
  }

  // =====================================
  // 10. CERRAR SESIÓN
  // =====================================

  async function cerrarSesion() {

    if (cargando) return

    setError('')
    setMensaje('')
    setCargando(true)

    try {

      await signOut(auth)

      setUsuario(null)
      setVerificado(false)

      setCorreo('')
      setContrasena('')
      setConfirmacion('')
      setModo('login')

      setMensaje('Sesión cerrada correctamente.')

    } catch (err) {

      setError(interpretarError(err.code))

    } finally {

      setCargando(false)
    }
  }

  // =====================================
  // 11. INTERFAZ PRINCIPAL
  // =====================================

  return (

    <main className="investigator-page">

      <Link className="back-link" to="/">
        ← Volver al inicio
      </Link>

      <section
        className={
          usuario && verificado
            ? 'auth-card dashboard-card'
            : 'auth-card'
        }
      >

        {/* Encabezado del acceso.
            Se oculta cuando aparece el Dashboard. */}

        {!(usuario && verificado) && (

          <div className="auth-header">

            <span
              className="auth-icon"
              aria-hidden="true"
            >
              ✦
            </span>

            <h1>SPHEREx Explorer</h1>

            <h2>Acceso de investigadores</h2>

            <p>
              Tu espacio de exploración y análisis astronómico.
            </p>

          </div>
        )}

        {/* Mensajes del sistema */}

        {error && (

          <p className="auth-message" role="alert">
            {error}
          </p>

        )}

        {mensaje && !(usuario && verificado) && (

          <p className="auth-message" role="status">
            {mensaje}
          </p>

        )}

        {/* =====================================
            CONTROL DE ACCESO
        ===================================== */}

        {verificando ? (

          <p>Comprobando sesión...</p>

        ) : usuario ? (

          // Usuario autenticado

          !verificado ? (

            // =====================================
            // CORREO NO VERIFICADO
            // =====================================

            <div className="auth-form">

              <h2>¡Bienvenido!</h2>

              <p>{usuario.email}</p>

              <h3>Verifica tu correo electrónico</h3>

              <p>
                Para continuar, verifica tu dirección
                de correo electrónico.
              </p>

              <p>
                Revisa tu bandeja de entrada y abre
                el enlace enviado por Firebase.
              </p>

              <button
                className="auth-submit"
                type="button"
                onClick={comprobarVerificacion}
                disabled={cargando}
              >
                Ya verifiqué mi correo
              </button>

              <button
                type="button"
                onClick={reenviarVerificacion}
                disabled={cargando}
              >
                Reenviar correo de verificación
              </button>

              <button
                className="auth-submit"
                type="button"
                onClick={cerrarSesion}
                disabled={cargando}
              >
                {cargando
                  ? 'Procesando...'
                  : 'Cerrar sesión'}
              </button>

            </div>

          ) : (

            // =====================================
            // CORREO VERIFICADO
            // MOSTRAR DASHBOARD
            // =====================================

            <DashboardInvestigador
              usuario={usuario}
              cerrarSesion={cerrarSesion}
              cargando={cargando}
            />

          )

        ) : (

          // =====================================
          // USUARIO SIN SESIÓN
          // LOGIN Y REGISTRO
          // =====================================

          <>

            <div className="auth-tabs">

              <button
                type="button"
                className={modo === 'login' ? 'active' : ''}
                aria-pressed={modo === 'login'}
                onClick={() => cambiarModo('login')}
              >
                Iniciar sesión
              </button>

              <button
                type="button"
                className={esRegistro ? 'active' : ''}
                aria-pressed={esRegistro}
                onClick={() => cambiarModo('registro')}
              >
                Registrarse
              </button>

            </div>

            <form
              className="auth-form"
              onSubmit={manejarEnvio}
            >

              {/* CORREO */}

              <label htmlFor="correo">
                Correo electrónico
              </label>

              <input
                id="correo"
                type="email"
                placeholder="correo@ejemplo.com"
                autoComplete="email"
                value={correo}
                onChange={e => setCorreo(e.target.value)}
                required
              />

              {/* CONTRASEÑA */}

              <label htmlFor="contrasena">
                Contraseña
              </label>

              <div className="password-field">

                <input
                  id="contrasena"
                  type={
                    mostrarContrasena
                      ? 'text'
                      : 'password'
                  }
                  placeholder="Contraseña"
                  autoComplete={
                    esRegistro
                      ? 'new-password'
                      : 'current-password'
                  }
                  value={contrasena}
                  onChange={e => setContrasena(e.target.value)}
                  minLength={
                    esRegistro ? 8 : undefined
                  }
                  required
                />

                <button
                  type="button"
                  onClick={() =>
                    setMostrarContrasena(actual => !actual)
                  }
                  aria-label={
                    mostrarContrasena
                      ? 'Ocultar contraseña'
                      : 'Mostrar contraseña'
                  }
                >
                  {mostrarContrasena
                    ? 'Ocultar'
                    : 'Mostrar'}
                </button>

              </div>

              {/* CONFIRMACIÓN */}

              {esRegistro && (

                <>

                  <label htmlFor="confirmacion">
                    Confirmar contraseña
                  </label>

                  <input
                    id="confirmacion"
                    type="password"
                    placeholder="Repite tu contraseña"
                    autoComplete="new-password"
                    value={confirmacion}
                    onChange={e =>
                      setConfirmacion(e.target.value)
                    }
                    minLength={8}
                    required
                  />

                </>

              )}

              {/* ENVIAR */}

              <button
                className="auth-submit"
                type="submit"
                disabled={cargando}
              >
                {cargando
                  ? 'Procesando...'
                  : esRegistro
                    ? 'Crear cuenta'
                    : 'Ingresar'}
              </button>

              {/* RECUPERAR CONTRASEÑA */}

              {!esRegistro && (

                <button
                  type="button"
                  onClick={recuperarContrasena}
                  disabled={cargando}
                >
                  ¿Olvidaste tu contraseña?
                </button>

              )}

            </form>

          </>

        )}

        {!(usuario && verificado) && (

          <p className="auth-disclaimer">
            Autenticación mediante Firebase.
          </p>

        )}

      </section>

    </main>
  )
}

export default Investigador
