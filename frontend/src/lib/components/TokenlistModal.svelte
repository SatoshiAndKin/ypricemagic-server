<script lang="ts">
  import { onMount } from 'svelte';
  import {
    allLists,
    getListKey,
    countTokensForChain,
    toggleList,
    addList,
    removeList,
    type TokenlistEntry,
  } from '../stores/tokenlist';
  import { fetchTokenlistProxy } from '../api';

  let { isOpen, onclose, chain, chainId }: {
    isOpen: boolean;
    onclose: () => void;
    chain: string;
    chainId: number;
  } = $props();

  let urlInput = $state('');
  let urlLoading = $state(false);
  let message = $state('');
  let messageType = $state<'success' | 'error' | 'loading' | ''>('');
  let showDeleteConfirm = $state(false);
  let deleteIndex = $state(-1);
  let deleteListName = $state('');
  let fileInputEl = $state<HTMLInputElement | null>(null);

  // Body scroll lock
  $effect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  });

  // Keyboard handler
  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && isOpen) onclose();
  }

  onMount(() => {
    document.addEventListener('keydown', handleKeydown);
    return () => document.removeEventListener('keydown', handleKeydown);
  });

  // ---------------------------------------------------------------------------
  // Helper functions
  // ---------------------------------------------------------------------------

  function getSourceLabel(list: TokenlistEntry): string {
    if (list.isDefault) return 'Built-in';
    if (list.isLocal) return 'Saved locally';
    if (list.url) return list.url.length > 50 ? list.url.slice(0, 50) + '...' : list.url;
    return 'Imported from file';
  }

  async function addByUrl() {
    const url = urlInput.trim();
    if (!url) return;

    // Validate HTTPS only
    if (!url.startsWith('https://')) {
      message = 'Only HTTPS URLs are allowed';
      messageType = 'error';
      return;
    }

    // Check duplicate by URL
    const existingUrl = $allLists.find((l) => l.url === url);
    if (existingUrl) {
      message = 'This URL is already in your list';
      messageType = 'error';
      return;
    }

    urlLoading = true;
    message = '';
    messageType = '';

    try {
      const timeoutPromise = new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error('Request timed out after 30 seconds')), 30000)
      );
      const list = await Promise.race([fetchTokenlistProxy(chain, url), timeoutPromise]);

      // Validate structure
      if (!list.name || !Array.isArray(list.tokens)) {
        throw new Error('Invalid tokenlist structure: missing name or tokens array');
      }

      // Check duplicate by name
      const dupName = $allLists.find((l) => l.name === list.name);
      if (dupName) {
        throw new Error(`A list named "${list.name}" already exists`);
      }

      addList({
        name: list.name,
        tokens: list.tokens,
        url,
        enabled: true,
        timestamp: list.timestamp,
        version: list.version,
      });

      message = `Successfully added "${list.name}" with ${list.tokens.length} tokens`;
      messageType = 'success';
      urlInput = '';

      // Auto-clear success after 5s
      setTimeout(() => {
        if (messageType === 'success') {
          message = '';
          messageType = '';
        }
      }, 5000);
    } catch (err) {
      message = err instanceof Error ? err.message : 'Failed to fetch tokenlist';
      messageType = 'error';
    } finally {
      urlLoading = false;
    }
  }

  function importFile() {
    fileInputEl?.click();
  }

  function handleFileImport(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const text = e.target?.result as string;
        const parsed = JSON.parse(text) as {
          name?: unknown;
          tokens?: unknown;
          timestamp?: string;
          version?: { major: number; minor: number; patch: number };
        };

        if (!parsed.name || !Array.isArray(parsed.tokens)) {
          message = 'Invalid tokenlist file: missing name or tokens array';
          messageType = 'error';
          return;
        }

        // Check duplicate by name
        const dupName = $allLists.find((l) => l.name === parsed.name);
        if (dupName) {
          message = `A list named "${parsed.name as string}" already exists`;
          messageType = 'error';
          return;
        }

        addList({
          name: parsed.name as string,
          tokens: parsed.tokens as TokenlistEntry['tokens'],
          enabled: true,
          timestamp: parsed.timestamp,
          version: parsed.version,
        });

        message = `Imported "${parsed.name as string}" with ${(parsed.tokens as unknown[]).length} tokens`;
        messageType = 'success';
      } catch {
        message = 'Failed to parse file as JSON';
        messageType = 'error';
      }
    };
    reader.readAsText(file);
    // Reset input so the same file can be re-imported if needed
    input.value = '';
  }

  function exportLocal() {
    const localList = $allLists.find((l) => l.isLocal && l.name === 'Local Tokens');
    if (!localList || localList.tokens.length === 0) {
      message = 'No local tokens to export';
      messageType = 'error';
      return;
    }

    const data = JSON.stringify({ name: localList.name, tokens: localList.tokens }, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = 'local-tokens.json';
    a.click();
    URL.revokeObjectURL(blobUrl);
  }

  function confirmDelete(index: number, name: string) {
    deleteIndex = index;
    deleteListName = name;
    showDeleteConfirm = true;
  }

  function performDelete() {
    removeList(deleteIndex);
    showDeleteConfirm = false;
    deleteIndex = -1;
    deleteListName = '';
  }

  async function retryList(index: number) {
    const list = $allLists[index];
    if (!list?.url) return;

    try {
      const updated = await fetchTokenlistProxy(chain, list.url);
      removeList(index);
      addList({
        name: updated.name,
        tokens: updated.tokens,
        url: list.url,
        enabled: list.enabled,
        timestamp: updated.timestamp,
        version: updated.version,
      });
    } catch (err) {
      message = err instanceof Error ? err.message : 'Failed to retry list';
      messageType = 'error';
    }
  }
</script>

{#if isOpen}
<div
  class="modal-overlay tokenlist-modal-overlay"
  role="none"
  onclick={(e) => { if (e.target === e.currentTarget) onclose(); }}
  onkeydown={(e) => { if (e.key === 'Escape') onclose(); }}
>
  <div class="modal tokenlist-modal" role="dialog" aria-modal="true">
    <!-- Header -->
    <div class="modal-header">
      <h3>Manage Tokenlists</h3>
      <button type="button" class="modal-close" onclick={onclose}>×</button>
    </div>

    <!-- Trust warning -->
    <div class="trust-warning">
      ⚠ Be careful with untrusted tokenlists. Malicious lists can contain harmful tokens.
    </div>

    <!-- List of tokenlists -->
    <div class="tokenlist-lists" id="tokenlist-lists">
      {#each $allLists as list, i}
        <div class="tokenlist-item" class:disabled={!list.enabled} class:error-state={!!list.error}>
          {#if list.error}
            <!-- Error state -->
            <div class="tokenlist-item-info">
              <div class="tokenlist-item-name">{list.name || list.url || 'Unknown'}</div>
              <div class="tokenlist-item-source">{getSourceLabel(list)}</div>
              <div class="tokenlist-item-error">{list.error}</div>
            </div>
            <div class="tokenlist-item-actions">
              <button type="button" onclick={() => retryList(i)}>Retry</button>
              {#if !list.isDefault}
                <button type="button" class="tokenlist-delete-x" onclick={() => confirmDelete(i, list.name)}>×</button>
              {/if}
            </div>
          {:else}
            <!-- Normal state -->
            <div class="tokenlist-item-info">
              <div class="tokenlist-item-name">{list.name}</div>
              <div class="tokenlist-item-source">{getSourceLabel(list)}</div>
              {#if countTokensForChain(list, chainId) === 0}
                <div class="tokenlist-item-chain-warning">0 tokens on {chain} ⚠</div>
              {:else}
                <div class="tokenlist-item-count">{countTokensForChain(list, chainId)} tokens on {chain}</div>
              {/if}
            </div>
            <div class="tokenlist-item-actions">
              <div
                class="tokenlist-toggle"
                class:enabled={list.enabled}
                role="switch"
                aria-checked={list.enabled}
                tabindex="0"
                onclick={() => toggleList(getListKey(list))}
                onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleList(getListKey(list)); } }}
              >
                <div class="tokenlist-toggle-knob"></div>
              </div>
              {#if !list.isDefault}
                <button type="button" class="tokenlist-delete-x" onclick={() => confirmDelete(i, list.name)}>×</button>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>

    <!-- Add by URL -->
    <div class="tokenlist-add-section">
      <h4>Add by URL</h4>
      <div class="tokenlist-add-row">
        <input
          type="text"
          bind:value={urlInput}
          placeholder="https://..."
          onkeydown={(e) => e.key === 'Enter' && addByUrl()}
        />
        <button type="button" onclick={addByUrl} disabled={urlLoading}>
          {urlLoading ? 'Loading...' : 'Add'}
        </button>
      </div>
      {#if message}
        <div class="tokenlist-message {messageType}">{message}</div>
      {/if}
    </div>

    <!-- Import/Export -->
    <div class="tokenlist-file-section">
      <button type="button" onclick={importFile}>Import from file</button>
      <button type="button" onclick={exportLocal}>Export local tokens</button>
      <input
        type="file"
        accept=".json"
        style="display:none"
        bind:this={fileInputEl}
        onchange={handleFileImport}
      />
    </div>
  </div>
</div>

<!-- Delete confirmation modal (higher z-index) -->
{#if showDeleteConfirm}
<div
  class="delete-confirm-overlay"
  role="none"
  onclick={(e) => { if (e.target === e.currentTarget) showDeleteConfirm = false; }}
  onkeydown={(e) => { if (e.key === 'Escape') showDeleteConfirm = false; }}
>
  <div class="delete-confirm-dialog" role="dialog" aria-modal="true">
    <p>Delete "<strong>{deleteListName}</strong>"?</p>
    <div class="delete-confirm-buttons">
      <button type="button" onclick={() => showDeleteConfirm = false}>Cancel</button>
      <button type="button" class="btn-danger" onclick={performDelete}>Delete</button>
    </div>
  </div>
</div>
{/if}
{/if}
