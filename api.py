from fastapi import FastAPI, HTTPException, BackgroundTasks, Form, Depends, status, Body
from fastapi.responses import JSONResponse
import subprocess
import os
import sys
import yaml
import logging
from typing import Optional, List, Dict, Any
import uvicorn
import re
from pydantic import BaseModel, validator, Field

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="LLM-Bridge API",
    description="Ollama LLMモデルのダウンロードと設定管理のためのAPI",
    version="0.1.0"
)

CONFIG_PATH = "litellm_proxy/config.yaml"
LITELLM_CONTAINER_NAME = "litellm"

def get_available_local_models() -> List[Dict[str, Any]]:
    """ローカルのOllamaモデルを取得"""
    try:
        result = subprocess.run(
            ["docker", "exec", "ollama", "ollama", "list"],
            capture_output=True,
            text=True,
            check=True
        )
        models = []
        lines = result.stdout.strip().split("\n")
        if len(lines) > 1:
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

def get_configured_models() -> List[Dict[str, Any]]:
    """設定ファイルから構成されたモデルを取得"""
    if not os.path.exists(CONFIG_PATH):
        logger.error(f"設定ファイルが存在しません: {CONFIG_PATH}")
        return []
    try:
        with open(CONFIG_PATH, "r") as file:
            config = yaml.safe_load(file)
        if "model_list" in config and isinstance(config["model_list"], list):
            return config["model_list"]
        return []
    except Exception as e:
        logger.error(f"設定ファイルの読み込みに失敗: {e}")
        return []

def is_ollama_model(model_config: Dict[str, Any]) -> bool:
    """設定がOllamaモデルかどうかを判定"""
    if "litellm_params" in model_config and "model" in model_config["litellm_params"]:
        return model_config["litellm_params"]["model"].startswith("ollama/")
    return False

def remove_ollama_models_from_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """設定からOllamaモデルを削除"""
    if "model_list" in config and isinstance(config["model_list"], list):
        # Ollamaモデル以外を保持
        config["model_list"] = [
            model for model in config["model_list"] 
            if not is_ollama_model(model)
        ]
    return config

@app.get("/")
def root():
    """APIのルートエンドポイント"""
    return {"message": "LLM-Bridge API is running"}

@app.get("/models", response_model=List[Dict[str, Any]])
def list_models():
    ollama_models = get_available_local_models()
    configured_models = get_configured_models()
    configured_names = {model.get("model_name", "") for model in configured_models}

    result = []
    for model in ollama_models:
        result.append({
            "name": model["name"],
            "size": model["size"],
            "type": "ollama",
            "configured": model["name"] in configured_names
        })
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

class ModelRequest(BaseModel):
    model_path: str

@app.post("/models/download")
def download_ollama_model(req: ModelRequest):
    try:
        # "run" ではなく "pull" を使う
        process = subprocess.Popen(
            ["docker", "exec", "-i", "ollama", "ollama", "pull", req.model_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        output_lines = []
        for line in iter(process.stdout.readline, ''):
            output_lines.append(line)
            print(line.strip())

        process.stdout.close()
        returncode = process.wait(timeout=1800)

        if returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"エラーが発生しました（exit code: {returncode}）\n出力:\n{''.join(output_lines)}"
            )

        return {"message": "モデルのダウンロードが完了しました", "log": ''.join(output_lines)}

    except subprocess.TimeoutExpired:
        process.kill()
        raise HTTPException(status_code=504, detail="ダウンロードがタイムアウトしました（30分）")

class ModelManageRequest(BaseModel):
    model_name: str
    provider_model: Optional[str] = None
    no_restart: bool = False
    
    @validator('provider_model')
    def validate_provider_model(cls, v, values):
        if v is not None and '/' not in v:
            raise ValueError("provider_modelはプロバイダー/モデル名 の形式で指定してください（例: ollama/phi3, openai/gpt-4）")
        return v

@app.post("/models/manage")
def manage_model(req: ModelManageRequest):
    """
    モデルの追加または切り替えを行う統合エンドポイント
    provider_modelが指定された場合は新規追加、指定がない場合は既存モデルの切り替えとして動作

    Parameters:
        req (ModelManageRequest): 
            - model_name: モデル名
            - provider_model: プロバイダー/モデル名 (オプション、新規追加時のみ必要、例: ollama/phi3)
            - no_restart: 再起動しない場合はTrue
        
    Returns:
        dict: 操作結果を含むレスポンス
    """
    if not req.model_name:
        raise HTTPException(status_code=400, detail="モデル名は必須です")
    
    # 設定ファイル読み込み
    if not os.path.exists(CONFIG_PATH):
        raise HTTPException(status_code=500, detail="設定ファイルが見つかりません")
    
    try:
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f) or {}
            
        if "model_list" not in config:
            config["model_list"] = []
        
        model_list = config.get("model_list", [])
        
        # 新規追加モード (provider_modelあり)
        if req.provider_model:
            # プロバイダーチェック
            if '/' not in req.provider_model:
                raise HTTPException(
                    status_code=400, 
                    detail="provider_modelはプロバイダー/モデル名 の形式で指定してください（例: ollama/phi3, openai/gpt-4）"
                )
                
            # 新しいモデルがOllamaモデルか確認
            is_new_ollama_model = req.provider_model.startswith("ollama/")
            
            if is_new_ollama_model:
                # 既存のOllamaモデルを削除
                config = remove_ollama_models_from_config(config)
                
            # 新しいモデル設定を作成
            new_model_config = {
                "model_name": req.model_name,
                "litellm_params": {
                    "model": req.provider_model
                }
            }
            
            # Ollamaの場合はAPI Baseも設定
            if is_new_ollama_model:
                new_model_config["litellm_params"]["api_base"] = "http://ollama:11434"
            
            # 新しいモデルを追加（Ollamaモデルの場合は先頭に）
            if is_new_ollama_model:
                config["model_list"].insert(0, new_model_config)
            else:
                config["model_list"].append(new_model_config)
                
            operation = "追加"
            is_ollama = is_new_ollama_model
                
        # 切り替えモード (provider_modelなし)
        else:
            matched_model = None
            
            # 要求されたモデル名と一致するモデルを探す (完全一致)
            for model in model_list:
                if model.get("model_name", "") == req.model_name:
                    matched_model = model
                    break
                    
            # モデル名が見つからない場合はモデルパスも検索
            if not matched_model:
                for model in model_list:
                    if req.model_name in model.get("litellm_params", {}).get("model", ""):
                        matched_model = model
                        break
                        
            if not matched_model:
                raise HTTPException(status_code=404, detail=f"モデル {req.model_name} は設定に存在しません")
            
            # 要求されたモデルがOllamaモデルかチェック
            target_is_ollama = is_ollama_model(matched_model)
                
            if target_is_ollama:
                # Ollamaモデルの場合、他のOllamaモデルを削除
                non_ollama_models = [m for m in model_list if not is_ollama_model(m)]
                new_model_list = [matched_model] + non_ollama_models
            else:
                # Ollamaモデル以外の場合、モデルを先頭に移動
                new_model_list = [matched_model] + [m for m in model_list if m != matched_model]
                
            config["model_list"] = new_model_list
            operation = "切り替え"
            is_ollama = target_is_ollama
        
        # 設定ファイルを書き込み
        with open(CONFIG_PATH, "w") as f:
            yaml.safe_dump(config, f)
            
        # litellmの再起動（Docker前提）
        restart_info = ""
        if not req.no_restart:
            result = subprocess.run(
                ["docker", "restart", LITELLM_CONTAINER_NAME],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"Dockerコンテナの再起動に失敗しました: {result.stderr}"
                )
            restart_info = f"、再起動しました: {result.stdout.strip()}"
                
        return {
            "message": f"モデル {req.model_name} を {operation} しました{restart_info}",
            "status": "success",
            "operation": operation,
            "is_ollama": is_ollama
        }
            
    except Exception as e:
        logger.error(f"モデル操作中にエラーが発生: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"モデル操作に失敗しました: {str(e)}"
        )

@app.get("/config", response_model=Dict[str, Any])
def get_current_config():
    """現在の設定を取得"""
    try:
        if not os.path.exists(CONFIG_PATH):
            raise HTTPException(status_code=500, detail="設定ファイルが見つかりません")
            
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)
            
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"設定ファイルの読み込みに失敗しました: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=9999, reload=True)
