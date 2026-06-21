/* ─── Perde frontend app.js ─────────────────────────────────────────────────
   Single JS file for all pages. Each page calls its init function.
   ────────────────────────────────────────────────────────────────────────── */

const API = ''; // same-origin — served by FastAPI

// ── Auth helpers ─────────────────────────────────────────────────────────────

function getToken() { return localStorage.getItem('perde_token'); }
function setToken(t) { localStorage.setItem('perde_token', t); }
function clearToken() { localStorage.removeItem('perde_token'); }

function getUser() {
  try { return JSON.parse(localStorage.getItem('perde_user')); } catch { return null; }
}
function setUser(u) { localStorage.setItem('perde_user', JSON.stringify(u)); }
function clearUser() { localStorage.removeItem('perde_user'); }

function requireAuth() {
  if (!getToken()) { window.location.href = '/'; return false; }
  return true;
}

// ── API fetch wrapper ─────────────────────────────────────────────────────────

async function api(method, path, body) {
  const headers = { 'Content-Type': 'application/json' };
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const resp = await fetch(API + path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (resp.status === 204) return null;

  let data;
  try { data = await resp.json(); } catch { data = {}; }

  if (!resp.ok) {
    const msg = data.detail || `Error ${resp.status}`;
    throw { status: resp.status, message: msg };
  }
  return data;
}

// ── Toast ─────────────────────────────────────────────────────────────────────

function showToast(msg, duration = 2000) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), duration);
}

// ── Relative time ─────────────────────────────────────────────────────────────

function relativeTime(dateStr) {
  const diff = (Date.now() - new Date(dateStr + (dateStr.endsWith('Z') ? '' : 'Z'))) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

// ── Avatar helpers ────────────────────────────────────────────────────────────

function initials(name) {
  return name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
}

function avatarEl(contributor, index) {
  const el = document.createElement('div');
  el.className = `avatar avatar-${Math.min(index, 2)}`;
  el.title = contributor.display_name;
  el.textContent = initials(contributor.display_name);
  return el;
}

// ── Modal helpers ─────────────────────────────────────────────────────────────

function openModal(id) {
  document.getElementById(id).classList.add('visible');
}

function closeModal(id) {
  document.getElementById(id).classList.remove('visible');
}

// ═════════════════════════════════════════════════════════════════════════════
// Auth page
// ═════════════════════════════════════════════════════════════════════════════

function initAuthPage() {
  // Already logged in?
  if (getToken()) { window.location.href = '/home.html'; return; }

  let isRegister = false;

  const loginForm = document.getElementById('login-form');
  const regForm = document.getElementById('register-form');
  const toggleLink = document.getElementById('toggle-link');
  const toggleText = document.getElementById('toggle-text');

  toggleLink.addEventListener('click', () => {
    isRegister = !isRegister;
    loginForm.style.display = isRegister ? 'none' : 'flex';
    regForm.style.display = isRegister ? 'flex' : 'none';
    document.getElementById('login-error').textContent = '';
    document.getElementById('reg-error').textContent = '';
    toggleText.innerHTML = isRegister
      ? `already have an account? <span id="toggle-link">sign in</span>`
      : `no account? <span id="toggle-link">register</span>`;
    // Re-bind after innerHTML swap
    document.getElementById('toggle-link').addEventListener('click', toggleLink.onclick);
  });

  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('login-btn');
    const errEl = document.getElementById('login-error');
    errEl.textContent = '';
    btn.disabled = true;
    btn.textContent = 'signing in…';
    try {
      const data = await api('POST', '/auth/login', {
        email: document.getElementById('login-email').value.trim(),
        password: document.getElementById('login-password').value,
      });
      setToken(data.token);
      setUser(data.user);
      window.location.href = '/home.html';
    } catch (err) {
      errEl.textContent = err.message;
      btn.disabled = false;
      btn.textContent = 'sign in';
    }
  });

  regForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('reg-btn');
    const errEl = document.getElementById('reg-error');
    errEl.textContent = '';
    btn.disabled = true;
    btn.textContent = 'creating…';
    try {
      const data = await api('POST', '/auth/register', {
        email: document.getElementById('reg-email').value.trim(),
        password: document.getElementById('reg-password').value,
        display_name: document.getElementById('reg-name').value.trim(),
      });
      setToken(data.token);
      setUser(data.user);
      window.location.href = '/home.html';
    } catch (err) {
      errEl.textContent = err.message;
      btn.disabled = false;
      btn.textContent = 'create account';
    }
  });
}

// ═════════════════════════════════════════════════════════════════════════════
// Home page
// ═════════════════════════════════════════════════════════════════════════════

function initHomePage() {
  if (!requireAuth()) return;

  const user = getUser();
  if (user) document.getElementById('nav-user-name').textContent = user.display_name;

  // Logout
  document.getElementById('logout-btn').addEventListener('click', () => {
    clearToken();
    clearUser();
    window.location.href = '/';
  });

  // New story modal
  const newStoryBtn = document.getElementById('new-story-btn');
  const cancelStoryBtn = document.getElementById('cancel-story-btn');
  const createStoryBtn = document.getElementById('create-story-btn');
  const titleInput = document.getElementById('new-story-title');
  const newStoryError = document.getElementById('new-story-error');

  newStoryBtn.addEventListener('click', () => {
    titleInput.value = '';
    newStoryError.textContent = '';
    openModal('new-story-modal');
    titleInput.focus();
  });

  cancelStoryBtn.addEventListener('click', () => closeModal('new-story-modal'));

  document.getElementById('new-story-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeModal('new-story-modal');
  });

  titleInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); createStoryBtn.click(); }
  });

  createStoryBtn.addEventListener('click', async () => {
    const title = titleInput.value.trim();
    if (!title) { newStoryError.textContent = 'Title is required'; return; }
    createStoryBtn.disabled = true;
    newStoryError.textContent = '';
    try {
      const story = await api('POST', '/stories', { title });
      closeModal('new-story-modal');
      window.location.href = `/editor.html?id=${story.id}`;
    } catch (err) {
      newStoryError.textContent = err.message;
      createStoryBtn.disabled = false;
    }
  });

  loadStories();
}

async function loadStories() {
  const listEl = document.getElementById('story-list');
  try {
    const stories = await api('GET', '/stories');
    if (!stories.length) {
      listEl.innerHTML = '<div class="empty-state">no stories yet. create one to get started.</div>';
      return;
    }
    listEl.innerHTML = '';
    stories.forEach(s => listEl.appendChild(storyCard(s)));
  } catch (err) {
    if (err.status === 401) { clearToken(); window.location.href = '/'; return; }
    listEl.innerHTML = `<div class="empty-state">${err.message}</div>`;
  }
}

function storyCard(story) {
  const card = document.createElement('div');
  card.className = 'card';
  card.setAttribute('role', 'button');
  card.setAttribute('tabindex', '0');
  card.id = `story-${story.id}`;

  const avatarRow = (story.contributors || [])
    .map((c, i) => `<div class="avatar avatar-${Math.min(i, 2)}" title="${c.display_name}">${initials(c.display_name)}</div>`)
    .join('');

  card.innerHTML = `
    <div class="story-card-title">${escHtml(story.title)}</div>
    <div class="story-card-meta">
      <div class="avatar-row">${avatarRow}</div>
      <span>${story.commit_count} ${story.commit_count === 1 ? 'commit' : 'commits'}</span>
      <span>${relativeTime(story.latest_commit_at)}</span>
    </div>
  `;

  const go = () => { window.location.href = `/editor.html?id=${story.id}`; };
  card.addEventListener('click', go);
  card.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') go(); });
  return card;
}

// ═════════════════════════════════════════════════════════════════════════════
// Editor page
// ═════════════════════════════════════════════════════════════════════════════

let editorState = {
  storyId: null,
  latestCommitId: null,
  contributors: [],
  hasConflict: false,
  lockAcquired: false,
  titleSaveTimer: null,
};

function initEditorPage() {
  if (!requireAuth()) return;

  const params = new URLSearchParams(location.search);
  const storyId = parseInt(params.get('id'));
  if (!storyId) { window.location.href = '/home.html'; return; }
  editorState.storyId = storyId;

  // Back button
  document.getElementById('back-btn').addEventListener('click', () => {
    releaseLock();
    window.location.href = '/home.html';
  });

  // Tab switching
  document.getElementById('tab-write').addEventListener('click', () => switchTab('write'));
  document.getElementById('tab-history').addEventListener('click', () => switchTab('history'));

  // Save button
  document.getElementById('save-btn').addEventListener('click', saveCommit);

  // Textarea — acquire lock on first keystroke
  const editor = document.getElementById('editor');
  editor.addEventListener('input', () => {
    if (!editorState.lockAcquired && !editorState.hasConflict) acquireLock();
    document.getElementById('save-btn').disabled = editorState.hasConflict;
  });

  // Inline title editing
  const titleInput = document.getElementById('story-title-input');
  titleInput.addEventListener('blur', () => saveTitle(titleInput.value));
  titleInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') titleInput.blur(); });

  // Add contributor modal
  const addBtn = document.getElementById('add-contributor-btn');
  const cancelBtn = document.getElementById('cancel-contributor-btn');
  const submitBtn = document.getElementById('add-contributor-submit-btn');
  const emailInput = document.getElementById('contributor-email');
  const errEl = document.getElementById('contributor-error');

  addBtn.addEventListener('click', () => {
    emailInput.value = '';
    errEl.textContent = '';
    openModal('add-contributor-modal');
    emailInput.focus();
  });
  cancelBtn.addEventListener('click', () => closeModal('add-contributor-modal'));
  document.getElementById('add-contributor-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeModal('add-contributor-modal');
  });
  emailInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') submitBtn.click(); });

  submitBtn.addEventListener('click', async () => {
    const email = emailInput.value.trim();
    if (!email) return;
    submitBtn.disabled = true;
    errEl.textContent = '';
    try {
      const newUser = await api('POST', `/stories/${storyId}/contributors`, { email });
      editorState.contributors.push({ ...newUser, index: editorState.contributors.length });
      renderContributors(editorState.contributors);
      closeModal('add-contributor-modal');
      showToast('contributor added');
    } catch (err) {
      errEl.textContent = err.message;
    } finally {
      submitBtn.disabled = false;
    }
  });

  // Release lock on page leave
  window.addEventListener('beforeunload', releaseLock);

  loadStory(storyId);
}

async function loadStory(storyId) {
  try {
    const story = await api('GET', `/stories/${storyId}`);
    document.title = `Perde — ${story.title}`;
    document.getElementById('story-title-input').value = story.title;
    document.getElementById('editor').value = story.latest_content || '';
    editorState.latestCommitId = story.latest_commit_id;
    editorState.contributors = story.contributors || [];
    renderContributors(editorState.contributors);
    document.getElementById('save-btn').disabled = false;
  } catch (err) {
    if (err.status === 401) { clearToken(); window.location.href = '/'; return; }
    if (err.status === 403) { window.location.href = '/home.html'; return; }
    showToast('Failed to load story');
  }
}

function renderContributors(contributors) {
  const row = document.getElementById('contributor-avatars');
  row.innerHTML = '';
  contributors.forEach((c, i) => row.appendChild(avatarEl(c, i)));
}

async function switchTab(tab) {
  const writePanel = document.getElementById('panel-write');
  const historyPanel = document.getElementById('panel-history');
  const writeTab = document.getElementById('tab-write');
  const historyTab = document.getElementById('tab-history');

  if (tab === 'write') {
    writePanel.style.display = '';
    historyPanel.style.display = 'none';
    writeTab.classList.add('active');
    historyTab.classList.remove('active');
  } else {
    writePanel.style.display = 'none';
    historyPanel.style.display = '';
    writeTab.classList.remove('active');
    historyTab.classList.add('active');
    await loadHistory();
  }
}

async function loadHistory() {
  const listEl = document.getElementById('history-list');
  const me = getUser();
  listEl.innerHTML = '<div class="empty-state">loading…</div>';
  try {
    const commits = await api('GET', `/stories/${editorState.storyId}/commits`);
    if (!commits.length) {
      listEl.innerHTML = '<div class="empty-state">no history yet</div>';
      return;
    }
    listEl.innerHTML = '';
    commits.forEach(c => {
      const isMe = me && c.author_id === me.id;
      const row = document.createElement('div');
      row.className = 'commit-row';
      row.innerHTML = `
        <div class="commit-dot ${isMe ? 'commit-dot-mine' : 'commit-dot-theirs'}"></div>
        <div class="commit-body">
          <div class="commit-author">${escHtml(c.author_name)}</div>
          <div class="commit-preview">${escHtml(c.preview)}</div>
        </div>
        <div class="commit-time">${relativeTime(c.created_at)}</div>
      `;
      listEl.appendChild(row);
    });
  } catch {
    listEl.innerHTML = '<div class="empty-state">failed to load history</div>';
  }
}

async function saveCommit() {
  if (editorState.hasConflict) return;
  const btn = document.getElementById('save-btn');
  btn.disabled = true;
  btn.textContent = 'saving…';

  const content = document.getElementById('editor').value;
  try {
    const commit = await api('POST', `/stories/${editorState.storyId}/commits`, {
      content,
      base_commit_id: editorState.latestCommitId,
    });
    editorState.latestCommitId = commit.id;
    editorState.lockAcquired = false;
    showToast('saved');
  } catch (err) {
    if (err.status === 409) {
      showConflict();
    } else {
      showToast('failed to save — try again');
    }
  } finally {
    btn.textContent = 'save';
    if (!editorState.hasConflict) btn.disabled = false;
  }
}

function showConflict() {
  editorState.hasConflict = true;
  document.getElementById('conflict-banner').classList.add('visible');
  document.getElementById('save-btn').disabled = true;
}

async function acquireLock() {
  try {
    await api('POST', `/stories/${editorState.storyId}/lock`);
    editorState.lockAcquired = true;
  } catch {
    // Non-critical; ignore
  }
}

function releaseLock() {
  if (!editorState.storyId || !editorState.lockAcquired) return;
  const token = getToken();
  if (!token) return;
  // keepalive:true works during beforeunload and sends auth headers (sendBeacon cannot)
  fetch(`${API}/stories/${editorState.storyId}/lock`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    keepalive: true,
  }).catch(() => {});
}

async function saveTitle(newTitle) {
  const t = newTitle.trim();
  if (!t) return;
  try {
    await api('PATCH', `/stories/${editorState.storyId}`, { title: t });
    document.title = `Perde — ${t}`;
  } catch {
    // Non-critical; silently ignore
  }
}

// ── Utility ───────────────────────────────────────────────────────────────────

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
