import discord
import asyncio
import feedparser
import json
import os
import random
import aiohttp

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

CHECK_INTERVAL = 180

NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.perennialte.ch",
    "https://nitter.moomoo.me",
    "https://nitter.woodland.cafe",
    "https://nitter.kavin.rocks",
    "https://nitter.1d4.us"
]

intents = discord.Intents.default()
client = discord.Client(intents=intents)

session = None
LAST_FILE = "last_tweets.json"


def load_accounts():
    try:
        with open("accounts.txt", "r", encoding="utf-8") as f:
            return [x.strip() for x in f if x.strip()]
    except:
        print("accounts.txt が見つかりません")
        return []


def load_last():

    if not os.path.exists(LAST_FILE):
        return {}

    try:
        with open(LAST_FILE, "r") as f:
            return json.load(f)
    except:
        print("last_tweets.json 破損 → リセット")
        return {}


def save_last(data):
    try:
        with open(LAST_FILE, "w") as f:
            json.dump(data, f)
    except:
        print("last_tweets 保存失敗")


async def get_feed(user):

    instances = random.sample(NITTER_INSTANCES, len(NITTER_INSTANCES))

    for instance in instances:

        url = f"{instance}/{user}/rss"

        try:

            async with session.get(url, timeout=6) as resp:

                if resp.status != 200:
                    continue

                text = await resp.text()

                feed = feedparser.parse(text)

                if feed.bozo:
                    continue

                if feed.entries:
                    return feed

        except:
            continue

    return None


def clean_text(text):

    if "http" in text:
        text = text.split("http")[0]

    return text.strip()


async def process_account(user, channel, last):

    feed = await get_feed(user)

    if not feed:
        print(f"{user} 取得失敗")
        return

    if user not in last:
        last[user] = []

    for tweet in reversed(feed.entries[:5]):

        tweet_id = tweet.link

        if tweet_id in last[user]:
            continue

        title = tweet.title

        if title.startswith("RT") or "Quote Tweet" in title:
            continue

        text = clean_text(title)

        embed = discord.Embed(
            title=f"{user} のツイート",
            description=text,
            url=tweet.link,
            color=0x1DA1F2
        )

        if hasattr(tweet, "media_content"):
            try:
                embed.set_image(url=tweet.media_content[0]["url"])
            except:
                pass

        try:
            await channel.send(embed=embed)
            print(f"送信: {user}")
        except Exception as e:
            print("送信失敗", e)

        last[user].append(tweet_id)

        if len(last[user]) > 100:
            last[user].pop(0)

        await asyncio.sleep(2)


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

        if not accounts:
            print("監視アカウントなし")

        for user in accounts:

            try:
                print(f"Checking {user}")
                await process_account(user, channel, last)
                save_last(last)

            except Exception as e:
                print("アカウント処理エラー", e)

        print(f"待機 {CHECK_INTERVAL}秒")
        await asyncio.sleep(CHECK_INTERVAL)


@client.event
async def on_ready():

    global session

    print(f"Bot起動: {client.user}")

    session = aiohttp.ClientSession()

    asyncio.create_task(check_loop())


client.run(TOKEN)
