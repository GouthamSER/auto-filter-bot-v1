<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=6C63FF&height=200&section=header&text=Auto%20Filter%20Bot&fontSize=50&fontColor=ffffff&fontAlignY=38&desc=Telegram%20Media%20Search%20Bot&descAlignY=58&descAlign=50" width="100%"/>
</p>

<p align="center">
  <a href="https://github.com/GouthamSER/auto-filter-bot-v1/stargazers"><img src="https://img.shields.io/github/stars/GouthamSER/auto-filter-bot-v1?color=6C63FF&style=for-the-badge&logo=github"/></a>
  <a href="https://github.com/GouthamSER/auto-filter-bot-v1/fork"><img src="https://img.shields.io/github/forks/GouthamSER/auto-filter-bot-v1?color=FF6584&style=for-the-badge&logo=github"/></a>
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/Pyrogram-v2-29ABE2?style=for-the-badge&logo=telegram&logoColor=white"/>
  <img src="https://img.shields.io/badge/MongoDB-Motor-47A248?style=for-the-badge&logo=mongodb&logoColor=white"/>
  <img src="https://img.shields.io/badge/Deploy-Heroku%20%7C%20Render%20%7C%20Koyeb-430098?style=for-the-badge&logo=heroku&logoColor=white"/>
</p>

<p align="center">
  <b>A powerful Telegram media search bot.</b><br/>
  Search movies & files in PM or any group — paginated results, dual-database support,<br/>
  auto-delete, broadcast, user tracking, and deep-link file delivery.
</p>

---

## ✨ Features

<table>
<tr><td>💬 <b>PM Search</b></td><td>Type any name → paginated results → tap to receive instantly</td></tr>
<tr><td>👥 <b>Group Search</b></td><td>Results in group → tap → file delivered to PM via deep-link</td></tr>
<tr><td>🗄 <b>Dual Database</b></td><td>Optional second MongoDB — writes to DB2, searches DB2 first, falls back to DB1</td></tr>
<tr><td>◀▶ <b>Pagination</b></td><td>PREV / NEXT with live counter — only the searcher can scroll their own results</td></tr>
<tr><td>⏳ <b>Auto-Delete</b></td><td>Files auto-delete after configurable time to avoid copyright issues</td></tr>
<tr><td>📌 <b>Save Reminder</b></td><td>Users prompted to forward to Saved Messages before deletion</td></tr>
<tr><td>👤 <b>User Tracking</b></td><td>Every /start saved to DB — new users trigger log channel notification</td></tr>
<tr><td>📢 <b>Broadcast</b></td><td>Send any message type to all users — live progress, cancel button, auto-cleanup blocked users</td></tr>
<tr><td>📡 <b>Auto Index</b></td><td>Files posted in watched channels saved to DB instantly</td></tr>
<tr><td>🌐 <b>Inline Mode</b></td><td>Search via <code>@bot query</code> in any chat</td></tr>
<tr><td>🔒 <b>Force Subscribe</b></td><td>Require users to join a channel before access</td></tr>
<tr><td>🌍 <b>Always Alive</b></td><td>Built-in aiohttp web server — no sleep on Render & Koyeb</td></tr>
</table>

---

## 🗄 Dual Database

> Set `DATABASE_URI_2` to enable. Leave unset for normal single-DB mode — zero behaviour change.

```
┌─────────────────────────────────────────────────────┐
│                   Write Flow                        │
│                                                     │
│  New file / user  ──►  DB2 (if set)  ──►  DB1       │
│                        (primary write)  (fallback)  │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                   Search Flow                       │
│                                                     │
│  Query  ──►  DB2  ──► results? ──► YES  ──►  return │
│                              └──► NO   ──►  DB1     │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                  Delete / Count                     │
│                                                     │
│  /delete  ──►  removes from BOTH DBs                │
│  /total   ──►  DB1 count + DB2 count combined       │
└─────────────────────────────────────────────────────┘
```

---

## 🖼 Preview

<details>
<summary><b>Group Search</b></summary>

```
User: Kumki

🔎 Results for: Kumki
📁 Found: 9 file(s)
👇 Tap a file → you'll be taken to my PM where it will be sent!

[1.59 GB]- 🎬 -Kumki 2 (2025) Tamil HQ HDRip 1080p HEVC x…
[1.38 GB]- 🎬 -Kumki 2 (2025) Tamil HQ HDRip 720p x264 (D…
[904.43 MB]- 🎬 -Kumki 2 (2025) Tamil HQ HDRip 720p HEVC …

◀ PREV   [🗂 1/2]   NEXT ▶
```
</details>

<details>
<summary><b>File in PM</b></summary>

```
🎬 Kumki 2 (2025) Tamil HQ HDRip 1080p HEVC x265.mkv
📦 Size: 1.59 GB
🗂 Type: Video

⚠️ This file will be auto-deleted in 5 minute(s) to avoid copyright issues.
📌 Forward it to your Saved Messages to keep it forever!

[ 💾 Save to Saved Messages ]
```
</details>

<details>
<summary><b>Status Panel</b></summary>

```
╔══════════════════════╗
      📊 Bot Status
╚══════════════════════╝

🤖 Bot: @YourBot
🔗 Username: @yourbot

━━━━━━━━━━━━━━━━━━━━━━
📁 Total Files:  12,453
👥 Total Users:   1,284
━━━━━━━━━━━━━━━━━━━━━━

🗄 Database:  🟡 Dual DB (DB1 + DB2)
🟢 Status:  Online & Running
```
</details>

<details>
<summary><b>Broadcast Progress</b></summary>

```
📢 Broadcasting…

[████░░░░░░] 40%
Done: 400/1000

✅ Sent: 385
🚫 Blocked: 12  ← auto-removed from DB
❌ Failed: 3

[ ⛔ Cancel ]
```
</details>

<details>
<summary><b>New User Log</b></summary>

```
👤 New User Started Bot!

🆔 ID: 123456789
📛 Name: John Doe
🔗 Username: @johndoe
📅 Joined: 12 Mar 2026 • 10:45 UTC

👥 Total Users: 142
```
</details>

---

## 🚀 Deploy

### ☁️ Heroku (Container Stack)

```bash
# 1. Clone & push
git clone https://github.com/GouthamSER/auto-filter-bot-v1
cd auto-filter-bot-v1
heroku create your-app-name
heroku stack:set container -a your-app-name

# 2. Set env vars (or use Heroku dashboard)
heroku config:set API_ID=... API_HASH=... BOT_TOKEN=... -a your-app-name

# 3. Deploy
git push heroku main
```

### 🎨 Render / Koyeb

| Setting | Value |
|---|---|
| **Start Command** | `python main.py` |
| **Health Check** | `/health` |
| **Build Command** | `pip install -r requirements.txt` |

Add all env vars in the dashboard → Deploy.

### 🖥️ VPS / Local

```bash
git clone https://github.com/GouthamSER/auto-filter-bot-v1
cd auto-filter-bot-v1
pip install -r requirements.txt
cp sample.env .env
nano .env        # fill in your values
python main.py
```

---

## ⚙️ Environment Variables

### 🔴 Required

| Variable | Description |
|---|---|
| `API_ID` | From [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | From [my.telegram.org](https://my.telegram.org) |
| `BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) |
| `DATABASE_URI` | MongoDB URI — `mongodb+srv://user:pass@cluster...` |
| `ADMINS` | Space-separated user IDs — `123456 789012` |
| `CHANNELS` | Space-separated channel IDs to watch — `-100123 -100456` |
| `LOG_CHANNEL` | Channel ID for logs & new user alerts |

### 🟡 Dual Database (Optional)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URI_2` | — | Second MongoDB URI — **enables dual-DB mode** |
| `DATABASE_NAME_2` | same as DB1 | Database name for DB2 |
| `COLLECTION_NAME_2` | same as DB1 | Collection name for DB2 |

### 🔵 Optional

| Variable | Default | Description |
|---|---|---|
| `DATABASE_NAME` | `MediaSearchDB` | DB1 database name |
| `COLLECTION_NAME` | `tgfls` | DB1 collection name |
| `SESSION` | `MediaSearchBot` | Pyrogram session name |
| `MAX_RESULTS` | `10` | Files per page |
| `CACHE_TIME` | `300` | Inline query cache (seconds) |
| `USE_CAPTION_FILTER` | `false` | Search inside file captions too |
| `AUTH_CHANNEL` | — | Channel ID users must join first |
| `AUTH_USERS` | — | Extra whitelisted user IDs |
| `URL` | — | App public URL for keep-alive self-ping |
| `PORT` | `8080` | Web server port |
| `START_MSG` | built-in | Custom start message (`{mention}` `{username}` `{first_name}`) |
| `FORCE_SUB_MSG` | built-in | Custom force-subscribe message |

---

## 🤖 Bot Commands

### 👤 Users

| Command | Description |
|---|---|
| `/start` | Welcome message + search buttons |

> `Help` and `Status` are inline buttons on the start message.

### 🛠 Admins Only

| Command | Description |
|---|---|
| `/index` | Bulk-index a channel (two-step wizard, no userbot needed) |
| `/cancelindex` | Abort the index wizard |
| `/setskip <N>` | Set message-ID offset before indexing |
| `/total` | Total files in database (both DBs combined) |
| `/users` | Total registered users |
| `/broadcast` | Send any message to all users (reply or inline text) |
| `/cancelbroadcast` | Stop a running broadcast |
| `/channel` | List all watched channels |
| `/delete` | Reply to any media → remove from database |
| `/logs` | Download the bot log file |

### 📋 BotFather — Paste to set commands

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

Or run the included script to set scoped commands
(users see only `/start`, admins see full list):

```bash
export BOT_TOKEN=your_token
export ADMINS="123456789"
python set_commands.py
```

---

## 🔍 Search Tips

```
Basic search       →  just type the name
Filter by type     →  name | video   /   name | audio   /   name | document
Inline anywhere    →  @YourBot movie name
Pagination         →  ◀ PREV  [🗂 page/total]  NEXT ▶
Group delivery     →  tap result → bot sends file to your PM
```

---

## 📁 Project Structure

```
auto-filter-bot-v1/
├── main.py                  ← Entry point + aiohttp keep-alive server
├── config.py                ← All env var parsing
├── set_commands.py          ← One-shot BotFather command scope setter
├── Dockerfile               ← Container image
├── heroku.yml               ← Heroku container stack config
├── requirements.txt
├── sample.env
│
├── database/
│   └── db.py                ← Dual-DB motor driver (Media + Users)
│
└── plugins/
    ├── start.py             ← /start · Help · Status · deep-link delivery
    ├── search.py            ← PM & group search · pagination · auto-delete
    ├── inline.py            ← Inline query handler
    ├── channel.py           ← Auto-index files from watched channels
    ├── users.py             ← User tracking + log channel notifications
    ├── broadcast.py         ← /broadcast · progress · cancel · cleanup
    └── admin.py             ← /index wizard + all admin commands
```

---

## 🛠 Tech Stack

| Library | Purpose |
|---|---|
| [pyrotgfork](https://github.com/TelegramPlayGround/Pyrogram) | Telegram MTProto client (Pyrogram fork) |
| [TgCrypto](https://github.com/pyrogram/tgcrypto) | Fast C crypto for Pyrogram |
| [Motor](https://motor.readthedocs.io/) | Async MongoDB driver |
| [PyMongo](https://pymongo.readthedocs.io/) | MongoDB sync utilities |
| [aiohttp](https://docs.aiohttp.org/) | Async web server for keep-alive |

---

## 👨‍💻 Credits

| | |
|---|---|
| **Maintainer & Rewritten By** | [GouthamSER](https://github.com/GouthamSER) |
| Original Concept | Media-Search-bot |

---

## 📄 License

[MIT License](LICENSE) — free to use, modify, and distribute.

---

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=6C63FF&height=100&section=footer" width="100%"/>
</p>

<p align="center">
  Made with ❤️ by <a href="https://github.com/GouthamSER">GouthamSER</a>
</p>
