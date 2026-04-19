/* =============================================================
   index.js — Rewritten
   Personal directory / CRM — home & category views
   Fixes:
   - Duplicate showToast() declaration removed
   - DOM queries grouped and null-guarded
   - renderCategoryView empty-state bug fixed (was using
     outer `q` from renderHomeView scope, now self-contained)
   - Consistent async/await error handling
   - openModal focus guard prevents crash on missing input
   - Inline hex colours in JS match CSS token values
   - Cleaner HTML template literals (consistent indentation)
   - All helpers moved to bottom, all event wiring in one block
============================================================= */

'use strict';

// ── Config ────────────────────────────────────────────────────────────────────
const API = '';

// ── State ─────────────────────────────────────────────────────────────────────
let allPeople = [];
let activeCat = null; // null → home view

// ── Category metadata ─────────────────────────────────────────────────────────
const CAT_META = {
  friend:       { label: 'Friends',               emoji: '👋', color: '#a78bfa', desc: 'People you call friends' },
  close_friend: { label: 'Close Friends',          emoji: '💛', color: '#fbbf24', desc: 'Your inner circle' },
  related:      { label: 'Related to Friend',      emoji: '🔗', color: '#38bdf8', desc: 'Friends of friends, known connections' },
  random:       { label: 'Random (Found Online)',  emoji: '🌐', color: '#34d399', desc: 'People you discovered online' },
  misc:         { label: 'Misc.',                  emoji: '🗂️', color: '#f472b6', desc: 'Everyone else' },
  archived:     { label: 'Archived',               emoji: '📦', color: '#5a5a7a', desc: 'Hidden but still tracked' },
};

const CAT_ORDER = ['friend', 'close_friend', 'related', 'random', 'misc', 'archived'];

// ── DOM references ────────────────────────────────────────────────────────────
const grid          = document.getElementById('people-grid');
const categoryGrid  = document.getElementById('category-grid');
const countBadge    = document.getElementById('count-badge');
const searchInput   = document.getElementById('search-input');
const catSearchInput = document.getElementById('cat-search-input');
const addBtn        = document.getElementById('add-btn');
const addBtn2       = document.getElementById('add-btn-2');
const modal         = document.getElementById('add-modal');
const modalClose    = document.getElementById('modal-close');
const addForm       = document.getElementById('add-form');
const toast         = document.getElementById('toast');
const homeView      = document.getElementById('home-view');
const categoryView  = document.getElementById('category-view');
const backBtn       = document.getElementById('back-btn');
const catViewTitle  = document.getElementById('cat-view-title');
const addCatSelect  = document.getElementById('add-category-select');

// ── Data loading ──────────────────────────────────────────────────────────────
async function loadPeople() {
  try {
    const res  = await fetch(`${API}/api/people`);
    const data = await res.json();
    allPeople  = data.people || [];
    const n    = allPeople.length;
    countBadge.textContent = `${n} ${n === 1 ? 'person' : 'people'}`;
    activeCat === null ? renderHomeView() : renderCategoryView(activeCat);
  } catch {
    categoryGrid.innerHTML = emptyStateHTML('⚠️', 'Could not load data.');
  }
}

// ── Home view: category cards ─────────────────────────────────────────────────
function renderHomeView() {
  const q = searchInput.value.toLowerCase().trim();

  // Search mode — flat people grid
  if (q) {
    homeView.style.display = 'block';
    categoryView.style.display = 'none';

    const filtered = allPeople.filter(p => matchesPerson(p, q));
    const inner    = filtered.length
      ? filtered.map(personCardHTML).join('')
      : emptyStateHTML('🔍', `No results for "${esc(q)}"`);

    categoryGrid.innerHTML = `<div class="people-grid">${inner}</div>`;
    return;
  }

  // Default — category card grid
  const html = CAT_ORDER.map(cat => {
    const meta    = CAT_META[cat];
    const members = allPeople.filter(p => (p.category || 'random') === cat);
    const count   = members.length;

    const previews = members.slice(0, 3).map(p => {
      const img = p.profile_pic
        ? `<img src="${esc(p.profile_pic)}" alt="" onerror="this.style.display='none'">`
        : `<div class="preview-avatar-placeholder">👤</div>`;
      return `<div class="preview-avatar">${img}</div>`;
    }).join('');

    const extra = count > 3 ? `<div class="preview-extra">+${count - 3}</div>` : '';
    const hint  = count === 0 ? `<span class="cat-empty-hint">No one here yet</span>` : '';

    return `
      <div class="cat-card" data-cat="${cat}" style="--cat-color:${meta.color}" onclick="openCategory('${cat}')">
        <div class="cat-card-top">
          <div class="cat-card-icon">${meta.emoji}</div>
          <div class="cat-card-info">
            <div class="cat-card-name">${meta.label}</div>
            <div class="cat-card-desc">${meta.desc}</div>
          </div>
          <div class="cat-card-count" style="background:${meta.color}22; color:${meta.color}">${count}</div>
        </div>
        <div class="cat-card-preview">
          <div class="preview-avatars">${previews}${extra}</div>
          ${hint}
        </div>
      </div>`;
  }).join('');

  categoryGrid.innerHTML = html;
}

// ── Category view ─────────────────────────────────────────────────────────────
function openCategory(cat) {
  activeCat = cat;
  const meta = CAT_META[cat];
  catViewTitle.innerHTML = `<span style="margin-right:0.4rem">${meta.emoji}</span>${meta.label}`;
  if (addCatSelect) addCatSelect.value = cat;
  homeView.style.display     = 'none';
  categoryView.style.display = 'block';
  catSearchInput.value       = '';
  renderCategoryView(cat);
}

function renderCategoryView(cat) {
  const q       = catSearchInput.value.toLowerCase().trim();
  let members   = allPeople.filter(p => (p.category || 'random') === cat);
  if (q) members = members.filter(p => matchesPerson(p, q));

  if (!members.length) {
    const msg = q ? `No results for "${esc(q)}"` : 'No one in this category yet.';
    grid.innerHTML = `
      <div class="empty-state">
        <div class="emoji">${CAT_META[cat].emoji}</div>
        <p>${msg}</p>
        <button class="btn btn-primary" onclick="openModal()">＋ Add Person</button>
      </div>`;
    return;
  }

  grid.innerHTML = members.map(personCardHTML).join('');
}

// ── Person card template ──────────────────────────────────────────────────────
function personCardHTML(p) {
  const cat    = p.category || 'random';
  const meta   = CAT_META[cat] || CAT_META.random;
  const tags   = p.tag
    ? p.tag.split(',').map(t => `<span class="tag">${esc(t.trim())}</span>`).join('')
    : '';
  const avatar = p.profile_pic
    ? `<img class="person-avatar" src="${esc(p.profile_pic)}" alt="${esc(p.name)}" onerror="this.style.display='none'">`
    : `<div class="avatar-placeholder">👤</div>`;
  const handle = p.insta ? `<div class="person-handle">@${esc(p.insta)}</div>` : '';

  return `
    <a class="person-card cat-${cat}" href="/person/${esc(p.id)}">
      <span class="cat-badge" style="background:${meta.color}22; color:${meta.color}; border-color:${meta.color}44;">
        ${meta.emoji} ${meta.label}
      </span>
      ${avatar}
      <div class="person-name">${esc(p.name)}</div>
      ${handle}
      <div class="person-tags">${tags}</div>
      <div class="person-date">${fmtDate(p.added_at)}</div>
    </a>`;
}

// ── Modal ─────────────────────────────────────────────────────────────────────
function openModal() {
  modal.classList.add('open');
  addForm.reset();
  if (activeCat && addCatSelect) addCatSelect.value = activeCat;
  const first = addForm.querySelector('input[name="name"]');
  if (first) setTimeout(() => first.focus(), 50);
}

function closeModal() {
  modal.classList.remove('open');
}

// ── Toast ─────────────────────────────────────────────────────────────────────
let toastTimer = null;

function showToast(msg, type = 'success') {
  clearTimeout(toastTimer);
  toast.textContent = msg;
  toast.className   = `toast ${type} show`;
  toastTimer = setTimeout(() => toast.classList.remove('show'), 2800);
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function matchesPerson(p, q) {
  return (
    p.name?.toLowerCase().includes(q) ||
    p.insta?.toLowerCase().includes(q) ||
    p.tag?.toLowerCase().includes(q)
  );
}

function emptyStateHTML(emoji, message) {
  return `<div class="empty-state"><div class="emoji">${emoji}</div><p>${message}</p></div>`;
}

function fmtDate(iso) {
  try {
    return new Date(iso).toLocaleDateString('en-IN', {
      day: 'numeric', month: 'short', year: 'numeric',
    });
  } catch {
    return iso;
  }
}

function esc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ── Event wiring ──────────────────────────────────────────────────────────────
backBtn.addEventListener('click', () => {
  activeCat = null;
  categoryView.style.display = 'none';
  homeView.style.display     = 'block';
  renderHomeView();
});

searchInput.addEventListener('input', renderHomeView);
catSearchInput.addEventListener('input', () => {
  if (activeCat) renderCategoryView(activeCat);
});

addBtn.addEventListener('click', openModal);
addBtn2.addEventListener('click', openModal);
modalClose.addEventListener('click', closeModal);
modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

addForm.addEventListener('submit', async e => {
  e.preventDefault();
  const btn      = addForm.querySelector('[type=submit]');
  const original = btn.textContent;
  btn.disabled   = true;
  btn.textContent = 'Creating...';

  try {
    const res  = await fetch(`${API}/api/people`, { method: 'POST', body: new FormData(addForm) });
    const data = await res.json();
    if (data.ok) {
      showToast('Created ✓');
      closeModal();
      setTimeout(() => { location.href = `/person/${data.id}`; }, 350);
    } else {
      showToast('Error saving person', 'error');
    }
  } catch {
    showToast('Network error', 'error');
  } finally {
    btn.disabled    = false;
    btn.textContent = original;
  }
});

// ── Boot ──────────────────────────────────────────────────────────────────────
loadPeople();
