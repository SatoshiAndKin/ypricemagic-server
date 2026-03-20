<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchBucket } from '../api';
  import type { BucketResponse } from '../types';

  let {
    token,
    chain,
    onsave,
    oncontinue,
    onreject,
  }: {
    token: string;
    chain: string;
    onsave: (metadata: { symbol: string; name: string; decimals: number } | null) => void;
    oncontinue: () => void;
    onreject: () => void;
  } = $props();

  let loading = $state(true);
  let metadata = $state<{ symbol: string; name: string; decimals: number } | null>(null);
  let fetchError = $state(false);

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') onreject();
  }

  /** Truncate address for fallback display: "0x6399...2e70" */
  function truncateAddress(addr: string): string {
    if (addr.length <= 10) return addr;
    return addr.slice(0, 6) + '...' + addr.slice(-4);
  }

  onMount(() => {
    document.addEventListener('keydown', handleKeydown);

    // Fetch token metadata from the check_bucket endpoint
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10_000);

    fetchBucket(chain, token, controller.signal)
      .then((resp: BucketResponse) => {
        if (resp.symbol && resp.name != null && resp.decimals != null) {
          metadata = { symbol: resp.symbol, name: resp.name, decimals: resp.decimals };
        } else {
          // Backend returned OK but without metadata
          fetchError = true;
        }
      })
      .catch(() => {
        fetchError = true;
      })
      .finally(() => {
        clearTimeout(timeout);
        loading = false;
      });

    return () => {
      document.removeEventListener('keydown', handleKeydown);
      controller.abort();
      clearTimeout(timeout);
    };
  });
</script>

<div
  class="modal-overlay"
  role="none"
  onclick={(e) => {
    if (e.target === e.currentTarget) onreject();
  }}
  onkeydown={(e) => {
    if (e.key === 'Escape') onreject();
  }}
>
  <div class="modal" role="dialog" aria-modal="true" tabindex="-1">
    <div class="modal-title">Unknown Token</div>
    <div class="modal-message">
      {#if loading}
        <p>
          Fetching metadata for <code class="modal-token">{truncateAddress(token)}</code> on
          <strong>{chain}</strong>...
        </p>
        <div class="modal-loading" aria-label="Loading metadata">
          <span class="spinner"></span>
        </div>
      {:else if metadata}
        <p>
          This token is not in any enabled tokenlist for <strong>{chain}</strong>.
        </p>
        <div class="modal-metadata">
          <div class="metadata-row">
            <span class="metadata-label">Symbol</span>
            <span class="metadata-value">{metadata.symbol}</span>
          </div>
          <div class="metadata-row">
            <span class="metadata-label">Name</span>
            <span class="metadata-value">{metadata.name}</span>
          </div>
          <div class="metadata-row">
            <span class="metadata-label">Decimals</span>
            <span class="metadata-value">{metadata.decimals}</span>
          </div>
          <div class="metadata-row">
            <span class="metadata-label">Address</span>
            <span class="metadata-value"><code class="modal-token">{truncateAddress(token)}</code></span>
          </div>
        </div>
      {:else}
        <p>
          This token (<code class="modal-token">{truncateAddress(token)}</code>) is not in any
          enabled tokenlist for <strong>{chain}</strong>. Metadata could not be fetched.
        </p>
      {/if}
    </div>
    <div class="modal-buttons">
      <button type="button" class="modal-btn modal-btn-save" disabled={loading} onclick={() => onsave(metadata)}>
        Save to Local List
      </button>
      <button type="button" class="modal-btn modal-btn-continue" onclick={oncontinue}>
        Continue
      </button>
      <button type="button" class="modal-btn modal-btn-reject" onclick={onreject}>Reject</button>
    </div>
  </div>
</div>

<style>
  .modal-loading {
    display: flex;
    justify-content: center;
    padding: 1rem 0;
  }

  .spinner {
    width: 1.5rem;
    height: 1.5rem;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .modal-metadata {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    margin-top: 0.75rem;
    padding: 0.75rem;
    background: var(--bg-input, var(--bg-secondary, #f5f5f5));
    border-radius: 6px;
    font-size: 0.9rem;
  }

  .metadata-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
  }

  .metadata-label {
    font-weight: 500;
    color: var(--text-muted, #666);
    flex-shrink: 0;
  }

  .metadata-value {
    text-align: right;
    word-break: break-all;
  }
</style>
