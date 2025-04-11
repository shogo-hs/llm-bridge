import requests
import json
import os
import argparse

LITELLM_API_BASE = "http://localhost:8000"

def test_model(model_name, prompt):
    """指定されたモデルでプロンプトを実行し、結果を表示"""
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 500
    }
    try:
        response = requests.post(
            f"{LITELLM_API_BASE}/v1/chat/completions",
            headers=headers,
            data=json.dumps(payload)
        )
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            print(f"\n===== {model_name} の応答 =====")
            print(content)
            return content
        else:
            print(f"エラー: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"例外発生: {str(e)}")
        return None

if __name__ == "__main__":
    # 引数の定義
    parser = argparse.ArgumentParser(description="LiteLLM Proxy 経由でモデルを実行します")
    parser.add_argument("--model", type=str, required=True, help="使用するモデル名")
    parser.add_argument("--prompt", type=str, default="日本の四季について短く説明してください", help="プロンプト文")

    args = parser.parse_args()

    print("LiteLLM Proxyを使用してLLMモデルをテスト中...\n")
    test_model(args.model, args.prompt)
