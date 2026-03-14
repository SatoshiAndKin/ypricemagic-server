<script lang="ts">
  import { untrack } from 'svelte';
  import Autocomplete from './Autocomplete.svelte';
  import UnknownTokenModal from './UnknownTokenModal.svelte';
  import { fetchPrice } from '../api';
  import type { PriceResponse } from '../types';
  import {
    getEffectivePair,
    isTokenInIndex,
    addLocalToken,
    tokenIndex,
    type Chain,
  } from '../stores/tokenlist';
  import { getTokenFromIndex } from '../stores/tokenlist';
  import { formatRelativeAge, formatTimestamp } from '../utils';
  import ChainSelector from './ChainSelector.svelte';

  let { chain, chainId }: { chain: string; chainId: number } = $props();

  // Component refs (not reactive; accessed imperatively)
  let fromRef: ReturnType<typeof Autocomplete> | undefined;

  // Internal address tracking
  let fromAddress = $state('');
  let fromTokenInfo = $derived.by(() => {
    void $tokenIndex;
    return fromAddress ? getTokenFromIndex(fromAddress, chainId) ?? null : null;
  });

  // Form state
  let blockInput = $state('');
  let blockType = $state<'text' | 'datetime-local'>('text');
  let amount = $state('');
  let showAmountWarning = $state(false);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let result = $state<PriceResponse | null>(null);

  // Unknown token modal state
  let showUnknownModal = $state(false);
  let unknownToken = $state('');
  let unknownModalResolve = $state<((action: 'save' | 'continue' | 'reject') => void) | null>(
    null
  );

  // Abort controller for in-flight requests
  let abortController: AbortController | null = null;

  // Age / timestamp state
  let ageInterval: ReturnType<typeof setInterval> | null = null;
  let blockTimestamp = $state<number | null>(null);
  let ageDisplay = $state('');

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  const HEX_ADDR = /^0x[0-9a-fA-F]{40}$/;

  const BLOCK_EXPLORER: Record<string, string> = {
    ethereum: 'https://etherscan.io',
    arbitrum: 'https://arbiscan.io',
    optimism: 'https://optimistic.etherscan.io',
    base: 'https://basescan.org',
  };

  function getBlockParam(): string {
    if (!blockInput.trim()) return '';
    if (blockType === 'datetime-local') {
      const ts = Math.floor(new Date(blockInput).getTime() / 1000);
      return isNaN(ts) ? '' : String(ts);
    }
    return blockInput.trim();
  }

  function stopAgeInterval() {
    if (ageInterval !== null) {
      clearInterval(ageInterval);
      ageInterval = null;
    }
  }

  function startAgeInterval(timestamp: number) {
    stopAgeInterval();
    blockTimestamp = timestamp;
    ageDisplay = formatRelativeAge(timestamp);
    ageInterval = setInterval(() => {
      ageDisplay = formatRelativeAge(timestamp);
    }, 1000);
  }

  // ---------------------------------------------------------------------------
  // Unknown token modal
  // ---------------------------------------------------------------------------

  async function checkUnknownToken(
    address: string,
    wasUserEdited: boolean
  ): Promise<'proceed' | 'reject'> {
    if (!address || !HEX_ADDR.test(address)) return 'proceed';
    if (isTokenInIndex(address, chainId)) return 'proceed';
    if (!wasUserEdited) return 'proceed';

    return new Promise<'proceed' | 'reject'>((resolve) => {
      unknownToken = address;
      showUnknownModal = true;
      unknownModalResolve = (action) => {
        showUnknownModal = false;
        unknownModalResolve = null;
        if (action === 'save') {
          addLocalToken({
            chainId,
            address,
            symbol: address.slice(0, 8),
            name: address,
            decimals: 18,
          });
          resolve('proceed');
        } else if (action === 'continue') {
          resolve('proceed');
        } else {
          resolve('reject');
        }
      };
    });
  }

  // ---------------------------------------------------------------------------
  // Event handlers
  // ---------------------------------------------------------------------------

  function cancelIfLoading() {
    if (loading) {
      abortPending();
      loading = false;
      result = null;
      error = null;
      stopAgeInterval();
    }
  }

  function handleFromSelect(_token: unknown, address: string) {
    cancelIfLoading();
    fromAddress = address;
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

  function abortPending() {
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    abortPending();
    stopAgeInterval();
    result = null;
    error = null;

    const fromAddr = fromRef?.getValue() ?? fromAddress;
    const fromEdited = fromRef?.getWasUserEdited() ?? false;

    const fromAction = await checkUnknownToken(fromAddr, fromEdited);
    if (fromAction === 'reject') return;

    const blockParam = getBlockParam() || undefined;
    const amountParam = amount.trim() || undefined;

    abortController = new AbortController();
    loading = true;
    try {
      const priceData = await fetchPrice(
        chain,
        fromAddr,
        blockParam,
        abortController.signal,
        amountParam,
      );

      result = priceData;

      if (priceData.block_timestamp != null) {
        startAgeInterval(priceData.block_timestamp);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      error = err instanceof Error ? err.message : String(err);
    } finally {
      loading = false;
    }
  }

  // ---------------------------------------------------------------------------
  // Chain change effect — load effective pair when chain changes
  // ---------------------------------------------------------------------------

  $effect(() => {
    const _chain = chain;
    // Only access refs in untrack to avoid tracking them
    untrack(() => {
      abortPending();
      loading = false;
      result = null;
      error = null;
      stopAgeInterval();

      const pair = getEffectivePair(_chain as Chain);
      fromAddress = pair.from;
      fromRef?.setFromAddress(pair.from);
    });
  });

  // Cleanup on unmount
  $effect(() => {
    return () => {
      stopAgeInterval();
      abortPending();
    };
  });

  // ---------------------------------------------------------------------------
  // Exported methods for URL state management
  // ---------------------------------------------------------------------------

  export function setFromAddress(address: string, suppress = true): void {
    if (fromRef) {
      fromRef.setFromAddress(address);
      if (suppress) fromRef.setSuppressModal(true);
    }
    fromAddress = address;
  }

  export function setBlock(block: string): void {
    blockInput = block;
  }

  export function setTimestamp(isoString: string): void {
    blockType = 'datetime-local';
    // Convert ISO to datetime-local format: "2024-01-15T12:00" (no seconds)
    blockInput = isoString.replace('Z', '').slice(0, 16);
  }

  export function setAmount(amt: string): void {
    amount = amt;
    showAmountWarning = !!amt.trim();
  }

  // ---------------------------------------------------------------------------
  // Format helpers for display
  // ---------------------------------------------------------------------------

  function formatPrice(price: number | null): string {
    if (price == null) return 'N/A';
    return '$' + price.toFixed(4);
  }

  function getSymbol(address: string): string {
    if (!address) return '?';
    const token = getTokenFromIndex(address, chainId);
    return token?.symbol ?? address.slice(0, 8) + '...';
  }
</script>

<section class="form-section">
  <form onsubmit={handleSubmit}>
    <ChainSelector />

    <div class="form-group">
      <label for="from-token" class="token-field-label">
        Token
        {#if fromTokenInfo?.symbol}
          <span class="token-label-info">
            {#if fromTokenInfo.logoURI}
              <img src={fromTokenInfo.logoURI} alt="" class="token-label-icon" />
            {/if}
            <span>{fromTokenInfo.symbol}</span>
          </span>
        {/if}
      </label>
      <Autocomplete
        bind:this={fromRef}
        chain={chainId}
        onselect={handleFromSelect}
        oninputchange={cancelIfLoading}
        initialAddress={fromAddress}
        placeholder="0x... or symbol"
      />
    </div>

    <div class="form-group">
      <label for="amount">Amount</label>
      <input
        id="amount"
        type="text"
        bind:value={amount}
        oninput={() => (showAmountWarning = !!amount.trim())}
        placeholder="1"
      />
      {#if showAmountWarning}
        <p class="hint warning">Amount set — may result in cache miss</p>
      {/if}
    </div>

    <div class="form-group">
      <label for="block">Block</label>
      {#if blockType === 'text'}
        <input
          id="block"
          type="text"
          bind:value={blockInput}
          oninput={handleBlockInput}
          placeholder="defaults to latest"
        />
        <p class="hint">Block number, or type "/" for a date picker.</p>
      {:else}
        <input
          id="block"
          type="datetime-local"
          bind:value={blockInput}
          onchange={handleDateChange}
        />
        <p class="hint">
          Pick a date. <button type="button" class="link-btn" onclick={switchToBlock}>Clear</button> to switch back.
        </p>
      {/if}
    </div>

    <div class="form-actions">
      <button type="submit" class="btn-wide" disabled={loading}>
        {loading ? 'Fetching...' : 'Get Price'}
      </button>
    </div>

    {#if error}
      <div class="error-box">{error}</div>
    {/if}
  </form>

  {#if result}
    <div class="result-card">
      <div class="result-section-title">Result</div>

      {#if result.chain !== chain}
        <div class="result-warning">
          ⚠ Chain mismatch: response is for <strong>{result.chain}</strong>, but you selected
          <strong>{chain}</strong>.
        </div>
      {/if}

      <div class="result-grid">
        <div class="result-row">
          <span class="result-label">Price (USD)</span>
          <span class="result-value result-value-number">
            {formatPrice(result.price)}
          </span>
        </div>

        <div class="result-row">
          <span class="result-label">Chain</span>
          <span class="result-value">{result.chain}</span>
        </div>

        <div class="result-row">
          <span class="result-label">Block</span>
          <span class="result-value result-value-number">
            <a href="{(BLOCK_EXPLORER[result.chain] ?? BLOCK_EXPLORER['ethereum'])}/block/{result.block}" target="_blank" rel="noreferrer" class="block-link">{result.block}</a>
          </span>
        </div>

        {#if result.block_timestamp != null}
          <div class="result-row">
            <span class="result-label">Block Timestamp</span>
            <span class="result-value">{formatTimestamp(result.block_timestamp)}</span>
          </div>

          <div class="result-row">
            <span class="result-label">Block Age</span>
            <span class="result-value result-value-muted">{ageDisplay}</span>
          </div>
        {/if}

        {#if result.trade_path?.length}
          <div class="result-row result-row-route">
            <span class="result-label">Price Route</span>
            <span class="result-value">
              {#each result.trade_path as step, i}
                <div class="route-step">
                  <span class="route-step-num">{i + 1}.</span>
                  <span class="route-step-tokens">{getSymbol(step.input_token)} → {getSymbol(step.output_token)}</span>
                  <span class="route-step-pool">{step.source}{#if step.pool} <code>{step.pool.slice(0, 10)}…</code>{/if}</span>
                </div>
              {/each}
            </span>
          </div>
        {/if}
      </div>
    </div>
  {/if}

  {#if showUnknownModal && unknownModalResolve}
    <UnknownTokenModal
      token={unknownToken}
      {chain}
      onsave={() => unknownModalResolve?.('save')}
      oncontinue={() => unknownModalResolve?.('continue')}
      onreject={() => unknownModalResolve?.('reject')}
    />
  {/if}
</section>
