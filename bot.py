import discord
import asyncio
import feedparser
import json
import os
import random
import aiohttp

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

CHECK_INTERVAL = 30

NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.unixfox.eu",
    "https://nitter.poast.org",
    "https://nitter.privacydev.net"
]

intents = discord.Intents.default()
client = discord.Client(intents=intents)


def load_accounts():
    with open("accounts.txt","r",encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip()]


def load_last():
    try:
        with open("last_tweets.json","r") as f:
            return json.load(f)
    except:
        return {}


def save_last(data):
    with open("last_tweets.json","w") as f:
        json.dump(data,f)


async def get_feed(url):

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url,timeout=10) as resp:
                text = await resp.text()
                return feedparser.parse(text)
    except:
        return None


def clean_text(text):

    if "http" in text:
        text = text.split("http")[0]

    return text.strip()


async def check_loop():

    await client.wait_until_ready()

    channel = client.get_channel(CHANNEL_ID)

    last = load_last()

    while True:

        accounts = load_accounts()

        for user in accounts:

            instance = random.choice(NITTER_INSTANCES)

            url = f"{instance}/{user}/rss"

            feed = await get_feed(url)

            if not feed or not feed.entries:
                continue

            if user not in last:
                last[user] = []

            for tweet in feed.entries[:5]:

                tweet_id = tweet.link

                if tweet_id in last[user]:
                    continue

                title = tweet.title

                if title.startswith("RT"):
                    continue

                if "Quote Tweet" in title:
                    continue

                text = clean_text(title)

                embed = discord.Embed(
                    title=f"{user} のツイート",
                    description=text,
                    url=tweet.link,
                    color=0x1DA1F2
                )

                if "media" in tweet:
                    embed.set_image(url=tweet.media[0]["url"])

                await channel.send(embed=embed)

                last[user].append(tweet_id)

                if len(last[user]) > 50:
                    last[user].pop(0)

                save_last(last)

        await asyncio.sleep(CHECK_INTERVAL)


@client.event
async def on_ready():

    print("Bot起動")

    client.loop.create_task(check_loop())


client.run(TOKEN)
