import discord
import asyncio
import feedparser
import json
import os
import random
import aiohttp

# 環境変数
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
CHECK_INTERVAL = 60  # 1分おきにチェック（短すぎるとブロックされます）

# 現在比較的安定しているNitterインスタンス
NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.perennialte.ch",
    "https://nitter.moomoo.me"
]

intents = discord.Intents.default()
client = discord.Client(intents=intents)

def load_accounts():
    try:
        with open("accounts.txt", "r", encoding="utf-8") as f:
            return [x.strip() for x in f if x.strip()]
    except FileNotFoundError:
        print("Error: accounts.txt が見つかりません。")
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

async def get_feed(user):
    # インスタンスをランダムに試行
    shuffled_instances = random.sample(NITTER_INSTANCES, len(NITTER_INSTANCES))
    
    for instance in shuffled_instances:
        url = f"{instance}/{user}/rss"
        try:
            async with aiohttp.ClientSession() as session:
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
        print(f"Error: チャンネルID {CHANNEL_ID} が見つかりません。")
        return

    while not client.is_closed():
        accounts = load_accounts()
        last = load_last()

        for user in accounts:
            print(f"Checking: {user}...")
            
            # 引数を url ではなく user に修正
            feed = await get_feed(user)

            if not feed:
                print(f"  [!] {user}: 取得失敗（インスタンス全滅または制限）")
                continue

            if not feed.entries:
                print(f"  [!] {user}: ツイートが0件です")
                continue

            print(f"  [OK] {user}: {len(feed.entries)}件取得")

            if user not in last:
                last[user] = []

            # 投稿を古い順に処理するため逆順にする
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

                # 画像の取得（Nitterの構造に合わせる）
                if hasattr(tweet, 'media_content'):
                    embed.set_image(url=tweet.media_content[0]['url'])

                try:
                    await channel.send(embed=embed)
                    print(f"  [送信完了] {user}")
                except Exception as e:
                    print(f"  [送信エラー] {e}")

                last[user].append(tweet_id)
                if len(last[user]) > 50:
                    last[user].pop(0)

            save_last(last)
            await asyncio.sleep(2) # 連続送信による負荷軽減

        print(f"待機中... ({CHECK_INTERVAL}秒)")
        await asyncio.sleep(CHECK_INTERVAL)

@client.event
async def on_ready():
    print(f"Bot起動: {client.user}")
    client.loop.create_task(check_loop())

client.run(TOKEN)
