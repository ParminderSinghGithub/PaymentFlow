import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/health': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
      '/cases': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
      '/webhooks': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
})
