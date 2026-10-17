import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // API_PROXY lets a second dev copy talk to another backend.
      '/api': process.env.API_PROXY || 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.js',
    // Typing-heavy UI tests can be slow on a busy machine; don't fail them for that.
    testTimeout: 15000,
  },
})
