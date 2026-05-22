let selected = null;
let pollTimer = null;
const diffCache = {};

async function api(method, path, body) {
  const res = await fetch('/api' + path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function badge(status) {
  const spinner = status === 'PENDING' ? '<span class="spinner"></span>' : '';
  return `<span class="badge ${status}">${status}</span>${spinner}`;
}

function renderCards(records) {
  const cards = document.getElementById('cards');
  cards.innerHTML = records
    .map(r => `
      <div class="card ${r.id === selected ? 'active' : ''}" data-id="${r.id}">
        <div class="repo">${r.repository}</div>
        <div class="sha">${r.sha.slice(0, 7)}</div>
        ${badge(r.status)}
      </div>`)
    .join('');
  cards.querySelectorAll('.card').forEach(el =>
    el.addEventListener('click', () => selectRecord(el.dataset.id))
  );
}

function renderDetail(r) {
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
  loadDiff(r.id);
}

function renderDiff(container, diffStr) {
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

async function loadDiff(id) {
  const container = document.getElementById('diff-container');
  if (!container) return;
  if (diffCache[id]) { renderDiff(container, diffCache[id]); return; }
  container.innerHTML = '<p class="empty" style="margin-top:12px">Loading diff…</p>';
  try {
    const res = await fetch(`/api/analyses/${id}/diff`);
    if (!res.ok) throw new Error(await res.text());
    diffCache[id] = await res.text();
    renderDiff(container, diffCache[id]);
  } catch (e) {
    container.innerHTML = `<p class="empty" style="margin-top:12px;color:#f85149">Failed to load diff: ${e.message}</p>`;
  }
}

async function loadList() {
  const records = await api('GET', '/analyses');
  renderCards(records);
  if (selected && pollTimer) {
    const r = records.find(r => r.id === selected);
    if (r) renderDetail(r);
  }
  return records;
}

async function selectRecord(id) {
  selected = id;
  const r = await api('GET', `/analyses/${id}`);
  renderDetail(r);
  await loadList();
  poll(r);
}

function poll(r) {
  if (pollTimer) clearInterval(pollTimer);
  if (r.status !== 'PENDING') return;
  pollTimer = setInterval(async () => {
    const updated = await api('GET', `/analyses/${r.id}`);
    renderDetail(updated);
    await loadList();
    if (updated.status !== 'PENDING') {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }, 2000);
}

// --- tabs ---

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => { c.style.display = 'none'; });
    tab.classList.add('active');
    document.getElementById('tab-' + tab.dataset.tab).style.display = 'flex';
  });
});

// --- random ---

document.getElementById('trigger').addEventListener('click', async () => {
  const btn = document.getElementById('trigger');
  btn.disabled = true;
  btn.textContent = '…';
  try {
    const r = await api('POST', '/analyses');
    await loadList();
    await selectRecord(r.id);
  } catch (e) {
    alert('Failed: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = '▶ Run random analysis';
  }
});

// --- historical ---

async function loadCuratedRepos() {
  const repos = await api('GET', '/curated-repos');
  const select = document.getElementById('repo-select');
  const byLang = {};
  repos.forEach(({ repo, language }) => {
    if (!byLang[language]) byLang[language] = [];
    byLang[language].push(repo);
  });
  Object.entries(byLang).forEach(([lang, repoList]) => {
    const group = document.createElement('optgroup');
    group.label = lang;
    repoList.forEach(repo => {
      const opt = document.createElement('option');
      opt.value = repo;
      opt.textContent = repo;
      group.appendChild(opt);
    });
    select.appendChild(group);
  });
}

document.getElementById('repo-select').addEventListener('change', () => {
  if (document.getElementById('repo-select').value) {
    document.getElementById('repo-custom').value = '';
  }
});

document.getElementById('repo-custom').addEventListener('input', () => {
  if (document.getElementById('repo-custom').value.trim()) {
    document.getElementById('repo-select').value = '';
  }
});

document.getElementById('trigger-replay').addEventListener('click', async () => {
  const btn = document.getElementById('trigger-replay');
  const msg = document.getElementById('replay-msg');
  const repo = document.getElementById('repo-custom').value.trim()
    || document.getElementById('repo-select').value;
  if (!repo) { alert('Select or enter a repo first.'); return; }

  btn.disabled = true;
  btn.textContent = '…';
  msg.style.display = 'none';
  try {
    const r = await api('POST', '/replay', { repository: repo });
    await loadList();
    await selectRecord(r.id);
  } catch (e) {
    if (e.message.includes('409') || e.message.toLowerCase().includes('replayed')) {
      msg.textContent = `All commits for ${repo} have been replayed.`;
      msg.style.display = 'block';
    } else {
      alert('Failed: ' + e.message);
    }
  } finally {
    btn.disabled = false;
    btn.textContent = '▶ Next commit';
  }
});

loadCuratedRepos();
loadList();
setInterval(loadList, 5000);
