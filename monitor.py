import os
import re
import requests
import feedparser
from datetime import datetime, timezone
from urllib.parse import unquote

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
TWITTER_USERNAME = os.environ["TWITTER_USERNAME"]
LAST_ID_FILE = "last_tweet_id.txt"

# Nitter instances tried in order until one returns entries
RSSHUB_INSTANCES = [
    f"https://nitter.net/{TWITTER_USERNAME}/rss",
    f"https://nitter.privacydev.net/{TWITTER_USERNAME}/rss",
    f"https://nitter.poast.org/{TWITTER_USERNAME}/rss",
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


def _iso_timestamp(entry):
    """Return an ISO 8601 timestamp Discord accepts (e.g. 2026-04-09T10:00:00+00:00)."""
    parsed = entry.get("published_parsed")  # time.struct_time in UTC from feedparser
    if parsed:
        return datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def _clean_text(entry):
    """Convert nitter RSS HTML to clean plain text, preserving line breaks."""
    raw = entry.get("summary", entry.get("title", ""))
    text = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _x_link(entry):
    """Rewrite nitter link to x.com."""
    nitter = entry.get("link", "")
    x = re.sub(r"https?://[^/]+/", "https://x.com/", nitter, count=1)
    return x or f"https://x.com/{TWITTER_USERNAME}"


def _image_url(entry):
    """Return the URL of the first image in the entry's HTML summary, or None."""
    raw = entry.get("summary", "")
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw, re.IGNORECASE)
    if not match:
        return None
    url = match.group(1)
    # Nitter proxies images — rewrite to the direct twimg CDN URL Discord can embed
    # e.g. https://nitter.net/pic/media%2FHFj1yg4WAAA0PUw.jpg
    #   -> https://pbs.twimg.com/media/HFj1yg4WAAA0PUw.jpg
    url = re.sub(r"https?://[^/]+/pic/(.+)", lambda m: "https://pbs.twimg.com/" + unquote(m.group(1)), url)
    return url


def send_to_discord(entry):
    text = _clean_text(entry)
    if len(text) > 1800:
        text = text[:1797] + "..."

    link = _x_link(entry)
    image = _image_url(entry)

    embed = {
        "author": {
            "name": f"@{TWITTER_USERNAME}",
            "url": f"https://x.com/{TWITTER_USERNAME}",
        },
        "title": "View on X \u2192",
        "url": link,
        "description": text,
        "color": 0x000000,
        "footer": {"text": "X (Twitter)"},
        "timestamp": _iso_timestamp(entry),
    }

    if image:
        embed["image"] = {"url": image}

    payload = {"embeds": [embed]}

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
