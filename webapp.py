from fastapi import FastAPI, HTTPException, APIRouter, Query
from fastapi.responses import StreamingResponse
import os
from urllib.parse import quote

app = FastAPI(title="Webapp Agents API", version="0.1.0")

router = APIRouter(prefix="/app")


# 文件下载端点
@router.get("/download/{thread_id}", tags=["app"])
async def download_file(
    thread_id: str,
    file_path: str = Query(..., description="要下载的文件路径（相对于 thread_dir）")
):
    """
    根据指定的 thread_id 和文件路径下载文件。
    
    Args:
        thread_id: 对话线程 ID
        file_path: 要下载的文件路径（相对于 thread_dir 的虚拟路径）
    
    Returns:
        StreamingResponse: 文件内容的流式响应
    """
    from deepagents.backends.filesystem_async import AsyncFilesystemBackend
    import io

    sandbox_root_dir = os.getenv('SANDBOX_ROOT_DIR', './data/sandbox_sessions')
    
    # 动态构造该用户专属的目录
    # 结果示例：./data/sandbox_sessions/thread_abc/
    thread_dir = f"{sandbox_root_dir}/{thread_id}"

    # 创建新的 Backend 实例
    backend = AsyncFilesystemBackend(
        thread_dir=thread_dir,
        max_file_size_mb=50,
        thread_id=thread_id,
    )
    
    try:
        # 使用后端下载文件
        responses = await backend.adownload_files([file_path])
        
        if not responses:
            raise HTTPException(status_code=404, detail="文件未找到")
        
        response = responses[0]
        
        if response.error:
            # 根据错误类型返回相应的 HTTP 状态码
            if response.error == "file_not_found":
                raise HTTPException(status_code=404, detail=f"文件未找到: {file_path}")
            elif response.error == "permission_denied":
                raise HTTPException(status_code=403, detail=f"无权限访问文件: {file_path}")
            elif response.error == "is_directory":
                raise HTTPException(status_code=400, detail=f"路径是一个目录，不是文件: {file_path}")
            elif response.error == "invalid_path":
                raise HTTPException(status_code=400, detail=f"无效的路径: {file_path}")
            else:
                raise HTTPException(status_code=500, detail=f"下载文件失败: {response.error}")
        
        if response.content is None:
            raise HTTPException(status_code=404, detail="文件内容为空")
        
        # 创建流式响应
        file_like = io.BytesIO(response.content)
        
        # 从路径中提取文件名
        filename = os.path.basename(file_path)
        
        # 根据文件扩展名确定媒体类型
        media_type = "application/octet-stream"
        if file_path.endswith('.txt'):
            media_type = "text/plain"
        elif file_path.endswith('.pdf'):
            media_type = "application/pdf"
        elif file_path.endswith('.json'):
            media_type = "application/json"
        elif file_path.endswith('.csv'):
            media_type = "text/csv"
        elif file_path.endswith(('.png', '.jpg', '.jpeg', '.gif')):
            media_type = f"image/{file_path.split('.')[-1]}"
        
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


app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
