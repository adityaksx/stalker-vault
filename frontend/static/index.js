const API = '';
let allPeople = [];
let activeCat = null; // null = home view

// ── Category meta ─────────────────────────────────────────────────────────────
const CAT_META = {
  friend:       { label: 'Friends',                    emoji: '👋', color: '#a78bfa', desc: 'People you call friends' },
  close_friend: { label: 'Close Friends',              emoji: '💛', color: '#fbbf24', desc: 'Your inner circle' },
  related:      { label: 'Related to Friend',          emoji: '🔗', color: '#38bdf8', desc: 'Friends of friends, known connections' },
  random:       { label: 'Random (Found Online)',      emoji: '🌐', color: '#34d399', desc: 'People you discovered online' },
  misc:         { label: 'Misc.',                      emoji: '🗂️', color: '#f472b6', desc: 'Everyone else' },
  archived:     { label: 'Archived',                   emoji: '📦', color: '#5a5a7a', desc: 'Hidden but still tracked' },
};

const CAT_ORDER = ['friend', 'close_friend', 'related', 'random', 'misc', 'archived'];

const grid        = document.getElementById('people-grid');
const categoryGrid = document.getElementById('category-grid');
const countBadge  = document.getElementById('count-badge');
const searchInput = document.getElementById('search-input');
const catSearchInput = document.getElementById('cat-search-input');
const addBtn      = document.getElementById('add-btn');
const addBtn2     = document.getElementById('add-btn-2');
const modal       = document.getElementById('add-modal');
const modalClose  = document.getElementById('modal-close');
const addForm     = document.getElementById('add-form');
const toast       = document.getElementById('toast');
const homeView    = document.getElementById('home-view');
const categoryView = document.getElementById('category-view');
const backBtn     = document.getElementById('back-btn');
const catViewTitle = document.getElementById('cat-view-title');
const addCatSelect = document.getElementById('add-category-select');

// ── Toast ──────────────────────────────────────────────────────────────────────
function showToast(msg, type = 'success') {
  toast.textContent = msg;
  toast.className = `toast ${type} show`;
  setTimeout(() => toast.classList.remove('show'), 2800);
}

// ── Load ───────────────────────────────────────────────────────────────────────
async function loadPeople() {
  try {
    const res  = await fetch(`${API}/api/people`);
    const data = await res.json();
    allPeople  = data.people || [];
    countBadge.textContent = `${allPeople.length} ${allPeople.length === 1 ? 'person' : 'people'}`;
    if (activeCat === null) renderHomeView();
    else renderCategoryView(activeCat);
  } catch {
    categoryGrid.innerHTML = `<div class="empty-state"><div class="emoji">⚠️</div><p>Could not load data.</p></div>`;
  }
}

// ── HOME VIEW: 6 category cards ───────────────────────────────────────────────
function renderHomeView() {
  const q = searchInput.value.toLowerCase().trim();

  // If searching, show flat grid instead of category cards
  if (q) {
    homeView.style.display = 'block';
    categoryView.style.display = 'none';
    const filtered = allPeople.filter(p =>
      p.name?.toLowerCase().includes(q) ||
      p.insta?.toLowerCase().includes(q) ||
      p.tag?.toLowerCase().includes(q)
    );
    categoryGrid.innerHTML = '';
    const tempGrid = document.createElement('div');
    tempGrid.className = 'people-grid';
    tempGrid.innerHTML = filtered.length ? filtered.map(personCardHTML).join('') :
      `<div class="empty-state"><div class="emoji">🔍</div><p>No results for "${esc(q)}"</p></div>`;
    categoryGrid.appendChild(tempGrid);
    return;
  }

  // Build category cards
  const html = CAT_ORDER.map(cat => {
    const meta    = CAT_META[cat];
    const members = allPeople.filter(p => (p.category || 'random') === cat);
    const count   = members.length;

    // 3 preview people (blurred avatars)
    const previews = members.slice(0, 3).map(p => {
      const src = p.profile_pic
        ? `<img src="${esc(p.profile_pic)}" alt="" onerror="this.style.display='none'">`
        : `<div class="preview-avatar-placeholder">👤</div>`;
      return `<div class="preview-avatar">${src}</div>`;
    }).join('');

    // Remaining count bubble
    const extra = count > 3 ? `<div class="preview-extra">+${count - 3}</div>` : '';

    return `
      <div class="cat-card" data-cat="${cat}" onclick="openCategory('${cat}')">
        <div class="cat-card-top" style="--cat-color:${meta.color}">
          <div class="cat-card-icon">${meta.emoji}</div>
          <div class="cat-card-info">
            <div class="cat-card-name">${meta.label}</div>
            <div class="cat-card-desc">${meta.desc}</div>
          </div>
          <div class="cat-card-count" style="background:${meta.color}22; color:${meta.color}">${count}</div>
        </div>
        <div class="cat-card-preview">
          <div class="preview-avatars">${previews}${extra}</div>
          ${count === 0 ? '<span class="cat-empty-hint">No one here yet</span>' : ''}
        </div>
      </div>`;
  }).join('');

  categoryGrid.innerHTML = html;
}

// ── CATEGORY VIEW ─────────────────────────────────────────────────────────────
function openCategory(cat) {
  activeCat = cat;
  const meta = CAT_META[cat];
  catViewTitle.innerHTML = `<span style="margin-right:0.4rem">${meta.emoji}</span>${meta.label}`;
  // Pre-select category in add modal
  if (addCatSelect) addCatSelect.value = cat;
  homeView.style.display = 'none';
  categoryView.style.display = 'block';
  catSearchInput.value = '';
  renderCategoryView(cat);
}

function renderCategoryView(cat) {
  const q = catSearchInput.value.toLowerCase().trim();
  let members = allPeople.filter(p => (p.category || 'random') === cat);
  if (q) {
    members = members.filter(p =>
      p.name?.toLowerCase().includes(q) ||
      p.insta?.toLowerCase().includes(q) ||
      p.tag?.toLowerCase().includes(q)
    );
  }

  if (!members.length) {
    grid.innerHTML = `
      <div class="empty-state">
        <div class="emoji">${CAT_META[cat].emoji}</div>
        <p>${q ? `No results for "${esc(q)}"` : 'No one in this category yet.'}</p>
        <button class="btn btn-primary" onclick="openModal()">＋ Add Person</button>
      </div>`;
    return;
  }

  grid.innerHTML = members.map(personCardHTML).join('');
}

// ── Person card HTML (used in both views) ─────────────────────────────────────
function personCardHTML(p) {
  const cat  = p.category || 'random';
  const meta = CAT_META[cat] || CAT_META['random'];
  const tags = p.tag
    ? p.tag.split(',').map(t => `<span class="tag">${esc(t.trim())}</span>`).join('')
    : '';
  const avatar = p.profile_pic
    ? `<img class="person-avatar" src="${esc(p.profile_pic)}" alt="${esc(p.name)}" onerror="this.style.display='none'">`
    : `<div class="avatar-placeholder">👤</div>`;
  const handle = p.insta ? `<div class="person-handle">@${esc(p.insta)}</div>` : '';
  return `
    <a class="person-card cat-${cat}" href="/person/${p.id}">
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

// ── Back button ───────────────────────────────────────────────────────────────
backBtn.addEventListener('click', () => {
  activeCat = null;
  categoryView.style.display = 'none';
  homeView.style.display = 'block';
  renderHomeView();
});

// ── Search ────────────────────────────────────────────────────────────────────
searchInput.addEventListener('input', renderHomeView);
catSearchInput.addEventListener('input', () => {
  if (activeCat) renderCategoryView(activeCat);
});

// ── Modal ──────────────────────────────────────────────────────────────────────
function openModal() {
  modal.classList.add('open');
  addForm.reset();
  if (activeCat && addCatSelect) addCatSelect.value = activeCat;
  setTimeout(() => addForm.querySelector('input[name="name"]').focus(), 50);
}
function closeModal() { modal.classList.remove('open'); }

addBtn.addEventListener('click', openModal);
addBtn2.addEventListener('click', openModal);
modalClose.addEventListener('click', closeModal);
modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

addForm.addEventListener('submit', async e => {
  e.preventDefault();
  const btn = addForm.querySelector('[type=submit]');
  btn.disabled = true; btn.textContent = 'Creating...';
  const fd = new FormData(addForm);
  try {
    const res  = await fetch(`${API}/api/people`, { method: 'POST', body: fd });
    const data = await res.json();
    if (data.ok) {
      showToast('Created ✓');
      closeModal();
      setTimeout(() => location.href = `/person/${data.id}`, 350);
    } else { showToast('Error', 'error'); }
  } catch { showToast('Network error', 'error'); }
  finally { btn.disabled = false; btn.textContent = 'Create →'; }
});

// ── Helpers ────────────────────────────────────────────────────────────────────
function fmtDate(iso) {
  try {
    return new Date(iso).toLocaleDateString('en-IN', {
      day: 'numeric', month: 'short', year: 'numeric'
    });
  } catch { return iso; }
}

function esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

loadPeople();
