import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  return {
    plugins: [react()],
    define: { __API_BASE_URL__: JSON.stringify(env.VITE_API_BASE_URL || '/api') },
    resolve: { alias: {
      '@': path.resolve(__dirname, 'src'),
      '@pages': path.resolve(__dirname, 'src/pages'),
      '@components': path.resolve(__dirname, 'src/components'),
      '@api': path.resolve(__dirname, 'src/api')
    } },
    server: { host: '0.0.0.0', port: 5173, strictPort: true, proxy: {
      '/api': { target: 'http://127.0.0.1:8000', rewrite: url => url.replace(/^\/api/, '') }
    } }
  };
});
