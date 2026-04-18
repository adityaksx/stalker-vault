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

async function loadPerson() {
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

function render() { renderHero(); renderFields(); renderMedia(); updateCatBadge(personData?.category); }

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
        <div class="cat-badge-wrap" style="margin-bottom:0.5rem;">
          <span id="person-cat-badge" class="cat-badge" style="cursor:pointer;font-size:0.8rem;padding:0.25rem 0.7rem;" onclick="openCatModal()" title="Click to change category">
            Loading...
          </span>
        </div>
        <div class="hero-actions">
          <button class="btn btn-secondary btn-sm" onclick="editName()">✏️ Rename</button>
          <button class="btn btn-secondary btn-sm" onclick="openCatModal()">🏷 Category</button>
          <button class="btn btn-danger btn-sm" onclick="confirmDelete()">🗑 Delete</button>
        </div>
        <div class="added-date">Added ${fmtDt(d.added_at)}</div>
      </div>
    </div>`;
}

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

function renderMedia() {
  const media = personData.media || [];
  if (!media.length) {
    document.getElementById('media-section').innerHTML =
      `<div class="section-empty">No media added yet.</div>`;
    renderHighlights();
    renderFeedPosts();
    return;
  }
  const photos = media.filter(m => ['photo','screenshot','profile_pic'].includes(m.type));
  const videos = media.filter(m => m.type === 'video');
  const audios = media.filter(m => m.type === 'audio');
  const files  = media.filter(m => !['photo','screenshot','profile_pic','video','audio'].includes(m.type));
  let html = '';

  if (photos.length) {
    const preview = photos.slice(0,5), rest = photos.slice(5);
    html += `<div class="info-section" id="photos-section">
      <div class="media-section-header">
        <h2>📷 Photos &amp; Screenshots (${photos.length})</h2>
        ${photos.length>5?`<button class="btn btn-secondary btn-sm" onclick="toggleBlur('photos-section',this)">👁 Show All</button>`:''}
      </div>
      <div class="screenshots-grid blurred-group" id="photos-grid" data-expanded="0">
        ${preview.map(m=>mediaThumbHTML(m,true)).join('')}
      </div>
      ${rest.length?`<div class="screenshots-grid" id="photos-rest" style="display:none;margin-top:.75rem">${rest.map(m=>mediaThumbHTML(m,false)).join('')}</div>`:''}
    </div>`;
  }

  if (videos.length) {
    const preview = videos.slice(0,5), rest = videos.slice(5);
    html += `<div class="info-section" id="videos-section">
      <div class="media-section-header">
        <h2>🎬 Videos (${videos.length})</h2>
        ${videos.length>5?`<button class="btn btn-secondary btn-sm" onclick="toggleBlur('videos-section',this)">👁 Show All</button>`:''}
      </div>
      <div class="screenshots-grid blurred-group" id="videos-grid" data-expanded="0">
        ${preview.map(m=>videoThumbHTML(m,true)).join('')}
      </div>
      ${rest.length?`<div class="screenshots-grid" id="videos-rest" style="display:none;margin-top:.75rem">${rest.map(m=>videoThumbHTML(m,false)).join('')}</div>`:''}
    </div>`;
  }

  if (audios.length) {
    html += `<div class="info-section"><h2>🎵 Audio (${audios.length})</h2><div class="fields-grid">
      ${audios.map(m=>`<div class="field-card">
        <div class="field-label">🎵 Audio</div>
        <audio controls style="width:100%;margin:.4rem 0"><source src="${m.path}"></audio>
        <div class="field-value" style="font-size:.8rem"><span class="fname-badge">${esc(m.filename||'')}</span></div>
        <div class="field-meta">
          <span class="field-time">⏱ ${fmtDt(m.added_at)}</span>
          <span style="display:flex;gap:.3rem">
            <button class="rename-media-btn" onclick="renameMedia(${m.id},'${esc(m.filename||'')}')">✏️</button>
            <button class="field-del" onclick="deleteMedia(${m.id})">✕</button>
          </span>
        </div></div>`).join('')}
    </div></div>`;
  }

  if (files.length) {
    html += `<div class="info-section"><h2>📁 Files &amp; Repos (${files.length})</h2><div class="fields-grid">
      ${files.map(m=>`<div class="field-card">
        <div class="field-label">${MEDIA_LABELS[m.type]||m.type}</div>
        <div class="field-value">
          ${m.type==='repo_url'?`<a href="${esc(m.path)}" target="_blank">🐙 ${esc(m.path)} ↗</a>`
            :`<a href="${esc(m.path)}" download="${esc(m.filename||'file')}">⬇ ${esc(m.filename||'Download')}</a>`}
          ${m.caption?`<div style="color:var(--muted2);font-size:.8rem;margin-top:.25rem">${esc(m.caption)}</div>`:''}
        </div>
        <div class="field-meta">
          <span class="field-time">⏱ ${fmtDt(m.added_at)}</span>
          <button class="field-del" onclick="deleteMedia(${m.id})">✕</button>
        </div></div>`).join('')}
    </div></div>`;
  }

  document.getElementById('media-section').innerHTML = html;
  renderHighlights();
  renderFeedPosts();
}

function mediaThumbHTML(m, blurred) {
  return `<div class="media-item${blurred?' media-blurred':''}">
    <img class="screenshot-thumb" src="${m.path}"
      onclick="${blurred?'unblurItem(this);':''} openLightbox('${m.path}','${esc(m.filename||'')}','${esc(m.local_path||'')}')"
      onerror="this.style.opacity='0.15'" loading="lazy">
    <div class="media-caption"><span class="fname-badge" title="${esc(m.filename||'')}">${esc(m.filename||'')}</span></div>
    <div class="media-meta">
      <span class="field-time">⏱ ${fmtDt(m.added_at)}</span>
      <span style="display:flex;gap:.3rem;align-items:center">
        <button class="rename-media-btn" onclick="renameMedia(${m.id},'${esc(m.filename||'')}')">✏️</button>
        <button class="field-del" onclick="deleteMedia(${m.id})">✕</button>
      </span>
    </div>
  </div>`;
}

function videoThumbHTML(m, blurred) {
  return `<div class="media-item${blurred?' media-blurred':''}">
    <video controls class="screenshot-thumb" style="aspect-ratio:9/16;background:#000">
      <source src="${m.path}">
    </video>
    <div class="media-caption"><span class="fname-badge">${esc(m.filename||'')}</span></div>
    <div class="media-meta">
      <span class="field-time">⏱ ${fmtDt(m.added_at)}</span>
      <span style="display:flex;gap:.3rem;align-items:center">
        <button class="rename-media-btn" onclick="renameMedia(${m.id},'${esc(m.filename||'')}')">✏️</button>
        <button class="field-del" onclick="deleteMedia(${m.id})">✕</button>
      </span>
    </div>
  </div>`;
}

function toggleBlur(sectionId, btn) {
  const section = document.getElementById(sectionId);
  const grid = section.querySelector('.blurred-group');
  const rest = section.querySelector('[id$="-rest"]');
  if (grid.dataset.expanded === '1') {
    grid.querySelectorAll('.media-item').forEach(el => el.classList.add('media-blurred'));
    grid.dataset.expanded = '0';
    if (rest) rest.style.display = 'none';
    btn.textContent = '👁 Show All';
  } else {
    grid.querySelectorAll('.media-blurred').forEach(el => el.classList.remove('media-blurred'));
    grid.dataset.expanded = '1';
    if (rest) rest.style.display = 'grid';
    btn.textContent = '🙈 Collapse';
  }
}

function unblurItem(imgEl) {
  imgEl.closest('.media-item')?.classList.remove('media-blurred');
}

// ── Highlights ──────────────────────────────────────────────────────────────
async function renderHighlights() {
  const sec = document.getElementById('highlights-section');
  if (!sec) return;
  let data = [];
  try { data = await (await fetch(`${API}/api/people/${pid}/highlights`)).json(); } catch {}
  if (!data.length) { sec.innerHTML = ''; return; }
  sec.innerHTML = `<div class="info-section">
    <h2>🎬 Instagram Highlights (${data.length})</h2>
    <div class="ig-highlights-row">
      ${data.map(h=>`
        <div class="ig-highlight-bubble" onclick="openHighlight(${h.id})">
          <div class="ig-hl-ring">
            <div class="ig-hl-thumb">
              ${h.thumb?`<img src="${h.thumb}" loading="lazy" style="width:100%;height:100%;object-fit:cover">`:`<span style="font-size:1.8rem">📽️</span>`}
            </div>
          </div>
          <div class="ig-hl-name">${esc(h.name)}</div>
          <div class="ig-hl-count">${h.story_count} stories</div>
        </div>`).join('')}
    </div>
  </div>`;
}

async function openHighlight(hlId) {
  const stories = await (await fetch(`${API}/api/highlights/${hlId}/stories`)).json();
  document.getElementById('hl-modal-body').innerHTML = `<div class="hl-stories-grid">
    ${stories.map(s=>s.is_video
      ?`<div class="hl-story-item"><video controls class="hl-story-media"><source src="${s.path}"></video><div class="hl-story-date">${s.story_date||fmtDt(s.added_at)}</div></div>`
      :`<div class="hl-story-item"><img class="hl-story-media" src="${s.path}" onclick="openLightbox('${s.path}','','')"><div class="hl-story-date">${s.story_date||fmtDt(s.added_at)}</div></div>`
    ).join('')}
  </div>`;
  document.getElementById('hl-modal').classList.add('open');
}

// ── Feed Posts ────────────────────────────────────────────────────────────────
async function renderFeedPosts() {
  const sec = document.getElementById('feed-section');
  if (!sec) return;
  let posts = [];
  try { posts = await (await fetch(`${API}/api/people/${pid}/feed-posts`)).json(); } catch {}
  if (!posts.length) { sec.innerHTML = ''; return; }
  sec.innerHTML = `<div class="info-section">
    <h2>📸 Instagram Posts / Reels (${posts.length})</h2>
    <div class="feed-posts-grid">
      ${posts.map(p=>{
        const cover=p.items?.[0], isVid=cover?.is_video;
        return `<div class="feed-post-card" onclick="openFeedPost(${p.id})">
          <div class="feed-post-thumb">
            ${isVid
              ?`<video class="feed-thumb-media" muted preload="none"><source src="${cover.path}"></video><span class="feed-type-badge">▶</span>`
              :`<img class="feed-thumb-media" src="${cover?.path||''}" loading="lazy">`}
            ${p.items.length>1?`<span class="feed-multi-badge">⊞ ${p.items.length}</span>`:''}
          </div>
          <div class="feed-post-date">${p.post_date||''}</div>
        </div>`;
      }).join('')}
    </div>
  </div>`;
}

async function openFeedPost(postId) {
  const items = await (await fetch(`${API}/api/feed-posts/${postId}/items`)).json();
  document.getElementById('feed-modal-body').innerHTML = `<div class="hl-stories-grid">
    ${items.map(item=>item.is_video
      ?`<div class="hl-story-item"><video controls class="hl-story-media"><source src="${item.path}"></video><div class="hl-story-date">${esc(item.filename||'')}</div></div>`
      :`<div class="hl-story-item"><img class="hl-story-media" src="${item.path}" onclick="openLightbox('${item.path}','','')"><div class="hl-story-date">${esc(item.filename||'')}</div></div>`
    ).join('')}
  </div>`;
  document.getElementById('feed-modal').classList.add('open');
}

// ── Category ──────────────────────────────────────────────────────────────────
const CAT_LABELS = {
  friend:'👋 Friends', close_friend:'💛 Close Friends',
  related:'🔗 Related to Friend/Close Friend',
  random:'🌐 Random (Found Online)', misc:'🗂️ Misc.', archived:'📦 Archived',
};
const CAT_COLORS = {
  friend:'#a78bfa', close_friend:'#fbbf24', related:'#38bdf8',
  random:'#34d399', misc:'#f472b6', archived:'#5a5a7a',
};

function updateCatBadge(cat) {
  const badge = document.getElementById('person-cat-badge');
  if (!badge) return;
  const c = cat||'random';
  badge.textContent  = CAT_LABELS[c]||c;
  badge.style.background  = (CAT_COLORS[c]||'#888')+'22';
  badge.style.color       = CAT_COLORS[c]||'#888';
  badge.style.borderColor = (CAT_COLORS[c]||'#888')+'66';
}

function openCatModal() {
  const sel = document.getElementById('cat-select');
  if (sel) sel.value = personData?.category||'random';
  document.getElementById('cat-modal')?.classList.add('open');
}

document.addEventListener('DOMContentLoaded', () => {
  ['cat-modal','hl-modal','feed-modal'].forEach(id => {
    document.getElementById(id)?.addEventListener('click', e => {
      if (e.target.id === id) document.getElementById(id).classList.remove('open');
    });
  });
  document.getElementById('cat-modal-close')?.addEventListener('click',
    () => document.getElementById('cat-modal')?.classList.remove('open'));

  document.getElementById('cat-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const newCat = document.getElementById('cat-select').value;
    const fd = new FormData(); fd.append('category', newCat);
    const r = await fetch(`${API}/api/people/${pid}/category`,{method:'PATCH',body:fd});
    const d = await r.json();
    if (d.ok) {
      personData.category = newCat;
      updateCatBadge(newCat);
      document.getElementById('cat-modal').classList.remove('open');
      showToast('Category updated ✓');
    }
  });
});


// ── Add Field ──
document.getElementById('add-field-form').addEventListener('submit', async e => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const res = await fetch(`${API}/api/people/${pid}/fields`, { method: 'POST', body: fd });
  const data = await res.json();
  if (data.ok) { showToast('Field added ✓'); e.target.reset(); await init(); }
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

// ── Upload ──
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
    if (data.ok) { showToast('Saved ✓'); e.target.reset(); await init(); }
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
  await init();
});

// ── Delete ──
async function deleteField(fid) {
  if (!confirm('Remove this field?')) return;
  await fetch(`${API}/api/fields/${fid}`, { method: 'DELETE' });
  showToast('Removed'); await init();
}
async function deleteMedia(mid) {
  if (!confirm('Remove this media?')) return;
  await fetch(`${API}/api/media/${mid}`, { method: 'DELETE' });
  showToast('Removed'); await init();
}

async function editName() {
  const newName = prompt('Rename:', personData.name);
  if (!newName || newName === personData.name) return;
  const fd = new FormData(); fd.append('name', newName);
  await fetch(`${API}/api/people/${pid}`, { method: 'PATCH', body: fd });
  showToast('Renamed ✓'); await init();
}

async function renameMedia(mid, current) {
  const newName = prompt('Rename file (keep extension):', current);
  if (!newName || newName === current) return;
  const fd = new FormData(); fd.append('filename', newName);
  const res = await fetch(`${API}/api/media/${mid}/rename`, { method: 'PATCH', body: fd });
  const data = await res.json();
  if (data.ok) { showToast('Renamed ✓'); await init(); }
  else showToast('Error', 'error');
}

async function confirmDelete() {
  if (!confirm('Delete this person permanently?')) return;
  await fetch(`${API}/api/people/${pid}`, { method: 'DELETE' });
  showToast('Deleted');
  setTimeout(() => location.href = '/', 600);
}

// ── Lightbox with local path ──
function openLightbox(src, filename, localPath) {
  document.getElementById('lightbox-img').src = src;
  document.getElementById('lb-filename').textContent = filename || '';

  const pathEl = document.getElementById('lb-local-path');
  if (localPath) {
    pathEl.textContent = localPath;
    pathEl.parentElement.style.display = 'block';
  } else {
    pathEl.parentElement.style.display = 'none';
  }

  document.getElementById('lightbox').classList.add('open');
}

document.getElementById('lightbox').addEventListener('click', function(e) {
  const inner = document.getElementById('lb-inner');
  if (!inner.contains(e.target))
    this.classList.remove('open');
});
document.getElementById('lb-close').addEventListener('click', () => {
  document.getElementById('lightbox').classList.remove('open');
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') document.getElementById('lightbox').classList.remove('open');
});

// ════════ Instagram Tracker ════════
let igSnapshots = [];

async function loadIg() {
  const res = await fetch(`${API}/api/people/${pid}/ig-snapshots`);
  igSnapshots = (await res.json()).snapshots || [];
  renderIgSection();
}

function renderIgSection() {
  const wrap = document.getElementById('ig-section');
  if (!wrap) return;
  const followers = igSnapshots.filter(s => s.list_type === 'followers');
  const following = igSnapshots.filter(s => s.list_type === 'following');

  wrap.innerHTML = `
  <div class="info-section">
    <h2>📊 Instagram Tracker</h2>
    <div class="ig-import-panel">
      <h3>➕ Import Snapshot</h3>
      <form id="ig-import-form">
        <div class="ig-form-row">
          <div class="form-group">
            <label>IG Username (whose list)</label>
            <input type="text" name="ig_username" placeholder="_vaishnnavvi_" required/>
          </div>
          <div class="form-group">
            <label>List Type</label>
            <select name="list_type">
              <option value="followers">👥 Followers</option>
              <option value="following">➡️ Following</option>
            </select>
          </div>
          <div class="form-group">
            <label>Label <span style="color:var(--muted);font-size:0.7rem">(optional)</span></label>
            <input type="text" name="label" placeholder="Week 1, April 2026"/>
          </div>
        </div>
        <div class="form-group">
          <label>CSV File <span style="color:var(--muted);font-size:0.7rem">(_Followers.csv or _Following.csv)</span></label>
          <label class="file-label">📂 Choose CSV
            <input type="file" id="ig-csv-input" accept=".csv,.txt" required/>
          </label>
          <div id="ig-csv-preview" style="font-size:0.75rem;color:var(--muted2);margin-top:0.3rem"></div>
        </div>
        <div id="ig-import-bar" class="upload-bar"></div>
        <button type="submit" class="btn btn-primary" id="ig-import-btn">📥 Import & Save</button>
      </form>
    </div>

    <div class="ig-tabs" style="margin-top:1.5rem">
      <button class="ig-tab active" onclick="switchIgTab('followers',this)">👥 Followers (${followers.length})</button>
      <button class="ig-tab" onclick="switchIgTab('following',this)">➡️ Following (${following.length})</button>
      <button class="ig-tab" onclick="switchIgTab('diff',this)">🔍 Diff</button>
    </div>
    <div id="ig-tab-followers">${renderSnapList(followers)}</div>
    <div id="ig-tab-following" style="display:none">${renderSnapList(following)}</div>
    <div id="ig-tab-diff" style="display:none">${renderDiffPanel()}</div>
  </div>`;

  document.getElementById('ig-csv-input').addEventListener('change', e => {
    const f = e.target.files[0];
    document.getElementById('ig-csv-preview').textContent = f ? `${f.name} (${(f.size/1024).toFixed(1)} KB)` : '';
  });
  document.getElementById('ig-import-form').addEventListener('submit', igImport);
}

function renderSnapList(snaps) {
  if (!snaps.length) return `<div class="section-empty">No snapshots yet.</div>`;
  return `<div class="ig-snapshots-list">${snaps.map(s => `
    <div class="ig-snapshot-card" id="igsnap-${s.id}">
      <div class="ig-snap-header">
        <div>
          <span class="ig-snap-label">${esc(s.label||s.imported_at)}</span>
          <span class="ig-snap-meta">@${esc(s.ig_username)} · ${s.count} people · ${fmtDt(s.imported_at)}</span>
        </div>
        <div style="display:flex;gap:0.4rem">
          <button class="btn btn-secondary btn-sm" onclick="viewSnapshot(${s.id})">👁 View</button>
          <button class="field-del" onclick="deleteSnapshot(${s.id})">✕</button>
        </div>
      </div>
      <div class="ig-entries-wrap" id="igentries-${s.id}" style="display:none"></div>
    </div>`).join('')}</div>`;
}

function renderDiffPanel() {
  if (igSnapshots.length < 2) return `<div class="section-empty">Import at least 2 snapshots to compare.</div>`;
  const opts = igSnapshots.map(s =>
    `<option value="${s.id}">[${s.list_type}] ${esc(s.label||s.imported_at)} @${esc(s.ig_username)} (${s.count})</option>`).join('');
  return `<div class="ig-diff-controls">
    <div class="form-group"><label>Old Snapshot</label><select id="diff-old">${opts}</select></div>
    <div class="form-group"><label>New Snapshot</label><select id="diff-new">${opts}</select></div>
    <button class="btn btn-primary" onclick="runDiff()">🔍 Compare</button>
  </div><div id="diff-result" style="margin-top:1rem"></div>`;
}

function switchIgTab(name, btn) {
  document.querySelectorAll('.ig-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  ['followers','following','diff'].forEach(t => {
    const el = document.getElementById(`ig-tab-${t}`);
    if (el) el.style.display = t === name ? 'block' : 'none';
  });
}

async function viewSnapshot(sid) {
  const wrap = document.getElementById(`igentries-${sid}`);
  if (wrap.style.display === 'block') { wrap.style.display = 'none'; return; }
  wrap.innerHTML = `<div style="color:var(--muted);padding:0.5rem">Loading…</div>`;
  wrap.style.display = 'block';
  const data = await (await fetch(`${API}/api/ig-snapshots/${sid}/entries`)).json();
  const entries = data.entries || [];
  wrap.innerHTML = entries.length
    ? `<div class="ig-entries-grid">${entries.map(igCard).join('')}</div>`
    : `<div class="section-empty">No entries.</div>`;
}

function igCard(e) {
  const src = e.local_pic_path || e.profile_pic_url || '';
  const av  = src
    ? `<img src="${esc(src)}" class="ig-avatar" onerror="this.outerHTML='<div class=ig-avatar-placeholder>👤</div>'">`
    : `<div class="ig-avatar-placeholder">👤</div>`;
  return `<div class="ig-entry-card">${av}
    <div class="ig-entry-info">
      <div class="ig-entry-username"><a href="https://instagram.com/${esc(e.username)}" target="_blank">@${esc(e.username)} ↗</a></div>
      <div class="ig-entry-name">${esc(e.full_name||'')}</div>
    </div></div>`;
}

async function deleteSnapshot(sid) {
  if (!confirm('Delete this snapshot?')) return;
  await fetch(`${API}/api/ig-snapshots/${sid}`, {method:'DELETE'});
  showToast('Deleted'); await loadIg();
}

async function igImport(e) {
  e.preventDefault();
  const form = e.target;
  const btn  = document.getElementById('ig-import-btn');
  const bar  = document.getElementById('ig-import-bar');
  const file = document.getElementById('ig-csv-input').files[0];
  if (!file) return showToast('Choose a CSV','error');
  btn.disabled = true; btn.textContent = 'Importing…'; bar.style.width = '40%';
  const csvText = await file.text();
  const fd = new FormData();
  fd.append('ig_username', form.ig_username.value.trim());
  fd.append('list_type',   form.list_type.value);
  fd.append('label',       form.label.value.trim());
  fd.append('csv_data',    csvText);
  const data = await (await fetch(`${API}/api/people/${pid}/ig-snapshots`, {method:'POST',body:fd})).json();
  bar.style.width = '100%'; setTimeout(()=>{ bar.style.width='0'; },600);
  if (data.ok) { showToast(`✅ Imported ${data.count} entries`); form.reset(); await loadIg(); }
  else showToast('Import failed','error');
  btn.disabled = false; btn.textContent = '📥 Import & Save';
}

async function runDiff() {
  const oldSid = document.getElementById('diff-old').value;
  const newSid = document.getElementById('diff-new').value;
  if (oldSid === newSid) return showToast('Pick two different snapshots','error');
  const data = await (await fetch(`${API}/api/ig-snapshots/diff?old_sid=${oldSid}&new_sid=${newSid}`)).json();
  const oldS = igSnapshots.find(s=>s.id==oldSid);
  const newS = igSnapshots.find(s=>s.id==newSid);
  document.getElementById('diff-result').innerHTML = `
    <div class="ig-diff-summary">
      <span>📊 Old: <b>${data.old_count}</b></span>
      <span>📊 New: <b>${data.new_count}</b></span>
      <span style="color:#f87171">😞 Unfollowed: <b>${data.unfollowed.length}</b></span>
      <span style="color:#4ade80">🎉 New: <b>${data.new.length}</b></span>
      <span style="color:var(--muted2)">↔️ Same: <b>${data.retained}</b></span>
    </div>
    ${data.unfollowed.length ? `
    <div class="info-section" style="margin-top:1rem">
      <h3 style="color:#f87171">😞 Unfollowed (${data.unfollowed.length})</h3>
      <p style="font-size:0.75rem;color:var(--muted);margin-bottom:0.75rem">
        Comparing <b>${esc(oldS?.label||oldS?.imported_at)}</b> → <b>${esc(newS?.label||newS?.imported_at)}</b>
      </p>
      <div class="ig-entries-grid">${data.unfollowed.map(igCard).join('')}</div>
    </div>` : '<div style="padding:1rem;color:#4ade80;font-weight:600">✅ Nobody unfollowed!</div>'}
    ${data.new.length ? `
    <div class="info-section" style="margin-top:1rem">
      <h3 style="color:#4ade80">🎉 New (${data.new.length})</h3>
      <div class="ig-entries-grid">${data.new.map(igCard).join('')}</div>
    </div>` : ''}`;
}

// ════════ Entry Point ════════
async function init() {
  await loadPerson();
  await loadIg();
}

init();
// ── Category ──────────────────────────────────────────────────────────────────
const CAT_LABELS = {
  friend:'👋 Friends', close_friend:'💛 Close Friends',
  related:'🔗 Related to Friend/Close Friend',
  random:'🌐 Random (Found Online)', misc:'🗂️ Misc.', archived:'📦 Archived',
};
const CAT_COLORS = {
  friend:'#a78bfa', close_friend:'#fbbf24', related:'#38bdf8',
  random:'#34d399', misc:'#f472b6', archived:'#5a5a7a',
};

function updateCatBadge(cat) {
  const badge = document.getElementById('person-cat-badge');
  if (!badge) return;
  const c = cat || 'random';
  badge.textContent = CAT_LABELS[c] || c;
  badge.style.background = (CAT_COLORS[c] || '#888') + '22';
  badge.style.color = CAT_COLORS[c] || '#888';
  badge.style.borderColor = (CAT_COLORS[c] || '#888') + '44';
  badge.dataset.cat = c;
}

function openCatModal() {
  const current = personData?.category || 'random';
  const sel = document.getElementById('cat-select');
  if (sel) sel.value = current;
  document.getElementById('cat-modal')?.classList.add('open');
}

document.addEventListener('DOMContentLoaded', () => {
  const catModalClose = document.getElementById('cat-modal-close');
  const catModal      = document.getElementById('cat-modal');
  const catForm       = document.getElementById('cat-form');

  if (catModalClose) catModalClose.addEventListener('click', () => catModal?.classList.remove('open'));
  if (catModal) catModal.addEventListener('click', e => { if (e.target === catModal) catModal.classList.remove('open'); });

  if (catForm) catForm.addEventListener('submit', async e => {
    e.preventDefault();
    const newCat = document.getElementById('cat-select').value;
    const fd = new FormData();
    fd.append('category', newCat);
    try {
      const r = await fetch(`/api/people/${pid}/category`, { method: 'PATCH', body: fd });
      if ((await r.json()).ok) {
        personData.category = newCat;
        updateCatBadge(newCat);
        catModal.classList.remove('open');
        showToast && showToast('Category updated ✓');
      }
    } catch { alert('Failed to update category'); }
  });
});
