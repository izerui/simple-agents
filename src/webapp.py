from fastapi import FastAPI, HTTPException, APIRouter, Query
from fastapi.responses import StreamingResponse
import logging
import os
from pathlib import Path
import shutil
import traceback
from typing import Any
from urllib.parse import quote

from langgraph_sdk import get_client
from langsmith import tracing_context

from deepagents.backends import FilesystemBackend
from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field

from src.prompts import load_prompt_from_file
from src.utils.model_config import get_model_init_kwargs

app = FastAPI(title="Webapp Agents API", version="0.1.0")

router = APIRouter(prefix="/webapp")


# ============ 响应模型 ============

class ApiResponse(BaseModel):
    """通用 API 响应模型"""
    success: bool
    err_message: str | None = None
    data: Any = None


class ModelInfo(BaseModel):
    """模型信息"""
    name: str
    provider: str | None = None
    base_url: str | None = None
    is_default: bool = False


class ModelListResponse(BaseModel):
    """模型列表响应"""
    success: bool
    err_message: str | None = None
    data: list[ModelInfo] | None = None


class ResetThreadRequest(BaseModel):
    """重置线程请求"""
    metadata: dict[str, Any] | None = None


def _get_thread_dir(thread_id: str) -> Path:
    """基于 thread_id 计算线程沙箱目录，并阻止路径逃逸。"""
    sandbox_root_dir = Path(os.getenv('SANDBOX_ROOT_DIR', './data/sandbox_sessions')).resolve()
    thread_dir = (sandbox_root_dir / thread_id).resolve()

    if sandbox_root_dir not in thread_dir.parents and thread_dir != sandbox_root_dir:
        raise HTTPException(status_code=400, detail="非法的 thread_id")

    return thread_dir


# 文件下载端点
@router.get("/download/{thread_id}", tags=["Webapp"])
async def download_file(
    thread_id: str,
    path: str = Query(..., description="要下载的文件路径（相对于 thread_dir）")
):
    """
    根据指定的 thread_id 和文件路径下载文件。
    
    Args:
        thread_id: 对话线程 ID
        path: 要下载的文件路径（相对于 thread_dir 的虚拟路径）
    
    Returns:
        StreamingResponse: 文件内容的流式响应
    """
    import io

    thread_dir = str(_get_thread_dir(thread_id))

    # 创建新的 Backend 实例
    backend = FilesystemBackend(
        root_dir=thread_dir,
        max_file_size_mb=50,
    )
    
    try:
        # 去掉前导斜杠，支持 path=/deepthink/... 和 path=deepthink/... 两种格式
        path = path.lstrip('/')

        # 使用后端下载文件
        responses = await backend.adownload_files([path])
        
        if not responses:
            raise HTTPException(status_code=404, detail="文件未找到")
        
        response = responses[0]
        
        if response.error:
            # 根据错误类型返回相应的 HTTP 状态码
            if response.error == "file_not_found":
                raise HTTPException(status_code=404, detail=f"文件未找到: {path}")
            elif response.error == "permission_denied":
                raise HTTPException(status_code=403, detail=f"无权限访问文件: {path}")
            elif response.error == "is_directory":
                raise HTTPException(status_code=400, detail=f"路径是一个目录，不是文件: {path}")
            elif response.error == "invalid_path":
                raise HTTPException(status_code=400, detail=f"无效的路径: {path}")
            else:
                raise HTTPException(status_code=500, detail=f"下载文件失败: {response.error}")
        
        if response.content is None:
            raise HTTPException(status_code=404, detail="文件内容为空")
        
        # 创建流式响应
        file_like = io.BytesIO(response.content)
        
        # 从路径中提取文件名
        filename = os.path.basename(path)
        
        # 根据文件扩展名确定媒体类型
        media_type = "application/octet-stream"
        if path.endswith('.txt'):
            media_type = "text/plain"
        elif path.endswith('.pdf'):
            media_type = "application/pdf"
        elif path.endswith('.json'):
            media_type = "application/json"
        elif path.endswith('.csv'):
            media_type = "text/csv"
        elif path.endswith(('.png', '.jpg', '.jpeg', '.gif')):
            media_type = f"image/{path.split('.')[-1]}"
        
        # 处理文件名编码，支持中文和其他非 ASCII 字符
        # 使用 RFC 5987 标准：filename*=UTF-8''url_encoded_filename
        encoded_filename = quote(filename)
        content_disposition = f"attachment; filename*=UTF-8''{encoded_filename}"
        
        return StreamingResponse(
            file_like,
            media_type=media_type,
            headers={"Content-Disposition": content_disposition}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载文件时发生错误: {str(e)}")


@router.post("/reset/{thread_id}", tags=["Webapp"], response_model=ApiResponse)
async def reset_thread_with_sandbox(
    thread_id: str,
    request: ResetThreadRequest | None = None,
) -> ApiResponse:
    """
    清空 thread 对应的沙箱目录和线程状态，并用同一个 thread_id 重建线程。
    """
    import asyncio

    try:
        thread_dir = _get_thread_dir(thread_id)

        if thread_dir.exists():
            await asyncio.to_thread(shutil.rmtree, thread_dir)

        api_base_url = os.getenv("LANGGRAPH_API_URL", os.getenv("EXTRACT_API_URL", "http://localhost:2024")).rstrip("/")
        client = get_client(url=api_base_url, api_key="")
        metadata: dict[str, Any] = {}

        try:
            existing_thread = await client.threads.get(thread_id=thread_id)
            existing_metadata = existing_thread.get("metadata")
            if isinstance(existing_metadata, dict):
                metadata.update(existing_metadata)
        except Exception as e:
            if "not found" not in str(e).lower():
                raise

        if request and request.metadata:
            metadata.update(request.metadata)

        try:
            await client.threads.delete(thread_id=thread_id)
        except Exception as e:
            if "not found" not in str(e).lower():
                raise

        await client.threads.create(
            thread_id=thread_id,
            metadata=metadata or None,
        )

        return ApiResponse(
            success=True,
            err_message=None,
            data={
                "thread_id": thread_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        error_detail = f"清空线程和沙箱失败: {str(e)}\n{traceback.format_exc()}"
        logging.getLogger(__name__).error(error_detail)
        return ApiResponse(
            success=False,
            err_message=str(e),
            data=None,
        )



# LLM 提取文件列表接口
_extract_model = None


def _get_extract_model():
    """获取用于提取文件列表的模型（延迟初始化）"""
    global _extract_model
    if _extract_model is None:
        _extract_model = init_chat_model(
            **get_model_init_kwargs(streaming=False, temperature=0.0),
        )
    return _extract_model


class FilePaths(BaseModel):
    """提取文件路径。

    用法:
    - 从输入文本中返回实际写出的真实文件路径列表
    - 未找到时返回空数组
    """

    files: list[str] = Field(
        default_factory=list,
        description=(
            "参数: 文件路径数组。"
            "返回输入文本中实际写出的真实文件路径；未找到时传空数组。"
        ),
    )


class SuggestedQuestions(BaseModel):
    """生成建议问题。

    用法:
    - 返回用户下一步可能输入的内容列表
    - 至少返回 3 条
    """

    questions: list[str] = Field(
        default_factory=list,
        description=(
            "参数: 建议内容数组。"
            "每项是一条用户下一步可能输入的简短内容，至少传 3 条。"
        ),
    )


# 请求模型
class ExtractFilePathsRequest(BaseModel):
    content: str


class GenerateSuggestedQuestionsRequest(BaseModel):
    """生成建议问题的请求模型"""
    system_prompt: str = ""
    human_message: str = ""


# 文件列表提取接口
@router.post("/extract-file-paths", tags=["Webapp"], response_model=ApiResponse)
async def extract_file_paths(request: ExtractFilePathsRequest) -> ApiResponse:
    """
    从 AI 回复内容中提取生成的文件路径。

    Args:
        request: 请求体，包含 content 字段

    Returns:
        JSON: {"success": true, "err_message": null, "data": ["path1", "path2"]}
    """
    try:
        model = _get_extract_model()
        content = request.content

        # 构建提取提示
        prompt = load_prompt_from_file("prompt/extract_file_paths_prompt.md", content=content)

        import asyncio

        # 使用工具调用提取，仅当模型实际调用工具时才读取工具参数
        tool_model = model.bind_tools([FilePaths], tool_choice="FilePaths")

        # 使用 tracing_context 临时关闭追踪
        with tracing_context(enabled=False):
            result = await asyncio.to_thread(tool_model.invoke, prompt)

        # 仅提取工具调用参数；未调用工具时返回空列表
        files: list[str] = []
        tool_calls = getattr(result, 'tool_calls', None) or []
        if tool_calls:
            args = tool_calls[0].get('args', {}) or {}
            files = args.get('files', []) or []

        return ApiResponse(
            success=True,
            err_message=None,
            data=files,
        )

    except Exception as e:
        error_detail = f"提取文件路径失败: {str(e)}\n{traceback.format_exc()}"
        logging.getLogger(__name__).error(error_detail)
        return ApiResponse(
            success=False,
            err_message=str(e),
            data=None,
        )


# 生成建议问题接口
@router.post("/generate-suggested-questions", tags=["Webapp"], response_model=ApiResponse)
async def generate_suggested_questions(request: GenerateSuggestedQuestionsRequest) -> ApiResponse:
    """
    根据系统提示词和用户消息生成建议问题。

    Args:
        request: 请求体，包含 system_prompt 和 human_message

    Returns:
        JSON: {"success": true, "err_message": null, "data": ["问题1", "问题2", "问题3"]}
    """
    try:
        model = _get_extract_model()
        system_prompt = request.system_prompt
        human_message = request.human_message

        # 构建提示
        prompt = load_prompt_from_file(
            "prompt/suggested_questions_prompt.md",
            system_prompt=system_prompt,
            human_message=human_message,
        )

        import asyncio

        # 使用工具调用提取，仅当模型实际调用工具时才读取工具参数
        tool_model = model.bind_tools([SuggestedQuestions], tool_choice="SuggestedQuestions")

        # 临时关闭追踪
        with tracing_context(enabled=False):
            result = await asyncio.to_thread(tool_model.invoke, prompt)

        # 仅提取工具调用参数；未调用工具时返回空列表
        questions: list[str] = []
        tool_calls = getattr(result, 'tool_calls', None) or []
        if tool_calls:
            args = tool_calls[0].get('args', {}) or {}
            questions = args.get('questions', []) or []

        return ApiResponse(
            success=True,
            err_message=None,
            data=questions,
        )

    except Exception as e:
        error_detail = f"生成建议问题失败: {str(e)}\n{traceback.format_exc()}"
        logging.getLogger(__name__).error(error_detail)
        return ApiResponse(
            success=False,
            err_message=str(e),
            data=None,
        )

# 模型列表端点
@router.get("/models", tags=["Models"], response_model=ModelListResponse)
async def list_models() -> ModelListResponse:
    """
    获取可用的模型列表。

    从环境变量中读取模型配置，返回当前可用的模型信息。

    支持两种配置方式：
    1. L_MODEL_SUPPORTED_MODELS: 逗号分隔的模型 ID 列表
    2. L_MODEL_MODEL_ID: 单个模型配置
    """
    import os

    try:
        models: list[ModelInfo] = []

        # 优先读取 L_MODEL_SUPPORTED_MODELS（逗号分隔的模型列表）
        model_id_list = os.getenv("L_MODEL_SUPPORTED_MODELS", "").strip()
        if model_id_list:
            # 共享相同的 provider、base_url、api_key
            provider = os.getenv("L_MODEL_PROVIDER")
            base_url = os.getenv("L_MODEL_BASE_URL")

            # 解析模型列表
            model_ids = [m.strip() for m in model_id_list.split(",") if m.strip()]
            default_model = os.getenv("L_MODEL_MODEL_ID", "").strip()

            for i, model_id in enumerate(model_ids):
                models.append(ModelInfo(
                    name=model_id,
                    provider=provider,
                    base_url=base_url,
                    is_default=model_id == default_model or i == 0,
                ))
        else:
            model_id = os.getenv("L_MODEL_MODEL_ID")
            if model_id:
                models.append(ModelInfo(
                    name=model_id,
                    provider=os.getenv("L_MODEL_PROVIDER"),
                    base_url=os.getenv("L_MODEL_BASE_URL"),
                    is_default=True,
                ))

        return ModelListResponse(
            success=True,
            err_message=None,
            data=models,
        )
    except Exception as e:
        return ModelListResponse(
            success=False,
            err_message=str(e),
            data=None,
        )

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
