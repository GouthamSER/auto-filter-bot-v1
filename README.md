# 🎬 auto-filter-bot-v1

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/Pyrogram-v2-green?style=for-the-badge&logo=telegram&logoColor=white"/>
  <img src="https://img.shields.io/badge/MongoDB-Motor-brightgreen?style=for-the-badge&logo=mongodb&logoColor=white"/>
  <img src="https://img.shields.io/badge/Deploy-Heroku%20%7C%20Render%20%7C%20Koyeb-purple?style=for-the-badge"/>
</p>

<p align="center">
  A powerful Telegram media search bot — search movies and files directly in PM or any group, with paginated results, auto-delete, broadcast, user tracking, and deep-link file delivery.
</p>

---

## ✨ Features

| Feature | Description |
|---|---|
| 💬 **PM Search** | Type any name → paginated file buttons → tap to receive instantly |
| 👥 **Group Search** | Results shown in group → tap → file delivered to your PM via deep-link |
| 🔗 **Deep-Link Delivery** | Group buttons use `t.me/bot?start=<file_id>` — works even if user never started bot |
| ◀▶ **Prev / Next Pages** | Pagination with live page counter — only the searcher can press PREV/NEXT |
| 🗑 **Auto-Delete** | Files auto-delete after configurable time to avoid copyright issues |
| 📌 **Save Reminder** | Users instructed to forward to Saved Messages before deletion |
| 👤 **User Tracking** | Every `/start` user is saved to DB; new users trigger a log channel notification |
| 📢 **Broadcast** | Send any message (text, photo, video, etc.) to all registered users |
| 📡 **Auto Index** | New files posted in watched channels saved to DB instantly |
| 🛠 **Admin Commands** | Full suite: `/index`, `/setskip`, `/total`, `/users`, `/broadcast`, `/delete`, `/channel`, `/logs` |
| 🌐 **Inline Mode** | Search via `@bot query` in any chat |
| 🔒 **Force Subscribe** | Optionally require users to join a channel before access |
| 🌍 **Always Alive** | Built-in `aiohttp` web server — compatible with Render & Koyeb (no sleep) |

---

## 🖼 Preview

### Group Search
```
User: Kumki

Bot:
  🔎 Results for: Kumki
  📁 Found: 9 file(s)
  👇 Tap a file → you'll be taken to my PM where it will be sent!

  [1.59 GB]- 🎬 -Kumki 2 (2025) Tamil HQ HDRip 1080p HEVC x…
  [1.38 GB]- 🎬 -Kumki 2 (2025) Tamil HQ HDRip 720p x264 (D…
  [904.43 MB]- 🎬 -Kumki 2 (2025) Tamil HQ HDRip 720p HEVC …
  ──────────────────────────────────────────
  [🗂 1/2]   [NEXT ▶]
```

### File Caption in PM
```
🎬 Kumki 2 (2025) Tamil HQ HDRip 1080p HEVC x265.mkv
📦 Size: 1.59 GB
🗂 Type: Video

⚠️ This file will be auto-deleted in 5 minute(s) to avoid copyright issues.
📌 Forward it to your Saved Messages to keep it forever!

[💾 Save to Saved Messages]
```

### New User Notification in Log Channel
```
👤 New User Started Bot!

🆔 ID: 123456789
📛 Name: John Doe
🔗 Username: @johndoe
📅 Joined: 12 Mar 2026 • 10:45 UTC

👥 Total Users: 142
```

### Broadcast Progress
```
📢 Broadcasting…

[████░░░░░░] 40%
Done: 400/1000

✅ Sent: 385
🚫 Blocked: 12  ← auto-removed from DB
❌ Failed: 3

[⛔ Cancel]
```

---

## 🚀 Deploy

### Heroku
[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

1. Click the button above
2. Fill in the required environment variables
3. Deploy — uses `heroku.yml` (container stack) → `web: python main.py`

> **Note:** Switch your Heroku app to the container stack first:
> ```bash
> heroku stack:set container -a <your-app>
> git push heroku main
> ```

### Render / Koyeb
1. Connect your GitHub repo
2. Set **Start Command:** `python main.py`
3. Set **Health Check URL:** `/health`
4. Add all environment variables
5. Deploy — the built-in web server keeps the container alive permanently

### Manual / VPS
```bash
git clone https://github.com/GouthamSER/auto-filter-bot-v1
cd auto-filter-bot-v1
pip install -r requirements.txt
cp sample.env .env
# Edit .env with your values
python main.py
```

---

## ⚙️ Environment Variables

### Required
| Variable | Description |
|---|---|
| `API_ID` | Get from [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | Get from [my.telegram.org](https://my.telegram.org) |
| `BOT_TOKEN` | Get from [@BotFather](https://t.me/BotFather) |
| `DATABASE_URI` | MongoDB connection string (e.g. `mongodb+srv://...`) |
| `ADMINS` | Space-separated Telegram user IDs — e.g. `123456 789012` |
| `CHANNELS` | Space-separated channel IDs the bot watches — e.g. `-100123 -100456` |
| `LOG_CHANNEL` | Channel ID for bot logs + new user notifications |

### Optional
| Variable | Default | Description |
|---|---|---|
| `DATABASE_NAME` | `MediaSearchDB` | MongoDB database name |
| `COLLECTION_NAME` | `Telegram_files` | MongoDB collection name |
| `SESSION` | `MediaSearchBot` | Pyrogram session name |
| `MAX_RESULTS` | `10` | Files shown per page |
| `AUTO_DELETE_TIME` | `300` | Seconds before file is deleted (300 = 5 min) |
| `CACHE_TIME` | `300` | Inline query cache duration in seconds |
| `USE_CAPTION_FILTER` | `false` | Also search inside file captions |
| `AUTH_CHANNEL` | — | Force users to join this channel ID before using bot |
| `URL` | — | Your app's public URL for keep-alive pings |
| `PORT` | `8080` | Web server port (auto-set by Render/Koyeb/Heroku) |

### Custom Messages (Optional)
| Variable | Description |
|---|---|
| `START_MSG` | Custom welcome message. Supports `{mention}`, `{username}`, `{first_name}` |
| `FORCE_SUB_MSG` | Message shown when user hasn't joined `AUTH_CHANNEL` |

---

## 🤖 Bot Commands

### Everyone
| Command | Description |
|---|---|
| `/start` | Welcome message + inline search buttons |

> 💡 `/help` and `/status` are available as **inline buttons** on the start message — not slash commands.

### Admins Only
| Command | Description |
|---|---|
| `/index` | Bulk-index a channel range (two-step wizard — no userbot needed) |
| `/cancelindex` | Abort the index wizard mid-setup |
| `/setskip <N>` | Set message-ID offset before indexing (resume from a specific point) |
| `/total` | Total files saved in database |
| `/users` | Total registered users count |
| `/broadcast` | Send a message to all users (reply to any message, or inline text) |
| `/cancelbroadcast` | Stop a running broadcast mid-way |
| `/channel` | List all watched/indexed channels |
| `/delete` | Reply to any media message → removes it from DB |
| `/logs` | Download the bot log file |

### Setting Commands via BotFather

Open [@BotFather](https://t.me/BotFather) → your bot → **Edit Bot** → **Edit Commands** → paste:

```
start - Start the bot / get welcome message
index - Index a channel range (wizard)
cancelindex - Abort a running index wizard
setskip - Set message-ID offset for indexing
total - Total files in the database
users - Total registered users
broadcast - Broadcast a message to all users
cancelbroadcast - Stop an in-progress broadcast
channel - List watched/indexed channels
delete - Remove a file from the database (reply to it)
logs - Get the bot log file
```

Or use the included script to set scoped commands automatically
(regular users only see `/start`, admins see the full list):

```bash
export BOT_TOKEN=your_token
export ADMINS="123456789 987654321"
python set_commands.py
```

---

## 📢 Broadcast Usage

**Option 1 — Copy any message (photo, video, sticker, text…):**
```
Reply to any message with /broadcast
```

**Option 2 — Inline text only:**
```
/broadcast 🎉 New movies added! Go search now!
```

Bot shows a **preview with recipient count** and **Confirm / Cancel** buttons before sending. Live progress updates during send. Blocked/deactivated users are **automatically removed** from the database.

---

## 🔍 Search Tips

- **Basic:** type any movie or file name in PM or any group
- **Filter by type:** `movie name | video` or `song name | audio` or `doc name | document`
- **Inline anywhere:** `@YourBot movie name` in any chat
- **Pagination:** tap **◀ PREV** / **NEXT ▶** to browse all results — only the user who searched can press these
- **Group:** results appear in the group; tapping a file delivers it to your PM

---

## 📁 Project Structure

```
auto-filter-bot-v1/
├── main.py                 ← Bot entry point + aiohttp web server + keep-alive
├── config.py               ← All configuration via environment variables
├── set_commands.py         ← One-shot script to set BotFather command scopes
├── requirements.txt
├── Dockerfile              ← Docker image (used by Heroku container stack)
├── heroku.yml              ← Heroku container stack config
├── sample.env              ← Example environment variables
│
├── database/
│   ├── __init__.py
│   └── db.py               ← MongoDB motor (Media + Users collections)
│
└── plugins/
    ├── __init__.py
    ├── start.py            ← /start + deep-link file delivery + force-subscribe + help/status buttons
    ├── search.py           ← PM & group search, pagination (owner-only), auto-delete
    ├── inline.py           ← Inline mode search
    ├── channel.py          ← Auto-index new files from watched channels
    ├── users.py            ← User tracking + new user log channel notification
    ├── broadcast.py        ← /broadcast with live progress + cancel + auto-cleanup
    └── admin.py            ← /index wizard + all other admin commands
```

---

## 🗄 Database Collections

| Collection | Purpose |
|---|---|
| `Telegram_files` | All indexed media files (searchable) |
| `users` | All registered users — used for broadcast & analytics |

---

## 🛠 Tech Stack

- **[Pyrogram v2](https://github.com/pyrogram/pyrogram)** — Telegram MTProto client
- **[Motor](https://motor.readthedocs.io/)** — Async MongoDB driver
- **[aiohttp](https://docs.aiohttp.org/)** — Async web server (keep-alive for Render/Koyeb)
- **[MongoDB Atlas](https://www.mongodb.com/atlas)** — Cloud database (free tier works)

---

## 👨‍💻 Credits

| Role | Person |
|---|---|
| **Maintainer & Rewritten By** | [GouthamSER](https://github.com/GouthamSER) |
| Original Concept | Media-Search-bot |

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/GouthamSER">GouthamSER</a>
</p>
