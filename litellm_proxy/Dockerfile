FROM python:3.10-slim

WORKDIR /app

# 必要なパッケージのインストール
RUN pip install --no-cache-dir litellm[proxy]

# 設定ファイルをコピー
COPY config.yaml .

# サーバー起動コマンド
CMD ["litellm", "--config", "config.yaml"]
