import * as Sentry from '@sentry/svelte';
import { mount } from 'svelte';
import App from './App.svelte';

const sentryDsn = import.meta.env.VITE_SENTRY_DSN;
if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    environment: import.meta.env.VITE_SENTRY_ENVIRONMENT ?? 'production',
    integrations: [Sentry.browserTracingIntegration()],
    tracesSampleRate: 0.1,
  });
}

const app = mount(App, {
  target: document.getElementById('app')!,
});

export default app;
