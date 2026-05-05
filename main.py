import os
import discord
import requests
import json
from discord.ext import tasks, commands
from discord import app_commands
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DEBUG_CHANNEL_ID = int(os.getenv("DEBUG_CHANNEL_ID")) if os.getenv("DEBUG_CHANNEL_ID") else None
ALS_API_KEY = os.getenv("ALS_API_KEY")
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
MY_USER_ID = int(os.getenv("MY_USER_ID")) if os.getenv("MY_USER_ID") else None

DATA_FILE = "channels.json"

# デバッグメッセージを送信するヘルパー関数
async def send_debug(bot, message):
    if DEBUG_MODE and DEBUG_CHANNEL_ID:
        channel = bot.get_channel(DEBUG_CHANNEL_ID)
        if channel:
            # 2000文字制限に配慮し、長い場合はカット
            await channel.send(f"**[DEBUG]** {message[:1900]}", silent=True)

# 権限チェック用の関数
def is_admin_or_me():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator or interaction.user.id == MY_USER_ID:
            return True
        await interaction.response.send_message("このコマンドを実行する権限がありません。", ephemeral=True)
        return False
    return app_commands.check(predicate)

class ApexBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="/", intents=intents)
        
        self.last_br_map = None
        self.last_ranked_map = None
        self.config = self.load_channels()

    # 設定ファイルを読み込む
    def load_channels(self):
        default_config = {"br": [], "ranked": [], "guild_nicks": {}}
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    data = json.load(f)
                    for key in default_config:
                        if key not in data:
                            data[key] = default_config[key]
                    return data
            except Exception as e:
                print(f"Load error: {e}")
        return default_config

    # 設定ファイルを保存する
    def save_channels(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.config, f)

    # 起動時のセットアップ
    async def setup_hook(self):
        await self.tree.sync()
        self.map_monitor.start()

    # ニックネームを更新
    async def update_nicknames(self, br_map, rk_map):
        for guild in self.guilds:
            mode = self.config["guild_nicks"].get(str(guild.id), "ranked")
            new_nick = f"BR: {br_map}" if mode == "br" else f"Rank: {rk_map}"
            try:
                if guild.me.display_name != new_nick:
                    await guild.me.edit(nick=new_nick)
            except Exception as e:
                # ニックネーム更新失敗もデバッグ送信
                await send_debug(self, f"Nickname update failed in {guild.name}: {e}")
                continue

    # メインの監視ループ
    @tasks.loop(seconds=60)
    async def map_monitor(self):
        if not self.config["br"] and not self.config["ranked"] and not DEBUG_MODE:
            return

        url = f"https://api.mozambiquehe.re/maprotation?version=2&auth={ALS_API_KEY}"
        try:
            response = requests.get(url, timeout=10)
            data = response.json()

            # 取得した生のJSONをデバッグ送信
            if DEBUG_MODE:
                debug_json = json.dumps(data, indent=2, ensure_ascii=False)
                await send_debug(self, f"API Response:\n```json\n{debug_json}\n```")

            br_curr = data.get("battle_royale", {}).get("current", {}).get("map")
            rk_curr = data.get("ranked", {}).get("current", {}).get("map")

            # マップ名がNoneの場合のデバッグとスキップ
            if not br_curr or not rk_curr:
                await send_debug(self, f"Invalid data received (BR: {br_curr}, Rank: {rk_curr}). Skipping this cycle.")
                return

            # 初回データ保持
            if self.last_br_map is None or self.last_ranked_map is None:
                self.last_br_map = br_curr
                self.last_ranked_map = rk_curr
                await self.update_nicknames(br_curr, rk_curr)
                await send_debug(self, f"Initial map data set: BR={br_curr}, Rank={rk_curr}")
                return

            # 変更検知のデバッグ
            change_detected = False
            if br_curr != self.last_br_map:
                await send_debug(self, f"BR Map Change Detected: {self.last_br_map} -> {br_curr}")
                await self.broadcast_map_update("br", f"**カジュアル** のマップが **{br_curr}** に変更されました。")
                change_detected = True
            
            if rk_curr != self.last_ranked_map:
                await send_debug(self, f"Rank Map Change Detected: {self.last_ranked_map} -> {rk_curr}")
                await self.broadcast_map_update("ranked", f"**ランク** のマップが **{rk_curr}** に変更されました。")
                change_detected = True

            # 変更があった場合のみニックネームを更新
            if change_detected:
                await self.update_nicknames(br_curr, rk_curr)
            else:
                # 1分ごとの生存確認用（DEBUG時のみ）
                if DEBUG_MODE:
                    print("No change in map rotation.")

            self.last_br_map = br_curr
            self.last_ranked_map = rk_curr

        except Exception as e:
            await send_debug(self, f"Monitor Loop Error: {e}")

    # 通知の一斉送信
    async def broadcast_map_update(self, mode_key, message):
        for cid in self.config[mode_key][:]:
            channel = self.get_channel(cid)
            if channel:
                try:
                    await channel.send(message, silent=True)
                except discord.Forbidden:
                    await send_debug(self, f"Permission Denied: Cannot send message to channel {cid}")
            else:
                await send_debug(self, f"Removing invalid channel ID from config: {cid}")
                self.config[mode_key].remove(cid)
                self.save_channels()

    @map_monitor.before_loop
    async def before_monitor(self):
        await self.wait_until_ready()

bot = ApexBot()

# --- スラッシュコマンド ---

class MapRote(app_commands.Group):
    @app_commands.command(name="enable", description="通知を有効にします")
    @app_commands.choices(mode=[
        app_commands.Choice(name="カジュアル", value="br"),
        app_commands.Choice(name="ランク", value="ranked")
    ])
    @is_admin_or_me()
    async def enable(self, interaction: discord.Interaction, mode: str):
        if interaction.channel_id not in bot.config[mode]:
            bot.config[mode].append(interaction.channel_id)
            bot.save_channels()
            await interaction.response.send_message(f"通知を有効にしました。", ephemeral=False)
            await send_debug(bot, f"Notification ENABLED for {mode} in channel {interaction.channel_id} (User: {interaction.user})")
        else:
            await interaction.response.send_message("既に有効です。", ephemeral=True)

    @app_commands.command(name="disable", description="通知を無効にします")
    @app_commands.choices(mode=[
        app_commands.Choice(name="カジュアル", value="br"),
        app_commands.Choice(name="ランク", value="ranked")
    ])
    @is_admin_or_me()
    async def disable(self, interaction: discord.Interaction, mode: str):
        if interaction.channel_id in bot.config[mode]:
            bot.config[mode].remove(interaction.channel_id)
            bot.save_channels()
            await interaction.response.send_message(f"通知を無効にしました。", ephemeral=False)
            await send_debug(bot, f"Notification DISABLED for {mode} in channel {interaction.channel_id} (User: {interaction.user})")
        else:
            await interaction.response.send_message("設定されていません。", ephemeral=True)

    @app_commands.command(name="set-nick", description="Botのニックネーム表示モードを設定します")
    @app_commands.choices(mode=[
        app_commands.Choice(name="カジュアルを表示", value="br"),
        app_commands.Choice(name="ランクを表示", value="ranked")
    ])
    @is_admin_or_me()
    async def set_nick(self, interaction: discord.Interaction, mode: str):
        bot.config["guild_nicks"][str(interaction.guild_id)] = mode
        bot.save_channels()
        
        current_br = bot.last_br_map or "取得中..."
        current_rk = bot.last_ranked_map or "取得中..."
        new_nick = f"BR: {current_br}" if mode == "br" else f"Rank: {current_rk}"
        
        try:
            await interaction.guild.me.edit(nick=new_nick)
            await interaction.response.send_message(f"表示モードを **{mode}** に変更しました。", ephemeral=False)
            await send_debug(bot, f"Nickname mode changed to {mode} in guild {interaction.guild.name}")
        except discord.Forbidden:
            await interaction.response.send_message("権限不足でニックネームを変更できませんでした。", ephemeral=False)
            await send_debug(bot, f"Failed to change nick in {interaction.guild.name} due to missing permissions.")

bot.tree.add_command(MapRote(name="map-rote"))
bot.run(TOKEN)