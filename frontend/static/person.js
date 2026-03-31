const API = '';
const pid = location.pathname.split('/').pop();

// ── Field type config ──
const FIELD_TYPES = {
  // Social
  instagram:  { label: '📸 Instagram',  group: 'Social',   fmt: v => `<a href="https://instagram.com/${v}" target="_blank">@${v} ↗</a>` },
  snapchat:   { label: '👻 Snapchat',   group: 'Social',   fmt: v => v },
  twitter:    { label: '𝕏 X / Twitter', group: 'Social',   fmt: v => `<a href="https://x.com/${v}" target="_blank">@${v} ↗</a>` },
  linkedin:   { label: '💼 LinkedIn',   group: 'Social',   fmt: v => `<a href="${v}" target="_blank">View ↗</a>` },
  pinterest:  { label: '📌 Pinterest',  group: 'Social',   fmt: v => `<a href="https://pinterest.com/${v}" target="_blank">${v} ↗</a>` },
  facebook:   { label: '📘 Facebook',   group: 'Social',   fmt: v => `<a href="${v}" target="_blank">View ↗</a>` },
  tiktok:     { label: '🎵 TikTok',     group: 'Social',   fmt: v => `<a href="https://tiktok.com/@${v}" target="_blank">@${v} ↗</a>` },
  youtube:    { label: '▶️ YouTube',    group: 'Social',   fmt: v => `<a href="${v}" target="_blank">Channel ↗</a>` },
  telegram:   { label: '✈️ Telegram',   group: 'Social',   fmt: v => v },
  discord:    { label: '🎮 Discord',    group: 'Social',   fmt: v => v },
  reddit:     { label: '🤖 Reddit',     group: 'Social',   fmt: v => `<a href="https://reddit.com/u/${v}" target="_blank">u/${v} ↗</a>` },
  threads:    { label: '🧵 Threads',    group: 'Social',   fmt: v => `<a href="https://threads.net/@${v}" target="_blank">@${v} ↗</a>` },
  bereal:     { label: '📷 BeReal',     group: 'Social',   fmt: v => v },
  // Contact
  phone:      { label: '📞 Phone',      group: 'Contact',  fmt: v => `<a href="tel:${v}">${v}</a>` },
  email:      { label: '📧 Email',      group: 'Contact',  fmt: v => `<a href="mailto:${v}">${v}</a>` },
  whatsapp:   { label: '💬 WhatsApp',   group: 'Contact',  fmt: v => v },
  // Identity
  nickname:   { label: '🏷 Nickname',   group: 'Identity', fmt: v => v },
  dob:        { label: '🎂 Date of Birth', group: 'Identity', fmt: v => v },
  gender:     { label: '⚧ Gender',      group: 'Identity', fmt: v => v },
  // Education & Work
  school:     { label: '🏫 School',     group: 'Education', fmt: v => v },
  college:    { label: '🎓 College',    group: 'Education', fmt: v => v },
  workplace:  { label: '🏢 Workplace',  group: 'Work',     fmt: v => v },
  jobtitle:   { label: '💼 Job Title',  group: 'Work',     fmt: v => v },
  github:     { label: '🐙 GitHub',     group: 'Work',     fmt: v => `<a href="https://github.com/${v}" target="_blank">${v} ↗</a>` },
  website:    { label: '🌐 Website',    group: 'Web',      fmt: v => `<a href="${v}" target="_blank">${v} ↗</a>` },
  // Location
  location:   { label: '📍 Location',   group: 'Location', fmt: v => v },
  address:    { label: '🏠 Address',    group: 'Location', fmt: v => v },
  // Misc
  note:       { label: '📝 Note',       group: 'Notes',    fmt: v => v },
  tag:        { label: '🔖 Tag',        group: 'Tags',     fmt: v => `<span class="tag">${v}</span>` },
  custom:     { label: '✏️ Custom',     group: 'Custom',   fmt: v => v },
};

const MEDIA_TYPES = {
  photo:      '🖼 Photo',
  screenshot: '📸 Screenshot',
  video:      '🎬 Video',
  repo_url:   '🐙 GitHub Repo URL',
  repo_zip:   '📦 Repo ZIP',
  other:      '📎 Other File',
};

let personData = null;

// ── Toast ──
function showToast(msg, type = 'success') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = `toast ${type} show`;
  setTimeout(() => t.classList.remove('show'), 2800);
}

// ── Format date ──
function fmtDt(iso) {
  try {
    return new Date(iso).toLocaleString('en-IN', {
      day: 'numeric', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  } catch { return iso; }
}

function escHtml(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Load ──
async function load() {
  const res = await fetch(`${API}/api/people/${pid}`);
  if (!res.ok) {
    document.querySelector('.page').innerHTML = `<a class="back-link" href="/">← Back</a><div class="empty-state"><div class="emoji">❓</div><p>Person not found.</p></div>`;
    return;
  }
  personData = await res.json();
  render();
}

function render() {
  renderHero();
  renderFields();
  renderMedia();
}

// ── Hero ──
function renderHero() {
  const d = personData;
  const pic = d.media?.find(m => m.type === 'profile_pic')
         || d.media?.find(m => m.type === 'photo');
  const avatar = pic
    ? `<img class="person-hero-avatar" src="${pic.path}" alt="${d.name}">`
    : `<div class="hero-placeholder">👤</div>`;

  const tags = d.fields?.filter(f => f.type === 'tag')
    .map(f => `<span class="tag">${escHtml(f.value)}</span>`).join('') || '';

  const insta = d.fields?.find(f => f.type === 'instagram');
  const handle = insta ? `<div class="handle">@${escHtml(insta.value)}</div>` : '';

  document.getElementById('hero-section').innerHTML = `
    <div class="person-hero">
      ${avatar}
      <div class="person-hero-info">
        <h1 id="person-name">${escHtml(d.name)}</h1>
        ${handle}
        <div class="tags">${tags}</div>
        <div class="hero-actions">
          <button class="btn btn-secondary btn-sm" onclick="editName()">✏️ Rename</button>
          <button class="btn btn-danger btn-sm" onclick="confirmDelete()">🗑 Delete</button>
        </div>
        <div class="added-date">Added ${fmtDt(d.added_at)}</div>
      </div>
    </div>`;
}

// ── Fields ──
function renderFields() {
  const fields = personData.fields || [];
  if (!fields.length) {
    document.getElementById('fields-section').innerHTML = `
      <div class="section-empty">No info added yet. Use the panel below to add.</div>`;
    return;
  }

  // Group by category
  const groups = {};
  fields.forEach(f => {
    const meta = FIELD_TYPES[f.type] || { label: f.type, group: 'Custom' };
    const g = meta.group;
    if (!groups[g]) groups[g] = [];
    groups[g].push({ ...f, meta });
  });

  const html = Object.entries(groups).map(([group, items]) => `
    <div class="info-section">
      <h2>${group}</h2>
      <div class="fields-grid">
        ${items.map(f => `
          <div class="field-card" data-fid="${f.id}">
            <div class="field-label">${f.meta.label}${f.label ? ` <span class="field-sublabel">(${escHtml(f.label)})</span>` : ''}</div>
            <div class="field-value">${f.meta.fmt ? f.meta.fmt(escHtml(f.value)) : escHtml(f.value)}</div>
            <div class="field-meta">
              <span class="field-time">⏱ ${fmtDt(f.added_at)}</span>
              <button class="field-del" onclick="deleteField(${f.id})" title="Delete">✕</button>
            </div>
          </div>`).join('')}
      </div>
    </div>`).join('');

  document.getElementById('fields-section').innerHTML = html;
}

// ── Media ──
function renderMedia() {
  const media = personData.media || [];
  if (!media.length) {
    document.getElementById('media-section').innerHTML = `
      <div class="section-empty">No media added yet.</div>`;
    return;
  }

  const photos = media.filter(m => m.type === 'photo' || m.type === 'screenshot');
  const videos = media.filter(m => m.type === 'video');
  const files  = media.filter(m => !['photo','screenshot','video'].includes(m.type));

  let html = '';

  if (photos.length) {
    html += `<div class="info-section"><h2>Photos & Screenshots (${photos.length})</h2>
      <div class="screenshots-grid">
        ${photos.map(m => `
          <div class="media-item" data-mid="${m.id}">
            <img class="screenshot-thumb" src="${m.path}" alt="${m.filename||''}"
              onclick="openLightbox('${m.path}')"
              onerror="this.style.opacity='0.2'">
            <div class="media-caption">${escHtml(m.caption||m.filename||'')}</div>
            <div class="media-meta">⏱ ${fmtDt(m.added_at)} <button class="field-del" onclick="deleteMedia(${m.id})">✕</button></div>
          </div>`).join('')}
      </div></div>`;
  }

  if (videos.length) {
    html += `<div class="info-section"><h2>Videos (${videos.length})</h2>
      <div class="screenshots-grid">
        ${videos.map(m => `
          <div class="media-item" data-mid="${m.id}">
            <video controls class="screenshot-thumb" style="object-fit:contain; background:#000;">
              <source src="${m.path}">
            </video>
            <div class="media-caption">${escHtml(m.caption||m.filename||'')}</div>
            <div class="media-meta">⏱ ${fmtDt(m.added_at)} <button class="field-del" onclick="deleteMedia(${m.id})">✕</button></div>
          </div>`).join('')}
      </div></div>`;
  }

  if (files.length) {
    html += `<div class="info-section"><h2>Files & Repos (${files.length})</h2>
      <div class="fields-grid">
        ${files.map(m => `
          <div class="field-card" data-mid="${m.id}">
            <div class="field-label">${MEDIA_TYPES[m.type]||m.type}</div>
            <div class="field-value">
              ${m.type === 'repo_url'
                ? `<a href="${escHtml(m.path)}" target="_blank">🐙 ${escHtml(m.path)} ↗</a>`
                : `<a href="${escHtml(m.path)}" download="${escHtml(m.filename||'file')}">⬇ ${escHtml(m.filename||'Download')}</a>`}
              ${m.caption ? `<div style="color:var(--muted);font-size:0.82rem;margin-top:0.3rem;">${escHtml(m.caption)}</div>` : ''}
            </div>
            <div class="field-meta">
              <span class="field-time">⏱ ${fmtDt(m.added_at)}</span>
              <button class="field-del" onclick="deleteMedia(${m.id})">✕</button>
            </div>
          </div>`).join('')}
      </div></div>`;
  }

  document.getElementById('media-section').innerHTML = html;
}

// ── Add Field ──
async function submitAddField(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  const res = await fetch(`${API}/api/people/${pid}/fields`, { method: 'POST', body: fd });
  const data = await res.json();
  if (data.ok) {
    showToast('Field added ✓');
    e.target.reset();
    await load();
  } else { showToast('Error', 'error'); }
}

// ── Add Media ──
async function submitAddMedia(e) {
  e.preventDefault();
  const btn = e.target.querySelector('[type=submit]');
  btn.disabled = true; btn.textContent = 'Uploading...';
  const fd = new FormData(e.target);
  try {
    const res = await fetch(`${API}/api/people/${pid}/media`, { method: 'POST', body: fd });
    const data = await res.json();
    if (data.ok) { showToast('Media added ✓'); e.target.reset(); await load(); }
    else { showToast('Error', 'error'); }
  } finally { btn.disabled = false; btn.textContent = 'Upload'; }
}

// ── Delete Field ──
async function deleteField(fid) {
  if (!confirm('Remove this field?')) return;
  await fetch(`${API}/api/fields/${fid}`, { method: 'DELETE' });
  showToast('Removed');
  await load();
}

// ── Delete Media ──
async function deleteMedia(mid) {
  if (!confirm('Remove this media?')) return;
  await fetch(`${API}/api/media/${mid}`, { method: 'DELETE' });
  showToast('Removed');
  await load();
}

// ── Rename ──
async function editName() {
  const current = personData.name;
  const newName = prompt('Rename:', current);
  if (!newName || newName === current) return;
  const fd = new FormData(); fd.append('name', newName);
  await fetch(`${API}/api/people/${pid}`, { method: 'PATCH', body: fd });
  showToast('Renamed ✓');
  await load();
}

// ── Delete Person ──
async function confirmDelete() {
  if (!confirm('Delete this person permanently?')) return;
  await fetch(`${API}/api/people/${pid}`, { method: 'DELETE' });
  showToast('Deleted');
  setTimeout(() => location.href = '/', 600);
}

// ── Lightbox ──
function openLightbox(src) {
  document.getElementById('lightbox-img').src = src;
  document.getElementById('lightbox').classList.add('open');
}
document.getElementById('lightbox').addEventListener('click', function(e) {
  if (e.target !== document.getElementById('lightbox-img'))
    this.classList.remove('open');
});

// ── Media type toggle (show repo_url input vs file input) ──
document.getElementById('media-type-select').addEventListener('change', function() {
  const isUrl = this.value === 'repo_url';
  document.getElementById('media-file-group').style.display  = isUrl ? 'none' : 'block';
  document.getElementById('media-url-group').style.display   = isUrl ? 'block' : 'none';
});

// ── Form listeners ──
document.getElementById('add-field-form').addEventListener('submit', submitAddField);
document.getElementById('add-media-form').addEventListener('submit', submitAddMedia);

load();