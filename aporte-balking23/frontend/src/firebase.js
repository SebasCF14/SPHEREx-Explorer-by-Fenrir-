
import { initializeApp } from 'firebase/app'
import { getAuth } from 'firebase/auth'

// Configuración oficial de Firebase
const firebaseConfig = {
  apiKey: "AIzaSyCYExYVSOuByV0awC26Sc5cYrrUf4p0cbw",
  authDomain: "spherex-explorer.firebaseapp.com",
  projectId: "spherex-explorer",
  storageBucket: "spherex-explorer.firebasestorage.app",
  messagingSenderId: "789690457538",
  appId: "1:789690457538:web:1c8250d78390531fb00a5b"
}

// Inicializar Firebase
const app = initializeApp(firebaseConfig)

// Servicio de autenticación
export const auth = getAuth(app)

export default app
