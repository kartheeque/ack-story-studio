import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy /api to FastAPI at 8080 during dev
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8080'
    }
  }
})
