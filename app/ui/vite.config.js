import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://app:8000',
        changeOrigin: true,
        ws:false,
      },
      '/ws': {
        target: 'ws://app:8000',
        ws: true, 
      },
    },
    watch: {
      usePolling: true // Нужно для корректной работы hot-reload в Docker
    }
  }
})