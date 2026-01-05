from fastapi import FastAPI, HTTPException, APIRouter
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Simple Agents API", version="0.1.0")

router = APIRouter(prefix="/app")

# 健康检查端点
@router.get("/health", tags=["app"])
async def health_check():
    """健康检查端点，用于验证服务是否正常运行"""
    return {
        "status": "healthy",
        "message": "服务运行正常",
        "version": "0.1.0"
    }


# 根路径端点
@router.get("/", tags=["app"])
async def root():
    """根路径，返回欢迎信息"""
    return {
        "message": "欢迎使用 Simple Agents API",
        "docs": "/docs",
        "health": "/health"
    }


# 定义请求数据模型
class User(BaseModel):
    name: str
    age: int
    email: Optional[str] = None


# POST 端点 - 创建用户
@router.post("/users", tags=["app"])
async def create_user(user: User):
    """创建用户端点"""
    return {
        "message": "用户创建成功",
        "user": {
            "name": user.name,
            "age": user.age,
            "email": user.email,
            "id": 1
        }
    }


# GET 端点 - 获取用户信息（带路径参数）
@router.get("/users/{user_id}", tags=["app"])
async def get_user(user_id: int):
    """根据用户 ID 获取用户信息"""
    if user_id < 1:
        raise HTTPException(status_code=400, detail="用户 ID 必须大于 0")
    
    return {
        "user_id": user_id,
        "name": f"用户{user_id}",
        "email": f"user{user_id}@example.com"
    }


# GET 端点 - 列表查询（带查询参数）
@router.get("/items", tags=["app"])
async def get_items(
    skip: int = 0,
    limit: int = 10,
    keyword: Optional[str] = None
):
    """获取物品列表，支持分页和关键词搜索"""
    items = [
        {"id": i, "name": f"物品{i}", "description": f"这是物品{i}的描述"}
        for i in range(1, 21)
    ]
    
    # 应用关键词过滤
    if keyword:
        items = [item for item in items if keyword in item["name"]]
    
    # 应用分页
    items = items[skip:skip + limit]
    
    return {
        "total": len(items),
        "skip": skip,
        "limit": limit,
        "keyword": keyword,
        "items": items
    }


# PUT 端点 - 更新用户信息
@router.put("/users/{user_id}", tags=["app"])
async def update_user(user_id: int, user: User):
    """更新用户信息"""
    return {
        "message": "用户信息更新成功",
        "user_id": user_id,
        "updated_data": {
            "name": user.name,
            "age": user.age,
            "email": user.email
        }
    }


# DELETE 端点 - 删除用户
@router.delete("/users/{user_id}", tags=["app"])
async def delete_user(user_id: int):
    """删除用户"""
    if user_id < 1:
        raise HTTPException(status_code=400, detail="用户 ID 必须大于 0")
    
    return {
        "message": "用户删除成功",
        "user_id": user_id
    }


# 测试异步端点
@router.get("/async-test", tags=["app"])
async def async_test():
    """测试异步端点"""
    import asyncio
    await asyncio.sleep(0.1)
    return {"message": "异步操作完成"}


# POST 端点 - 表单数据处理
@router.post("/echo", tags=["app"])
async def echo_data(data: dict):
    """回显接收到的数据"""
    return {
        "message": "数据接收成功",
        "received_data": data,
        "data_length": len(data)
    }


app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)