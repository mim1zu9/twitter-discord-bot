import discord
import asyncio
import feedparser
import json

TOKEN = "MTQ5MDI1ODEwMzE4OTUwODI4NA.GppLBM.RDeZkZ0spK66yHuZ8oR03_g-F50u-e2YU8-UZo"
CHANNEL_ID = 1490066821108203560

CHECK_INTERVAL = 300

def load_accounts():
    with open("accounts.txt", "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def load_last():
    try:
        with open("last_tweets.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_last(data):
    with open("last_tweets.json", "w") as f:
        json.dump(data, f)

class Bot(discord.Client):
    async def on_ready(self):
        print("Bot起動")
        self.loop.create_task(check_loop())

intents = discord.Intents.default()
client = Bot(intents=intents)

async def check_loop():
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    last = load_last()

    while True:
        accounts = load_accounts()

        for user in accounts:
            url = f"https://nitter.net/{user}/rss"
            feed = feedparser.parse(url)

            if not feed.entries:
                continue

            tweet = feed.entries[0]
            tweet_id = tweet.link

            if last.get(user) != tweet_id:
                last[user] = tweet_id
                save_last(last)

                text = tweet.title

                embed = discord.Embed(
                    title=f"{user} のツイート",
                    description=text,
                    url=tweet.link,
                    color=0x1DA1F2
                )

                await channel.send(embed=embed)

        await asyncio.sleep(CHECK_INTERVAL)

client.run(TOKEN)