# x-webhook

Monitors an X (Twitter) account via Nitter RSS and posts new tweets to a Discord channel using a webhook. Runs automatically every 15 minutes via GitHub Actions.

## How it works

1. Fetches the Nitter RSS feed for the configured account (tries multiple instances in order)
2. Compares entries against the last seen tweet ID stored in `last_tweet_id.txt`
3. Posts any new tweets to Discord as embeds, oldest first
4. Commits the updated `last_tweet_id.txt` back to the repo

## Setup

### 1. Fork / clone this repo

### 2. Add GitHub secrets and variables

In your repo go to **Settings → Secrets and variables → Actions**:

| Type | Name | Value |
|------|------|-------|
| Secret | `DISCORD_WEBHOOK` | Your Discord webhook URL |
| Variable | `TWITTER_USERNAME` | X username to monitor (without `@`) |

### 3. Enable GitHub Actions

The workflow runs automatically on push. It will also trigger every 15 minutes via the cron schedule.

You can also trigger a manual run from the **Actions** tab using **Run workflow**.

## Local testing

```bash
pip install requests feedparser

export DISCORD_WEBHOOK="https://discord.com/api/webhooks/..."
export TWITTER_USERNAME="someuser"

python monitor.py
```

To force a test post (ignores the last seen ID):

```bash
echo "" > last_tweet_id.txt
python monitor.py
```

## Configuration

To monitor a different account, update the `TWITTER_USERNAME` variable in GitHub Actions settings. No code changes needed.

To add or swap Nitter instances, edit the `RSSHUB_INSTANCES` list in `monitor.py`. A list of public instances is maintained at [nitter.net/about](https://nitter.net/about).
