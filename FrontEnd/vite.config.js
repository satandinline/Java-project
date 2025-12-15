import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        ws: true, // 支持websocket
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('proxy error', err);
          });
        },
      },
      '/avatars': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/default.jpg': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/AIGC_graph': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/image_from_users': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      }
    }
  }
})
