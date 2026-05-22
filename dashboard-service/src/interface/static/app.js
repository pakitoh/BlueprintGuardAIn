import { api } from './api.js';
import { renderCards, renderDetail, renderDiff } from './render.js';

let selected = null;
let pollTimer = null;
const diffCache = {};

async function loadDiff(id) {
  const container = document.getElementById('diff-container');
  if (!container) return;
  if (diffCache[id]) {
    renderDiff(container, diffCache[id]);
    return;
  }
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
  renderCards(records, selected, selectRecord);
  if (selected && pollTimer) {
    const r = records.find(r => r.id === selected);
    if (r) {
      renderDetail(r);
      loadDiff(r.id);
    }
  }
  return records;
}

async function selectRecord(id) {
  selected = id;
  const r = await api('GET', `/analyses/${id}`);
  renderDetail(r);
  loadDiff(r.id);
  await loadList();
  poll(r);
}

function poll(r) {
  if (pollTimer) clearInterval(pollTimer);
  if (r.status !== 'PENDING') return;
  pollTimer = setInterval(async () => {
    const updated = await api('GET', `/analyses/${r.id}`);
    renderDetail(updated);
    loadDiff(updated.id);
    await loadList();
    if (updated.status !== 'PENDING') {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }, 2000);
}

// Tabs
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => { c.style.display = 'none'; });
    tab.classList.add('active');
    document.getElementById('tab-' + tab.dataset.tab).style.display = 'flex';
  });
});

// Random analysis
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

// Historical replay
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

document.getElementById('repo-select').addEventListener('change', (e) => {
  if (e.target.value) {
    document.getElementById('repo-custom').value = '';
  }
});

document.getElementById('repo-custom').addEventListener('input', (e) => {
  if (e.target.value.trim()) {
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
