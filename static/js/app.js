// Utility functions
function getChain() {
  return document.getElementById('chain').value;
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

setupDatePickerSwitch('price-block', 'price-block-hint');
setupDatePickerSwitch('batch-block', 'batch-block-hint');

// Single Price Form
const priceForm = document.getElementById('price-form');
const priceResult = document.getElementById('price-result');
const priceSubmit = document.getElementById('price-submit');

function chainMismatchWarning(expected, actual) {
  if (actual && actual !== expected) {
    return `<div class="field" style="background:#553300;padding:8px;border-radius:4px;margin-bottom:12px;">
      <div class="field-label" style="color:#ffaa00;">&#9888; Chain Mismatch</div>
      <div class="field-value" style="color:#ffcc44;">Expected <b>${escapeHtml(expected)}</b> but backend reported <b>${escapeHtml(actual)}</b>. Check your nginx routing.</div>
    </div>`;
  }
  return '';
}

function showPriceResult(data, chain) {
  priceResult.className = 'result show';
  const mismatch = chainMismatchWarning(chain, data.chain);
  const timestampField = data.block_timestamp != null ? `
    <div class="field">
      <div class="field-label">Block Timestamp</div>
      <div class="field-value">${escapeHtml(data.block_timestamp)}</div>
    </div>` : '';
  const amountField = data.amount != null ? `
    <div class="field">
      <div class="field-label">Amount</div>
      <div class="field-value">${escapeHtml(data.amount)}</div>
    </div>` : '';
  priceResult.innerHTML = `
    <div class="result-header">Price Result</div>${mismatch}
    <div class="field">
      <div class="field-label">Chain</div>
      <div class="field-value">${escapeHtml(data.chain)}</div>
    </div>
    <div class="field">
      <div class="field-label">Token</div>
      <div class="field-value"><span class="dim">${escapeHtml(data.token)}</span></div>
    </div>
    <div class="field">
      <div class="field-label">Block</div>
      <div class="field-value">${escapeHtml(data.block)}</div>
    </div>${timestampField}${amountField}
    <div class="field">
      <div class="field-label">Price (USD per token)</div>
      <div class="field-value number">${escapeHtml(data.price)}</div>
    </div>
    <div class="field">
      <div class="field-label">Cached</div>
      <div class="field-value">${data.cached ? 'yes' : 'no'}</div>
    </div>
  `;
}

priceForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const chain = getChain();
  const token = document.getElementById('price-token').value.trim();
  const blockInput = document.getElementById('price-block');
  const blockVal = blockInput.value.trim();
  const isDate = blockInput.type === 'datetime-local';
  const amount = document.getElementById('price-amount').value.trim();
  const ignorePools = document.getElementById('price-ignore-pools').value.trim();

  priceSubmit.disabled = true;
  priceSubmit.textContent = 'Fetching...';
  showLoading(priceResult, 'Fetching price...');

  try {
    const params = new URLSearchParams({ token });
    if (blockVal && isDate) {
      params.set('timestamp', new Date(blockVal).toISOString());
    } else if (blockVal) {
      params.set('block', blockVal);
    }
    if (amount) params.set('amount', amount);
    if (ignorePools) params.set('ignore_pools', ignorePools);

    const res = await fetch('/' + chain + '/price?' + params.toString());
    const data = await res.json();

    if (data.error) {
      showError(priceResult, data.error);
    } else {
      showPriceResult(data, chain);
    }
  } catch (err) {
    showError(priceResult, 'Request failed: ' + err.message);
  } finally {
    priceSubmit.disabled = false;
    priceSubmit.textContent = 'Get Price';
  }
});

// Batch Pricing Form — dynamic token rows
const batchForm = document.getElementById('batch-form');
const batchResult = document.getElementById('batch-result');
const batchSubmit = document.getElementById('batch-submit');
const batchTokenRows = document.getElementById('batch-token-rows');

function addTokenRow(token, amount) {
  const row = document.createElement('div');
  row.className = 'token-row';
  row.innerHTML = `<input type="text" class="token-addr" placeholder="0x..." value="${escapeHtml(token || '')}">` +
    `<input type="text" class="token-amt" placeholder="Amount (opt)" value="${escapeHtml(amount || '')}">` +
    `<button type="button" class="btn-remove" title="Remove">&times;</button>`;
  row.querySelector('.btn-remove').addEventListener('click', function() {
    row.remove();
  });
  batchTokenRows.appendChild(row);
}

document.getElementById('batch-add-token').addEventListener('click', function() {
  addTokenRow('', '');
});

// Start with one empty row
addTokenRow('', '');

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
    rows += `<tr>
      <td>${escapeHtml(item.token)}</td>
      <td>${escapeHtml(item.block)}</td>
      <td>${priceDisplay}</td>
      <td>${tsDisplay}</td>
      <td>${cachedDisplay}</td>
    </tr>`;
  }

  batchResult.innerHTML = `
    <div class="result-header">Batch Results (${escapeHtml(data.length)} tokens)</div>
    <table>
      <thead>
        <tr>
          <th>Token</th>
          <th>Block</th>
          <th>Price</th>
          <th>Timestamp</th>
          <th>Cached</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
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

function showBucketResult(data, chain) {
  bucketResult.className = 'result show';
  const mismatch = chainMismatchWarning(chain, data.chain);
  const bucketDisplay = data.bucket !== null ? escapeHtml(data.bucket) : '<span class="null">null</span>';
  bucketResult.innerHTML = `
    <div class="result-header">Classification Result</div>${mismatch}
    <div class="field">
      <div class="field-label">Token</div>
      <div class="field-value"><span class="dim">${escapeHtml(data.token)}</span></div>
    </div>
    <div class="field">
      <div class="field-label">Chain</div>
      <div class="field-value">${escapeHtml(data.chain)}</div>
    </div>
    <div class="field">
      <div class="field-label">Bucket</div>
      <div class="field-value">${bucketDisplay}</div>
    </div>
  `;
}

bucketForm.addEventListener('submit', async (e) => {
  e.preventDefault();
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

// Load URL params to restore form state
const params = new URLSearchParams(window.location.search);
if (params.get('chain')) document.getElementById('chain').value = params.get('chain');
if (params.get('token')) document.getElementById('price-token').value = params.get('token');
if (params.get('block')) document.getElementById('price-block').value = params.get('block');
if (params.get('timestamp')) {
  const priceBlockEl = document.getElementById('price-block');
  priceBlockEl.type = 'datetime-local';
  const d = new Date(params.get('timestamp'));
  if (!isNaN(d)) priceBlockEl.value = d.toISOString().slice(0, 16);
  const priceHint = document.getElementById('price-block-hint');
  priceHint.innerHTML = 'Pick a date/time. <a href="#" style="color:#58a6ff;cursor:pointer;" id="price-block-clear-restore">Clear</a> to switch back to block number.';
  document.getElementById('price-block-clear-restore').addEventListener('click', function(e) {
    e.preventDefault();
    priceBlockEl.type = 'text';
    priceBlockEl.value = '';
    priceBlockEl.placeholder = 'defaults to latest';
    priceHint.textContent = 'Block number, or type "/" for a date picker. Defaults to latest block.';
  });
}
if (params.get('amount')) document.getElementById('price-amount').value = params.get('amount');
if (params.get('ignore_pools')) document.getElementById('price-ignore-pools').value = params.get('ignore_pools');
if (params.get('tokens')) {
  const savedTokens = params.get('tokens').split(',');
  const savedAmounts = params.get('amounts') ? params.get('amounts').split(',') : [];
  batchTokenRows.innerHTML = '';
  savedTokens.forEach(function(t, i) {
    addTokenRow(t.trim(), savedAmounts[i] ? savedAmounts[i].trim() : '');
  });
}
if (params.get('bucket_token')) document.getElementById('bucket-token').value = params.get('bucket_token');

// No mutual exclusivity dispatch needed — block/date unified in one field
