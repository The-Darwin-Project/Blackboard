// BlackBoard/ui/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
function devAuthMock() {
  return {
    name: 'dev-auth-mock',
    configureServer(server: any) {
      server.middlewares.use('/config', (_req: any, res: any) => {
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({
          contactEmail: '',
          feedbackFormUrl: '',
          appVersion: 'dev',
          auth: { enabled: true, issuerUrl: 'http://localhost:5556/dex', clientId: 'darwin-dashboard', loginDisclaimer: '' },
        }));
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), devAuthMock()],
  // Base path - UI served at root
  base: '/',
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-graph': ['@xyflow/react', '@dagrejs/dagre'],
          'vendor-ui': ['lucide-react', 'recharts'],
        },
      },
    },
    chunkSizeWarningLimit: 1800,
  },
  server: {
    proxy: {
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
      '/topology': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/metrics': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/queue': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/events': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/chat': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // Reports API -- Vite proxies fetch/XHR only, not HTML page navigations.
      // Browser navigation to /reports serves the SPA; API calls proxy to FastAPI.
      '/reports': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/telemetry': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
