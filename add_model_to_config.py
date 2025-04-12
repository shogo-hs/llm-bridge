import argparse
import os
import sys
import yaml
import subprocess

# configファイルのパス
CONFIG_PATH = "litellm_proxy/config.yaml"

def load_config():
    """設定ファイルを読み込む"""
    try:
        with open(CONFIG_PATH, "r") as file:
            config = yaml.safe_load(file)
        return config
    except FileNotFoundError:
        print(f"エラー：設定ファイル {CONFIG_PATH} が見つかりません。")
        return None
    except yaml.YAMLError as e:
        print(f"エラー：設定ファイルの解析中にエラーが発生しました: {e}")
        return None

def save_config(config):
    """設定ファイルを保存する"""
    try:
        with open(CONFIG_PATH, "w") as file:
            yaml.dump(config, file, default_flow_style=False, sort_keys=False, allow_unicode=True)
        return True
    except Exception as e:
        print(f"エラー：設定ファイルの保存中にエラーが発生しました: {e}")
        return False

def add_model_to_config(model_name, model_path):
    """モデルを設定ファイルに追加する"""
    # 設定ファイルを読み込む
    config = load_config()
    if config is None:
        return False
    
    # モデルリストがない場合は作成
    if "model_list" not in config:
        config["model_list"] = []
    
    # モデルが既に存在するか確認
    for model in config["model_list"]:
        if model.get("model_name") == model_name:
            print(f"警告：モデル名 {model_name} は既に設定ファイルに存在します。")
            user_input = input("上書きしますか？ (y/n): ").strip().lower()
            if user_input \!= "y":
                print("操作をキャンセルしました。")
                return False
            # 既存のモデルを削除
            config["model_list"].remove(model)
            break
    
    # 新しいモデルを追加
    new_model = {
        "model_name": model_name,
        "litellm_params": {
            "model": f"ollama/{model_path}",
            "api_base": "http://ollama:11434"
        }
    }
    
    config["model_list"].append(new_model)
    
    # 設定ファイルを保存
    if save_config(config):
        print(f"モデル {model_name} を設定ファイルに追加しました。")
        return True
    return False

def restart_litellm_container():
    """LiteLLM Proxyコンテナを再起動する"""
    try:
        print("LiteLLM Proxyコンテナを再起動しています...")
        subprocess.run(
            ["docker-compose", "restart", "litellm"],
            check=True
        )
        print("LiteLLM Proxyコンテナの再起動が完了しました。")
        return True
    except subprocess.CalledProcessError as e:
        print(f"エラー：コンテナの再起動中に問題が発生しました: {e}")
        return False

def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="モデルを設定ファイルに追加するスクリプト")
    parser.add_argument("model_name", help="モデルの名前（例：Llama-3-ELYZA-JP-8B-GGUF）")
    parser.add_argument("model_path", help="モデルのパス（例：hf.co/elyza/Llama-3-ELYZA-JP-8B-GGUF）")
    parser.add_argument("--no-restart", action="store_true", help="設定変更後にコンテナを再起動しない")
    
    args = parser.parse_args()
    
    # 設定ファイルにモデルを追加
    if add_model_to_config(args.model_name, args.model_path):
        if not args.no_restart:
            # コンテナを再起動
            if not restart_litellm_container():
                print("警告：設定は更新されましたが、コンテナの再起動に失敗しました。")
                print("手動で再起動するには次のコマンドを実行してください：docker-compose restart litellm")
                return 1
        else:
            print("コンテナの再起動をスキップしました。")
            print("変更を適用するには次のコマンドを実行してください：docker-compose restart litellm")
        return 0
    return 1

if __name__ == "__main__":
    sys.exit(main())

