import re
import os
import json
import time
import logging
import feedparser
import openai
import requests
from urllib.parse import quote_plus
from dateutil.parser import parse
from datetime import timezone
import boto3

openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
S3_BUCKET = os.getenv("S3_BUCKET", "cs2-news-bot-data")
S3_KEY = "last_seen.json"

RSS_URLS = [
    "https://www.hltv.org/rss/news",
    "https://liquipedia.net/counterstrike/Special:RecentChanges?feed=rss",
    "https://www.reddit.com/r/GlobalOffensive/.rss"
]

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")


def get_s3_key_for_url(url: str) -> str:
    return f"last_seen/{quote_plus(url)}.json"


def load_last_seen(url: str) -> str:
    key = get_s3_key_for_url(url)
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
        return json.loads(obj["Body"].read())
    except s3.exceptions.NoSuchKey:
        return "1970-01-01T00:00:00Z"


def save_last_seen(url: str, timestamp: str):
    key = get_s3_key_for_url(url)
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=json.dumps(timestamp))


def smart_trim(text, limit=4096):
    if len(text) <= limit:
        return text
    trimmed = text[:limit]
    for punct in ['.', '!', '?', '\n']:
        idx = trimmed.rfind(punct)
        if idx != -1 and idx > limit * 0.7:
            return trimmed[:idx + 1].strip()
    return trimmed.strip()


def fetch_rss_entries(url):
    try:
        feed = feedparser.parse(url)
        return feed.entries or []
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return []


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
    content = f"{title}\n{summary}"

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
        logger.info(
            f"OpenAI usage: prompt_tokens={usage['prompt_tokens']}, "
            f"completion_tokens={usage['completion_tokens']}, "
            f"total_tokens={usage['total_tokens']}"
        )
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "[Ошибка генерации текста]", None

    image_url = extract_image_url(entry)
    text_lines = text.splitlines()
    filtered_lines = []
    for line in text_lines:
        line_strip = line.strip().lower()
        if line_strip.startswith("image_url") or line_strip.startswith("(image_url") or line_strip.startswith("изображение"):
            continue
        if re.search(r'\(https?://[^)]+\)', line):
            continue
        filtered_lines.append(line)

    text = "\n".join(filtered_lines).strip()
    return text, image_url


def post_to_telegram(text, image_url=None):
    try:
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

        resp = requests.post(url, data=payload)
        if not resp.ok:
            logger.error(f"Telegram error: {resp.text}")
        else:
            logger.info("Message posted to Telegram successfully.")
    except Exception as e:
        logger.exception(f"Failed to send message to Telegram: {e}")


def lambda_handler(event, context):
    logger.info("Lambda started. Monitoring RSS feeds...")
    seen_links = set()

    for url in RSS_URLS:
        entries = fetch_rss_entries(url)
        latest_seen_str = load_last_seen(url)
        latest_seen = parse(latest_seen_str).astimezone(timezone.utc)

        entries.sort(
            key=lambda ent: parse(
                getattr(ent, "pubDate", "") or getattr(ent, "updated", "") or "1970-01-01T00:00:00Z"
            )
        )

        for entry in entries:
            if entry.link in seen_links:
                continue
            seen_links.add(entry.link)

            publish_time = getattr(entry, "pubDate", "") or getattr(entry, "updated", "")
            if not publish_time:
                continue
            publish_time = parse(publish_time)
            if publish_time.tzinfo is None:
                publish_time = publish_time.replace(tzinfo=timezone.utc)
            else:
                publish_time = publish_time.astimezone(timezone.utc)

            if publish_time < latest_seen:
                logger.info(f'Skipped entry (Already parsed): {entry.link}')
                continue

            logger.info(f"New entry detected: {entry.link} [{publish_time}]")
            text, img = summarize_entry(entry)
            if "Извините," in text:
                logger.info(f"Пропущен пост: недостаточно информации для {entry.link}")
                continue
            post_to_telegram(text, img)
            time.sleep(10)

            latest_seen = publish_time
            save_last_seen(url, latest_seen.isoformat())

    logger.info("Lambda finished")
