import os
import discord
import requests
import json
import io
from discord.ext import tasks, commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DEBUG_CHANNEL_ID = int(os.getenv("DEBUG_CHANNEL_ID"))
ALS_API_KEY = os.getenv("ALS_API_KEY")
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

DATA_FILE = "channels.json"

class ApexBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="/", intents=intents)
        
        self.last_br_map = None
        self.last_ranked_map = None
        # 通知対象のチャンネルIDリスト（初期状態は空）
        self.enabled_channels = self.load_channels()

    def load_channels(self):
        """保存されたチャンネルIDを読み込む"""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Load error: {e}")
        return []

    def save_channels(self):
        """チャンネルIDをファイルに保存する"""
        with open(DATA_FILE, "w") as f:
            json.dump(self.enabled_channels, f)

    async def setup_hook(self):
        # スラッシュコマンドの登録
        await self.tree.sync()
        self.map_monitor.start()

    async def update_nickname(self, map_name):
        new_nick = f"Map: {map_name}"
        for guild in self.guilds:
            try:
                if guild.me.display_name != new_nick:
                    await guild.me.edit(nick=new_nick)
            except Exception:
                continue

    @tasks.loop(seconds=60)
    async def map_monitor(self):
        if not self.enabled_channels and not DEBUG_MODE:
            return

        url = f"https://api.mozambiquehe.re/maprotation?version=2&auth={ALS_API_KEY}"
        
        try:
            response = requests.get(url)
            data = response.json()

            # デバッグ処理
            if DEBUG_MODE:
                debug_channel = self.get_channel(DEBUG_CHANNEL_ID)
                if debug_channel:
                    debug_json = json.dumps(data, indent=2, ensure_ascii=False)
                    if len(debug_json) < 1900:
                        await debug_channel.send(f"**[DEBUG]**\n```json\n{debug_json}\n```")

            br_curr = data.get("battle_royale", {}).get("current", {}).get("map")
            rk_curr = data.get("ranked", {}).get("current", {}).get("map")

            # メッセージ構築
            notif_msg = ""
            if self.last_ranked_map and self.last_ranked_map != rk_curr:
                notif_msg += f"**ランク** のマップが **{rk_curr}** に変更されました。\n"
                await self.update_nickname(rk_curr)
            
            if self.last_br_map and self.last_br_map != br_curr:
                notif_msg += f"**カジュアル** のマップが **{br_curr}** に変更されました。"

            # 通知の実行
            if notif_msg:
                for cid in self.enabled_channels[:]:
                    channel = self.get_channel(cid)
                    if channel:
                        try:
                            await channel.send(notif_msg)
                        except discord.Forbidden:
                            print(f"Permission denied for channel: {cid}")
                    else:
                        # チャンネルが存在しない場合はリストから除外
                        self.enabled_channels.remove(cid)
                        self.save_channels()

            self.last_br_map = br_curr
            self.last_ranked_map = rk_curr

        except Exception as e:
            print(f"Monitor Error: {e}")

    @map_monitor.before_loop
    async def before_monitor(self):
        await self.wait_until_ready()

bot = ApexBot()

# --- スラッシュコマンドの定義 ---

class MapRote(app_commands.Group):
    @app_commands.command(name="enable", description="このチャンネルでマップ通知を有効にします")
    @app_commands.checks.has_permissions(administrator=True)
    async def enable(self, interaction: discord.Interaction):
        if interaction.channel_id not in bot.enabled_channels:
            bot.enabled_channels.append(interaction.channel_id)
            bot.save_channels()
            await interaction.response.send_message(f"このチャンネルでの通知を **有効** にしました。", ephemeral=False)
        else:
            await interaction.response.send_message("ℹこのチャンネルでは既に通知が有効です。", ephemeral=True)

    @app_commands.command(name="disable", description="このチャンネルでマップ通知を無効にします")
    @app_commands.checks.has_permissions(administrator=True)
    async def disable(self, interaction: discord.Interaction):
        if interaction.channel_id in bot.enabled_channels:
            bot.enabled_channels.remove(interaction.channel_id)
            bot.save_channels()
            await interaction.response.send_message(f"このチャンネルでの通知を **無効** にしました。", ephemeral=False)
        else:
            await interaction.response.send_message(f"このチャンネルは通知設定されていません。", ephemeral=True)

# グループをBotのTreeに追加
bot.tree.add_command(MapRote(name="map-rote"))

bot.run(TOKEN)