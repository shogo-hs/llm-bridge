import argparse
import subprocess
import os
import sys
import time

def check_docker_running():
    """Dockerが実行中かチェック"""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=ollama", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=True
        )
        return "ollama" in result.stdout
    except subprocess.CalledProcessError:
        return False

def download_model(model_path):
    """Ollamaコンテナでモデルをダウンロード"""
    print(f"モデル {model_path} のダウンロードを開始します...")
    
    # モデル名を取得（パスの最後の部分）
    model_name = model_path.split("/")[-1] if "/" in model_path else model_path
    
    try:
        # ollama runコマンドを実行
        process = subprocess.Popen(
            ["docker", "exec", "-it", "ollama", "ollama", "run", model_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        # 進行状況をリアルタイムに表示
        start_time = time.time()
        last_update = ""
        downloading = False
        
        for line in iter(process.stdout.readline, ""):
            # ダウンロード関連の行かどうかをチェック
            if "downloading model" in line.lower() or "pulling" in line.lower():
                downloading = True
                sys.stdout.write(f"{line.strip()}")
                sys.stdout.flush()
                last_update = line.strip()
            # 通常のダウンロード進捗表示
            elif downloading and "%" in line:
                sys.stdout.write(f"{line.strip()}")
                sys.stdout.flush()
                last_update = line.strip()
            # 対話モードに入ったらCtrl+Cを送信
            elif ">>" in line or "Prompt:" in line:
                # プロセスを終了（Ctrl+C相当）
                process.terminate()
                print("モデルのダウンロードが完了しました。")
                break
        
        # プロセスの終了を待つ
        process.wait(timeout=5)
        
        # ダウンロードが成功したかを確認
        if verify_model_installed(model_path):
            print(f"モデル {model_name} が正常にインストールされました！")
            return True
        else:
            print(f"エラー：モデル {model_name} のインストールを確認できませんでした。")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"エラー：モデルのダウンロード中に問題が発生しました: {e}")
        return False
    except KeyboardInterrupt:
        print("ダウンロードがユーザーによって中断されました。")
        return False

def verify_model_installed(model_path):
    """モデルが正しくインストールされたか確認"""
    # モデル名を取得（パスの最後の部分）
    model_name = model_path.split("/")[-1] if "/" in model_path else model_path
    
    try:
        # ollama listコマンドを実行
        result = subprocess.run(
            ["docker", "exec", "ollama", "ollama", "list"],
            capture_output=True,
            text=True,
            check=True
        )
        
        # 出力に目的のモデル名が含まれているかチェック
        return model_name in result.stdout or model_path in result.stdout
    except subprocess.CalledProcessError:
        return False

def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="Ollamaでモデルをダウンロードするスクリプト")
    parser.add_argument("model_path", help="ダウンロードするモデルのパス（例：hf.co/elyza/Llama-3-ELYZA-JP-8B-GGUF）")
    args = parser.parse_args()
    
    # Dockerが実行中か確認
    if not check_docker_running():
        print("エラー：Ollamaコンテナが実行されていません。")
        print("docker-compose up -d を実行してから再試行してください。")
        return 1
    
    # モデルをダウンロード
    success = download_model(args.model_path)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())

