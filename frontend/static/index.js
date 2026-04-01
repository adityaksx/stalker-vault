const API = '';
let allPeople = [];

const grid        = document.getElementById('people-grid');
const countBadge  = document.getElementById('count-badge');
const searchInput = document.getElementById('search-input');
const addBtn      = document.getElementById('add-btn');
const modal       = document.getElementById('add-modal');
const modalClose  = document.getElementById('modal-close');
const addForm     = document.getElementById('add-form');
const toast       = document.getElementById('toast');


function showToast(msg, type = 'success') {
  toast.textContent = msg;
  toast.className = `toast ${type} show`;
  setTimeout(() => toast.classList.remove('show'), 2800);
}

async function loadPeople() {
  grid.innerHTML = `<div class="loader"><div class="spinner"></div> Loading...</div>`;
  try {
    const res  = await fetch(`${API}/api/people`);
    const data = await res.json();
    allPeople  = data.people || [];
    countBadge.textContent = `${allPeople.length} ${allPeople.length === 1 ? 'person' : 'people'}`;
    renderGrid(allPeople);
  } catch {
    grid.innerHTML = `<div class="empty-state"><div class="emoji">⚠️</div><p>Could not load data.</p></div>`;
  }
}

function renderGrid(people) {
  if (!people.length) {
    grid.innerHTML = `
      <div class="empty-state">
        <div class="emoji">🕵️</div>
        <p>No one tracked yet.</p>
        <button class="btn btn-primary" onclick="openModal()">＋ Add First Person</button>
      </div>`;
    return;
  }
  grid.innerHTML = people.map(p => {
    const tags = p.tag
      ? p.tag.split(',').map(t => `<span class="tag">${esc(t.trim())}</span>`).join('')
      : '';
    const avatar = p.profile_pic
      ? `<img class="person-avatar" src="${esc(p.profile_pic)}" alt="${esc(p.name)}" onerror="this.style.display='none'">`
      : `<div class="avatar-placeholder">👤</div>`;
    const handle = p.insta ? `<div class="person-handle">@${esc(p.insta)}</div>` : '';
    return `
      <a class="person-card" href="/person/${p.id}">
        ${avatar}
        <div class="person-name">${esc(p.name)}</div>
        ${handle}
        <div class="person-tags">${tags}</div>
        <div class="person-date">${fmtDate(p.added_at)}</div>
      </a>`;
  }).join('');
}

searchInput.addEventListener('input', () => {
  const q = searchInput.value.toLowerCase();
  renderGrid(allPeople.filter(p =>
    p.name?.toLowerCase().includes(q) ||
    p.insta?.toLowerCase().includes(q) ||
    p.tag?.toLowerCase().includes(q)
  ));
});

function openModal()  {
  modal.classList.add('open');
  addForm.reset();
  setTimeout(() => addForm.querySelector('input[name="name"]').focus(), 50);}

function closeModal() { modal.classList.remove('open'); }
addBtn.addEventListener('click', openModal);
modalClose.addEventListener('click', closeModal);
modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') document.getElementById('add-modal').classList.remove('open');
});

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