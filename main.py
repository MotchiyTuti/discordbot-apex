import os
import discord
import requests
import json
import io
from discord.ext import tasks, commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
DEBUG_CHANNEL_ID = int(os.getenv("DEBUG_CHANNEL_ID"))
ALS_API_KEY = os.getenv("ALS_API_KEY")
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

class ApexBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.last_br_map = None
        self.last_ranked_map = None

    async def setup_hook(self):
        self.map_monitor.start()

    async def update_nickname(self, map_name):
        """全サーバーのニックネームをランクマップ名に更新する共通処理"""
        new_nick = f"Map: {map_name}"
        for guild in self.guilds:
            try:
                # 現在のニックネームと異なる場合のみAPIを叩く（負荷軽減）
                if guild.me.display_name != new_nick:
                    await guild.me.edit(nick=new_nick)
            except discord.Forbidden:
                print(f"[{guild.name}] 権限不足で名前を変更できません。")
            except Exception as e:
                print(f"[{guild.name}] エラー: {e}")

    async def on_ready(self):
        print(f'Logged in as {self.user}')
        # 起動直後に一度APIを叩いて現在のマップを反映させる
        url = f"https://api.mozambiquehe.re/maprotation?version=2&auth={ALS_API_KEY}"
        try:
            response = requests.get(url)
            data = response.json()
            rk_curr = data.get("ranked", {}).get("current", {}).get("map")
            if rk_curr:
                await self.update_nickname(rk_curr)
                self.last_ranked_map = rk_curr
                print(f"Initial nickname set to: {rk_curr}")
        except Exception as e:
            print(f"Initial setup error: {e}")

    @tasks.loop(seconds=60)
    async def map_monitor(self):
        channel = self.get_channel(CHANNEL_ID)
        debug_channel = self.get_channel(DEBUG_CHANNEL_ID)
        url = f"https://api.mozambiquehe.re/maprotation?version=2&auth={ALS_API_KEY}"
        
        try:
            response = requests.get(url)
            data = response.json()

            # デバッグ送信
            if DEBUG_MODE and debug_channel:
                try:
                    debug_json = json.dumps(data, indent=2, ensure_ascii=False)
                    if len(debug_json) < 1900:
                        await debug_channel.send(f"**[DEBUG LOG]**\n```json\n{debug_json}\n```")
                    else:
                        with io.BytesIO(debug_json.encode('utf-8')) as f:
                            await debug_channel.send("**[DEBUG LOG]** (Data too long)", file=discord.File(f, filename="debug_log.json"))
                except discord.errors.Forbidden:
                    print("Debug channel access denied.")

            # マップ解析
            br_curr = data.get("battle_royale", {}).get("current", {}).get("map")
            rk_curr = data.get("ranked", {}).get("current", {}).get("map")

            # --- ランクマップ変更検知 ---
            if self.last_ranked_map and self.last_ranked_map != rk_curr:
                if channel: 
                    await channel.send(f"**ランク** のマップが **{rk_curr}** に変更されました。")
                # ニックネーム更新
                await self.update_nickname(rk_curr)
            
            # --- カジュアルマップ変更検知 ---
            if self.last_br_map and self.last_br_map != br_curr:
                if channel: 
                    await channel.send(f"**カジュアル** のマップが **{br_curr}** に変更されました。")

            self.last_br_map = br_curr
            self.last_ranked_map = rk_curr

        except Exception as e:
            print(f"Error: {e}")

    @map_monitor.before_loop
    async def before_monitor(self):
        await self.wait_until_ready()

bot = ApexBot()
bot.run(TOKEN)