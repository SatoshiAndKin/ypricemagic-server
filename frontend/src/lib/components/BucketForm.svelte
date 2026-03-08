<script lang="ts">
  import Autocomplete from './Autocomplete.svelte';
  import UnknownTokenModal from './UnknownTokenModal.svelte';
  import { fetchBucket } from '../api';
  import type { BucketResponse } from '../types';
  import { isTokenInIndex, addLocalToken } from '../stores/tokenlist';

  let { chain, chainId }: { chain: string; chainId: number } = $props();

  let tokenRef: ReturnType<typeof Autocomplete> | undefined;
  let tokenAddress = $state('');
  let loading = $state(false);
  let error = $state<string | null>(null);
  let result = $state<BucketResponse | null>(null);

  let showUnknownModal = $state(false);
  let unknownModalToken = $state('');
  let unknownModalResolve = $state<((action: 'save' | 'continue' | 'reject') => void) | null>(
    null
  );

  const HEX_ADDR = /^0x[0-9a-fA-F]{40}$/;

  async function checkUnknownToken(
    address: string,
    wasUserEdited: boolean
  ): Promise<'proceed' | 'reject'> {
    if (!address || !HEX_ADDR.test(address)) return 'proceed';
    if (isTokenInIndex(address, chainId)) return 'proceed';
    if (!wasUserEdited) return 'proceed';

    return new Promise<'proceed' | 'reject'>((resolve) => {
      unknownModalToken = address;
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
  // Exported methods for URL state management
  // ---------------------------------------------------------------------------

  export function setToken(address: string, suppress = true): void {
    tokenAddress = address;
    if (tokenRef) {
      tokenRef.setFromAddress(address);
      if (suppress) tokenRef.setSuppressModal(true);
    }
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    error = null;
    result = null;

    const addr = tokenRef?.getValue() ?? tokenAddress;
    const wasEdited = tokenRef?.getWasUserEdited() ?? false;

    if (!addr.trim()) {
      error = 'Enter a token address';
      return;
    }

    const action = await checkUnknownToken(addr, wasEdited);
    if (action === 'reject') return;

    loading = true;
    try {
      const data = await fetchBucket(chain, addr);
      result = data;
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    } finally {
      loading = false;
    }
  }
</script>

<section class="form-section">
  <h2>Token Classification</h2>
  <form onsubmit={handleSubmit}>
    <div class="form-group">
      <label for="bucket-token">Token</label>
      <Autocomplete
        bind:this={tokenRef}
        chain={chainId}
        onselect={(_token, addr) => (tokenAddress = addr)}
        placeholder="0x..."
      />
    </div>

    <button type="submit" disabled={loading}>
      {loading ? 'Checking...' : 'Check Bucket'}
    </button>

    {#if loading}
      <p class="hint">Classifying token (this may take 10-30s)...</p>
    {/if}

    {#if error}
      <div class="error-box">{error}</div>
    {/if}
  </form>

  {#if result}
    <div class="result-card">
      <div class="result-section-title">Classification Result</div>

      {#if result.chain !== chain}
        <div class="result-warning">
          ⚠ Chain mismatch: response is for <strong>{result.chain}</strong>, but you selected
          <strong>{chain}</strong>.
        </div>
      {/if}

      <div class="result-grid">
        <div class="result-row">
          <span class="result-label">Token</span>
          <span class="result-value">{result.token}</span>
        </div>
        <div class="result-row">
          <span class="result-label">Chain</span>
          <span class="result-value">{result.chain}</span>
        </div>
        <div class="result-row">
          <span class="result-label">Bucket</span>
          <span class="result-value">
            {#if result.bucket !== null}
              {result.bucket}
            {:else}
              <span class="null">null</span>
            {/if}
          </span>
        </div>
      </div>
    </div>
  {/if}

  {#if showUnknownModal && unknownModalResolve}
    <UnknownTokenModal
      token={unknownModalToken}
      {chain}
      onsave={() => unknownModalResolve?.('save')}
      oncontinue={() => unknownModalResolve?.('continue')}
      onreject={() => unknownModalResolve?.('reject')}
    />
  {/if}
</section>
