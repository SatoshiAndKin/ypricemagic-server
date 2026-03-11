import type { HealthResponse } from './types';

export type HealthIndicatorState = 'ok' | 'warning' | 'error';

export function mapHealthResponseToState(response: HealthResponse): HealthIndicatorState {
  if (response.status !== 'ok') {
    return 'error';
  }

  if (response.synced === true) {
    return 'ok';
  }

  return 'warning';
}
