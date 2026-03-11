<script lang="ts">
  import { onMount } from 'svelte';

  type Theme = 'light' | 'dark' | 'system';

  interface Props {
    onopenModal?: () => void;
    chain?: string;
  }

  let { onopenModal, chain = 'ethereum' }: Props = $props();

  let currentTheme = $state<Theme>('system');

  function applyTheme(theme: Theme) {
    currentTheme = theme;
    if (theme === 'system') {
      localStorage.removeItem('theme');
      document.documentElement.removeAttribute('data-theme');
    } else {
      localStorage.setItem('theme', theme);
      document.documentElement.setAttribute('data-theme', theme);
    }
  }

  function cycleTheme() {
    // Cycle: system → light → dark → system
    if (currentTheme === 'system') {
      applyTheme('light');
    } else if (currentTheme === 'light') {
      applyTheme('dark');
    } else {
      applyTheme('system');
    }
  }

  function handleThemeKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      cycleTheme();
    }
  }

  onMount(() => {
    const stored = localStorage.getItem('theme');
    if (stored === 'light' || stored === 'dark') {
      currentTheme = stored;
      document.documentElement.setAttribute('data-theme', stored);
    } else {
      currentTheme = 'system';
      document.documentElement.removeAttribute('data-theme');
    }
  });
</script>

<div class="page-header">
  <div class="header-brand">
    <h1><span class="brand-y">y</span>pricemagic</h1>
    <p class="header-tagline">Multi-chain ERC-20 token price API</p>
  </div>
  <div class="header-actions">
    <button
      type="button"
      class="theme-toggle"
      title="Toggle theme (light/dark/system)"
      aria-label="Theme: {currentTheme}"
      onclick={cycleTheme}
      onkeydown={handleThemeKeydown}
    >
      <span class="theme-icon theme-icon-light">☀</span>
      <span class="theme-icon theme-icon-dark">☾</span>
      <span class="theme-icon theme-icon-system">◐</span>
    </button>
    <a
      class="docs-btn"
      href={`/${chain}/docs`}
      target="_blank"
      rel="noreferrer"
      title="API Docs ({chain})"
    >
      <svg class="docs-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
    </a>
    <a
      class="github-btn"
      href="https://github.com/SatoshiAndKin/ypricemagic-server"
      target="_blank"
      rel="noreferrer"
      title="GitHub Repository"
      aria-label="GitHub Repository"
    >
      <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
        <path d="M8 0C3.58 0 0 3.58 0 8a8 8 0 0 0 5.47 7.59c.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.5-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.5 7.5 0 0 1 4 0c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8 8 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
      </svg>
    </a>
    <button
      type="button"
      class="gear-btn"
      title="Token Lists Settings"
      onclick={() => onopenModal?.()}
    >
      <span class="gear-icon">⚙</span>
    </button>
  </div>
</div>
