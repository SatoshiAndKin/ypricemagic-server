<script lang="ts">
  import { tick } from 'svelte';
  import Autocomplete from './Autocomplete.svelte';
  import { fetchBatchPrices } from '../api';
  import type { BatchPriceItem } from '../types';
  import { formatTimestamp } from '../utils';

  let { chain, chainId }: { chain: string; chainId: number } = $props();

  interface TokenRow {
    id: number;
    address: string;
    amount: string;
    ref?: ReturnType<typeof Autocomplete>;
  }

  let rows = $state<TokenRow[]>([{ id: 0, address: '', amount: '' }]);
  let nextId = $state(1);
  let blockInput = $state('');
  let blockType = $state<'text' | 'datetime-local'>('text');
  let loading = $state(false);
  let error = $state<string | null>(null);
  let result = $state<{ items: BatchPriceItem[]; chain: string } | null>(null);

  function addRow() {
    rows = [...rows, { id: nextId, address: '', amount: '' }];
    nextId += 1;
  }

  function removeRow(id: number) {
    rows = rows.filter((r) => r.id !== id);
  }

  function getBlockParam(): string {
    if (!blockInput.trim()) return '';
    if (blockType === 'datetime-local') {
      const ts = Math.floor(new Date(blockInput).getTime() / 1000);
      return isNaN(ts) ? '' : String(ts);
    }
    return blockInput.trim();
  }

  function handleBlockInput(e: Event) {
    const val = (e.target as HTMLInputElement).value;
    blockInput = val;
    if (val.includes('/')) {
      blockType = 'datetime-local';
      blockInput = '';
    }
  }

  function handleDateChange() {
    if (!blockInput) {
      blockType = 'text';
    }
  }

  function switchToBlock() {
    blockType = 'text';
    blockInput = '';
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    error = null;
    result = null;

    // Collect address+amount pairs together so they stay aligned after filtering
    const pairs = rows
      .map((row) => ({
        token: row.ref?.getValue() ?? row.address,
        amount: row.amount.trim(),
      }))
      .filter(({ token }) => token.trim() !== '');

    if (pairs.length === 0) {
      error = 'Add at least one token address';
      return;
    }

    const tokens = pairs.map((p) => p.token);
    const amounts = pairs.map((p) => p.amount);
    const hasAmounts = amounts.some((a) => a !== '');

    const blockParam = getBlockParam() || undefined;
    const amountsParam = hasAmounts ? amounts : undefined;

    loading = true;
    try {
      const data = await fetchBatchPrices(chain, tokens, blockParam, amountsParam);
      result = { items: data.prices, chain: data.chain };
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    } finally {
      loading = false;
    }
  }

  // ---------------------------------------------------------------------------
  // Exported methods for URL state management
  // ---------------------------------------------------------------------------

  export function setTokens(addresses: string[], amounts: string[]): void {
    rows = addresses.map((addr, i) => ({
      id: i,
      address: addr,
      amount: amounts[i] || ''
    }));
    nextId = addresses.length;

    tick().then(() => {
      rows.forEach((row) => {
        if (row.ref) {
          row.ref.setFromAddress(row.address);
          row.ref.setSuppressModal(true);
        }
      });
    });
  }

  function formatPrice(price: number | null): string {
    if (price === null) return '';
    return '$' + price.toFixed(4);
  }
</script>

<section class="form-section">
  <h2>Batch Prices</h2>
  <form onsubmit={handleSubmit}>
    <div id="batch-token-rows">
      {#each rows as row (row.id)}
        <div class="token-row">
          <Autocomplete
            bind:this={row.ref}
            chain={chainId}
            placeholder="0x..."
            onselect={(_token, addr) => {
              row.address = addr;
            }}
          />
          <input type="text" bind:value={row.amount} placeholder="Amount (opt)" />
          <button type="button" class="btn-remove" onclick={() => removeRow(row.id)}>×</button>
        </div>
      {/each}
    </div>

    <div class="form-group" style="margin-top: 8px;">
      <button type="button" class="btn-secondary" onclick={addRow}>+ Add Token</button>
    </div>

    <div class="form-group">
      <label for="batch-block">Block</label>
      {#if blockType === 'text'}
        <input
          id="batch-block"
          type="text"
          bind:value={blockInput}
          oninput={handleBlockInput}
          placeholder="defaults to latest"
        />
        <p class="hint">Block number, or type "/" for a date picker.</p>
      {:else}
        <input
          id="batch-block"
          type="datetime-local"
          bind:value={blockInput}
          onchange={handleDateChange}
        />
        <p class="hint">
          Pick a date. <button type="button" class="link-btn" onclick={switchToBlock}>Clear</button> to switch back.
        </p>
      {/if}
    </div>

    <button type="submit" disabled={loading}>
      {loading ? 'Fetching...' : 'Get Prices'}
    </button>

    {#if error}
      <div class="error-box">{error}</div>
    {/if}
  </form>

  {#if result}
    <div class="result-card">
      <div class="result-section-title">Batch Results ({result.items.length} tokens)</div>
      <table>
        <thead>
          <tr>
            <th>Token</th>
            <th>Block</th>
            <th>Price</th>
            <th>Timestamp</th>
            <th>Cached</th>
          </tr>
        </thead>
        <tbody>
          {#each result.items as item}
            <tr>
              <td class="monospace">{item.token}</td>
              <td class="monospace">{item.block}</td>
              <td>
                {#if item.price !== null}
                  <span class="result-value-number">{formatPrice(item.price)}</span>
                {:else}
                  <span class="null">null</span>
                {/if}
              </td>
              <td>{formatTimestamp(item.timestamp)}</td>
              <td>{item.cached ? 'Yes' : 'No'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</section>
