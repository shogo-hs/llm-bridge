import argparse
import os
import sys
import subprocess
import time

def run_download_model(model_path):
    """モデルをダウンロードするスクリプトを実行"""
    print(f"モデル {model_path} のダウンロードを開始します...")
    
    try:
        subprocess.run(
            [sys.executable, "download_model.py", model_path],
            check=True
        )
        return True
    except subprocess.CalledProcessError:
        print("モデルのダウンロードに失敗しました。")
        return False

def run_add_model_to_config(model_name, model_path, no_restart=False):
    """モデルを設定に追加するスクリプトを実行"""
    print(f"モデル {model_name} を設定に追加します...")
    
    cmd = [sys.executable, "add_model_to_config.py", model_name, model_path]
    if no_restart:
        cmd.append("--no-restart")
    
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        print("設定へのモデル追加に失敗しました。")
        return False

def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="モデルをダウンロードして設定に追加する統合スクリプト")
    parser.add_argument("model_path", help="ダウンロードするモデルのパス（例：hf.co/elyza/Llama-3-ELYZA-JP-8B-GGUF）")
    parser.add_argument("--name", help="設定に追加する際のモデル名（指定しない場合はモデルパスの最後の部分が使用されます）")
    parser.add_argument("--no-restart", action="store_true", help="設定変更後にコンテナを再起動しない")
    parser.add_argument("--skip-download", action="store_true", help="モデルのダウンロードをスキップして設定のみ更新")
    
    args = parser.parse_args()
    
    # モデル名がない場合はパスの最後の部分を使用
    model_name = args.name if args.name else args.model_path.split("/")[-1]
    
    # モデルをダウンロード
    if not args.skip_download:
        if not run_download_model(args.model_path):
            print("モデルのダウンロードに失敗したため、設定の更新はスキップされました。")
            return 1
    else:
        print("モデルのダウンロードをスキップします...")
    
    # 少し待機（ダウンロード完了後の処理のため）
    time.sleep(1)
    
    # 設定ファイルにモデルを追加
    if not run_add_model_to_config(model_name, args.model_path, args.no_restart):
        return 1
    
    print(f"✅ モデル {model_name} の追加プロセスが完了しました。")
    print(f"使用例: python run_llm.py --model {model_name} --prompt \"あなたの質問をここに入力\"")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

