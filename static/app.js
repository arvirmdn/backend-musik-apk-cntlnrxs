const API = ""; // sama origin dengan frontend

const audio = document.getElementById("audio");
const searchInput = document.getElementById("searchInput");
const searchResults = document.getElementById("searchResults");
const historyResults = document.getElementById("historyResults");
const playlistResults = document.getElementById("playlistResults");
const playlistList = document.getElementById("playlistList");
const playlistViewTitle = document.getElementById("playlistViewTitle");
const addToPlaylistSelect = document.getElementById("addToPlaylistSelect");

const views = {
  search: document.getElementById("searchView"),
  history: document.getElementById("historyView"),
  playlist: document.getElementById("playlistView"),
};

let currentTrack = null;
let isPlaying = false;
let activePlaylistId = null;
let playlists = [];

// ---------------------------------------------------------------------------
// Navigasi antar view
// ---------------------------------------------------------------------------
function showView(name) {
  Object.values(views).forEach((v) => v.classList.add("hidden"));
  views[name].classList.remove("hidden");
  document.querySelectorAll(".nav-item").forEach((btn) => btn.classList.remove("active"));
  const navBtn = document.querySelector(`.nav-item[data-view="${name}"]`);
  if (navBtn) navBtn.classList.add("active");
}

document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    showView(btn.dataset.view);
    if (btn.dataset.view === "history") loadHistory();
  });
});

// ---------------------------------------------------------------------------
// Render list track (dipakai di search / history / playlist)
// ---------------------------------------------------------------------------
function formatDuration(sec) {
  sec = sec || 0;
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

function renderTrackList(container, tracks, { showAdd = true } = {}) {
  container.innerHTML = "";
  if (!tracks.length) {
    container.innerHTML = `<div style="color:var(--text-dim);padding:12px;">Belum ada lagu di sini.</div>`;
    return;
  }
  tracks.forEach((track) => {
    const row = document.createElement("div");
    row.className = "track-row";
    row.innerHTML = `
      <img src="${track.thumbnail || ""}" alt="" />
      <div class="meta">
        <div class="t-title">${track.title}</div>
        <div class="t-artist">${track.artist || ""}</div>
      </div>
      <div class="t-duration">${formatDuration(track.duration)}</div>
      ${showAdd ? `<button class="add-btn" title="Tambah ke playlist">+</button>` : ""}
    `;
    row.addEventListener("click", (e) => {
      if (e.target.classList.contains("add-btn")) return;
      playTrack(track);
    });
    if (showAdd) {
      row.querySelector(".add-btn").addEventListener("click", (e) => {
        e.stopPropagation();
        quickAddToPlaylist(track);
      });
    }
    container.appendChild(row);
  });
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------
let searchTimer = null;
searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  const q = searchInput.value.trim();
  if (!q) {
    searchResults.innerHTML = "";
    return;
  }
  searchTimer = setTimeout(() => doSearch(q), 400);
});

async function doSearch(q) {
  showView("search");
  searchResults.innerHTML = `<div style="color:var(--text-dim);padding:12px;">Mencari...</div>`;
  try {
    const res = await fetch(`${API}/api/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    renderTrackList(searchResults, data.results || []);
  } catch (err) {
    searchResults.innerHTML = `<div style="color:var(--text-dim);padding:12px;">Gagal mencari lagu.</div>`;
  }
}

// ---------------------------------------------------------------------------
// Riwayat ("Baru diputar")
// ---------------------------------------------------------------------------
async function loadHistory() {
  const res = await fetch(`${API}/api/history`);
  const data = await res.json();
  renderTrackList(historyResults, data.history || []);
}

document.getElementById("clearHistoryBtn").addEventListener("click", async () => {
  await fetch(`${API}/api/history`, { method: "DELETE" });
  loadHistory();
});

async function pushHistory(track) {
  await fetch(`${API}/api/history`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(track),
  });
}

// ---------------------------------------------------------------------------
// Playlist
// ---------------------------------------------------------------------------
async function loadPlaylists() {
  const res = await fetch(`${API}/api/playlists`);
  const data = await res.json();
  playlists = data.playlists || [];
  renderPlaylistSidebar();
  renderPlaylistSelect();
}

function renderPlaylistSidebar() {
  playlistList.innerHTML = "";
  playlists.forEach((p) => {
    const li = document.createElement("li");
    li.textContent = p.name;
    li.className = p.id === activePlaylistId ? "active" : "";
    li.addEventListener("click", () => openPlaylist(p.id));
    playlistList.appendChild(li);
  });
}

function renderPlaylistSelect() {
  addToPlaylistSelect.innerHTML = `<option value="">+ Tambah ke playlist</option>`;
  playlists.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.name;
    addToPlaylistSelect.appendChild(opt);
  });
}

function openPlaylist(id) {
  activePlaylistId = id;
  const p = playlists.find((x) => x.id === id);
  if (!p) return;
  playlistViewTitle.textContent = p.name;
  renderTrackList(playlistResults, p.tracks || []);
  showView("playlist");
  renderPlaylistSidebar();
}

document.getElementById("newPlaylistBtn").addEventListener("click", async () => {
  const name = prompt("Nama playlist baru:");
  if (!name) return;
  const res = await fetch(`${API}/api/playlists`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const playlist = await res.json();
  await loadPlaylists();
  openPlaylist(playlist.id);
});

document.getElementById("renamePlaylistBtn").addEventListener("click", async () => {
  if (!activePlaylistId) return;
  const p = playlists.find((x) => x.id === activePlaylistId);
  const name = prompt("Nama baru:", p ? p.name : "");
  if (!name) return;
  await fetch(`${API}/api/playlists/${activePlaylistId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  await loadPlaylists();
  openPlaylist(activePlaylistId);
});

async function quickAddToPlaylist(track) {
  if (!playlists.length) {
    alert("Buat playlist dulu ya (tombol + di sidebar).");
    return;
  }
  const names = playlists.map((p, i) => `${i + 1}. ${p.name}`).join("\n");
  const choice = prompt(`Tambah ke playlist mana?\n${names}\n\nKetik nomornya:`);
  const idx = parseInt(choice, 10) - 1;
  if (isNaN(idx) || !playlists[idx]) return;
  await addTrackToPlaylist(playlists[idx].id, track);
}

async function addTrackToPlaylist(playlistId, track) {
  await fetch(`${API}/api/playlists/${playlistId}/tracks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ track }),
  });
  await loadPlaylists();
  if (activePlaylistId === playlistId) openPlaylist(playlistId);
}

addToPlaylistSelect.addEventListener("change", async () => {
  const playlistId = addToPlaylistSelect.value;
  if (!playlistId || !currentTrack) return;
  await addTrackToPlaylist(playlistId, currentTrack);
  addToPlaylistSelect.value = "";
});

// ---------------------------------------------------------------------------
// Player (mini + full sheet)
// ---------------------------------------------------------------------------
const miniPlayer = document.getElementById("miniPlayer");
const miniThumb = document.getElementById("miniThumb");
const miniTitle = document.getElementById("miniTitle");
const miniArtist = document.getElementById("miniArtist");
const miniPlayPause = document.getElementById("miniPlayPause");

const playerSheet = document.getElementById("playerSheet");
const sheetThumb = document.getElementById("sheetThumb");
const sheetTitle = document.getElementById("sheetTitle");
const sheetArtist = document.getElementById("sheetArtist");
const sheetPlayPause = document.getElementById("sheetPlayPause");
const seekBar = document.getElementById("seekBar");
const timeCurrent = document.getElementById("timeCurrent");
const timeDuration = document.getElementById("timeDuration");

function playTrack(track) {
  currentTrack = track;
  audio.src = `${API}/api/stream/${track.id}`;
  audio.play();
  isPlaying = true;

  miniThumb.src = track.thumbnail || "";
  miniTitle.textContent = track.title;
  miniArtist.textContent = track.artist || "";
  sheetThumb.src = track.thumbnail || "";
  sheetTitle.textContent = track.title;
  sheetArtist.textContent = track.artist || "";

  miniPlayer.classList.remove("hidden");
  updatePlayPauseIcons();
  pushHistory(track);
}

function togglePlayPause() {
  if (!currentTrack) return;
  if (isPlaying) {
    audio.pause();
  } else {
    audio.play();
  }
  isPlaying = !isPlaying;
  updatePlayPauseIcons();
}

function updatePlayPauseIcons() {
  const icon = isPlaying ? "⏸" : "▶";
  miniPlayPause.textContent = icon;
  sheetPlayPause.textContent = icon;
}

miniPlayPause.addEventListener("click", togglePlayPause);
sheetPlayPause.addEventListener("click", togglePlayPause);

document.getElementById("expandPlayer").addEventListener("click", () => {
  playerSheet.classList.remove("hidden");
});
document.getElementById("collapsePlayer").addEventListener("click", () => {
  playerSheet.classList.add("hidden");
});

audio.addEventListener("timeupdate", () => {
  if (!audio.duration) return;
  seekBar.value = (audio.currentTime / audio.duration) * 100;
  timeCurrent.textContent = formatDuration(audio.currentTime);
  timeDuration.textContent = formatDuration(audio.duration);
});

seekBar.addEventListener("input", () => {
  if (!audio.duration) return;
  audio.currentTime = (seekBar.value / 100) * audio.duration;
});

audio.addEventListener("ended", () => {
  isPlaying = false;
  updatePlayPauseIcons();
});

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
loadPlaylists();
