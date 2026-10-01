import { writable } from 'svelte/store';

export type Chain = 'ethereum' | 'base';

export const selectedChain = writable<Chain>('ethereum');
