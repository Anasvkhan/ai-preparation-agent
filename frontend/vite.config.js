import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Forward /api calls to FastAPI during development (no CORS issues).
    proxy: { '/api': 'http://localhost:8000' },
  },
})
