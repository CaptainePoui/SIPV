import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3020,
    proxy: {
      '/api': 'http://localhost:8020',
    },
  },
  build: {
    outDir: 'dist',
  },
})
