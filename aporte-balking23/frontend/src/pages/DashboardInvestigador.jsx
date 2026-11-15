
import { Link } from 'react-router-dom'

// Panel principal del investigador autenticado
function DashboardInvestigador({
  usuario,
  cerrarSesion,
  cargando
}) {
  return (
    <div className="dashboard-investigador">

      {/* ENCABEZADO */}

      <header className="dashboard-header">
        <div>
          <h1>SPHEREx Explorer</h1>
          <p>Research Dashboard</p>
        </div>

        <span className="dashboard-status">
          ✓ Correo verificado
        </span>
      </header>

      {/* BIENVENIDA */}

      <section className="dashboard-welcome">
        <h2>Bienvenido al universo</h2>

        <p>
          Explora observaciones astronómicas,
          compara imágenes y organiza
          tus futuras investigaciones.
        </p>

        <p className="dashboard-email">
          Investigador: {usuario?.email || 'Investigador'}
        </p>
      </section>

      {/* HERRAMIENTAS DE INVESTIGACIÓN */}

      <section className="dashboard-tools">
        <h2>Herramientas de investigación</h2>

        <div className="dashboard-grid">

          {/* EXPLORADOR */}

          <article className="dashboard-tool">
            <span
              className="dashboard-tool-icon"
              aria-hidden="true"
            >
              🔭
            </span>

            <h3>Explorar observaciones</h3>

            <p>
              Accede al explorador astronómico
              y visualiza las observaciones
              disponibles.
            </p>

            <Link
              className="dashboard-action"
              to="/observador"
            >
              Abrir explorador
            </Link>
          </article>

          {/* COMPARADOR */}

          <article className="dashboard-tool">
            <span
              className="dashboard-tool-icon"
              aria-hidden="true"
            >
              ◈
            </span>

            <h3>Comparar imágenes</h3>

            <p>
              Compara observaciones por fecha
              y canal infrarrojo para analizar
              sus diferencias.
            </p>

            <span className="dashboard-pending">
              Próxima implementación
            </span>
          </article>

          {/* HISTORIAL */}

          <article className="dashboard-tool">
            <span
              className="dashboard-tool-icon"
              aria-hidden="true"
            >
              ◷
            </span>

            <h3>Mi historial</h3>

            <p>
              Consulta las comparaciones
              guardadas en tu cuenta
              de investigador.
            </p>

            <span className="dashboard-pending">
              Próxima implementación
            </span>
          </article>

          {/* EXPORTACIÓN */}

          <article className="dashboard-tool">
            <span
              className="dashboard-tool-icon"
              aria-hidden="true"
            >
              ↓
            </span>

            <h3>Exportar resultados</h3>

            <p>
              Descarga tus futuras
              comparaciones en formatos
              PNG o PDF.
            </p>

            <span className="dashboard-pending">
              Próxima implementación
            </span>
          </article>

        </div>
      </section>

      {/* PIE DEL PANEL */}

      <footer className="dashboard-footer">

        <Link
          to="/"
          className="dashboard-home"
        >
          Volver al inicio
        </Link>

        <button
          type="button"
          className="dashboard-logout"
          onClick={cerrarSesion}
          disabled={cargando}
        >
          {cargando
            ? 'Cerrando sesión...'
            : 'Cerrar sesión'}
        </button>

      </footer>

    </div>
  )
}

export default DashboardInvestigador
