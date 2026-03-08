import { writable } from 'svelte/store';

export type Chain = 'ethereum' | 'arbitrum' | 'optimism' | 'base';

export const selectedChain = writable<Chain>('ethereum');
