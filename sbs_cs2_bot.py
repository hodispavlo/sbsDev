import datetime
import json
import logging
import os
import time
from logging.handlers import RotatingFileHandler

import feedparser
import openai
import requests
from dateutil.parser import parse
from dotenv import load_dotenv

load_dotenv()

SEEN_TIME_FILE = "seen_time.json"

openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
RSS_URLS = [
    "https://www.hltv.org/rss/news",
    "https://liquipedia.net/counterstrike/Special:RecentChanges?feed=rss",
    "https://www.reddit.com/r/GlobalOffensive/.rss"
]
CHECK_INTERVAL = 600
seen_links = set()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        RotatingFileHandler("bot.log", maxBytes=5_000_000, backupCount=5),
        logging.StreamHandler()
    ]
)


def smart_trim(text: str, limit: int = 4096) -> str:
    if len(text) <= limit:
        return text

    trimmed = text[:limit]

    for punct in ['.', '!', '?', '\n']:
        idx = trimmed.rfind(punct)
        if idx != -1 and idx > limit * 0.7:
            return trimmed[:idx + 1].strip()

    return trimmed.strip()


def fetch_rss_entries(url: str):
    try:
        feed = feedparser.parse(url)
        if not feed.entries:
            logging.warning(f"No entries found in feed: {url}")
        return feed.entries
    except Exception as e:
        logging.error(f"Failed to fetch RSS from {url}: {e}")


def extract_image_url(entry):
    media = getattr(entry, 'media_content', None)
    if media and isinstance(media, list) and 'url' in media[0]:
        return media[0]['url']
    enc = getattr(entry, 'enclosures', None)
    if enc and isinstance(enc, list) and 'href' in enc[0]:
        return enc[0]['href']
    return None


def summarize_entry(entry):
    title = getattr(entry, "title", "")
    summary = getattr(entry, "summary", "")
    link = getattr(entry, "link", "")
    content = f"{title}\n{summary}"
    logging.info(f"Generating summary for: {title}")
    prompt = f"""

You are the editor of an esports Telegram channel — SBS CS2 — focused on CS2.

Your task:
1. Read the news item (title, link, summary, full text).
2. Write a short, punchy, and readable post in Russian(max 300 characters). The style should be fan-driven, a bit edgy, as if written by a CS2 player, not a journalist.
3. Do NOT use bold, markdown, or links — only plain Telegram-style formatting: emojis, line breaks, and bullet points.
4. Emphasize facts, statistics, and specifics — no exaggeration or twisting.
5. Where appropriate, insert a creative one-liner, meme phrase, or sarcastic comment (AI can improvise here).
6. At the end, add 1–2 interesting related facts (only if they are actually relevant — like a player’s birthday, a record, or a historical moment).
7. If there are no good facts — skip this section entirely.
8. Finish the post with a brief comment on the current state of the CS2 pro scene (meta shifts, roster chaos, tournament intensity).
9. If the news item includes an image — provide the image link in parentheses so the bot can use it separately.
8. Do NOT add any commentary on the overall state of the CS2 pro scene; omit any closing “meta shifts” or “scene is tense” lines.  
10. Avoid publishing duplicate or very similar news items if they were already posted recently by the bot.
11. Write the entire post in Russian, formatted as ready-to-post for a Telegram channel with no further editing required.
12. Target audience is located in Ukraine, all times of tournaments or matches start time should be specified in Kiyv time but not directly say it.Just time would be fine.
Important aspects for parsing and use:
  - Identification of key entities: Automatically recognize and extract names of players, team names, tournaments, cities, dates, and times.

  - Tone detection: Analyze text for positive, negative, or neutral context to adapt the post's style.

  - Information prioritization: Identify the most important aspects of the news (e.g., match winner, roster changes, significant achievements) for inclusion in the post.

  - Duplicate/similar news detection: Avoid repeating information if a post on a similar topic has already been published.

  - Data freshness: Check how recent the information in the news item is to avoid publishing outdated facts.

  - Statistic extraction: Automatically find and extract statistical data (e.g., match scores, win rates, kill counts) for use in the post.
  
  - Important: The final post must be no more than 300 characters and if the news item includes an image, do NOT include the link in the message text at all. Instead, return it separately in a field named image_url. Do not wrap it in parentheses or include it in the body of the post.



 Source verification: Where possible, verify the reliability of information, especially for rumors or unconfirmed data.
 Reply with only the final post, no commentary or explanation.
Input:
{content}
"""
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=600,
        )

        text = completion.choices[0].message.content.strip()

        usage = completion.usage

        logging.info(
            f"OpenAI usage: prompt_tokens={usage['prompt_tokens']}, "
            f"completion_tokens={usage['completion_tokens']}, "
            f"total_tokens={usage['total_tokens']}"
        )
    except Exception as e:
        logging.error(f"OpenAI error: {e}")
        return "[Ошибка генерации текста]", None

    image_url = extract_image_url(entry)
    return text, image_url


def post_to_telegram(text, image_url=None):
    if image_url and len(text) <= 999:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        payload = {
            "chat_id": CHANNEL_USERNAME,
            "caption": smart_trim(text, 999),
            "photo": image_url,
            "parse_mode": "HTML"
        }
    else:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHANNEL_USERNAME,
            "text": smart_trim(text, 4096),
            "parse_mode": "HTML"
        }

    try:
        resp = requests.post(url, data=payload)
        if not resp.ok:
            logging.error(f"Telegram error: {resp.text}")
        else:
            logging.info("Message posted to Telegram successfully.")
    except Exception as e:
        logging.exception(f"Failed to send message to Telegram: {e}")


def main():
    while True:
        try:
            #if "Извините, не могу создать пост" in text:
            #logging.info(f"Пропущен пост: недостаточно информации для {entry.link}")
            #continue  # пропустить публикацию и перейти к следующей новости
            last_seen = {}
            if os.path.exists('last_seen.json'):
                with open('last_seen.json', 'r') as f:
                    last_seen = json.load(f)

            for url in RSS_URLS:
                entries = fetch_rss_entries(url)
                latest_seen_str = last_seen.get(url, '1970-01-01T00:00:00Z')
                latest_seen = parse(latest_seen_str).astimezone(datetime.timezone.utc)

                # sort entries by timestamp (1st - min timestamp)
                for entry in entries[::-1]:
                    if entry.link in seen_links:
                        continue
                    seen_links.add(entry.link)

                    publish_time = getattr(entry, "pubDate", "") or getattr(entry, "updated", "")
                    if not publish_time:
                        continue
                    publish_time = parse(publish_time)
                    if publish_time.tzinfo is None:
                        publish_time = publish_time.replace(tzinfo=datetime.timezone.utc)
                    else:
                        publish_time = publish_time.astimezone(datetime.timezone.utc)

                    if publish_time < latest_seen:
                        logging.info(f'Skipped entry (Already parsed): {entry.link}')
                        continue

                    logging.info(f"New entry detected: {entry.link} [{publish_time}]")
                    text, img = summarize_entry(entry)
                    post_to_telegram(text, img)
                    time.sleep(4)

                    latest_seen = publish_time
                    last_seen[url] = latest_seen.isoformat()
                    with open('last_seen.json', 'w') as f:
                        json.dump(last_seen, f, indent=2)


        except Exception as e:
            logging.exception("Error during RSS processing loop")
        logging.info(f"Sleeping for {CHECK_INTERVAL} seconds...")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    logging.info("Bot started. Monitoring RSS feeds...")
    main()

#promt