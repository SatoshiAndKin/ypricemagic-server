<script lang="ts">
  import { selectedChain, type Chain } from '../stores/chain';

  function handleChange(e: Event) {
    const target = e.target as HTMLSelectElement;
    selectedChain.set(target.value as Chain);
  }
</script>

<div class="form-group chain-selector">
  <label for="chain">Chain</label>
  <select id="chain" value={$selectedChain} onchange={handleChange}>
    <option value="ethereum">Ethereum</option>
    <option value="arbitrum">Arbitrum</option>
    <option value="optimism">Optimism</option>
    <option value="base">Base</option>
  </select>

</div>
