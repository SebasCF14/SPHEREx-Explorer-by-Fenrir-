# SPHEREx Explorer --- Informe de avance y tareas pendientes

**Fecha:** 14 de noviembre de 2026\
**Proyecto:** SPHEREx Explorer\
**Área:** Frontend, autenticación e integración científica

## 1. Resumen del estado

La aplicación web ya cuenta con navegación inicial, modo Observador de
demostración, autenticación mediante Firebase y un Dashboard para
investigadores con correo verificado.

**Importante:** el contenido astronómico mostrado hasta ahora es
demostrativo; la integración con observaciones reales de SPHEREx está
pendiente. Las herramientas «Comparar imágenes», «Mi historial» y
«Exportar resultados» aparecen en el Dashboard, pero todavía no están
implementadas.

## 2. Tecnologías

-   **React:** interfaz de usuario.
-   **Vite:** desarrollo y compilación.
-   **React Router:** navegación.
-   **CSS:** estilos provisionales.
-   **Firebase Authentication:** cuentas de usuario.
-   **Firebase Firestore:** previsto para historial privado; pendiente
    de implementar.
-   **API científica del equipo:** pendiente de integración.

## 3. Funcionalidades realizadas

### Página inicial y Observador

-   [x] Estructura del frontend React.
-   [x] Navegación entre inicio, Observador e Investigador.
-   [x] Vista Observador con animación demostrativa y controles de
    reproducción, pausa, velocidad y cambio de fotogramas.
-   [x] Selección demostrativa de canales infrarrojos.
-   [ ] Conectar el Observador con imágenes y metadatos reales.

### Autenticación de investigadores

-   [x] Registro con correo electrónico y contraseña.
-   [x] Inicio y cierre de sesión.
-   [x] Recuperación de contraseña.
-   [x] Envío y reenvío de correo de verificación.
-   [x] Comprobación del correo verificado.
-   [x] Mensajes de error y estados de carga.
-   [x] Cinco pruebas de verificación de correo completadas.
-   [x] Visualización del Dashboard para usuarios autenticados con
    correo verificado.

### Dashboard

-   [x] Componente `DashboardInvestigador.jsx`.
-   [x] Correo del usuario y estado verificado.
-   [x] Enlace funcional al explorador.
-   [x] Botón para cerrar sesión.
-   [x] Cuatro secciones visibles: Explorar observaciones, Comparar
    imágenes, Mi historial y Exportar resultados.
-   [ ] Implementar las tres herramientas pendientes.

**Seguridad:** condicionar la interfaz en React no reemplaza las reglas
de seguridad del backend ni de Firestore.

## 4. Archivos principales

``` text
spherex-explorer/
└── frontend/
    └── src/
        ├── App.jsx
        ├── App.css
        ├── firebase.js
        └── pages/
            ├── Investigador.jsx
            └── DashboardInvestigador.jsx
```

  Archivo                       Función
  ----------------------------- ------------------------------------------
  `App.jsx`                     Rutas y pantallas principales
  `App.css`                     Estilos actuales
  `firebase.js`                 Inicialización de Firebase
  `Investigador.jsx`            Autenticación y control de acceso visual
  `DashboardInvestigador.jsx`   Panel de herramientas

Esta es la estructura principal trabajada, no un inventario completo del
repositorio.

## 5. Pruebas confirmadas

-   [x] Creación de cuenta y sesión con Firebase.
-   [x] Verificación del correo electrónico.
-   [x] Aparición del Dashboard con sus cuatro herramientas.
-   [x] Compilación del frontend sin errores.

Última compilación informada:

``` text
vite v8.3.8 building client environment for production...
✓ 38 modules transformed.
✓ built in 211ms
```

**No confirmados todavía:** pruebas automatizadas, seguridad de
Firestore, despliegue público, comparación de imágenes reales y
exportación.

## 6. Pendientes de desarrollo

### Comparador de imágenes

-   [ ] Crear pantalla de comparación.
-   [ ] Seleccionar dos observaciones por los criterios admitidos por la
    API.
-   [ ] Comparar imágenes lado a lado.
-   [ ] Evaluar superposición y diferencias con validación científica.
-   [ ] Mostrar fechas, bandas y otros metadatos disponibles.
-   [ ] Gestionar cargas, errores y búsquedas sin resultados.

### Historial privado

-   [ ] Configurar Firestore.
-   [ ] Guardar comparaciones asociadas al `uid` del usuario.
-   [ ] Consultar, abrir y eliminar registros propios.
-   [ ] Implementar y probar reglas de seguridad de Firestore.

### Exportación

-   [ ] Descargar resultados en PNG.
-   [ ] Generar informes PDF.
-   [ ] Incluir metadatos y procedencia de las observaciones.

### Integración y publicación

-   [ ] Conectar la API del equipo científico.
-   [ ] Reemplazar los datos de demostración por observaciones reales.
-   [ ] Probar el flujo completo de consulta, comparación, guardado y
    exportación.
-   [ ] Probar acceso, errores de red y aislamiento entre usuarios.
-   [ ] Configurar y verificar el despliegue.
-   [ ] Revisar accesibilidad y compatibilidad móvil.

## 7. Información que necesitamos de los compañeros

Para integrar el backend científico, solicitar:

1.  **URL base y endpoints** de la API.
2.  **Parámetros de consulta**: coordenadas, radio, fechas y bandas,
    según corresponda.
3.  **Ejemplos reales de respuestas JSON**.
4.  **Formato y acceso a imágenes**: URL, PNG, JPEG, FITS u otro.
5.  **Identificadores únicos** de observaciones.
6.  **Metadatos disponibles** y unidades.
7.  **Manejo de errores, paginación y límites**.
8.  **Requisitos de autenticación y CORS**.
9.  **Definición científica** de qué comparaciones son válidas.
10. **Persona responsable** de la API para coordinar pruebas.

Ejemplo de estructura **ilustrativa**, todavía no confirmada por el
backend:

``` json
{
  "observations": [
    {
      "id": "ejemplo-001",
      "ra_deg": 269.45,
      "dec_deg": 4.69,
      "observation_date": "YYYY-MM-DD",
      "band": "banda-ejemplo",
      "image_url": "https://example.org/imagen.png"
    }
  ]
}
```

Los campos definitivos deberán acordarse con el equipo científico.

## 8. Responsabilidades y estado

  Área                              Estado
  --------------------------------- -----------------------------------------
  Autenticación de usuarios         Funcional y probada manualmente
  Dashboard inicial                 Visible y conectado
  Observador                        Demostración funcional
  Comparador                        Pendiente
  Historial con Firestore           Pendiente
  Exportación PNG/PDF               Pendiente
  Backend de observaciones          Estado por confirmar con los compañeros
  Integración de datos reales       Pendiente
  Pruebas integrales y despliegue   Pendiente
  Diseño visual definitivo          Pospuesto por decisión del equipo

## 9. Orden de trabajo recomendado

1.  **Coordinar la API:** obtener endpoints, ejemplos JSON y formato de
    imágenes.
2.  **Implementar el comparador:** trabajar sobre un contrato de datos
    acordado.
3.  **Agregar historial y seguridad:** Firestore y reglas por usuario.
4.  **Incorporar exportación:** PNG y PDF.
5.  **Integrar y probar:** datos reales, errores, seguridad y
    despliegue.
6.  **Rediseñar la apariencia:** colores, logo, tipografías, imágenes y
    distribución acordados por el equipo.

## 10. Comandos de desarrollo

Desde PowerShell:

``` powershell
cd "C:\Users\dilan\Documents\spherex-explorer\frontend"
npm.cmd run dev
```

La página local normalmente está en `http://localhost:5173/`.

En **otra terminal**, para compilar:

``` powershell
npm.cmd run build
```

## 11. Conclusión

La base de usuarios y el panel inicial del Investigador están
operativos. Para avanzar hacia las funciones científicas reales se
necesita acordar la interfaz con el backend de los compañeros. La
persistencia privada y la exportación aún deben desarrollarse. El diseño
estético definitivo puede realizarse al final, sin rehacer la lógica de
autenticación.
