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
  const res = await fetch(`${API}/api/people`);
  const data = await res.json();
  allPeople = data.people || [];
  countBadge.textContent = `${allPeople.length} people`;
  renderGrid(allPeople);
}

function renderGrid(people) {
  if (!people.length) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <div class="emoji">🕵️</div>
        <p>No people tracked yet.</p>
        <button class="btn btn-primary" onclick="openModal()">+ Add First Person</button>
      </div>`;
    return;
  }

  grid.innerHTML = people.map(p => {
    const tags = p.tag
      ? p.tag.split(',').map(t => `<span class="tag">${t.trim()}</span>`).join('')
      : '';
    const avatar = p.profile_pic
      ? `<img class="person-avatar" src="${p.profile_pic}" alt="${p.name}" onerror="this.style.display='none'">`
      : `<div class="avatar-placeholder">👤</div>`;
    const handle = p.insta ? `<div class="person-handle">@${p.insta}</div>` : '';
    const date   = p.added_at ? `<div class="person-date">${fmtDate(p.added_at)}</div>` : '';

    return `
      <a class="person-card" href="/person/${p.id}">
        ${avatar}
        <div class="person-name">${p.name}</div>
        ${handle}
        <div class="person-tags">${tags}</div>
        ${date}
      </a>`;
  }).join('');
}

// Search
searchInput.addEventListener('input', () => {
  const q = searchInput.value.toLowerCase();
  renderGrid(allPeople.filter(p =>
    p.name?.toLowerCase().includes(q) ||
    p.insta?.toLowerCase().includes(q) ||
    p.tag?.toLowerCase().includes(q)
  ));
});

// Modal
function openModal() { modal.classList.add('open'); addForm.reset(); }
function closeModal() { modal.classList.remove('open'); }
addBtn.addEventListener('click', openModal);
modalClose.addEventListener('click', closeModal);
modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });

// Submit — name only, then redirect to person page
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
      // Redirect straight to person page to start adding info
      setTimeout(() => location.href = `/person/${data.id}`, 400);
    } else {
      showToast('Error creating person', 'error');
    }
  } catch {
    showToast('Network error', 'error');
  } finally {
    btn.disabled = false; btn.textContent = 'Create →';
  }
});

function fmtDate(iso) {
  try {
    return new Date(iso).toLocaleDateString('en-IN', {
      day: 'numeric', month: 'short', year: 'numeric'
    });
  } catch { return iso; }
}

loadPeople();