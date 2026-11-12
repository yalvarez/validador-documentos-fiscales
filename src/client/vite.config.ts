import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// La consola se sirve en /client; sus llamadas van a /client/api, que nginx (o el proxy de
// desarrollo) reenvía a la API agregando la x-api-key del lado del servidor.
export default defineConfig({
  base: '/client/',
  plugins: [react()],
  server: {
    proxy: {
      '/client/api': {
        target: process.env.API_URL ?? 'http://localhost:7000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/client\/api/, ''),
        headers: { 'x-api-key': process.env.API_KEY ?? '' },
      },
    },
  },
})
