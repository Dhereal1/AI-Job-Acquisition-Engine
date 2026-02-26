# jobbot 🤖

Local Telegram job-hunting bot. Monitors channels + RSS feeds, scores posts against your skill profile, and delivers matched jobs with ready-to-send draft proposals to your Saved Messages.

**No auto-DMs. No auto-apply. You always send manually.**

---

## Quick Start

### 1. Get Telegram API credentials (free, 2 min)
1. Go to https://my.telegram.org/apps
2. Create an app (name doesn't matter)
3. Copy `api_id` and `api_hash`

### 2. Create your credentials file
```bash
cp config/credentials.yaml.example config/credentials.yaml
# Edit with your api_id and api_hash
```

### 3. Edit your profile
```bash
nano config/profile.yaml
# Update your_info section with your name, portfolio, timezone
```

### 4. Install and initialize
```bash
pip install -r requirements.txt
python scripts/init_db.py
```

### 5. Discover channels to monitor
```bash
python scripts/discover.py
# Lists all your Telegram chats → select which ones to monitor
```

### 6. Run the bot
```bash
python bot.py
```
First run will ask for your phone number and a 2FA code. After that, it's automatic.

---

## How It Works

```
Telegram channels → Listener → Scorer → Filter → Draft → Notify (Saved Messages)
RSS feeds ────────────────────────────────────────────────────────────────────────┘
```

1. **Listener** watches configured channels for new messages
2. **Scorer** runs keyword matching (must_have × 6pts, nice_to_have × 3pts, negative × -8pts)
3. **Filter** drops posts below `thresholds.notify` (default: 14)
4. **Draft generator** picks the best template based on matched keywords
5. **Notifier** sends a formatted message to your Saved Messages with score + excerpt + draft

---

## Configuration

### `config/profile.yaml` — Your profile and scoring weights
- Edit `keywords.must_have` and `keywords.nice_to_have` to match your stack
- Edit `negative_keywords` to filter roles you don't want
- Edit `your_info` with your actual details
- Adjust `thresholds.notify` to get more or fewer alerts

### `config/sources.yaml` — What to monitor
- Add/remove channels in the `channels` list
- Add/remove RSS feeds in `rss_feeds`

### `config/templates.yaml` — Proposal drafts
- Edit the templates in `templates.templates` to match your voice
- The bot auto-selects the best template based on matched keywords
- Add new template rules in `template_rules`

---

## Scripts

| Script | Description |
|--------|-------------|
| `python bot.py` | Run the main Telegram listener |
| `python scripts/discover.py` | Browse your chats, add to sources.yaml |
| `python scripts/rss_poller.py` | Run RSS polling separately |
| `python scripts/review.py` | Browse saved matches in terminal |
| `python scripts/review.py --min 20` | Show only strong matches (score ≥ 20) |
| `python scripts/init_db.py` | Initialize/reset the database |
| `python3 dashboard_cli.py --min 14 --status pending` | CLI dashboard with filters |
| `uvicorn dashboard_web:app --reload` | Web dashboard for review in browser |

---

## Dashboards

### CLI dashboard
```bash
python3 dashboard_cli.py --min 14 --status pending --limit 30
python3 dashboard_cli.py --details --limit 5
```

### Web dashboard (FastAPI)
```bash
uvicorn dashboard_web:app --reload
```

Open `http://127.0.0.1:8000` to filter jobs, inspect details, and toggle `pending/sent`.

---

## Data

All data is stored locally in `data/`:
- `jobs.db` — SQLite database with all matched posts
- `jobbot.session` — Telethon session (keep safe, don't share)
- `jobbot.log` — Log file

---

## Finding Good Channels to Monitor

Use [Telemetr.me](https://telemetr.me) to discover channels. Search for:
- `remote backend jobs`
- `python fastapi jobs`
- `web3 dev jobs`
- `telegram bot developer`
- `TON jobs`

Then use `python scripts/discover.py` to add them after you've joined.

---

## Safety Notes

- This bot **never auto-sends DMs** — you always manually send drafts
- Uses your personal Telegram account via Telethon (user-mode, not bot-mode)
- Don't monitor too many very-high-volume channels or Telegram may rate-limit you
- Never commit `credentials.yaml` or `.session` files to git
