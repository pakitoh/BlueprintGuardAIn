export function badge(status) {
  const spinner = status === 'PENDING' ? '<span class="spinner"></span>' : '';
  return `<span class="badge ${status}">${status}</span>${spinner}`;
}

export function renderCards(records, selectedId, onSelect) {
  const cards = document.getElementById('cards');
  cards.innerHTML = records
    .map(r => `
      <div class="card ${r.id === selectedId ? 'active' : ''}" data-id="${r.id}">
        <div class="repo">${r.repository}</div>
        <div class="sha">${r.sha.slice(0, 7)}</div>
        ${badge(r.status)}
      </div>`)
    .join('');
  cards.querySelectorAll('.card').forEach(el =>
    el.addEventListener('click', () => onSelect(el.dataset.id))
  );
}

export function renderDetail(r) {
  const latency = r.completed_at
    ? ((new Date(r.completed_at) - new Date(r.created_at)) / 1000).toFixed(1) + 's'
    : '…';
  const findingsHtml = r.status === 'PENDING'
    ? `<p class="empty">Analysis in progress…</p>`
    : r.findings.length
      ? `<ul id="findings">${r.findings.map(f => `<li class="finding">${marked.parse(f)}</li>`).join('')}</ul>`
      : `<p class="empty">No findings.</p>`;

  document.getElementById('detail').innerHTML = `
    <h2>${r.repository} <span style="color:#8b949e">@ ${r.sha.slice(0, 7)}</span></h2>
    <div class="meta">
      ${badge(r.status)} &nbsp;
      triggered: ${new Date(r.created_at).toLocaleTimeString()} &nbsp;|&nbsp;
      duration: ${latency}
    </div>
    <div id="findings-container">${findingsHtml}</div>
    <div id="diff-container"></div>
    `;
}

export function renderDiff(container, diffStr) {
  if (!diffStr.trim()) {
    container.innerHTML = '<p class="empty" style="margin-top:12px">No diff available.</p>';
    return;
  }
  container.innerHTML = '';
  const diff2htmlUi = new Diff2HtmlUI(container, diffStr, {
    drawFileList: true,
    matching: 'lines',
    outputFormat: 'line-by-line',
    highlight: true,
    renderNothingWhenEmpty: false,
  });
  diff2htmlUi.draw();
}
