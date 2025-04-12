# LLM統一インターフェース環境

このプロジェクトは、OllamaとLiteLLMを組み合わせることで、ローカルのHugging Faceモデルと、GPT-4oなどのAPIベースのLLMを同じインターフェースで使用できる環境を提供します。

## 構成

- **Ollama**: ローカルでLLMを実行するサービス
- **LiteLLM Proxy**: 異なるLLMへの統一インターフェースを提供
- **管理API**: モデルのダウンロードと設定管理のためのRESTful API

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

#### CPU版（デフォルト）

CPU版の環境を起動するには以下のコマンドを使用します：

```bash
# デフォルト（CPU版）
docker-compose up -d

# または明示的にCPU版を指定
docker-compose -f docker-compose.cpu.yml up -d
```

#### GPU版

NVIDIA GPUを使用する場合は、GPU対応の構成を使用できます：

```bash
docker-compose -f docker-compose.gpu.yml up -d
```

GPU版を使用するには、ホストマシンに以下のものが必要です：
- NVIDIA GPU
- NVIDIA Driverのインストール
- NVIDIA Container Toolkit（nvidia-docker2）のインストール

### 4. モデルのダウンロード

モデルを追加するには、以下の方法があります：

#### 4.1 管理API経由で追加（最も簡単）

RESTful APIを使用してモデルを追加できます：

```bash
# モデルをダウンロードして設定に追加
curl -X POST "http://localhost:9999/models/download" \
  -F "model_path=hf.co/elyza/Llama-3-ELYZA-JP-8B-GGUF"

# カスタム名でモデルを追加
curl -X POST "http://localhost:9999/models/download" \
  -F "model_path=hf.co/elyza/Llama-3-ELYZA-JP-8B-GGUF" \
  -F "model_name=ELYZA-Japanese"

# ダウンロードせずに設定のみ更新
curl -X POST "http://localhost:9999/models/config" \
  -F "model_name=ELYZA-Japanese" \
  -F "model_path=hf.co/elyza/Llama-3-ELYZA-JP-8B-GGUF"
```

利用可能なモデルの一覧を取得：

```bash
curl -X GET "http://localhost:9999/models"
```

#### 4.2 スクリプトによる追加

コマンドラインスクリプトを使用してモデルを追加することもできます：

```bash
# モデルをダウンロードして設定に追加
python add_model.py hf.co/elyza/Llama-3-ELYZA-JP-8B-GGUF

# カスタム名でモデルを追加
python add_model.py hf.co/elyza/Llama-3-ELYZA-JP-8B-GGUF --name "ELYZA-Japanese"

# ダウンロードをスキップして設定のみ更新
python add_model.py hf.co/elyza/Llama-3-ELYZA-JP-8B-GGUF --skip-download

# コンテナの再起動をスキップ
python add_model.py hf.co/elyza/Llama-3-ELYZA-JP-8B-GGUF --no-restart
```

#### 4.3 手動での追加

もしくは従来通り手動で行うこともできます：

```bash
# Dockerコンテナに入る
docker exec -it ollama bash

# モデルをダウンロード（例：ELYZA-JPのLlama 3モデル）
ollama run hf.co/elyza/Llama-3-ELYZA-JP-8B-GGUF
```

その後、`litellm_proxy/config.yaml`ファイルを編集してモデルを追加します。

### 5. モデルのテスト

提供されているPythonスクリプトを使ってモデルをテストできます：

```bash
# モデルを指定してテスト実行
python run_llm.py --model Llama-3-ELYZA-JP-8B-GGUF --prompt "こんにちは、自己紹介してください"
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

### 管理API

モデルの管理に使用できるRESTful APIが提供されています：

| エンドポイント | メソッド | 説明 |
|--------------|---------|------|
| `/models` | GET | 利用可能なモデルの一覧を取得 |
| `/models/download` | POST | モデルをダウンロードして設定に追加 |
| `/models/config` | POST | モデルを設定に追加（ダウンロードなし） |

APIは自動生成されたSwagger UIドキュメントでもアクセスできます：
`http://localhost:9999/docs`

### コマンドラインユーティリティ

このプロジェクトには、モデル管理を簡単にするための以下のユーティリティが追加されています：

- **add_model.py**: モデルのダウンロードと設定への追加を一度に行う統合スクリプト
- **download_model.py**: Ollamaモデルをダウンロードする単独スクリプト
- **add_model_to_config.py**: 設定ファイルにモデルを追加する単独スクリプト

### 設定ファイルの手動編集

設定ファイルを直接編集することもできます：

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
- **APIエラー**: ログを確認してエラーの原因を特定します：`docker logs llm-bridge-api`
- **スクリプトエラー**: 必要なPythonパッケージがインストールされているか確認します：`pip install pyyaml requests fastapi uvicorn python-multipart`
- **GPU関連エラー**: 
  - GPUが認識されているか確認：`nvidia-smi`
  - NVIDIA Container Toolkitが正しくインストールされているか確認：`docker info | grep -i nvidia`
  - GPU版を起動後、`docker exec -it ollama nvidia-smi`でOllamaコンテナ内からGPUが見えるか確認
