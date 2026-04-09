import discord
import asyncio
import feedparser
import json
import os
import aiohttp
import time
from datetime import datetime, timezone
import random

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

CHECK_INTERVAL = 300
MAX_TWEET_AGE = 86400  # 48時間以内のツイートのみ
FAIL_COOLDOWN = 600  # Nitterインスタンスの失敗時クールタイム

NITTER_INSTANCES = [
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.perennialte.ch",
    "https://nitter.moomoo.me",
    "https://nitter.kavin.rocks",
    "https://nitter.fdn.fr"
]

HEADERS = {"User-Agent": "Mozilla/5.0"}
FAILED = {}

intents = discord.Intents.default()
client = discord.Client(intents=intents)
session = None
LAST_FILE = "last_tweets.json"

# --- データ読み書き ---
def load_accounts():
    try:
        with open("accounts.txt", "r", encoding="utf-8") as f:
            return [x.strip() for x in f if x.strip()]
    except:
        return []

def load_last():
    if not os.path.exists(LAST_FILE):
        return {}
    try:
        with open(LAST_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_last(data):
    with open(LAST_FILE, "w") as f:
        json.dump(data, f)

# --- Nitterインスタンス管理 ---
def instance_alive(url):
    if url not in FAILED:
        return True
    return time.time() - FAILED[url] > FAIL_COOLDOWN

def mark_failed(url):
    FAILED[url] = time.time()

# --- RSS取得 ---
async def fetch(url, base):
    if not instance_alive(base):
        return None
    try:
        async with session.get(url, headers=HEADERS, timeout=12) as resp:
            if resp.status != 200:
                mark_failed(base)
                return None
            text = await resp.text()
            feed = feedparser.parse(text)
            return feed
    except:
        mark_failed(base)
        return None

async def get_feed(user):
    random.shuffle(NITTER_INSTANCES)
    for inst in NITTER_INSTANCES:
        url = f"{inst}/{user}/rss"
        feed = await fetch(url, inst)
        if feed and feed.entries:
            return feed
    return None

# --- ツイートの判定・加工 ---
def is_recent(tweet):
    try:
        tweet_time = datetime(*tweet.published_parsed[:6], tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - tweet_time).total_seconds() <= MAX_TWEET_AGE
    except:
        return True

def clean_text(text):
    if "http" in text:
        text = text.split("http")[0]
    return text.strip()

def extract_media(tweet):
    image = None
    video = None
    try:
        if hasattr(tweet, "media_content"):
            url = tweet.media_content[0]["url"]
            if ".mp4" in url:
                video = url
            else:
                image = url
        if hasattr(tweet, "links"):
            for l in tweet.links:
                if ".mp4" in l.href:
                    video = l.href
    except:
        pass
    return image, video

# --- アカウント処理 ---
async def process_account(user, channel, last):
    feed = await get_feed(user)
    if not feed:
        print("取得失敗:", user)
        return

    if user not in last:
        last[user] = []

    for tweet in reversed(feed.entries[:5]):
        tweet_id = tweet.link
        if tweet_id in last[user]:
            continue
        if not is_recent(tweet):
            continue
        title = tweet.title
        if title.startswith("RT") and "Quote Tweet" not in title:
            continue  # 通常RTは弾く
        text = clean_text(title)
        image, video = extract_media(tweet)

        embed = discord.Embed(
            description=text,
            url=tweet.link,
            color=0x1DA1F2
        )
        embed.set_author(
            name=user + " のツイート",
            url="https://twitter.com/" + user
        )
        try:
            tweet_time = datetime(*tweet.published_parsed[:6])
            embed.timestamp = tweet_time
        except:
            pass
        if image:
            embed.set_image(url=image)

        try:
            await channel.send(embed=embed)
            if video:
                await channel.send(video)
            print("送信:", user)
        except Exception as e:
            print("送信失敗:", e)

        last[user].append(tweet_id)
        if len(last[user]) > 200:
            last[user].pop(0)
        await asyncio.sleep(random.uniform(2, 4))

# --- メインループ ---
async def check_loop():
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)
    if not channel:
        print("チャンネルが見つかりません")
        return
    print("監視開始")
    last = load_last()
    while True:
        accounts = load_accounts()
        for user in accounts:
            try:
                print("Checking:", user)
                await process_account(user, channel, last)
                save_last(last)
            except Exception as e:
                print("処理エラー:", e)
        await asyncio.sleep(CHECK_INTERVAL)

# --- Discord起動 ---
@client.event
async def on_ready():
    global session
    print("Bot起動:", client.user)
    session = aiohttp.ClientSession()
    asyncio.create_task(check_loop())

client.run(TOKEN)
