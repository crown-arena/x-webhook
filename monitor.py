import os
import re
import requests
import feedparser
from datetime import datetime, timezone

DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
TWITTER_USERNAME = os.environ["TWITTER_USERNAME"]
LAST_ID_FILE = "last_tweet_id.txt"

# Multiple public RSSHub instances — tried in order until one works
RSSHUB_INSTANCES = [
    f"https://rsshub.app/twitter/user/{TWITTER_USERNAME}",
    f"https://rsshub.rssforever.com/twitter/user/{TWITTER_USERNAME}",
    f"https://hub.slarker.me/twitter/user/{TWITTER_USERNAME}",
]


def fetch_feed():
    for url in RSSHUB_INSTANCES:
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                print(f"Fetched {len(feed.entries)} entries from {url}")
                return feed.entries
            else:
                print(f"No entries from {url}")
        except Exception as e:
            print(f"Error fetching {url}: {e}")
    return []


def get_last_id():
    try:
        with open(LAST_ID_FILE) as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def save_last_id(tweet_id):
    with open(LAST_ID_FILE, "w") as f:
        f.write(tweet_id)


def send_to_discord(entry):
    # Strip HTML tags from summary
    raw = entry.get("summary", entry.get("title", ""))
    text = re.sub(r"<[^>]+>", "", raw).strip()
    if len(text) > 500:
        text = text[:497] + "..."

    link = entry.get("link", f"https://x.com/{TWITTER_USERNAME}")

    payload = {
        "embeds": [
            {
                "author": {
                    "name": f"@{TWITTER_USERNAME}",
                    "url": f"https://x.com/{TWITTER_USERNAME}",
                },
                "description": f"{text}\n\n[View on X]({link})",
                "color": 0x1D9BF0,
                "footer": {"text": "X (Twitter)"},
                "timestamp": entry.get(
                    "published", datetime.now(timezone.utc).isoformat()
                ),
            }
        ]
    }

    resp = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
    resp.raise_for_status()


def main():
    entries = fetch_feed()
    if not entries:
        print("All RSS sources failed — skipping this run")
        return

    last_id = get_last_id()

    # Collect new entries (stop when we hit the last seen ID)
    new_entries = []
    for entry in entries:
        entry_id = entry.get("id") or entry.get("link", "")
        if entry_id == last_id:
            break
        new_entries.append((entry_id, entry))

    if not new_entries:
        print("No new tweets")
        return

    # Send oldest-first so Discord order is chronological
    for entry_id, entry in reversed(new_entries):
        try:
            send_to_discord(entry)
            print(f"Sent: {entry_id}")
        except Exception as e:
            # Stop here — next run will retry from this point
            print(f"Discord POST failed: {e}")
            return

    # Persist only after all sends succeed
    save_last_id(new_entries[0][0])
    print(f"Done. {len(new_entries)} new tweet(s) sent.")


if __name__ == "__main__":
    main()
