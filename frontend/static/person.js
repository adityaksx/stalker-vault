const API = '';
const pid = location.pathname.split('/').pop();

const FIELD_TYPES = {
  instagram:   { label: '📸 Instagram',      group: 'Social',    fmt: v => `<a href="https://instagram.com/${v}" target="_blank">@${v} ↗</a>` },
  snapchat:    { label: '👻 Snapchat',        group: 'Social',    fmt: v => v },
  twitter:     { label: '𝕏 X / Twitter',     group: 'Social',    fmt: v => `<a href="https://x.com/${v}" target="_blank">@${v} ↗</a>` },
  linkedin:    { label: '💼 LinkedIn',        group: 'Social',    fmt: v => `<a href="${v}" target="_blank">View ↗</a>` },
  pinterest:   { label: '📌 Pinterest',       group: 'Social',    fmt: v => `<a href="https://pinterest.com/${v}" target="_blank">${v} ↗</a>` },
  facebook:    { label: '📘 Facebook',        group: 'Social',    fmt: v => `<a href="${v}" target="_blank">View ↗</a>` },
  tiktok:      { label: '🎵 TikTok',          group: 'Social',    fmt: v => `<a href="https://tiktok.com/@${v}" target="_blank">@${v} ↗</a>` },
  youtube:     { label: '▶️ YouTube',         group: 'Social',    fmt: v => `<a href="${v}" target="_blank">Channel ↗</a>` },
  telegram:    { label: '✈️ Telegram',        group: 'Social',    fmt: v => v },
  discord:     { label: '🎮 Discord',         group: 'Social',    fmt: v => v },
  reddit:      { label: '🤖 Reddit',          group: 'Social',    fmt: v => `<a href="https://reddit.com/u/${v}" target="_blank">u/${v} ↗</a>` },
  threads:     { label: '🧵 Threads',         group: 'Social',    fmt: v => `<a href="https://threads.net/@${v}" target="_blank">@${v} ↗</a>` },
  bereal:      { label: '📷 BeReal',          group: 'Social',    fmt: v => v },
  spotify:     { label: '🎧 Spotify',         group: 'Social',    fmt: v => `<a href="${v}" target="_blank">Profile ↗</a>` },
  phone:       { label: '📞 Phone',           group: 'Contact',   fmt: v => `<a href="tel:${v}">${v}</a>` },
  email:       { label: '📧 Email',           group: 'Contact',   fmt: v => `<a href="mailto:${v}">${v}</a>` },
  whatsapp:    { label: '💬 WhatsApp',        group: 'Contact',   fmt: v => v },
  nickname:    { label: '🏷 Nickname',        group: 'Identity',  fmt: v => v },
  dob:         { label: '🎂 Date of Birth',   group: 'Identity',  fmt: v => v },
  gender:      { label: '⚧ Gender',          group: 'Identity',  fmt: v => v },
  school:      { label: '🏫 School',          group: 'Education', fmt: v => v },
  college:     { label: '🎓 College',         group: 'Education', fmt: v => v },
  workplace:   { label: '🏢 Workplace',       group: 'Work',      fmt: v => v },
  jobtitle:    { label: '💼 Job Title',       group: 'Work',      fmt: v => v },
  github:      { label: '🐙 GitHub',          group: 'Work',      fmt: v => `<a href="https://github.com/${v}" target="_blank">${v} ↗</a>` },
  website:     { label: '🌐 Website',         group: 'Web',       fmt: v => `<a href="${v}" target="_blank">${v} ↗</a>` },
  location:    { label: '📍 Location',        group: 'Location',  fmt: v => v },
  address:     { label: '🏠 Address',         group: 'Location',  fmt: v => v },
  fav_song:    { label: '🎵 Fav Song',        group: 'Music',     fmt: v => v },
  fav_artist:  { label: '🎤 Fav Artist',      group: 'Music',     fmt: v => v },
  fav_album:   { label: '💿 Fav Album',       group: 'Music',     fmt: v => v },
  music_taste: { label: '🎼 Music Taste',     group: 'Music',     fmt: v => v },
  note:        { label: '📝 Note',            group: 'Notes',     fmt: v => v },
  tag:         { label: '🔖 Tag',             group: 'Tags',      fmt: v => `<span class="tag">${v}</span>` },
  custom:      { label: '✏️ Custom',          group: 'Custom',    fmt: v => v },
};

const MEDIA_LABELS = {
  profile_pic: '🧑 Profile Pic', photo: '🖼 Photo',
  screenshot: '📸 Screenshot',   video: '🎬 Video',
  audio: '🎵 Audio',             repo_url: '🐙 GitHub Repo',
  repo_zip: '📦 Repo ZIP',       other: '📎 File',
};

const MEDIA_ACCEPT = {
  profile_pic: 'image/*', photo: 'image/*', screenshot: 'image/*',
  video: 'video/*', audio: 'audio/*', repo_zip: '.zip,.tar,.gz', other: '*',
};

let personData  = null;
let queuedFiles = [];

// ── Helpers ──
function showToast(msg, type = 'success') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = `toast ${type} show`;
  setTimeout(() => t.classList.remove('show'), 2800);
}
function fmtDt(iso) {
  try {
    return new Date(iso).toLocaleString('en-IN', {
      day: 'numeric', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  } catch { return iso; }
}
function esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Load ──
async function load() {
  const res = await fetch(`${API}/api/people/${pid}`);
  if (!res.ok) {
    document.querySelector('.page').innerHTML = `
      <a class="back-link" href="/">← Back</a>
      <div class="empty-state"><div class="emoji">❓</div><p>Person not found.</p></div>`;
    return;
  }
  personData = await res.json();
  render();
}

function render() { renderHero(); renderFields(); renderMedia(); }

// ── Hero ──
function renderHero() {
  const d   = personData;
  const pic = d.media?.find(m => m.type === 'profile_pic')
           || d.media?.find(m => m.type === 'photo');
  const avatar = pic
    ? `<img class="person-hero-avatar" src="${pic.path}" alt="${esc(d.name)}">`
    : `<div class="hero-placeholder">👤</div>`;

  const tags   = d.fields?.filter(f => f.type === 'tag')
    .map(f => `<span class="tag">${esc(f.value)}</span>`).join('') || '';
  const insta  = d.fields?.find(f => f.type === 'instagram');
  const handle = insta ? `<div class="handle">@${esc(insta.value)}</div>` : '';

  document.getElementById('hero-section').innerHTML = `
    <div class="person-hero">
      ${avatar}
      <div class="person-hero-info">
        <h1>${esc(d.name)}</h1>
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
    document.getElementById('fields-section').innerHTML =
      `<div class="section-empty">No info added yet.</div>`;
    return;
  }
  const groups = {};
  fields.forEach(f => {
    const meta = FIELD_TYPES[f.type] || { label: f.type, group: 'Custom', fmt: v => v };
    if (!groups[meta.group]) groups[meta.group] = [];
    groups[meta.group].push({ ...f, meta });
  });

  document.getElementById('fields-section').innerHTML =
    Object.entries(groups).map(([group, items]) => `
      <div class="info-section">
        <h2>${group}</h2>
        <div class="fields-grid">
          ${items.map(f => `
            <div class="field-card">
              <div class="field-label">${f.meta.label}${f.label ? ` <span class="field-sublabel">(${esc(f.label)})</span>` : ''}</div>
              <div class="field-value">${f.meta.fmt(esc(f.value))}</div>
              <div class="field-meta">
                <span class="field-time">⏱ ${fmtDt(f.added_at)}</span>
                <button class="field-del" onclick="deleteField(${f.id})">✕</button>
              </div>
            </div>`).join('')}
        </div>
      </div>`).join('');
}

// ── Media ──
function renderMedia() {
  const media  = personData.media || [];
  if (!media.length) {
    document.getElementById('media-section').innerHTML =
      `<div class="section-empty">No media added yet.</div>`;
    return;
  }

  const photos = media.filter(m => ['photo','screenshot','profile_pic'].includes(m.type));
  const videos = media.filter(m => m.type === 'video');
  const audios = media.filter(m => m.type === 'audio');
  const files  = media.filter(m => !['photo','screenshot','profile_pic','video','audio'].includes(m.type));

  let html = '';

  if (photos.length) {
    html += `<div class="info-section"><h2>Photos &amp; Screenshots (${photos.length})</h2>
      <div class="screenshots-grid">
        ${photos.map(m => `
          <div class="media-item">
            <img class="screenshot-thumb" src="${m.path}"
              onclick="openLightbox('${m.path}')"
              onerror="this.style.opacity='0.15'">
            <div class="media-caption">
              <span class="fname-badge" title="${esc(m.filename||'')}">${esc(m.filename||'')}</span>
            </div>
            <div class="media-meta">
              <span class="field-time">⏱ ${fmtDt(m.added_at)}</span>
              <span style="display:flex;gap:0.3rem;align-items:center">
                <button class="rename-media-btn" onclick="renameMedia(${m.id},'${esc(m.filename||'')}')" title="Rename">✏️</button>
                <button class="field-del" onclick="deleteMedia(${m.id})">✕</button>
              </span>
            </div>
          </div>`).join('')}
      </div></div>`;
  }

  if (videos.length) {
    html += `<div class="info-section"><h2>Videos (${videos.length})</h2>
      <div class="screenshots-grid">
        ${videos.map(m => `
          <div class="media-item">
            <video controls class="screenshot-thumb" style="aspect-ratio:9/16;background:#000;">
              <source src="${m.path}">
            </video>
            <div class="media-caption">
              <span class="fname-badge">${esc(m.filename||'')}</span>
            </div>
            <div class="media-meta">
              <span class="field-time">⏱ ${fmtDt(m.added_at)}</span>
              <span style="display:flex;gap:0.3rem;align-items:center">
                <button class="rename-media-btn" onclick="renameMedia(${m.id},'${esc(m.filename||'')}')" title="Rename">✏️</button>
                <button class="field-del" onclick="deleteMedia(${m.id})">✕</button>
              </span>
            </div>
          </div>`).join('')}
      </div></div>`;
  }

  if (audios.length) {
    html += `<div class="info-section"><h2>Audio / Music (${audios.length})</h2>
      <div class="fields-grid">
        ${audios.map(m => `
          <div class="field-card">
            <div class="field-label">🎵 Audio</div>
            <audio controls style="width:100%;margin:0.4rem 0;">
              <source src="${m.path}">
            </audio>
            <div class="field-value" style="font-size:0.8rem">
              <span class="fname-badge">${esc(m.filename||'')}</span>
              ${m.caption ? `<div style="color:var(--muted2);margin-top:0.3rem">${esc(m.caption)}</div>` : ''}
            </div>
            <div class="field-meta">
              <span class="field-time">⏱ ${fmtDt(m.added_at)}</span>
              <span style="display:flex;gap:0.3rem;align-items:center">
                <button class="rename-media-btn" onclick="renameMedia(${m.id},'${esc(m.filename||'')}')" title="Rename">✏️</button>
                <button class="field-del" onclick="deleteMedia(${m.id})">✕</button>
              </span>
            </div>
          </div>`).join('')}
      </div></div>`;
  }

  if (files.length) {
    html += `<div class="info-section"><h2>Files &amp; Repos (${files.length})</h2>
      <div class="fields-grid">
        ${files.map(m => `
          <div class="field-card">
            <div class="field-label">${MEDIA_LABELS[m.type]||m.type}</div>
            <div class="field-value">
              ${m.type === 'repo_url'
                ? `<a href="${esc(m.path)}" target="_blank">🐙 ${esc(m.path)} ↗</a>`
                : `<a href="${esc(m.path)}" download="${esc(m.filename||'file')}">⬇ ${esc(m.filename||'Download')}</a>`}
              ${m.caption ? `<div style="color:var(--muted2);font-size:0.8rem;margin-top:0.25rem">${esc(m.caption)}</div>` : ''}
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
document.getElementById('add-field-form').addEventListener('submit', async e => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const res = await fetch(`${API}/api/people/${pid}/fields`, { method: 'POST', body: fd });
  const data = await res.json();
  if (data.ok) { showToast('Field added ✓'); e.target.reset(); await load(); }
  else showToast('Error', 'error');
});

// ── Media type change ──
const typeSelect   = document.getElementById('media-type-select');
const fileInput    = document.getElementById('media-file-input');
const fileGroup    = document.getElementById('media-file-group');
const urlGroup     = document.getElementById('media-url-group');
const multiHint    = document.getElementById('multi-hint');
const multiPreview = document.getElementById('multi-preview');

typeSelect.addEventListener('change', () => {
  const t = typeSelect.value;
  const isUrl = t === 'repo_url';
  fileGroup.style.display = isUrl ? 'none' : 'block';
  urlGroup.style.display  = isUrl ? 'block' : 'none';
  if (!isUrl) {
    fileInput.accept   = MEDIA_ACCEPT[t] || '*';
    fileInput.multiple = ['photo', 'screenshot'].includes(t);
    multiHint.textContent = fileInput.multiple ? '(select multiple)' : '';
  }
  queuedFiles = [];
  multiPreview.innerHTML = '';
});

// ── File picker → preview ──
fileInput.addEventListener('change', () => {
  queuedFiles = Array.from(fileInput.files);
  renderMultiPreview();
});

function renderMultiPreview() {
  multiPreview.innerHTML = '';
  queuedFiles.forEach((file, i) => {
    const item = document.createElement('div');
    item.className = 'multi-preview-item';
    if (file.type.startsWith('image/')) {
      const img = document.createElement('img');
      img.src = URL.createObjectURL(file);
      item.appendChild(img);
    } else if (file.type.startsWith('video/')) {
      const vid = document.createElement('video');
      vid.src = URL.createObjectURL(file);
      item.appendChild(vid);
    } else {
      item.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100%;font-size:1.4rem;">📄</div>`;
    }
    const rm = document.createElement('button');
    rm.className = 'rm'; rm.textContent = '✕';
    rm.onclick = () => { queuedFiles.splice(i, 1); renderMultiPreview(); };
    item.appendChild(rm);
    multiPreview.appendChild(item);
  });
}

// ── Upload (multi-file) ──
document.getElementById('add-media-form').addEventListener('submit', async e => {
  e.preventDefault();
  const btn = document.getElementById('upload-btn');
  const bar = document.getElementById('upload-bar');
  const t   = typeSelect.value;
  const cap = e.target.querySelector('[name=caption]').value;

  if (t === 'repo_url') {
    const url = e.target.querySelector('[name=repo_url]').value;
    if (!url) return showToast('Enter a URL', 'error');
    btn.disabled = true; btn.textContent = 'Saving...';
    const fd = new FormData();
    fd.append('media_type', 'repo_url');
    fd.append('repo_url', url);
    if (cap) fd.append('caption', cap);
    const res = await fetch(`${API}/api/people/${pid}/media`, { method:'POST', body:fd });
    const data = await res.json();
    if (data.ok) { showToast('Saved ✓'); e.target.reset(); await load(); }
    else showToast('Error', 'error');
    btn.disabled = false; btn.textContent = 'Upload';
    return;
  }

  const files = queuedFiles.length ? queuedFiles : Array.from(fileInput.files);
  if (!files.length) return showToast('No file selected', 'error');

  btn.disabled = true;
  bar.style.width = '0';

  for (let i = 0; i < files.length; i++) {
    bar.style.width = `${Math.round((i / files.length) * 90)}%`;
    btn.textContent = files.length > 1 ? `Uploading ${i+1}/${files.length}...` : 'Uploading...';
    const fd = new FormData();
    fd.append('media_type', t);
    fd.append('file', files[i]);
    if (cap) fd.append('caption', cap);
    const res = await fetch(`${API}/api/people/${pid}/media`, { method:'POST', body:fd });
    const data = await res.json();
    if (!data.ok) showToast(`Failed on file ${i+1}`, 'error');
  }

  bar.style.width = '100%';
  setTimeout(() => { bar.style.width = '0'; }, 600);
  showToast(`${files.length} file${files.length > 1 ? 's' : ''} uploaded ✓`);
  queuedFiles = []; multiPreview.innerHTML = '';
  e.target.reset();
  btn.disabled = false; btn.textContent = 'Upload';
  await load();
});

// ── Delete ──
async function deleteField(fid) {
  if (!confirm('Remove this field?')) return;
  await fetch(`${API}/api/fields/${fid}`, { method: 'DELETE' });
  showToast('Removed'); await load();
}
async function deleteMedia(mid) {
  if (!confirm('Remove this media?')) return;
  await fetch(`${API}/api/media/${mid}`, { method: 'DELETE' });
  showToast('Removed'); await load();
}

// ── Rename person ──
async function editName() {
  const newName = prompt('Rename:', personData.name);
  if (!newName || newName === personData.name) return;
  const fd = new FormData(); fd.append('name', newName);
  await fetch(`${API}/api/people/${pid}`, { method: 'PATCH', body: fd });
  showToast('Renamed ✓'); await load();
}

// ── Rename media ──
async function renameMedia(mid, current) {
  const newName = prompt('Rename file (keep extension):', current);
  if (!newName || newName === current) return;
  const fd = new FormData(); fd.append('filename', newName);
  const res = await fetch(`${API}/api/media/${mid}/rename`, { method: 'PATCH', body: fd });
  const data = await res.json();
  if (data.ok) { showToast('Renamed ✓'); await load(); }
  else showToast('Error', 'error');
}

// ── Delete person ──
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
document.getElementById('lb-close').addEventListener('click', () => {
  document.getElementById('lightbox').classList.remove('open');
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') document.getElementById('lightbox').classList.remove('open');
});

load();