import { svelte } from '@sveltejs/vite-plugin-svelte';
import { defineConfig } from 'vitest/config';

const chains = ['ethereum', 'arbitrum', 'optimism', 'base'];

const proxyTarget = 'http://localhost:8000';

const proxyConfig: Record<string, { target: string; changeOrigin: boolean }> = {};

for (const chain of chains) {
  proxyConfig[`/${chain}`] = {
    target: proxyTarget,
    changeOrigin: true,
  };
}

export default defineConfig({
  plugins: [svelte({ hot: !process.env.VITEST })],
  server: {
    proxy: proxyConfig,
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
});
