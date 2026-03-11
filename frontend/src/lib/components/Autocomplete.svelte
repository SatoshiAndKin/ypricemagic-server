<script lang="ts">
  import { untrack } from 'svelte';
  import { tokenIndex, searchTokens, getTokenFromIndex } from '../stores/tokenlist';
  import type { TokenlistToken } from '../types';

  let {
    placeholder = '0x...',
    chain,
    onselect,
    initialAddress,
    suppressModal = false,
    class: className = ''
  }: {
    placeholder?: string;
    chain: number;
    onselect?: (token: TokenlistToken | null, address: string) => void;
    initialAddress?: string;
    suppressModal?: boolean;
    class?: string;
  } = $props();

  type MatchToken = TokenlistToken & { sourceList: string; _needsDisambiguation?: boolean };

  let inputValue = $state('');
  let inputAddress = $state('');
  let matches = $state<MatchToken[]>([]);
  let highlightIndex = $state(-1);
  let isOpen = $state(false);
  let wasUserEdited = $state(false);
  let logoSrc = $state<string | undefined>(undefined);
  let logoError = $state(false);
  // Track local suppressModal override (can be set imperatively via setSuppressModal).
  // Initialized via $effect to avoid "captures initial value only" warning.
  let _suppressModal = $state(false);

  let inputEl: HTMLInputElement | undefined;
  let dropdownEl = $state<HTMLDivElement | undefined>(undefined);
  let debounceTimer: ReturnType<typeof setTimeout> | null = null;

  function formatTokenDisplay(_symbol: string | undefined, address: string): string {
    return address;
  }

  function extractAddress(): string {
    if (inputAddress) return inputAddress;
    const match = inputValue.match(/\((0x[0-9a-fA-F]+)\)/);
    if (match) return match[1];
    return inputValue;
  }

  function doSearch(
    query: string,
    chainId: number,
    index: Map<number, Map<string, TokenlistToken & { sourceList: string }>>
  ): void {
    if (!query.trim()) {
      matches = [];
      isOpen = false;
      return;
    }

    const results = searchTokens(index, query, chainId);

    // Determine which symbols need disambiguation (same symbol, different tokens)
    const symbolCounts = new Map<string, number>();
    for (const token of results) {
      const sym = token.symbol.toLowerCase();
      symbolCounts.set(sym, (symbolCounts.get(sym) ?? 0) + 1);
    }

    matches = results.slice(0, 20).map((token) => ({
      ...token,
      _needsDisambiguation: (symbolCounts.get(token.symbol.toLowerCase()) ?? 0) > 1
    }));

    highlightIndex = -1;
    isOpen = true;
  }

  // Re-run search when chain or tokenIndex changes
  $effect(() => {
    const _chain = chain;
    const _index = $tokenIndex;
    const query = untrack(() => inputValue);
    const edited = untrack(() => wasUserEdited);
    if (query.trim() && edited) {
      doSearch(query, _chain, _index);
    }
  });

  // Pre-fill from initialAddress on mount; retry when index loads
  $effect(() => {
    const addr = initialAddress;
    void $tokenIndex; // track index so we retry when tokenlist loads
    if (addr !== undefined && !untrack(() => wasUserEdited)) {
      untrack(() => setFromAddress(addr));
    }
  });

  // Sync suppressModal prop into local state
  $effect(() => {
    _suppressModal = suppressModal;
  });

  function selectToken(token: MatchToken): void {
    inputValue = formatTokenDisplay(token.symbol, token.address);
    inputAddress = token.address;
    logoSrc = token.logoURI;
    logoError = false;
    isOpen = false;
    highlightIndex = -1;
    onselect?.(token, token.address);
  }

  function handleInput(e: Event): void {
    const target = e.target as HTMLInputElement;
    inputValue = target.value;
    wasUserEdited = true;
    inputAddress = '';
    logoSrc = undefined;
    logoError = false;

    if (debounceTimer !== null) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      doSearch(inputValue, chain, $tokenIndex);
    }, 150);
  }

  function handleFocus(): void {
    if (matches.length > 0) {
      isOpen = true;
    }
  }

  function handleBlur(): void {
    setTimeout(() => {
      isOpen = false;
    }, 150);
  }

  function handleKeydown(e: KeyboardEvent): void {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!isOpen && matches.length > 0) {
        isOpen = true;
      }
      if (matches.length > 0) {
        highlightIndex = (highlightIndex + 1) % matches.length;
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (matches.length > 0) {
        highlightIndex = highlightIndex <= 0 ? matches.length - 1 : highlightIndex - 1;
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const idx = highlightIndex >= 0 ? highlightIndex : 0;
      if (matches.length > 0) {
        selectToken(matches[idx]);
      }
    } else if (e.key === 'Escape') {
      isOpen = false;
      highlightIndex = -1;
    } else if (e.key === 'Tab') {
      isOpen = false;
      highlightIndex = -1;
    }
  }

  // -----------------------------------------------------------------------
  // Exposed methods (accessible via bind:this on the component)
  // -----------------------------------------------------------------------

  export function setFromAddress(address: string): void {
    wasUserEdited = false;
    const token = getTokenFromIndex(address, chain);
    if (token) {
      inputValue = formatTokenDisplay(token.symbol, token.address);
      inputAddress = token.address;
      logoSrc = token.logoURI;
      logoError = false;
    } else {
      inputValue = address;
      inputAddress = address;
      logoSrc = undefined;
      logoError = false;
    }
    isOpen = false;
    highlightIndex = -1;
  }

  export function clear(): void {
    inputValue = '';
    inputAddress = '';
    logoSrc = undefined;
    logoError = false;
    matches = [];
    isOpen = false;
    highlightIndex = -1;
    wasUserEdited = false;
  }

  export function getValue(): string {
    return extractAddress();
  }

  export function getWasUserEdited(): boolean {
    return wasUserEdited;
  }

  export function setSuppressModal(val: boolean): void {
    _suppressModal = val;
  }
</script>

<div class="autocomplete-wrapper {className}">
  <div class="token-input-wrapper" class:no-icon={!logoSrc || logoError}>
    <img class="token-input-icon" src={logoSrc} alt="" onerror={() => (logoError = true)} />
    <input
      bind:this={inputEl}
      type="text"
      {placeholder}
      value={inputValue}
      oninput={handleInput}
      onfocus={handleFocus}
      onblur={handleBlur}
      onkeydown={handleKeydown}
    />
    {#if inputValue}
      <button
        type="button"
        class="token-clear-btn"
        onclick={() => {
          clear();
          onselect?.(null, '');
        }}
        aria-label="Clear token"
        title="Clear token"
      >
        ×
      </button>
    {/if}
  </div>
  {#if isOpen}
    <div bind:this={dropdownEl} class="autocomplete-dropdown" role="listbox">
      {#if matches.length === 0}
        <div class="autocomplete-no-match">No matches</div>
      {:else}
        {#each matches as token, i}
          <div
            class="autocomplete-item"
            class:highlighted={i === highlightIndex}
            role="option"
            aria-selected={i === highlightIndex}
            tabindex={-1}
            onmouseenter={() => (highlightIndex = i)}
            onmousedown={(e) => {
              e.preventDefault();
              selectToken(token);
            }}
          >
            {#if token.logoURI}
              <img
                class="autocomplete-logo"
                src={token.logoURI}
                alt=""
                onerror={(e) => ((e.target as HTMLImageElement).style.display = 'none')}
              />
            {/if}
            <div class="autocomplete-meta">
              <div class="autocomplete-title">
                <span class="autocomplete-symbol">{token.symbol}</span>
                <span class="autocomplete-name">{token.name}</span>
                {#if token._needsDisambiguation && token.sourceList}
                  <span class="autocomplete-source">{token.sourceList}</span>
                {/if}
              </div>
              <div class="autocomplete-addr">{token.address}</div>
            </div>
          </div>
        {/each}
      {/if}
    </div>
  {/if}
</div>
