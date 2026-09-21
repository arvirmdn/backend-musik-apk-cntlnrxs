# Musikin

Backend FastAPI + yt-dlp buat search & stream audio dari YouTube, plus riwayat
("Baru diputar") dan playlist. Frontend vanilla JS bergaya Spotify di folder `static/`.

## Cara pakai (dari HP, tanpa komputer)

1. Buka github.com, buat repo baru (misal `musikin`).
2. Klik "Add file" > "Upload files", extract zip ini di HP dulu, lalu upload
   SEMUA isinya (`main.py`, `requirements.txt`, `Procfile`, folder `static/`
   beserta isinya). Commit ke branch `main`.
3. Buka railway.app, login pakai akun GitHub, pilih **New Project** >
   **Deploy from GitHub repo**, pilih repo `musikin`.
4. Railway otomatis kebaca `requirements.txt` (Python) dan `Procfile` buat
   start command-nya (`uvicorn main:app --host 0.0.0.0 --port $PORT`) — tidak
   perlu diisi manual.
5. Setelah build selesai, buka tab **Settings > Networking**, klik
   **Generate Domain**. Railway kasih URL publik, misalnya:
   `https://musikin-production.up.railway.app`
6. Buka URL itu di browser — harusnya langsung muncul halaman Musikin.
   URL ini juga yang dipakai buat nyambungin menu Musik di aplikasi
   Contolonerxs.

## Endpoint API

- `GET /api/search?q=...` — cari lagu, balikin list `{id, title, artist, thumbnail, duration}`
- `GET /api/stream/{video_id}` — stream audio (dipakai langsung di tag `<audio>` / player)
- `GET /api/history` — riwayat "Baru diputar" (maks 50 terakhir)
- `POST /api/history` — tambah lagu ke riwayat (dipanggil otomatis pas mulai muter)
- `DELETE /api/history` — hapus semua riwayat
- `GET /api/playlists` — list semua playlist
- `POST /api/playlists` — buat playlist baru `{name}`
- `PUT /api/playlists/{id}` — ubah nama playlist `{name}`
- `DELETE /api/playlists/{id}` — hapus playlist
- `POST /api/playlists/{id}/tracks` — tambah lagu ke playlist `{track: {...}}`
- `DELETE /api/playlists/{id}/tracks/{track_id}` — hapus lagu dari playlist
- `POST /api/auth/register` — daftar akun baru `{username, password}` → `{username, token}`
- `POST /api/auth/login` — masuk `{username, password}` → `{username, token}`
- `GET /api/auth/me?token=...` — cek sesi token masih valid → `{username}`
- `POST /api/auth/logout` — keluar `{token}`

## Catatan

- Data riwayat, playlist, dan akun disimpan di file `db.json` (dibuat otomatis
  di server). Ini storage sederhana single-user/file-based — cukup buat
  pemakaian sendiri.
- Sandi akun disimpan sebagai hash (PBKDF2-SHA256 + salt per akun), bukan
  plain text.
- **Penting:** kalau route `/api/auth/*` di atas belum ada di server yang
  ter-deploy (versi lama), request `POST` ke path itu bakal "kepental" ke
  static file handler (`app.mount("/", StaticFiles(...))` di baris paling
  bawah `main.py`) — dan StaticFiles cuma terima method `GET`/`HEAD`, jadi
  balikin error `405 Method Not Allowed`. Kalau ketemu error ini di app,
  berarti `main.py` di GitHub/Railway belum sinkron dengan versi terbaru —
  upload ulang `main.py` ini ke repo, biarin Railway auto-deploy ulang.
- Kalau volume Railway di-reset (redeploy dari awal tanpa persistent disk),
  `db.json` bisa ikut kehapus. Untuk data yang lebih awet, nanti bisa
  di-upgrade ke database beneran (misal SQLite dengan volume, atau Postgres).
