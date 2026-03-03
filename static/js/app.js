// Utility functions
function getChain() {
  return document.getElementById('chain').value;
}

// Chain ID mapping
const CHAIN_IDS = {
  ethereum: 1,
  arbitrum: 42161,
  optimism: 10,
  base: 8453
};

function getChainId() {
  return CHAIN_IDS[getChain()] || 1;
}

// Default pairs per chain (factory defaults)
const DEFAULT_PAIRS = {
  ethereum: {
    from: '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', // USDC
    to: '0xf939E0A03FB07F59A73314E73794Be0E57ac1b4E'   // crvUSD
  },
  arbitrum: {
    from: '0xaf88d065e77c8cC2239327C5EDb3A432268e5831', // USDC (native)
    to: '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1'   // WETH
  },
  optimism: {
    from: '0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85', // USDC
    to: '0x4200000000000000000000000000000000000006'    // WETH
  },
  base: {
    from: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // USDC
    to: '0x4200000000000000000000000000000000000006'    // WETH
  }
};

// Get custom pairs from localStorage
function getCustomPairs() {
  try {
    return JSON.parse(localStorage.getItem('defaultPairs') || '{}');
  } catch (e) {
    return {};
  }
}

// Save custom pairs to localStorage
function saveCustomPair(chain, from, to) {
  const pairs = getCustomPairs();
  pairs[chain] = { from, to };
  localStorage.setItem('defaultPairs', JSON.stringify(pairs));
}

// Get the effective pair for a chain (custom if set, else factory default)
function getEffectivePair(chain) {
  const custom = getCustomPairs();
  if (custom[chain]) {
    return custom[chain];
  }
  return DEFAULT_PAIRS[chain] || { from: '', to: '' };
}

function escapeHtml(str) {
  if (str == null) return '';
  return String(str).replace(/[&<>"']/g, function(c) {
    return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'}[c];
  });
}

function showError(resultEl, msg) {
  resultEl.className = 'result show';
  resultEl.innerHTML = '<div class="error">' + escapeHtml(msg) + '</div>';
}

function showLoading(resultEl, msg) {
  resultEl.className = 'result show';
  resultEl.innerHTML = '<div class="result-header">' + escapeHtml(msg) + '</div>';
}

// Tokenlist management
let tokenlists = [];
let tokenIndex = new Map(); // Map<chainId, Map<lowercaseAddress, token>>

async function loadTokenlists() {
  tokenlists = [];
  tokenIndex.clear();

  // Load Uniswap default tokenlist
  try {
    const res = await fetch('/static/tokenlists/uniswap-default.json');
    if (res.ok) {
      const data = await res.json();
      data.enabled = true; // Default list is always enabled
      data.isDefault = true; // Cannot be deleted
      tokenlists.push(data);
    }
  } catch (e) {
    console.error('Failed to load Uniswap tokenlist:', e);
  }

  // Load user tokenlists from localStorage
  try {
    const savedLists = JSON.parse(localStorage.getItem('tokenlists') || '[]');
    for (const list of savedLists) {
      if (list.name && Array.isArray(list.tokens)) {
        tokenlists.push(list);
      }
    }
  } catch (e) {
    console.error('Failed to load localStorage tokenlists:', e);
  }

  // Load local tokens (saved via unknown token modal)
  try {
    const localTokens = JSON.parse(localStorage.getItem('localTokens') || '[]');
    if (localTokens.length > 0) {
      tokenlists.push({
        name: 'Local Tokens',
        version: { major: 1, minor: 0, patch: 0 },
        timestamp: new Date().toISOString(),
        tokens: localTokens,
        enabled: true,
        isLocal: true
      });
    }
  } catch (e) {
    console.error('Failed to load local tokens:', e);
  }

  // Build index
  rebuildTokenIndex();

  // Load enabled/disabled states
  loadTokenlistStates();

  // Rebuild index after loading states
  rebuildTokenIndex();
}

function rebuildTokenIndex() {
  tokenIndex.clear();

  for (const list of tokenlists) {
    if (!list.enabled) continue;

    for (const token of (list.tokens || [])) {
      const chainId = token.chainId;
      const addrLower = (token.address || '').toLowerCase();

      if (!chainId || !addrLower) continue;

      if (!tokenIndex.has(chainId)) {
        tokenIndex.set(chainId, new Map());
      }

      const chainMap = tokenIndex.get(chainId);

      // Only add if not already present (first list wins for dedup)
      if (!chainMap.has(addrLower)) {
        chainMap.set(addrLower, {
          ...token,
          sourceList: list.name
        });
      }
    }
  }
}

function getEnabledTokenlists() {
  return tokenlists.filter(l => l.enabled);
}

function saveLocalTokens() {
  const localList = tokenlists.find(l => l.isLocal);
  if (localList) {
    localStorage.setItem('localTokens', JSON.stringify(localList.tokens || []));
  } else {
    localStorage.setItem('localTokens', '[]');
  }
}

// Save user-added tokenlists to localStorage
function saveUserTokenlists() {
  const userLists = tokenlists.filter(l => !l.isDefault && !l.isLocal).map(l => ({
    ...l,
    enabled: l.enabled !== false // default to true
  }));
  localStorage.setItem('tokenlists', JSON.stringify(userLists));
}

// Load tokenlists state from localStorage
function loadTokenlistStates() {
  try {
    const states = JSON.parse(localStorage.getItem('tokenlistStates') || '{}');
    for (const list of tokenlists) {
      const key = list.isDefault ? 'default' : (list.url || list.name);
      if (states[key] !== undefined) {
        list.enabled = states[key];
      }
    }
  } catch (e) {
    console.error('Failed to load tokenlist states:', e);
  }
}

// Save tokenlist enabled states to localStorage
function saveTokenlistStates() {
  const states = {};
  for (const list of tokenlists) {
    const key = list.isDefault ? 'default' : (list.url || list.name);
    states[key] = list.enabled;
  }
  localStorage.setItem('tokenlistStates', JSON.stringify(states));
}

function addLocalToken(token) {
  let localList = tokenlists.find(l => l.isLocal);
  if (!localList) {
    localList = {
      name: 'Local Tokens',
      version: { major: 1, minor: 0, patch: 0 },
      timestamp: new Date().toISOString(),
      tokens: [],
      enabled: true,
      isLocal: true
    };
    tokenlists.push(localList);
  }

  // Check if token already exists
  const exists = localList.tokens.some(t =>
    t.chainId === token.chainId &&
    t.address.toLowerCase() === token.address.toLowerCase()
  );

  if (!exists) {
    localList.tokens.push(token);
    saveLocalTokens();
    rebuildTokenIndex();
  }
}

function isValidHexAddress(str) {
  return /^0x[a-fA-F0-9]{40}$/.test(str);
}

function isTokenInLists(address, chainId) {
  const chainMap = tokenIndex.get(chainId);
  if (!chainMap) return false;
  return chainMap.has(address.toLowerCase());
}

// Autocomplete component
class TokenAutocomplete {
  constructor(inputEl, options = {}) {
    this.input = inputEl;
    this.options = options;
    this.dropdown = null;
    this.matches = [];
    this.highlightIndex = -1;
    this.debounceTimer = null;
    this.isOpen = false;
    this.suppressModal = options.suppressModal || false; // For pre-filled values
    this.wasUserEdited = false;

    this.createDropdown();
    this.attachEvents();
  }

  createDropdown() {
    this.dropdown = document.createElement('div');
    this.dropdown.className = 'autocomplete-dropdown';
    this.dropdown.style.display = 'none';
    this.input.parentNode.style.position = 'relative';
    this.input.parentNode.appendChild(this.dropdown);
  }

  attachEvents() {
    // Input handler with debounce
    this.input.addEventListener('input', () => {
      this.wasUserEdited = true;
      this.scheduleSearch();
    });

    // Focus handler - show dropdown on focus if there's content
    this.input.addEventListener('focus', () => {
      if (this.input.value.length >= 1 && this.matches.length > 0) {
        this.showDropdown();
      }
    });

    // Blur handler - close dropdown when focus leaves
    this.input.addEventListener('blur', (e) => {
      // Delay to allow click on dropdown items
      setTimeout(() => {
        if (!this.dropdown.contains(document.activeElement)) {
          this.hideDropdown();
        }
      }, 150);
    });

    // Keyboard navigation
    this.input.addEventListener('keydown', (e) => {
      if (!this.isOpen) {
        if (e.key === 'ArrowDown' && this.input.value.length >= 1) {
          this.search();
          if (this.matches.length > 0) {
            this.showDropdown();
            this.highlightIndex = 0;
            this.updateHighlight();
          }
        }
        return;
      }

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          this.highlightIndex = Math.min(this.highlightIndex + 1, this.matches.length - 1);
          this.updateHighlight();
          break;
        case 'ArrowUp':
          e.preventDefault();
          this.highlightIndex = Math.max(this.highlightIndex - 1, 0);
          this.updateHighlight();
          break;
        case 'Enter':
          e.preventDefault();
          if (this.highlightIndex >= 0 && this.highlightIndex < this.matches.length) {
            this.selectToken(this.matches[this.highlightIndex]);
          } else if (this.matches.length > 0) {
            this.selectToken(this.matches[0]);
          }
          break;
        case 'Escape':
          e.preventDefault();
          this.hideDropdown();
          break;
        case 'Tab':
          this.hideDropdown();
          // Let default behavior move focus
          break;
      }
    });
  }

  scheduleSearch() {
    clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => {
      this.search();
    }, 150);
  }

  search() {
    const query = this.input.value.trim().toLowerCase();
    const chainId = getChainId();

    if (query.length < 1) {
      this.matches = [];
      this.hideDropdown();
      return;
    }

    const chainMap = tokenIndex.get(chainId);
    if (!chainMap) {
      this.matches = [];
      this.showNoMatches();
      return;
    }

    // Search by symbol, name, or address prefix
    this.matches = [];
    for (const [addr, token] of chainMap) {
      const symbol = (token.symbol || '').toLowerCase();
      const name = (token.name || '').toLowerCase();
      const address = (token.address || '').toLowerCase();

      if (symbol.startsWith(query) ||
          symbol.includes(query) ||
          name.includes(query) ||
          address.startsWith(query)) {
        this.matches.push(token);
      }

      if (this.matches.length >= 20) break; // Limit results
    }

    // Sort: exact symbol match first, then symbol prefix, then name match, then address prefix
    this.matches.sort((a, b) => {
      const aSymbol = (a.symbol || '').toLowerCase();
      const bSymbol = (b.symbol || '').toLowerCase();

      // Exact symbol match
      if (aSymbol === query && bSymbol !== query) return -1;
      if (bSymbol === query && aSymbol !== query) return 1;

      // Symbol prefix
      if (aSymbol.startsWith(query) && !bSymbol.startsWith(query)) return -1;
      if (bSymbol.startsWith(query) && !aSymbol.startsWith(query)) return 1;

      // Alphabetical by symbol
      return aSymbol.localeCompare(bSymbol);
    });

    this.highlightIndex = -1;

    if (this.matches.length === 0) {
      this.showNoMatches();
    } else {
      this.renderDropdown();
      this.showDropdown();
    }
  }

  renderDropdown() {
    let html = '';
    for (let i = 0; i < this.matches.length; i++) {
      const token = this.matches[i];
      const addrShort = token.address.slice(0, 6) + '...' + token.address.slice(-4);

      html += '<div class="autocomplete-item" data-index="' + i + '">' +
        '<div class="autocomplete-main">' + escapeHtml(token.symbol) + ' — ' + escapeHtml(token.name) + ' <span class="autocomplete-addr">(' + escapeHtml(addrShort) + ')</span></div>' +
        '<div class="autocomplete-source">' + escapeHtml(token.sourceList) + '</div>' +
      '</div>';
    }

    this.dropdown.innerHTML = html;

    // Attach click handlers to items
    const items = this.dropdown.querySelectorAll('.autocomplete-item');
    items.forEach(item => {
      item.addEventListener('mousedown', (e) => {
        e.preventDefault(); // Prevent input blur
        const index = parseInt(item.dataset.index, 10);
        this.selectToken(this.matches[index]);
      });

      item.addEventListener('mouseenter', () => {
        this.highlightIndex = parseInt(item.dataset.index, 10);
        this.updateHighlight();
      });
    });
  }

  showNoMatches() {
    this.dropdown.innerHTML = '<div class="autocomplete-no-match">No matches</div>';
    this.showDropdown();
  }

  showDropdown() {
    this.dropdown.style.display = 'block';
    this.isOpen = true;
  }

  hideDropdown() {
    this.dropdown.style.display = 'none';
    this.isOpen = false;
    this.highlightIndex = -1;
  }

  updateHighlight() {
    const items = this.dropdown.querySelectorAll('.autocomplete-item');
    items.forEach((item, i) => {
      if (i === this.highlightIndex) {
        item.classList.add('highlighted');
      } else {
        item.classList.remove('highlighted');
      }
    });

    // Scroll highlighted item into view
    if (this.highlightIndex >= 0 && items[this.highlightIndex]) {
      items[this.highlightIndex].scrollIntoView({ block: 'nearest' });
    }
  }

  selectToken(token) {
    // Save current values of adjacent fields before updating
    const form = this.input.closest('form');
    const currentBlock = form ? form.querySelector('input[id$="-block"]') : null;
    const currentAmount = form ? form.querySelector('input[id$="-amount"]') : null;

    const blockValue = currentBlock ? currentBlock.value : '';
    const amountValue = currentAmount ? currentAmount.value : '';

    // Update token address
    this.input.value = token.address;
    this.hideDropdown();

    // Restore adjacent field values (in case form framework resets them)
    if (currentBlock) currentBlock.value = blockValue;
    if (currentAmount) currentAmount.value = amountValue;
  }

  destroy() {
    this.hideDropdown();
    if (this.dropdown && this.dropdown.parentNode) {
      this.dropdown.parentNode.removeChild(this.dropdown);
    }
    clearTimeout(this.debounceTimer);
  }
}

// Unknown token warning modal
let modalOverlay = null;
let modalCallback = null;

function createModal() {
  if (modalOverlay) return modalOverlay;

  modalOverlay = document.createElement('div');
  modalOverlay.className = 'modal-overlay';
  modalOverlay.innerHTML =
    '<div class="modal">' +
      '<div class="modal-title">Unknown Token</div>' +
      '<div class="modal-message">This token address is not in any enabled tokenlist for the selected chain. What would you like to do?</div>' +
      '<div class="modal-buttons">' +
        '<button type="button" class="modal-btn modal-btn-save">Save to Local List</button>' +
        '<button type="button" class="modal-btn modal-btn-continue">Continue</button>' +
        '<button type="button" class="modal-btn modal-btn-reject">Reject</button>' +
      '</div>' +
    '</div>';

  document.body.appendChild(modalOverlay);

  // Button handlers
  modalOverlay.querySelector('.modal-btn-save').addEventListener('click', () => {
    closeModal('save');
  });

  modalOverlay.querySelector('.modal-btn-continue').addEventListener('click', () => {
    closeModal('continue');
  });

  modalOverlay.querySelector('.modal-btn-reject').addEventListener('click', () => {
    closeModal('reject');
  });

  // Close on overlay click
  modalOverlay.addEventListener('click', (e) => {
    if (e.target === modalOverlay) {
      closeModal('reject');
    }
  });

  // Escape key
  modalOverlay.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeModal('reject');
    }
  });

  return modalOverlay;
}

function showModal(token, chain, chainId, callback) {
  createModal();
  modalCallback = { fn: callback, token, chain, chainId };
  modalOverlay.style.display = 'flex';

  // Focus the first button
  modalOverlay.querySelector('.modal-btn-save').focus();
}

function closeModal(action) {
  if (!modalOverlay) return;

  modalOverlay.style.display = 'none';

  if (modalCallback) {
    const { fn, token, chain, chainId } = modalCallback;

    if (action === 'save') {
      // Add to local tokenlist
      addLocalToken({
        chainId: chainId,
        address: token,
        symbol: 'Unknown',
        name: 'Unknown Token',
        decimals: 18
      });
      fn(true, 'save'); // proceed
    } else if (action === 'continue') {
      fn(true, 'continue'); // proceed without saving
    } else {
      fn(false, 'reject'); // cancel
    }

    modalCallback = null;
  }
}

// Autocomplete instances registry
const autocompleteInstances = new Map();

function createAutocomplete(inputEl, options = {}) {
  if (autocompleteInstances.has(inputEl)) {
    return autocompleteInstances.get(inputEl);
  }

  const ac = new TokenAutocomplete(inputEl, options);
  autocompleteInstances.set(inputEl, ac);
  return ac;
}

function destroyAutocomplete(inputEl) {
  const ac = autocompleteInstances.get(inputEl);
  if (ac) {
    ac.destroy();
    autocompleteInstances.delete(inputEl);
  }
}

// Form submission with unknown token check
function checkUnknownToken(input, proceedCallback) {
  const value = input.value.trim();

  // Skip check if value is empty
  if (!value) {
    proceedCallback(true);
    return;
  }

  // Skip check if not a valid hex address
  if (!isValidHexAddress(value)) {
    proceedCallback(true);
    return;
  }

  // Get autocomplete instance
  const ac = autocompleteInstances.get(input);

  // Skip modal if suppressModal is set (pre-filled values)
  // But only skip if it wasn't user-edited
  if (ac && ac.suppressModal && !ac.wasUserEdited) {
    proceedCallback(true);
    return;
  }

  const chainId = getChainId();

  // Check if token is in lists
  if (isTokenInLists(value, chainId)) {
    proceedCallback(true);
    return;
  }

  // Show modal
  const chain = getChain();
  showModal(value, chain, chainId, (shouldProceed, action) => {
    if (shouldProceed) {
      proceedCallback(true);
    } else {
      // Return focus to input
      input.focus();
      proceedCallback(false);
    }
  });
}

// Switch block field to date picker when "/" is typed
function setupDatePickerSwitch(blockId, hintId) {
  const input = document.getElementById(blockId);
  const hint = document.getElementById(hintId);

  function switchToDatePicker() {
    input.type = 'datetime-local';
    input.value = '';
    hint.innerHTML = 'Pick a date/time. <a href="#" style="color:#58a6ff;cursor:pointer;" id="' + blockId + '-clear">Clear</a> to switch back to block number.';
    document.getElementById(blockId + '-clear').addEventListener('click', function(e) {
      e.preventDefault();
      switchToBlock();
    });
  }

  function switchToBlock() {
    input.type = 'text';
    input.value = '';
    input.placeholder = 'defaults to latest';
    hint.textContent = 'Block number, or type "/" for a date picker. Defaults to latest block.';
  }

  input.addEventListener('input', function() {
    if (this.type === 'text' && this.value.includes('/')) {
      switchToDatePicker();
    }
  });

  input.addEventListener('change', function() {
    if (this.type === 'datetime-local' && !this.value) {
      switchToBlock();
    }
  });
}

setupDatePickerSwitch('quote-block', 'quote-block-hint');
setupDatePickerSwitch('batch-block', 'batch-block-hint');

// Quote Form
const quoteForm = document.getElementById('quote-form');
const quoteResult = document.getElementById('quote-result');
const quoteSubmit = document.getElementById('quote-submit');
const quoteFromInput = document.getElementById('quote-from');
const quoteToInput = document.getElementById('quote-to');
const quoteAmountInput = document.getElementById('quote-amount');
const quoteAmountWarning = document.getElementById('quote-amount-warning');

// Age update interval reference
let quoteAgeInterval = null;
let quoteBlockTimestamp = null;

function chainMismatchWarning(expected, actual) {
  if (actual && actual !== expected) {
    return '<div class="field" style="background:#553300;padding:8px;border-radius:4px;margin-bottom:12px;">' +
      '<div class="field-label" style="color:#ffaa00;">&#9888; Chain Mismatch</div>' +
      '<div class="field-value" style="color:#ffcc44;">Expected <b>' + escapeHtml(expected) + '</b> but backend reported <b>' + escapeHtml(actual) + '</b>. Check your nginx routing.</div>' +
    '</div>';
  }
  return '';
}

// Format relative age (e.g., "14s ago", "2m ago", "1h ago")
function formatRelativeAge(timestamp) {
  if (timestamp == null) return 'unknown';

  const now = Math.floor(Date.now() / 1000);
  const diff = now - timestamp;

  if (diff < 0) return 'just now';
  if (diff < 60) return diff + 's ago';
  if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
  return Math.floor(diff / 86400) + 'd ago';
}

// Format Unix timestamp to human-readable
function formatTimestamp(timestamp) {
  if (timestamp == null) return 'unknown';
  const d = new Date(timestamp * 1000);
  return d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
}

// Update the age display in the result
function updateQuoteAge() {
  const ageEl = document.getElementById('quote-age-value');
  if (ageEl && quoteBlockTimestamp != null) {
    ageEl.textContent = formatRelativeAge(quoteBlockTimestamp);
  }
}

// Stop the age update interval
function stopQuoteAgeUpdate() {
  if (quoteAgeInterval) {
    clearInterval(quoteAgeInterval);
    quoteAgeInterval = null;
  }
}

// Start the age update interval
function startQuoteAgeUpdate() {
  stopQuoteAgeUpdate();
  updateQuoteAge();
  quoteAgeInterval = setInterval(updateQuoteAge, 1000);
}

function showQuoteResult(data, chain, fromPriceData, toPriceData) {
  quoteResult.className = 'result show';
  const mismatch = chainMismatchWarning(chain, data.chain);

  // Store timestamp for age updates
  quoteBlockTimestamp = data.block_timestamp;

  // Get token info from autocomplete index
  const chainId = CHAIN_IDS[chain] || 1;
  const chainMap = tokenIndex.get(chainId);
  const fromToken = chainMap ? chainMap.get(data.from.toLowerCase()) : null;
  const toToken = chainMap ? chainMap.get(data.to.toLowerCase()) : null;

  const fromSymbol = fromToken ? escapeHtml(fromToken.symbol) : escapeHtml(data.from.slice(0, 10) + '...');
  const toSymbol = toToken ? escapeHtml(toToken.symbol) : escapeHtml(data.to.slice(0, 10) + '...');

  // Conversion rate display
  const conversionRate = data.output_amount / data.amount;
  const oneUnitOutput = conversionRate.toFixed(8);

  // USD prices from separate /price calls (or null if not fetched)
  const fromPriceDisplay = fromPriceData && fromPriceData.price != null
    ? '$' + escapeHtml(parseFloat(fromPriceData.price).toFixed(4))
    : '<span class="null">N/A</span>';
  const toPriceDisplay = toPriceData && toPriceData.price != null
    ? '$' + escapeHtml(parseFloat(toPriceData.price).toFixed(4))
    : '<span class="null">N/A</span>';

  const timestampDisplay = data.block_timestamp != null
    ? formatTimestamp(data.block_timestamp)
    : 'unknown';

  quoteResult.innerHTML =
    '<div class="result-header">Quote Result</div>' + mismatch +
    '<div class="field"><div class="field-label">Conversion</div><div class="field-value number">1 ' + fromSymbol + ' = ' + escapeHtml(oneUnitOutput) + ' ' + toSymbol + '</div></div>' +
    '<div class="field"><div class="field-label">Input</div><div class="field-value">' + escapeHtml(data.amount) + ' ' + fromSymbol + ' → ' + escapeHtml(parseFloat(data.output_amount).toFixed(6)) + ' ' + toSymbol + '</div></div>' +
    '<div class="field"><div class="field-label">From Token Price (USD)</div><div class="field-value number">' + fromPriceDisplay + '</div></div>' +
    '<div class="field"><div class="field-label">To Token Price (USD)</div><div class="field-value number">' + toPriceDisplay + '</div></div>' +
    '<div class="field"><div class="field-label">Chain</div><div class="field-value">' + escapeHtml(data.chain) + '</div></div>' +
    '<div class="field"><div class="field-label">Block</div><div class="field-value">' + escapeHtml(data.block) + '</div></div>' +
    '<div class="field"><div class="field-label">Block Timestamp</div><div class="field-value">' + escapeHtml(timestampDisplay) + '</div></div>' +
    '<div class="field"><div class="field-label">Age</div><div class="field-value" id="quote-age-value">' + escapeHtml(formatRelativeAge(data.block_timestamp)) + '</div></div>' +
    '<div class="field"><div class="field-label">Route</div><div class="field-value">' + escapeHtml(data.route) + '</div></div>';

  // Start live age updates
  startQuoteAgeUpdate();
}

// Amount warning handler
quoteAmountInput.addEventListener('input', function() {
  const value = this.value.trim();
  if (value && parseFloat(value) > 0) {
    quoteAmountWarning.style.display = 'block';
  } else {
    quoteAmountWarning.style.display = 'none';
  }
});

// Quote form submission
quoteForm.addEventListener('submit', async (e) => {
  e.preventDefault();

  // Stop any previous age updates
  stopQuoteAgeUpdate();

  // Check for unknown tokens before proceeding
  checkUnknownToken(quoteFromInput, async (proceedFrom) => {
    if (!proceedFrom) return;

    checkUnknownToken(quoteToInput, async (proceedTo) => {
      if (!proceedTo) return;

      const chain = getChain();
      const fromToken = quoteFromInput.value.trim();
      const toToken = quoteToInput.value.trim();
      const amount = quoteAmountInput.value.trim() || '1';
      const blockInput = document.getElementById('quote-block');
      const blockVal = blockInput.value.trim();
      const isDate = blockInput.type === 'datetime-local';

      if (!fromToken || !toToken) {
        showError(quoteResult, 'Both From and To token addresses are required');
        return;
      }

      quoteSubmit.disabled = true;
      quoteSubmit.textContent = 'Fetching...';
      showLoading(quoteResult, 'Fetching quote...');

      try {
        // Build quote request params
        const params = new URLSearchParams({
          from: fromToken,
          to: toToken,
          amount: amount
        });
        if (blockVal && isDate) {
          params.set('timestamp', new Date(blockVal).toISOString());
        } else if (blockVal) {
          params.set('block', blockVal);
        }

        // Fetch quote
        const quoteRes = await fetch('/' + chain + '/quote?' + params.toString());
        const quoteData = await quoteRes.json();

        if (quoteData.error) {
          showError(quoteResult, quoteData.error);
          return;
        }

        // Fetch USD prices for both tokens (parallel requests)
        let fromPriceData = null;
        let toPriceData = null;

        try {
          const fromPriceParams = new URLSearchParams({ token: fromToken });
          if (blockVal && isDate) {
            fromPriceParams.set('timestamp', new Date(blockVal).toISOString());
          } else if (blockVal) {
            fromPriceParams.set('block', blockVal);
          }
          const fromPriceRes = await fetch('/' + chain + '/price?' + fromPriceParams.toString());
          if (fromPriceRes.ok) {
            fromPriceData = await fromPriceRes.json();
          }
        } catch (err) {
          console.error('Failed to fetch from token price:', err);
        }

        try {
          const toPriceParams = new URLSearchParams({ token: toToken });
          if (blockVal && isDate) {
            toPriceParams.set('timestamp', new Date(blockVal).toISOString());
          } else if (blockVal) {
            toPriceParams.set('block', blockVal);
          }
          const toPriceRes = await fetch('/' + chain + '/price?' + toPriceParams.toString());
          if (toPriceRes.ok) {
            toPriceData = await toPriceRes.json();
          }
        } catch (err) {
          console.error('Failed to fetch to token price:', err);
        }

        // Save custom pair
        saveCustomPair(chain, fromToken, toToken);

        showQuoteResult(quoteData, chain, fromPriceData, toPriceData);
      } catch (err) {
        showError(quoteResult, 'Request failed: ' + err.message);
      } finally {
        quoteSubmit.disabled = false;
        quoteSubmit.textContent = 'Get Quote';
      }
    });
  });
});

// Batch Pricing Form — dynamic token rows
const batchForm = document.getElementById('batch-form');
const batchResult = document.getElementById('batch-result');
const batchSubmit = document.getElementById('batch-submit');
const batchTokenRows = document.getElementById('batch-token-rows');

function addTokenRow(token, amount) {
  const row = document.createElement('div');
  row.className = 'token-row';
  row.innerHTML = '<input type="text" class="token-addr" placeholder="0x..." value="' + escapeHtml(token || '') + '">' +
    '<input type="text" class="token-amt" placeholder="Amount (opt)" value="' + escapeHtml(amount || '') + '">' +
    '<button type="button" class="btn-remove" title="Remove">&times;</button>';

  const removeBtn = row.querySelector('.btn-remove');
  const tokenInput = row.querySelector('.token-addr');

  removeBtn.addEventListener('click', function() {
    // Destroy autocomplete before removing row
    destroyAutocomplete(tokenInput);
    row.remove();
  });

  batchTokenRows.appendChild(row);

  // Create autocomplete for this row
  createAutocomplete(tokenInput);
}

document.getElementById('batch-add-token').addEventListener('click', function() {
  addTokenRow('', '');
});

function showBatchResult(data) {
  batchResult.className = 'result show';
  if (!Array.isArray(data)) {
    showError(batchResult, data.error || 'Unexpected response format');
    return;
  }

  let rows = '';
  for (const item of data) {
    const priceDisplay = item.price !== null ? escapeHtml(item.price) : '<span class="null">null</span>';
    const cachedDisplay = item.cached ? 'yes' : 'no';
    const tsDisplay = item.block_timestamp !== null ? escapeHtml(item.block_timestamp) : '-';
    rows += '<tr>' +
      '<td>' + escapeHtml(item.token) + '</td>' +
      '<td>' + escapeHtml(item.block) + '</td>' +
      '<td>' + priceDisplay + '</td>' +
      '<td>' + tsDisplay + '</td>' +
      '<td>' + cachedDisplay + '</td>' +
    '</tr>';
  }

  batchResult.innerHTML =
    '<div class="result-header">Batch Results (' + escapeHtml(data.length) + ' tokens)</div>' +
    '<table>' +
      '<thead><tr><th>Token</th><th>Block</th><th>Price</th><th>Timestamp</th><th>Cached</th></tr></thead>' +
      '<tbody>' + rows + '</tbody>' +
    '</table>';
}

batchForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const chain = getChain();

  const rows = batchTokenRows.querySelectorAll('.token-row');
  const tokenList = [];
  const amountList = [];
  let hasAnyAmount = false;
  for (const row of rows) {
    const t = row.querySelector('.token-addr').value.trim();
    const a = row.querySelector('.token-amt').value.trim();
    if (t) {
      tokenList.push(t);
      amountList.push(a);
      if (a) hasAnyAmount = true;
    }
  }
  const tokens = tokenList.join(',');
  const amounts = hasAnyAmount ? amountList.join(',') : '';

  const batchBlockInput = document.getElementById('batch-block');
  const batchBlockVal = batchBlockInput.value.trim();
  const batchIsDate = batchBlockInput.type === 'datetime-local';
  if (!tokens) {
    showError(batchResult, 'Add at least one token address');
    return;
  }

  batchSubmit.disabled = true;
  batchSubmit.textContent = 'Fetching...';
  showLoading(batchResult, 'Fetching batch prices...');

  try {
    const params = new URLSearchParams({ tokens });
    if (batchBlockVal && batchIsDate) {
      params.set('timestamp', new Date(batchBlockVal).toISOString());
    } else if (batchBlockVal) {
      params.set('block', batchBlockVal);
    }
    if (amounts) params.set('amounts', amounts);

    const res = await fetch('/' + chain + '/prices?' + params.toString());
    const data = await res.json();

    if (data.error) {
      showError(batchResult, data.error);
    } else {
      showBatchResult(data);
    }
  } catch (err) {
    showError(batchResult, 'Request failed: ' + err.message);
  } finally {
    batchSubmit.disabled = false;
    batchSubmit.textContent = 'Get Prices';
  }
});

// Token Classification Form
const bucketForm = document.getElementById('bucket-form');
const bucketResult = document.getElementById('bucket-result');
const bucketSubmit = document.getElementById('bucket-submit');
const bucketTokenInput = document.getElementById('bucket-token');

function showBucketResult(data, chain) {
  bucketResult.className = 'result show';
  const mismatch = chainMismatchWarning(chain, data.chain);
  const bucketDisplay = data.bucket !== null ? escapeHtml(data.bucket) : '<span class="null">null</span>';
  bucketResult.innerHTML =
    '<div class="result-header">Classification Result</div>' + mismatch +
    '<div class="field"><div class="field-label">Token</div><div class="field-value"><span class="dim">' + escapeHtml(data.token) + '</span></div></div>' +
    '<div class="field"><div class="field-label">Chain</div><div class="field-value">' + escapeHtml(data.chain) + '</div></div>' +
    '<div class="field"><div class="field-label">Bucket</div><div class="field-value">' + bucketDisplay + '</div></div>';
}

bucketForm.addEventListener('submit', async (e) => {
  e.preventDefault();

  // Check for unknown token before proceeding
  checkUnknownToken(bucketTokenInput, async (proceed) => {
    if (!proceed) return;

    const chain = getChain();
    const token = document.getElementById('bucket-token').value.trim();

    if (!token) {
      showError(bucketResult, 'Token address is required');
      return;
    }

    bucketSubmit.disabled = true;
    bucketSubmit.textContent = 'Checking...';
    showLoading(bucketResult, 'Classifying token (this may take 10-30s)...');

    try {
      const res = await fetch('/' + chain + '/check_bucket?token=' + encodeURIComponent(token));
      const data = await res.json();

      if (data.error) {
        showError(bucketResult, data.error);
      } else {
        showBucketResult(data, chain);
      }
    } catch (err) {
      showError(bucketResult, 'Request failed: ' + err.message);
    } finally {
      bucketSubmit.disabled = false;
      bucketSubmit.textContent = 'Check Bucket';
    }
  });
});

// Chain selector change handler
document.getElementById('chain').addEventListener('change', () => {
  const chain = getChain();

  // Update From/To to chain's effective pair (custom if set, else factory default)
  const pair = getEffectivePair(chain);
  quoteFromInput.value = pair.from;
  quoteToInput.value = pair.to;

  // Reset suppressModal flags for the autocomplete instances
  const fromAc = autocompleteInstances.get(quoteFromInput);
  const toAc = autocompleteInstances.get(quoteToInput);
  if (fromAc) {
    fromAc.suppressModal = true;
    fromAc.wasUserEdited = false;
  }
  if (toAc) {
    toAc.suppressModal = true;
    toAc.wasUserEdited = false;
  }

  // Re-search all open autocompletes
  for (const [input, ac] of autocompleteInstances) {
    if (ac.isOpen) {
      ac.search();
    }
  }

  // Re-render tokenlist panel to update token counts
  renderTokenlistPanel();
});

// Initialize autocomplete on token inputs
function initAutocompletes() {
  // Quote form token inputs
  createAutocomplete(quoteFromInput, { suppressModal: true });
  createAutocomplete(quoteToInput, { suppressModal: true });

  // Bucket token input
  createAutocomplete(bucketTokenInput);

  // Start with one empty batch row (will get autocomplete in addTokenRow)
  addTokenRow('', '');
}

// Set default token pair on load
function setDefaultPair() {
  const chain = getChain();
  const pair = getEffectivePair(chain);
  quoteFromInput.value = pair.from;
  quoteToInput.value = pair.to;

  // Mark as suppressModal so the unknown token modal doesn't appear
  const fromAc = autocompleteInstances.get(quoteFromInput);
  const toAc = autocompleteInstances.get(quoteToInput);
  if (fromAc) {
    fromAc.suppressModal = true;
    fromAc.wasUserEdited = false;
  }
  if (toAc) {
    toAc.suppressModal = true;
    toAc.wasUserEdited = false;
  }
}

// Tokenlist Management Panel
function countTokensForChain(list, chainId) {
  if (!list.tokens) return 0;
  return list.tokens.filter(t => t.chainId === chainId).length;
}

function countAllEnabledTokens() {
  let total = 0;
  const chainId = getChainId();
  for (const list of tokenlists) {
    if (list.enabled) {
      total += countTokensForChain(list, chainId);
    }
  }
  return total;
}

function renderTokenlistSummary() {
  // Update the gear badge
  const badgeEl = document.getElementById('gear-badge');
  if (!badgeEl) return;

  const enabledLists = tokenlists.filter(l => l.enabled).length;
  const totalTokens = countAllEnabledTokens();

  if (enabledLists > 0) {
    badgeEl.textContent = enabledLists;
    badgeEl.style.display = 'flex';
  } else {
    badgeEl.style.display = 'none';
  }
}

function renderTokenlistPanel() {
  const listsEl = document.getElementById('tokenlist-lists');
  if (!listsEl) return;

  listsEl.innerHTML = '';

  for (let i = 0; i < tokenlists.length; i++) {
    const list = tokenlists[i];
    const chainId = getChainId();
    const tokenCount = countTokensForChain(list, chainId);

    const itemEl = document.createElement('div');
    itemEl.className = 'tokenlist-item' + (list.enabled ? '' : ' disabled');

    // Toggle switch
    const toggleHtml =
      '<div class="tokenlist-toggle ' + (list.enabled ? 'enabled' : '') + '" data-index="' + i + '">' +
        '<div class="tokenlist-toggle-knob"></div>' +
      '</div>';

    // Delete button (disabled for default list)
    const deleteDisabled = list.isDefault ? ' disabled title="Cannot delete default list"' : '';
    const deleteHtml = '<button type="button" class="tokenlist-delete" data-index="' + i + '"' + deleteDisabled + '>Delete</button>';

    itemEl.innerHTML =
      '<div class="tokenlist-item-info">' +
        '<div class="tokenlist-item-name">' + escapeHtml(list.name) + '</div>' +
        '<div class="tokenlist-item-count">' + tokenCount + ' tokens on ' + getChain() + '</div>' +
      '</div>' +
      '<div class="tokenlist-item-actions">' +
        toggleHtml +
        deleteHtml +
      '</div>';

    listsEl.appendChild(itemEl);
  }

  // Attach event listeners
  listsEl.querySelectorAll('.tokenlist-toggle').forEach(toggle => {
    toggle.addEventListener('click', function() {
      const index = parseInt(this.dataset.index, 10);
      toggleTokenlist(index);
    });
  });

  listsEl.querySelectorAll('.tokenlist-delete').forEach(btn => {
    btn.addEventListener('click', function() {
      const index = parseInt(this.dataset.index, 10);
      deleteTokenlist(index);
    });
  });

  renderTokenlistSummary();
}

function toggleTokenlist(index) {
  if (index < 0 || index >= tokenlists.length) return;

  const list = tokenlists[index];
  list.enabled = !list.enabled;

  // Save state
  if (list.isLocal) {
    saveLocalTokens();
  } else if (!list.isDefault) {
    saveUserTokenlists();
  }
  saveTokenlistStates();

  // Rebuild token index
  rebuildTokenIndex();

  // Re-render panel
  renderTokenlistPanel();
}

function deleteTokenlist(index) {
  if (index < 0 || index >= tokenlists.length) return;

  const list = tokenlists[index];
  if (list.isDefault) return; // Cannot delete default

  // Remove from array
  tokenlists.splice(index, 1);

  // Save to localStorage
  saveUserTokenlists();
  saveTokenlistStates();

  // Rebuild token index
  rebuildTokenIndex();

  // Re-render panel
  renderTokenlistPanel();
}

function showTokenlistError(msg) {
  const errorEl = document.getElementById('tokenlist-error');
  if (errorEl) {
    errorEl.textContent = msg;
    // Clear after 5 seconds
    setTimeout(() => {
      if (errorEl.textContent === msg) {
        errorEl.textContent = '';
      }
    }, 5000);
  }
}

function clearTokenlistError() {
  const errorEl = document.getElementById('tokenlist-error');
  if (errorEl) {
    errorEl.textContent = '';
  }
}

async function addTokenlistByUrl(url) {
  clearTokenlistError();

  // Validate URL scheme
  if (!url.startsWith('https://')) {
    showTokenlistError('Only https:// URLs are allowed');
    return false;
  }

  // Reject dangerous schemes
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'https:') {
      showTokenlistError('Only https:// URLs are allowed');
      return false;
    }
  } catch (e) {
    showTokenlistError('Invalid URL format');
    return false;
  }

  const addBtn = document.getElementById('tokenlist-add-url');
  const urlInput = document.getElementById('tokenlist-url-input');

  // Show loading state
  addBtn.disabled = true;
  addBtn.innerHTML = '<span class="tokenlist-loading"></span>Loading...';

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timeoutId);

    if (!res.ok) {
      showTokenlistError('Failed to fetch: HTTP ' + res.status);
      return false;
    }

    const data = await res.json();

    // Validate tokenlist structure
    if (!data.name || !Array.isArray(data.tokens)) {
      showTokenlistError('Invalid tokenlist: must have name and tokens array');
      return false;
    }

    // Check for duplicate
    const exists = tokenlists.some(l =>
      l.url === url || (l.name === data.name && !l.isDefault && !l.isLocal)
    );
    if (exists) {
      showTokenlistError('Tokenlist already added');
      return false;
    }

    // Add the list
    data.url = url;
    data.enabled = true;
    data.isDefault = false;
    data.isLocal = false;
    tokenlists.push(data);

    // Save to localStorage
    saveUserTokenlists();
    saveTokenlistStates();

    // Rebuild token index
    rebuildTokenIndex();

    // Re-render panel
    renderTokenlistPanel();

    // Clear input
    urlInput.value = '';

    return true;
  } catch (e) {
    if (e.name === 'AbortError') {
      showTokenlistError('Request timed out (10s)');
    } else {
      showTokenlistError('Failed to fetch: ' + e.message);
    }
    return false;
  } finally {
    addBtn.disabled = false;
    addBtn.textContent = 'Add';
  }
}

function importTokenlistFile(file) {
  clearTokenlistError();

  const reader = new FileReader();
  reader.onload = function(e) {
    try {
      const data = JSON.parse(e.target.result);

      // Validate tokenlist structure
      if (!data.name || !Array.isArray(data.tokens)) {
        showTokenlistError('Invalid tokenlist: must have name and tokens array');
        return;
      }

      // Check for duplicate
      const exists = tokenlists.some(l =>
        l.name === data.name && !l.isDefault && !l.isLocal
      );
      if (exists) {
        showTokenlistError('Tokenlist with this name already exists');
        return;
      }

      // Add the list
      data.enabled = true;
      data.isDefault = false;
      data.isLocal = false;
      tokenlists.push(data);

      // Save to localStorage
      saveUserTokenlists();
      saveTokenlistStates();

      // Rebuild token index
      rebuildTokenIndex();

      // Re-render panel
      renderTokenlistPanel();
    } catch (err) {
      showTokenlistError('Invalid JSON file: ' + err.message);
    }
  };
  reader.readAsText(file);
}

function exportLocalTokenlist() {
  const localList = tokenlists.find(l => l.isLocal);

  if (!localList || !localList.tokens || localList.tokens.length === 0) {
    showTokenlistError('No local tokens to export');
    return;
  }

  const exportData = {
    name: 'Local Tokens',
    version: { major: 1, minor: 0, patch: 0 },
    timestamp: new Date().toISOString(),
    tokens: localList.tokens
  };

  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = url;
  a.download = 'local-tokens.json';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Tokenlist Management Modal
function openTokenlistModal() {
  const modal = document.getElementById('tokenlist-modal');
  if (modal) {
    modal.classList.add('open');
    document.body.style.overflow = 'hidden'; // Prevent background scroll
    renderTokenlistPanel();
  }
}

function closeTokenlistModal() {
  const modal = document.getElementById('tokenlist-modal');
  if (modal) {
    modal.classList.remove('open');
    document.body.style.overflow = ''; // Restore scroll
  }
}

function setupTokenlistModal() {
  const gearBtn = document.getElementById('tokenlist-gear-btn');
  const modal = document.getElementById('tokenlist-modal');
  const backdrop = document.getElementById('tokenlist-modal-backdrop');
  const closeBtn = document.getElementById('tokenlist-modal-close');
  const addBtn = document.getElementById('tokenlist-add-url');
  const urlInput = document.getElementById('tokenlist-url-input');
  const fileInput = document.getElementById('tokenlist-file-input');
  const importBtn = document.getElementById('tokenlist-import-btn');
  const exportBtn = document.getElementById('tokenlist-export-btn');

  // Gear button opens modal
  if (gearBtn) {
    gearBtn.addEventListener('click', openTokenlistModal);
  }

  // Close button closes modal
  if (closeBtn) {
    closeBtn.addEventListener('click', closeTokenlistModal);
  }

  // Backdrop click closes modal
  if (backdrop) {
    backdrop.addEventListener('click', closeTokenlistModal);
  }

  // Escape key closes modal
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && modal && modal.classList.contains('open')) {
      closeTokenlistModal();
    }
  });

  // Add by URL
  if (addBtn && urlInput) {
    addBtn.addEventListener('click', async function() {
      const url = urlInput.value.trim();
      if (url) {
        await addTokenlistByUrl(url);
      }
    });

    urlInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        const url = urlInput.value.trim();
        if (url) {
          addTokenlistByUrl(url);
        }
      }
    });
  }

  // Import file
  if (fileInput && importBtn) {
    importBtn.addEventListener('click', function() {
      fileInput.click();
    });

    fileInput.addEventListener('change', function() {
      if (fileInput.files.length > 0) {
        importTokenlistFile(fileInput.files[0]);
        fileInput.value = ''; // Reset for re-select
      }
    });
  }

  // Export local
  if (exportBtn) {
    exportBtn.addEventListener('click', exportLocalTokenlist);
  }

  // Initial render of summary
  renderTokenlistSummary();
}

loadTokenlists().then(() => {
  initAutocompletes();
  setDefaultPair();
  setupTokenlistModal();
});

// Load URL params to restore form state
const params = new URLSearchParams(window.location.search);
if (params.get('chain')) document.getElementById('chain').value = params.get('chain');
if (params.get('from') || params.get('token')) {
  const fromToken = params.get('from') || params.get('token');
  quoteFromInput.value = fromToken;
  const ac = autocompleteInstances.get(quoteFromInput);
  if (ac) {
    ac.suppressModal = true;
    ac.wasUserEdited = false;
  }
}
if (params.get('to') || params.get('to_token')) {
  const toToken = params.get('to') || params.get('to_token');
  quoteToInput.value = toToken;
  const ac = autocompleteInstances.get(quoteToInput);
  if (ac) {
    ac.suppressModal = true;
    ac.wasUserEdited = false;
  }
}
if (params.get('block')) document.getElementById('quote-block').value = params.get('block');
if (params.get('timestamp')) {
  const quoteBlockEl = document.getElementById('quote-block');
  quoteBlockEl.type = 'datetime-local';
  const d = new Date(params.get('timestamp'));
  if (!isNaN(d)) quoteBlockEl.value = d.toISOString().slice(0, 16);
  const quoteHint = document.getElementById('quote-block-hint');
  quoteHint.innerHTML = 'Pick a date/time. <a href="#" style="color:#58a6ff;cursor:pointer;" id="quote-block-clear-restore">Clear</a> to switch back to block number.';
  document.getElementById('quote-block-clear-restore').addEventListener('click', function(e) {
    e.preventDefault();
    quoteBlockEl.type = 'text';
    quoteBlockEl.value = '';
    quoteBlockEl.placeholder = 'defaults to latest';
    quoteHint.textContent = 'Block number, or type "/" for a date picker. Defaults to latest block.';
  });
}
if (params.get('amount')) quoteAmountInput.value = params.get('amount');
if (params.get('tokens')) {
  const savedTokens = params.get('tokens').split(',');
  const savedAmounts = params.get('amounts') ? params.get('amounts').split(',') : [];
  batchTokenRows.innerHTML = '';
  savedTokens.forEach(function(t, i) {
    addTokenRow(t.trim(), savedAmounts[i] ? savedAmounts[i].trim() : '');
  });
}
if (params.get('bucket_token')) {
  bucketTokenInput.value = params.get('bucket_token');
  // Mark as suppressModal for URL param
  const ac = autocompleteInstances.get(bucketTokenInput);
  if (ac) {
    ac.suppressModal = true;
    ac.wasUserEdited = false;
  }
}
