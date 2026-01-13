from fastapi import FastAPI, HTTPException, APIRouter, Query
from fastapi.responses import Response, StreamingResponse
import os
from urllib.parse import quote

from deepagents.backends import FilesystemBackend

app = FastAPI(title="Webapp Agents API", version="0.1.0")

router = APIRouter(prefix="/webapp")


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

    sandbox_root_dir = os.getenv('SANDBOX_ROOT_DIR', './data/sandbox_sessions')
    
    # 动态构造该用户专属的目录
    # 结果示例：./data/sandbox_sessions/thread_abc/
    thread_dir = os.path.join(sandbox_root_dir, thread_id)

    # 创建新的 Backend 实例
    backend = FilesystemBackend(
        thread_dir=thread_dir,
        max_file_size_mb=50,
        thread_id=thread_id,
    )
    
    try:
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


# HEAD 端点：检查报告是否存在
@router.head("/report/{thread_id}", tags=["Webapp"])
async def check_report_exists(thread_id: str):
    """
    检查指定 thread_id 的 final_report.md 文件是否存在（HEAD 方法）。
    
    Args:
        thread_id: 对话线程 ID
    
    Returns:
        Response: 只返回 headers，不返回内容体
    """
    data_root_dir = os.getenv('SANDBOX_ROOT_DIR', './data/sandbox_sessions')
    
    # 构造文件路径：{DATA_ROOT_DIR}/{thread_id}/.deepthink/final_report.md
    file_path = os.path.join(data_root_dir, thread_id, '.deepthink', 'final_report.md')
    
    # 解析绝对路径
    resolved_path = os.path.abspath(file_path)
    resolved_root = os.path.abspath(data_root_dir)
    
    # 安全检查：确保文件路径在根目录下
    if not resolved_path.startswith(resolved_root):
        raise HTTPException(status_code=403, detail="无权访问该路径")
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件未找到")
    
    # 检查是否是文件
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=400, detail="路径不是一个文件")
    
    # 获取文件状态
    file_stat = os.stat(file_path)
    
    # 设置响应头
    headers = {
        'Content-Type': 'text/markdown',
        'Content-Length': str(file_stat.st_size),
        'Last-Modified': os.path.getmtime(file_path).__str__()
    }
    
    # HEAD 请求只返回 headers，不返回内容体
    return Response(status_code=200, headers=headers)


app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
