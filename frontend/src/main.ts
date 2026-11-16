import * as Sentry from '@sentry/svelte';
import { mount } from 'svelte';
import App from './App.svelte';

const sentryDsn = import.meta.env.VITE_SENTRY_DSN;
if (sentryDsn?.startsWith('https://')) {
  const fetchUpload = globalThis.fetch.bind(globalThis);
  Sentry.init({
    dsn: sentryDsn,
    release: import.meta.env.VITE_SENTRY_RELEASE || undefined,
    environment: import.meta.env.VITE_SENTRY_ENVIRONMENT ?? 'production',
    integrations: [Sentry.browserTracingIntegration()],
    tracesSampleRate: 0.1,
    transport: (options) =>
      Sentry.makeFetchTransport(options, (input, init) =>
        fetchUpload(input, {
          ...init,
          redirect: 'error',
          signal: AbortSignal.timeout(2_000),
        })
      ),
  });
}

const app = mount(App, {
  target: document.getElementById('app')!,
});

export default app;
