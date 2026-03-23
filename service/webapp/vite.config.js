import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// In Docker the API container is reachable at 'scholarship-api'.
// In local dev (npm run dev outside Docker), it's at localhost:3001.
// Set VITE_API_TARGET in your env to override.
const apiTarget = process.env.VITE_API_TARGET
  || (process.env.DOCKER ? 'http://scholarship-api:3001' : 'http://localhost:3001')

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: true,   // required for Docker to expose the port
    port: 5173,
    proxy: {
      '/api': {
        target:       apiTarget,
        changeOrigin: true,
      },
    },
  },
})