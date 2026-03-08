<script lang="ts">
  import { onMount } from 'svelte';

  let {
    token,
    chain,
    onsave,
    oncontinue,
    onreject,
  }: {
    token: string;
    chain: string;
    onsave: () => void;
    oncontinue: () => void;
    onreject: () => void;
  } = $props();

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') onreject();
  }

  onMount(() => {
    document.addEventListener('keydown', handleKeydown);
    return () => document.removeEventListener('keydown', handleKeydown);
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
      This token (<code class="modal-token">{token}</code>) is not in any enabled tokenlist for
      <strong>{chain}</strong>. What would you like to do?
    </div>
    <div class="modal-buttons">
      <button type="button" class="modal-btn modal-btn-save" onclick={onsave}>
        Save to Local List
      </button>
      <button type="button" class="modal-btn modal-btn-continue" onclick={oncontinue}>
        Continue
      </button>
      <button type="button" class="modal-btn modal-btn-reject" onclick={onreject}>Reject</button>
    </div>
  </div>
</div>
