import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()

def get_map_data(api_key):
    url = f"https://api.mozambiquehe.re/maprotation?version=2&auth={api_key}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"APIエラー: {e}")
        return None

def monitor_maps():
    api_key = os.getenv("ALS_API_KEY")
    if not api_key:
        print("エラー: ALS_API_KEY が設定されていません。")
        return

    # 前回のマップを記録する変数
    last_br_map = None
    last_ranked_map = None

    print("マップの監視を開始しました... (Ctrl+C で終了)")

    while True:
        data = get_map_data(api_key)
        
        if data:
            # データの抽出
            br_current = data.get("battle_royale", {}).get("current", {})
            rk_current = data.get("ranked", {}).get("current", {})
            
            curr_br_map = br_current.get("map")
            curr_rk_map = rk_current.get("map")

            # カジュアルの変更検知
            if last_br_map is not None and last_br_map != curr_br_map:
                print(f"[カジュアル]のマップが[{curr_br_map}]に変更されました。")
            
            # ランクの変更検知
            if last_ranked_map is not None and last_ranked_map != curr_rk_map:
                print(f"[ランク]のマップが[{curr_rk_map}]に変更されました。")

            # 初回実行時または変更時にログを表示したい場合はここ
            # print(f"Check: BR={curr_br_map}, Ranked={curr_rk_map}")

            # 状態を更新
            last_br_map = curr_br_map
            last_ranked_map = curr_rk_map

        # 60秒待機してから再チェック
        time.sleep(60)

if __name__ == "__main__":
    monitor_maps()