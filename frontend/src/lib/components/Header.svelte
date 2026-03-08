<script lang="ts">
  import { onMount } from 'svelte';

  type Theme = 'light' | 'dark' | 'system';

  interface Props {
    onopenModal?: () => void;
  }

  let { onopenModal }: Props = $props();

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
