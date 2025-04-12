from fastapi import FastAPI, HTTPException, BackgroundTasks, Form, Depends, status
from fastapi.responses import JSONResponse
import subprocess
import os
import sys
import yaml
import logging
from typing import Optional, List, Dict, Any
import uvicorn
import re

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# 既存のスクリプトのインポート
# 直接インポートせず、サブプロセスとして実行するため実際のインポートは不要

app = FastAPI(
    title="LLM-Bridge API",
    description="Ollama LLMモデルのダウンロードと設定管理のためのAPI",
    version="0.1.0"
)

# モデル一覧を取得する関数
def get_available_models() -> List[Dict[str, Any]]:
    """Ollamaで利用可能なモデル一覧を取得"""
    try:
        # ollama listコマンドを実行
        result = subprocess.run(
            ["docker", "exec", "ollama", "ollama", "list"],
            capture_output=True,
            text=True,
            check=True
        )
        
        # 出力から必要な情報を抽出
        models = []
        lines = result.stdout.strip().split("
")
        if len(lines) > 1:  # ヘッダー行をスキップ
            for line in lines[1:]:
                parts = re.split(r"\s{2,}", line.strip())
                if len(parts) >= 3:
                    models.append({
                        "name": parts[0],
                        "size": parts[2],
                        "modified": parts[1]
                    })
        return models
    except subprocess.CalledProcessError as e:
        logger.error(f"モデル一覧の取得に失敗: {e}")
        return []

# 設定ファイルからモデル設定を取得
def get_configured_models() -> List[Dict[str, Any]]:
    """config.yamlから設定済みモデルを取得"""
    config_path = "litellm_proxy/config.yaml"
    try:
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)
        
        if "model_list" in config and isinstance(config["model_list"], list):
            return config["model_list"]
        return []
    except Exception as e:
        logger.error(f"設定ファイルの読み込みに失敗: {e}")
        return []

@app.get("/")
async def root():
    """APIのルートエンドポイント"""
    return {"message": "LLM-Bridge API is running"}

@app.get("/models", response_model=List[Dict[str, Any]])
async def list_models():
    """利用可能なモデルの一覧を取得"""
    # Ollamaモデル一覧
    ollama_models = get_available_models()
    
    # 設定ファイルからモデル設定を取得
    configured_models = get_configured_models()
    
    # 設定済みモデル名のセット
    configured_names = {model.get("model_name", "") for model in configured_models}
    
    # 結果を組み合わせる
    result = []
    
    # Ollamaモデルを追加
    for model in ollama_models:
        model_info = {
            "name": model["name"],
            "size": model["size"],
            "type": "ollama",
            "configured": model["name"] in configured_names
        }
        result.append(model_info)
    
    # 設定のみに存在するモデル（APIモデルなど）を追加
    for model in configured_models:
        name = model.get("model_name", "")
        if not any(m["name"] == name for m in ollama_models):
            model_type = "api"
            if "litellm_params" in model and "model" in model["litellm_params"]:
                if model["litellm_params"]["model"].startswith("ollama/"):
                    model_type = "ollama"
                elif "openai" in model["litellm_params"]["model"]:
                    model_type = "openai"
            
            result.append({
                "name": name,
                "size": "N/A",
                "type": model_type,
                "configured": True
            })
    
    return result

@app.post("/models/download")
async def download_model(
    background_tasks: BackgroundTasks,
    model_path: str = Form(...),
    model_name: Optional[str] = Form(None),
    skip_config: bool = Form(False),
    no_restart: bool = Form(False)
):
    """モデルをダウンロードし、オプションで設定に追加"""
    if not model_path:
        raise HTTPException(status_code=400, detail="モデルパスを指定してください")
    
    # バックグラウンドタスクとしてダウンロードを実行
    def download_task():
        cmd = [sys.executable, "add_model.py", model_path]
        if model_name:
            cmd.extend(["--name", model_name])
        if skip_config:
            cmd.append("--skip-download")
        if no_restart:
            cmd.append("--no-restart")
        
        try:
            subprocess.run(cmd, check=True)
            logger.info(f"モデル {model_path} のダウンロードが完了しました")
        except subprocess.CalledProcessError as e:
            logger.error(f"モデルのダウンロード中にエラーが発生: {e}")
    
    background_tasks.add_task(download_task)
    
    return {
        "message": f"モデル {model_path} のダウンロードを開始しました",
        "status": "processing"
    }

@app.post("/models/config")
async def add_model_config(
    model_name: str = Form(...),
    model_path: str = Form(...),
    no_restart: bool = Form(False)
):
    """モデルを設定に追加（ダウンロードはスキップ）"""
    if not model_name or not model_path:
        raise HTTPException(status_code=400, detail="モデル名とパスを指定してください")
    
    cmd = [sys.executable, "add_model_to_config.py", model_name, model_path]
    if no_restart:
        cmd.append("--no-restart")
    
    try:
        subprocess.run(cmd, check=True)
        return {"message": f"モデル {model_name} を設定に追加しました", "status": "success"}
    except subprocess.CalledProcessError as e:
        logger.error(f"設定の追加中にエラーが発生: {e}")
        raise HTTPException(status_code=500, detail=f"設定の追加に失敗しました: {str(e)}")

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """グローバル例外ハンドラ"""
    logger.error(f"予期しないエラーが発生: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "内部サーバーエラーが発生しました", "detail": str(exc)}
    )

# サーバー起動（直接実行時のみ）
if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=9999, reload=True)

