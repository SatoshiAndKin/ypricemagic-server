<script lang="ts">
  import { onMount } from 'svelte';
  import './app.css';
  import Header from './lib/components/Header.svelte';
  import ChainSelector from './lib/components/ChainSelector.svelte';
  import QuoteForm from './lib/components/QuoteForm.svelte';
  import TokenlistModal from './lib/components/TokenlistModal.svelte';
  import { selectedChain, type Chain } from './lib/stores/chain';
  import { CHAIN_IDS } from './lib/stores/tokenlist';

  let showTokenlistModal = $state(false);

  let quoteFormRef: ReturnType<typeof QuoteForm> | undefined;

  onMount(() => {
    const params = new URLSearchParams(window.location.search);

    // Chain
    const chainParam = params.get('chain');
    if (chainParam && ['ethereum', 'arbitrum', 'optimism', 'base'].includes(chainParam)) {
      selectedChain.set(chainParam as Chain);
    }

    // Wait a tick for chain to propagate, then set form values
    setTimeout(() => {
      // Quote form
      const from = params.get('from') || params.get('token');
      if (from && quoteFormRef) quoteFormRef.setFromAddress(from);

      const to = params.get('to') || params.get('to_token');
      if (to && quoteFormRef) quoteFormRef.setToAddress(to);

      const block = params.get('block');
      if (block && quoteFormRef) quoteFormRef.setBlock(block);

      const timestamp = params.get('timestamp');
      if (timestamp && quoteFormRef) quoteFormRef.setTimestamp(timestamp);

      const amount = params.get('amount');
      if (amount && quoteFormRef) quoteFormRef.setAmount(amount);
    }, 0);
  });
</script>

<Header onopenModal={() => { showTokenlistModal = true; }} />
<TokenlistModal
  isOpen={showTokenlistModal}
  onclose={() => showTokenlistModal = false}
  chain={$selectedChain}
  chainId={CHAIN_IDS[$selectedChain]}
/>
<ChainSelector />

<QuoteForm bind:this={quoteFormRef} chain={$selectedChain} chainId={CHAIN_IDS[$selectedChain]} />
