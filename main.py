import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def get_map_rotation():
    api_key = os.getenv("ALS_API_KEY")
    # 文字列として取得し、小文字にして比較する
    debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"

    if not api_key:
        print("エラー: ALS_API_KEY が設定されていません。")
        return

    url = f"https://api.mozambiquehe.re/maprotation?version=2&auth={api_key}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        # デバッグモードがONの時だけ生データを表示
        if debug_mode:
            print("\n--- [DEBUG] Raw API Response ---")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("-------------------------------\n")

        br = data.get("battle_royale", {})
        
        current_map = br.get("current", {}).get("map", "不明")
        remaining = br.get("current", {}).get("remainingTimer", "00:00")
        next_map = br.get("next", {}).get("map", "不明")

        print("=== Apex Legends Current Map Rotation ===")
        print(f"【現在のマップ】: {current_map}")
        print(f"【残り時間】  : {remaining}")
        print(f"【次のマップ】  : {next_map}")
        print("==========================================")

    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    get_map_rotation()