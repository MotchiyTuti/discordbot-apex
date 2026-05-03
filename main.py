import os
import requests
from dotenv import load_dotenv

# 1. .envファイルから環境変数を読み込む
load_dotenv()

# 2. 環境変数からAPIキーを取得
API_KEY = os.getenv("ALS_API_KEY")

if not API_KEY:
    print("エラー: APIキーが設定されていません。'.env' ファイルを確認してください。")
    exit()

def check_map_rotation():
    # エンドポイント
    url = "https://api.mozambiqueheere.com/maprotation"
    
    # クエリパラメータとして認証情報を渡す
    params = {
        "auth": API_KEY
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        br = data['battle_royale']['current']
        
        print(f"✅ 接続成功")
        print(f"現在のマップ: {br['map']}")
        print(f"終了まであと: {br['remainingMins']} 分")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ エラーが発生しました: {e}")

if __name__ == "__main__":
    check_map_rotation()