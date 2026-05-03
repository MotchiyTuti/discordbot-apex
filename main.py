import requests

# 1. あなたのAPIキーを設定
API_KEY = "8d3fdfcb60d8738591a5b4a8dea518b1"

# 2. エンドポイントの設定（マップローテーション取得用）
url = f"https://api.mozambiqueheere.com/maprotation?auth={API_KEY}"

try:
    # 3. APIリクエストの実行
    response = requests.get(url)
    
    # ステータスコードが200(成功)か確認
    response.raise_for_status()

    # 4. データの解析
    data = response.json()

    # 結果の表示
    current_map = data['battle_royale']['current']['map']
    remaining_time = data['battle_royale']['current']['remainingTimer']
    next_map = data['battle_royale']['next']['map']

    print(f"--- Apex Legends Map Status ---")
    print(f"現在のマップ: {current_map}")
    print(f"残り時間: {remaining_time}")
    print(f"次のマップ: {next_map}")

except requests.exceptions.HTTPError as err:
    print(f"HTTPエラーが発生しました: {err}")
except Exception as e:
    print(f"エラーが発生しました: {e}")