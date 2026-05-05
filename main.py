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

# 管理者権限または指定したユーザーIDのみ実行可能にする権限チェック
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

    # 起動時にスラッシュコマンドを同期し、監視ループを開始
    async def setup_hook(self):
        await self.tree.sync()
        self.map_monitor.start()

    # サーバーごとの設定に従ってBotのニックネームを更新
    async def update_nicknames(self, br_map, rk_map):
        for guild in self.guilds:
            mode = self.config["guild_nicks"].get(str(guild.id), "ranked")
            new_nick = f"BR: {br_map}" if mode == "br" else f"Rank: {rk_map}"
            try:
                if guild.me.display_name != new_nick:
                    await guild.me.edit(nick=new_nick)
            except Exception:
                continue

    # マップローテーションを監視し、変更があれば通知
    @tasks.loop(seconds=60)
    async def map_monitor(self):
        # 通知先が一つもなく、デバッグモードでもなければAPIを叩かない
        if not self.config["br"] and not self.config["ranked"] and not DEBUG_MODE:
            return

        url = f"https://api.mozambiquehe.re/maprotation?version=2&auth={ALS_API_KEY}"
        try:
            # タイムアウトを設定（API応答待ちによるフリーズ防止）
            response = requests.get(url, timeout=10)
            data = response.json()

            # デバッグログの送信
            if DEBUG_MODE and DEBUG_CHANNEL_ID:
                debug_channel = self.get_channel(DEBUG_CHANNEL_ID)
                if debug_channel:
                    debug_json = json.dumps(data, indent=2, ensure_ascii=False)
                    if len(debug_json) < 1900:
                        await debug_channel.send(f"**[DEBUG]**\n```json\n{debug_json}\n```")

            # APIから現在のマップ名を取得
            br_curr = data.get("battle_royale", {}).get("current", {}).get("map")
            rk_curr = data.get("ranked", {}).get("current", {}).get("map")

            # 【重要】どちらかのマップ名が取得できない（Noneや空）場合は、その回の処理をスキップ
            if not br_curr or not rk_curr:
                return

            # 初回起動時（Noneの状態）は通知せず、現在のマップ名を保存して終了
            if self.last_br_map is None or self.last_ranked_map is None:
                self.last_br_map = br_curr
                self.last_ranked_map = rk_curr
                await self.update_nicknames(br_curr, rk_curr)
                return

            # 変更チェック：マップ名が正しく取得できている前提での処理
            # ニックネームの更新
            if br_curr != self.last_br_map or rk_curr != self.last_ranked_map:
                await self.update_nicknames(br_curr, rk_curr)

            # ランクのマップ変更通知
            if rk_curr != self.last_ranked_map:
                await self.broadcast_map_update("ranked", f"**ランク** のマップが **{rk_curr}** に変更されました。")
            
            # カジュアルのマップ変更通知
            if br_curr != self.last_br_map:
                await self.broadcast_map_update("br", f"**カジュアル** のマップが **{br_curr}** に変更されました。")

            # 今回取得した正常なマップ名を保存
            self.last_br_map = br_curr
            self.last_ranked_map = rk_curr

        except Exception as e:
            print(f"Monitor Error: {e}")

    # 登録されたチャンネルへ通知を一斉送信
    async def broadcast_map_update(self, mode_key, message):
        for cid in self.config[mode_key][:]:
            channel = self.get_channel(cid)
            if channel:
                try:
                    await channel.send(message, silent=True)
                except discord.Forbidden:
                    pass
            else:
                # チャンネルが見つからない場合はリストから削除
                self.config[mode_key].remove(cid)
                self.save_channels()

    @map_monitor.before_loop
    async def before_monitor(self):
        await self.wait_until_ready()

bot = ApexBot()

# --- スラッシュコマンド ---

class MapRote(app_commands.Group):
    # 通知有効化
    @app_commands.command(name="enable", description="このチャンネルでマップ通知を有効にします")
    @app_commands.choices(mode=[
        app_commands.Choice(name="カジュアル", value="br"),
        app_commands.Choice(name="ランク", value="ranked")
    ])
    @is_admin_or_me()
    async def enable(self, interaction: discord.Interaction, mode: str):
        if interaction.channel_id not in bot.config[mode]:
            bot.config[mode].append(interaction.channel_id)
            bot.save_channels()
            await interaction.response.send_message(f"このチャンネルで **{mode}** の通知を有効にしました。", ephemeral=False)
        else:
            await interaction.response.send_message("このチャンネルでは既に通知が有効です。", ephemeral=True)

    # 通知無効化
    @app_commands.command(name="disable", description="このチャンネルでマップ通知を無効にします")
    @app_commands.choices(mode=[
        app_commands.Choice(name="カジュアル", value="br"),
        app_commands.Choice(name="ランク", value="ranked")
    ])
    @is_admin_or_me()
    async def disable(self, interaction: discord.Interaction, mode: str):
        if interaction.channel_id in bot.config[mode]:
            bot.config[mode].remove(interaction.channel_id)
            bot.save_channels()
            await interaction.response.send_message(f"このチャンネルで **{mode}** の通知を無効にしました。", ephemeral=False)
        else:
            await interaction.response.send_message("このチャンネルには通知設定がありません。", ephemeral=True)

    # ニックネーム表示モード設定
    @app_commands.command(name="set-nick", description="Botのニックネーム表示モード（カジュアル/ランク）を設定します")
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
        except discord.Forbidden:
            await interaction.response.send_message("権限不足によりニックネームを変更できませんでしたが、設定は保存されました。", ephemeral=False)

# コマンドグループの登録
bot.tree.add_command(MapRote(name="map-rote"))

bot.run(TOKEN)