# LLM統一インターフェース環境

このプロジェクトは、OllamaとLiteLLMを組み合わせることで、ローカルのHugging Faceモデルと、GPT-4oなどのAPIベースのLLMを同じインターフェースで使用できる環境を提供します。

## 構成

- **Ollama**: ローカルでLLMを実行するサービス
- **LiteLLM Proxy**: 異なるLLMへの統一インターフェースを提供

## セットアップ手順

### 1. 前提条件

- Docker
- Docker Compose
- （オプション）OpenAI APIキー（GPT-4oを使用する場合）等

### 2. 環境変数の設定（オプション）

OpenAI APIを使用する場合は、`.env`ファイルをプロジェクトルートに作成し、以下を追加します：

```
OPENAI_API_KEY=your_openai_api_key_here
...
...
...
```

### 3. 起動

以下のコマンドで環境を起動します：

```bash
docker-compose up -d
```

### 4. モデルのダウンロード

OllamaでHugging Faceモデルをダウンロードします：

```bash
# Dockerコンテナに入る
docker exec -it ollama bash

# モデルをダウンロード（例：ELYZA-JPのLlama 3モデル）
ollama run hf.co/elyza/Llama-3-ELYZA-JP-8B-GGUF
```

### 5. テスト

提供されているPythonスクリプトを使ってモデルをテストできます：

```bash
# テスト実行に必要なライブラリをインストール
pip install requests

# テストスクリプトを実行
python test_models.py
```

## 使用方法

### APIリクエスト

OpenAI互換のAPIを通じてモデルにアクセスできます：

```python
import requests
import json

# LiteLLM Proxyへリクエスト
response = requests.post(
    "http://localhost:8000/v1/chat/completions",
    headers={"Content-Type": "application/json"},
    json={
        "model": "Llama-3-ELYZA-JP-8B-GGUF",  # または "gpt-4o-mini"など
        "messages": [{"role": "user", "content": "こんにちは、自己紹介してください"}],
        "temperature": 0.7
    }
)

# 結果を表示
print(json.dumps(response.json(), indent=2, ensure_ascii=False))
```

### モデルの追加

新しいモデルを追加するには、`litellm_proxy/config.yaml`ファイルを編集します：

```yaml
model_list:
  - model_name: 新しいモデル名
    litellm_params:
      model: "ollama/新しいモデルのパス"
      api_base: "http://ollama:11434"
```

編集後、LiteLLM Proxyを再起動してください：

```bash
docker-compose restart litellm
```

## トラブルシューティング

- **接続エラー**: サービスが正しく起動しているか確認してください：`docker-compose ps`
- **モデルロードエラー**: モデルが正しくダウンロードされているか確認します：`docker exec -it ollama ollama list`
