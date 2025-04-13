import argparse
import os
import sys
import yaml
import subprocess

CONFIG_PATH = "litellm_proxy/config.yaml"

def load_config():
    try:
        with open(CONFIG_PATH, "r") as file:
            config = yaml.safe_load(file)
        return config
    except FileNotFoundError:
        print(f"[ERROR] 設定ファイル {CONFIG_PATH} が見つかりません。")
        return None
    except yaml.YAMLError as e:
        print(f"[ERROR] 設定ファイルの解析エラー: {e}")
        return None

def save_config(config):
    try:
        with open(CONFIG_PATH, "w") as file:
            yaml.dump(config, file, default_flow_style=False, sort_keys=False, allow_unicode=True)
        return True
    except Exception as e:
        print(f"[ERROR] 設定ファイルの保存に失敗しました: {e}")
        return False

def add_model_to_config(model_name, model_path, force=False):
    config = load_config()
    if config is None:
        return False

    if "model_list" not in config:
        config["model_list"] = []

    for model in config["model_list"]:
        if model.get("model_name") == model_name:
            if not force:
                print(f"[WARN] モデル名 {model_name} は既に存在します。--force を指定して上書きしてください。")
                return False
            else:
                print(f"[INFO] 既存のモデル {model_name} を上書きします。")
                config["model_list"].remove(model)
                break

    new_model = {
        "model_name": model_name,
        "litellm_params": {
            "model": f"ollama/{model_path}",
            "api_base": "http://ollama:11434"
        }
    }

    config["model_list"].append(new_model)

    if save_config(config):
        print(f"[INFO] モデル {model_name} を設定に追加しました。")
        return True
    return False

def restart_litellm_container():
    try:
        print("[INFO] LiteLLM Proxyコンテナを再起動しています...")
        result = subprocess.run(
            ["docker-compose", "restart", "litellm"],
            capture_output=True,
            text=True,
            check=True
        )
        print("[STDOUT] " + result.stdout.strip())
        print("[INFO] 再起動が完了しました。")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] コンテナの再起動に失敗しました。")
        print(f"[CMD] docker-compose restart litellm")
        print(f"[STDERR] {e.stderr.strip() if e.stderr else '詳細不明'}")
        return False

def main():
    parser = argparse.ArgumentParser(description="モデルを設定ファイルに追加するスクリプト")
    parser.add_argument("model_name", help="モデルの表示名（例：Llama-3-ELYZA-JP-8B-GGUF）")
    parser.add_argument("model_path", help="モデルのパス（例：hf.co/elyza/Llama-3-ELYZA-JP-8B-GGUF）")
    parser.add_argument("--force", action="store_true", help="既存モデルがあっても強制的に上書きする")
    parser.add_argument("--no-restart", action="store_true", help="設定後にlitellmコンテナを再起動しない")

    args = parser.parse_args()

    if add_model_to_config(args.model_name, args.model_path, args.force):
        if not args.no_restart:
            if not restart_litellm_container():
                print("[WARN] 設定は更新されましたが、コンテナの再起動に失敗しました。")
                print("手動で次を実行してください： docker-compose restart litellm")
                return 1
        else:
            print("[INFO] コンテナの再起動はスキップされました。")
        return 0
    return 1

if __name__ == "__main__":
    sys.exit(main())
