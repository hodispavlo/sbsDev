
# import feedparser
# import openai
# import time
# import requests

# # --- НАСТРОЙКИ ---
# openai.api_key        = "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"
# TELEGRAM_TOKEN        = "7704067333:AAFmimt4u0Ka8PFGrBmR6Yya3sdXFJwZFwU"
# CHANNEL_USERNAME      = "@testSBScs2"
# RSS_URL               = "https://www.hltv.org/rss/news"
# CHECK_INTERVAL        = 600  # 10 минут
# seen_links            = set()

# def fetch_rss_entries():
#     return feedparser.parse(RSS_URL).entries

# def extract_image_url(entry):
    
#     media = getattr(entry, 'media_content', None)
#     if media and isinstance(media, list) and 'url' in media[0]:
#         return media[0]['url']
    
#     enc = getattr(entry, 'enclosures', None)
#     if enc and isinstance(enc, list) and 'href' in enc[0]:
#         return enc[0]['href']
#     return None

# def summarize_entry(entry):
#     title   = entry.title
#     summary = getattr(entry, "summary", "")
#     content = f"{title}\n{summary}"

#     prompt = f"""
    
# You are the editor of an esports Telegram channel — SBS CS2 — focused on CS2.

# Your task:
# 1. Read the news item (title, link, summary, full text).
# 2. Write a short, punchy, and readable post in Russian. The style should be fan-driven, a bit edgy, as if written by a CS2 player, not a journalist.
# 3. Do NOT use bold, markdown, or links — only plain Telegram-style formatting: emojis, line breaks, and bullet points.
# 4. Emphasize facts, statistics, and specifics — no exaggeration or twisting.
# 5. Where appropriate, insert a creative one-liner, meme phrase, or sarcastic comment (AI can improvise here).
# 6. At the end, add 1–2 interesting related facts (only if they are actually relevant — like a player’s birthday, a record, or a historical moment).
# 7. If there are no good facts — skip this section entirely.
# 8. Finish the post with a brief comment on the current state of the CS2 pro scene (meta shifts, roster chaos, tournament intensity).
# 9. If the news item includes an image — provide the image link in parentheses so the bot can use it separately.
# 10. Write the entire post in Russian, formatted as ready-to-post for a Telegram channel with no further editing required.
# 11. Target audience is located in Ukraine, all times of tournaments or matches start time should be specified in Kiyv time but not directly say it.Just time would be fine.
# Important aspects for parsing and use:
#  - Identification of key entities: Automatically recognize and extract names of players, team names, tournaments, cities, dates, and times.

#  - Tone detection: Analyze text for positive, negative, or neutral context to adapt the post's style.

#  - Information prioritization: Identify the most important aspects of the news (e.g., match winner, roster changes, significant achievements) for inclusion in the post.

#  - Duplicate/similar news detection: Avoid repeating information if a post on a similar topic has already been published.

#  - Data freshness: Check how recent the information in the news item is to avoid publishing outdated facts.

#  - Statistic extraction: Automatically find and extract statistical data (e.g., match scores, win rates, kill counts) for use in the post.

# Source verification: Where possible, verify the reliability of information, especially for rumors or unconfirmed data.

# Input:
# [Insert: title, summary, link, full text, image (if available)]

# Reply with only the final post, no commentary or explanation.   


# {content}
# """
#     try:
#         completion = openai.ChatCompletion.create(
#             model="gpt-4o",     
#             messages=[{"role": "user", "content": prompt}],
#             temperature=0.8,
#             max_tokens=600,
#         )
#         text = completion.choices[0].message.content.strip()
#     except Exception as e:
#         text = f"[OpenAI Error] {e}"

#     image_url = extract_image_url(entry)
#     return text, image_url

# def post_to_telegram(text, image_url=None):
#     if image_url:
#         url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
#         payload = {
#             "chat_id": CHANNEL_USERNAME,
#             "caption": text,
#             "photo": image_url,
#             "parse_mode": "HTML"
#         }
#     else:
#         url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
#         payload = {
#             "chat_id": CHANNEL_USERNAME,
#             "text": text,
#             "parse_mode": "HTML"
#         }

#     try:
#         resp = requests.post(url, data=payload)
#         if not resp.ok:
#             print("[Telegram Error]", resp.text)
#     except Exception as e:
#         print("[Send Failed]", e)

# def main():
#     while True:
#         for entry in fetch_rss_entries():
#             if entry.link not in seen_links:
#                 seen_links.add(entry.link)
#                 text, img = summarize_entry(entry)
#                 post_to_telegram(text, img)
#                 time.sleep(2)
#         time.sleep(CHECK_INTERVAL)

# if __name__ == "__main__":
#     main()



import feedparser
import openai
import time
import requests


openai.api_key        = "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"
TELEGRAM_TOKEN        = "7704067333:AAFmimt4u0Ka8PFGrBmR6Yya3sdXFJwZFwU"
CHANNEL_USERNAME      = "@testSBScs2"
RSS_URLS              = [
    "https://www.hltv.org/rss/news",
    "https://liquipedia.net/counterstrike/Special:RecentChanges?feed=rss",
    "https://www.reddit.com/r/GlobalOffensive/.rss"
]
CHECK_INTERVAL        = 600  # 10 минут
seen_links            = set()


def fetch_rss_entries():
    entries = []
    for url in RSS_URLS:
        try:
            feed = feedparser.parse(url)
            entries.extend(feed.entries)
        except Exception:
            continue
    return entries


def extract_image_url(entry):
    media = getattr(entry, 'media_content', None)
    if media and isinstance(media, list) and 'url' in media[0]:
        return media[0]['url']
    enc = getattr(entry, 'enclosures', None)
    if enc and isinstance(enc, list) and 'href' in enc[0]:
        return enc[0]['href']
    return None


def summarize_entry(entry):
    title   = entry.title
    summary = getattr(entry, "summary", "")
    content = f"{title}\n{summary}"

    prompt = f"""

You are the editor of an esports Telegram channel — SBS CS2 — focused on CS2.

Your task:
1. Read the news item (title, link, summary, full text).
2. Write a short, punchy, and readable post in Russian. The style should be fan-driven, a bit edgy, as if written by a CS2 player, not a journalist.
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
    except Exception as e:
        text = f"[OpenAI Error] {e}"

    image_url = extract_image_url(entry)
    return text, image_url


def post_to_telegram(text, image_url=None):
    if image_url:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        payload = {
            "chat_id": CHANNEL_USERNAME,
            "caption": text,
            "photo": image_url,
            "parse_mode": "HTML"
        }
    else:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHANNEL_USERNAME,
            "text": text,
            "parse_mode": "HTML"
        }

    try:
        resp = requests.post(url, data=payload)
        if not resp.ok:
            print("[Telegram Error]", resp.text)
    except Exception as e:
        print("[Send Failed]", e)


def main():
    while True:
        for entry in fetch_rss_entries():
            if entry.link not in seen_links:
                seen_links.add(entry.link)
                text, img = summarize_entry(entry)
                post_to_telegram(text, img)
                time.sleep(2)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
