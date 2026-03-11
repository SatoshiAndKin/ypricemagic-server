import { describe, expect, it } from 'vitest';

import { mapHealthResponseToState } from './health';

describe('mapHealthResponseToState', () => {
  it('maps ok and synced=true to ok', () => {
    expect(
      mapHealthResponseToState({
        status: 'ok',
        chain: 'ethereum',
        synced: true,
      }),
    ).toBe('ok');
  });

  it('maps ok and synced=false to warning', () => {
    expect(
      mapHealthResponseToState({
        status: 'ok',
        chain: 'ethereum',
        synced: false,
      }),
    ).toBe('warning');
  });

  it('maps ok and synced=null to warning', () => {
    expect(
      mapHealthResponseToState({
        status: 'ok',
        chain: 'ethereum',
        synced: null,
      }),
    ).toBe('warning');
  });

  it('maps ok and missing synced to warning', () => {
    expect(
      mapHealthResponseToState({
        status: 'ok',
        chain: 'ethereum',
      }),
    ).toBe('warning');
  });

  it('maps non-ok status to error', () => {
    expect(
      mapHealthResponseToState({
        status: 'unhealthy',
        chain: 'ethereum',
        synced: true,
      }),
    ).toBe('error');
  });
});
