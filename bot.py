import discord
import asyncio
import feedparser
import json
import os
import random
import aiohttp

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
CHECK_INTERVAL = 300 # あまり短いとアクセス禁止（429）になりやすいです

# 生きているインスタンスを探すのが難しいですが、いくつか候補
NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.perennialte.ch"
]

intents = discord.Intents.default()
client = discord.Client(intents=intents)

def load_accounts():
    try:
        with open("accounts.txt", "r", encoding="utf-8") as f:
            return [x.strip() for x in f if x.strip()]
    except FileNotFoundError:
        return []

def load_last():
    try:
        with open("last_tweets.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_last(data):
    with open("last_tweets.json", "w") as f:
        json.dump(data, f)

async def get_feed(session, user):
    # インスタンスをランダムに入れ替えて試行
    shuffled_instances = random.sample(NITTER_INSTANCES, len(NITTER_INSTANCES))
    
    for instance in shuffled_instances:
        url = f"{instance}/{user}/rss"
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    feed = feedparser.parse(text)
                    if feed.entries:
                        return feed
        except:
            continue
    return None

def clean_text(text):
    if "http" in text:
        text = text.split("http")[0]
    return text.strip()

async def check_loop():
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)
    if not channel:
        print("チャンネルが見つかりません。IDを確認してください。")
        return

    # セッションを一つにまとめる
    async with aiohttp.ClientSession() as session:
        while not client.is_closed():
            accounts = load_accounts()
            last = load_last()

            for user in accounts:
            print(f"Checking: {user}...") # 進行状況の表示
            
    
            feed = await get_feed(user) # 修正: url ではなく user を渡す

            if not feed:
                print(f"  [!] {user}: サイトにアクセスできませんでした（Nitter全滅の可能性）")
                continue

            if not feed.entries:
                print(f"  [!] {user}: サイトには繋がりましたが、ツイートが0件です（制限中）")
                continue
            
            print(f"  [OK] {user}: {len(feed.entries)}件のツイートを確認しました")
            # --- ここまで診断用コード ---

            if user not in last:
                last[user] = []

                for tweet in reversed(feed.entries[:5]): # 古い順に投稿
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

                    # 画像取得の改善（Nitterのメディア構造に合わせる）
                    if hasattr(tweet, 'media_content'):
                        embed.set_image(url=tweet.media_content[0]['url'])

                    await channel.send(embed=embed)
                    last[user].append(tweet_id)

                    if len(last[user]) > 50:
                        last[user].pop(0)

                save_last(last)
                await asyncio.sleep(5) # 連続アクセスによる制限回避

            await asyncio.sleep(CHECK_INTERVAL)

@client.event
async def on_ready():
    print(f"Bot起動: {client.user}")
    client.loop.create_task(check_loop())

client.run(TOKEN)
