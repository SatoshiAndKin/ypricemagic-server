<script lang="ts">
  import { untrack } from 'svelte';
  import Autocomplete from './Autocomplete.svelte';
  import UnknownTokenModal from './UnknownTokenModal.svelte';
  import { fetchQuote } from '../api';
  import type { QuoteResponse } from '../types';
  import {
    getEffectivePair,
    saveCustomPair,
    isTokenInIndex,
    addLocalToken,
    type Chain,
  } from '../stores/tokenlist';
  import { getTokenFromIndex } from '../stores/tokenlist';
  import { formatRelativeAge, formatTimestamp } from '../utils';
  import ChainSelector from './ChainSelector.svelte';

  let { chain, chainId }: { chain: string; chainId: number } = $props();

  interface QuoteResult {
    quote: QuoteResponse;
  }

  // Component refs (not reactive; accessed imperatively)
  let fromRef: ReturnType<typeof Autocomplete> | undefined;
  let toRef: ReturnType<typeof Autocomplete> | undefined;

  // Internal address tracking
  let fromAddress = $state('');
  let toAddress = $state('');

  // Form state
  let blockInput = $state('');
  let blockType = $state<'text' | 'datetime-local'>('text');
  let amount = $state('');
  let showAmountWarning = $state(false);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let result = $state<QuoteResult | null>(null);

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

  function isValidAddress(addr: string): boolean {
    return HEX_ADDR.test(addr);
  }

  function getSymbol(address: string): string {
    if (!address) return '?';
    const token = getTokenFromIndex(address, chainId);
    return token?.symbol ?? address.slice(0, 8) + '...';
  }

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

  function handleFromSelect(_token: unknown, address: string) {
    fromAddress = address;
    if (isValidAddress(fromAddress) && isValidAddress(toAddress)) {
      saveCustomPair(chain, fromAddress, toAddress);
    }
  }

  function handleToSelect(_token: unknown, address: string) {
    toAddress = address;
    if (isValidAddress(fromAddress) && isValidAddress(toAddress)) {
      saveCustomPair(chain, fromAddress, toAddress);
    }
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
    const toAddr = toRef?.getValue() ?? toAddress;
    const fromEdited = fromRef?.getWasUserEdited() ?? false;
    const toEdited = toRef?.getWasUserEdited() ?? false;

    const fromAction = await checkUnknownToken(fromAddr, fromEdited);
    if (fromAction === 'reject') return;

    const toAction = await checkUnknownToken(toAddr, toEdited);
    if (toAction === 'reject') return;

    const blockParam = getBlockParam() || undefined;
    const amountParam = amount.trim() || undefined;

    abortController = new AbortController();
    loading = true;
    try {
      const quoteData = await fetchQuote(
        chain,
        fromAddr,
        toAddr,
        blockParam,
        amountParam,
        abortController.signal,
      );

      result = { quote: quoteData };

      if (isValidAddress(fromAddr) && isValidAddress(toAddr)) {
        saveCustomPair(chain, fromAddr, toAddr);
      }

      if (quoteData.block_timestamp != null) {
        startAgeInterval(quoteData.block_timestamp);
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
    const _chainId = chainId;
    // Only access refs in untrack to avoid tracking them
    untrack(() => {
      abortPending();
      loading = false;
      result = null;
      error = null;
      stopAgeInterval();

      const pair = getEffectivePair(_chain as Chain);
      fromAddress = pair.from;
      toAddress = pair.to;
      fromRef?.setFromAddress(pair.from);
      toRef?.setFromAddress(pair.to);
      void _chainId; // suppress unused variable warning
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
  }

  export function setToAddress(address: string, suppress = true): void {
    if (toRef) {
      toRef.setFromAddress(address);
      if (suppress) toRef.setSuppressModal(true);
    }
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

  function formatNumber(n: number): string {
    if (n === 0) return '0';
    if (Math.abs(n) < 0.0001) return n.toExponential(4);
    if (Math.abs(n) >= 1e9) return n.toExponential(4);
    return n.toPrecision(6).replace(/\.?0+$/, '');
  }
</script>

<section class="form-section">
  <form onsubmit={handleSubmit}>
    <ChainSelector />

    <div class="form-group">
      <label for="from-token">From Token</label>
      <Autocomplete
        bind:this={fromRef}
        chain={chainId}
        onselect={handleFromSelect}
        initialAddress={fromAddress}
        placeholder="0x... or symbol"
      />
    </div>

    <div class="form-group">
      <label for="to-token">To Token</label>
      <Autocomplete
        bind:this={toRef}
        chain={chainId}
        onselect={handleToSelect}
        initialAddress={toAddress}
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
        {loading ? 'Fetching...' : 'Get Quote'}
      </button>
    </div>

    {#if error}
      <div class="error-box">{error}</div>
    {/if}
  </form>

  {#if result}
    {@const q = result.quote}
    {@const fromSym = getSymbol(q.from)}
    {@const toSym = getSymbol(q.to)}
    {@const rate = q.amount > 0 ? q.output_amount / q.amount : 0}
    <div class="result-card">
      <div class="result-section-title">Result</div>

      {#if q.chain !== chain}
        <div class="result-warning">
          ⚠ Chain mismatch: response is for <strong>{q.chain}</strong>, but you selected
          <strong>{chain}</strong>.
        </div>
      {/if}

      <div class="result-grid">
        <div class="result-row">
          <span class="result-label">Conversion</span>
          <span class="result-value result-value-number">
            1 {fromSym} = {formatNumber(rate)}
            {toSym}
          </span>
        </div>

        <div class="result-row">
          <span class="result-label">Input / Output</span>
          <span class="result-value result-value-number">
            {formatNumber(q.amount)}
            {fromSym} →
            {formatNumber(q.output_amount)}
            {toSym}
          </span>
        </div>

        {#if q.from_price != null}
          <div class="result-row">
            <span class="result-label">From Token Price (USD)</span>
            <span class="result-value result-value-number">
              {formatPrice(q.from_price)}
            </span>
          </div>
        {/if}

        {#if q.to_price != null}
          <div class="result-row">
            <span class="result-label">To Token Price (USD)</span>
            <span class="result-value result-value-number">
              {formatPrice(q.to_price)}
            </span>
          </div>
        {/if}

        <div class="result-row">
          <span class="result-label">Chain</span>
          <span class="result-value">{q.chain}</span>
        </div>

        <div class="result-row">
          <span class="result-label">Block</span>
          <span class="result-value result-value-number">
            <a href="{(BLOCK_EXPLORER[q.chain] ?? BLOCK_EXPLORER['ethereum'])}/block/{q.block}" target="_blank" rel="noreferrer" class="block-link">{q.block}</a>
          </span>
        </div>

        {#if q.block_timestamp != null}
          <div class="result-row">
            <span class="result-label">Block Timestamp</span>
            <span class="result-value">{formatTimestamp(q.block_timestamp)}</span>
          </div>

          <div class="result-row">
            <span class="result-label">Block Age</span>
            <span class="result-value result-value-muted">{ageDisplay}</span>
          </div>
        {/if}

        <div class="result-row">
          <span class="result-label">Route</span>
          <span class="result-value result-value-muted">
            {#if q.route === 'divide'}
              {getSymbol(q.from)} → USD ÷ {getSymbol(q.to)} → USD
            {:else if q.route === 'identity'}
              identity (same token)
            {:else}
              {q.route}
            {/if}
          </span>
        </div>
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
