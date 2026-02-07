import requests
import json
import time
import os
from typing import Optional, Dict, List

# API配置
API_BASE = "https://gen1.diversityfaces.org"
API_KEY = "ak_OymjErKQRs-brINJuHFxKwIbxbZHq2KRiEzYthnwxMI"


class BeautyAPIClient:
    def __init__(self, api_base: str = API_BASE, api_key: str = API_KEY):
        self.api_base = api_base
        self.api_key = api_key
        self.session = requests.Session()
        self.session.timeout = 30
        # 设置默认请求头
        self.session.headers.update({
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        })

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """发送HTTP请求，包含重试机制和API Key认证"""
        url = f"{self.api_base}{endpoint}"
        max_retries = 3

        for attempt in range(max_retries):
            try:
                response = self.session.request(method, url, **kwargs)

                # 处理认证错误
                if response.status_code == 401:
                    error_data = response.json() if response.content else {}
                    error_code = error_data.get('code', 'UNKNOWN')
                    if error_code == 'MISSING_API_KEY':
                        raise Exception("缺少API密钥，请检查X-API-Key请求头")
                    elif error_code == 'INVALID_API_KEY':
                        raise Exception("API密钥无效，请检查密钥是否正确")
                    elif error_code == 'EXPIRED_API_KEY':
                        raise Exception("API密钥已过期，请更新密钥")
                    else:
                        raise Exception(f"认证失败: {error_data.get('message', '未知错误')}")

                # 处理速率限制
                if response.status_code == 429:
                    error_data = response.json() if response.content else {}
                    raise Exception(f"API调用频率超限: {error_data.get('message', '请稍后重试')}")

                response.raise_for_status()
                return response

            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise Exception(f"请求失败 (尝试{max_retries}次): {e}")
                time.sleep(2 ** attempt)  # 指数退避

    def generate_standard(self, **params) -> Dict:
        """标准生成美女图片"""
        default_params = {
            "style": "清纯",
            "age": "22",
            "nationality": "中国",
            "clothing": "连衣裙",
            "clothing_color": "白色",
            "width": 1024,
            "height": 1024,
            "steps": 4
        }
        default_params.update(params)

        response = self._make_request("POST", "/api/generate", json=default_params)
        return response.json()

    def generate_random(self, **override_params) -> Dict:
        """随机生成美女图片"""
        params = {"width": 1024, "height": 1024, "steps": 4}
        params.update(override_params)

        response = self._make_request("POST", "/api/generate/random", json=params)
        return response.json()

    def generate_custom(self, full_prompt: str, **params) -> Dict:
        """自定义提示词生成"""
        data = {"full_prompt": full_prompt, "width": 1024, "height": 1024, "steps": 4}
        data.update(params)

        response = self._make_request("POST", "/api/generate/custom", json=data)
        return response.json()

    def check_status(self, prompt_id: str) -> Dict:
        """检查生成状态"""
        response = self._make_request("GET", f"/api/status/{prompt_id}")
        return response.json()

    def wait_for_completion(self, prompt_id: str, max_wait: int = 300) -> Dict:
        """等待生成完成，返回最终状态"""
        start_time = time.time()

        while time.time() - start_time < max_wait:
            status = self.check_status(prompt_id)

            if status['status'] == 'completed':
                return status
            elif status['status'] == 'failed':
                raise Exception(f"生成失败: {status.get('message', '未知错误')}")

            time.sleep(2)

        raise Exception(f"等待超时 ({max_wait}秒)")

    def download_image(self, filename: str, save_path: str,
                       subfolder: str = "", img_type: str = "output",
                       format_type: str = "webp") -> str:
        """下载图片到本地"""
        params = {"subfolder": subfolder, "type": img_type, "format": format_type}
        response = self._make_request("GET", f"/api/image/{filename}", params=params)

        # 确保目录存在
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        with open(save_path, 'wb') as f:
            f.write(response.content)

        return save_path

    def generate_and_download(self, save_dir: str = "./images",
                              generation_type: str = "standard", **params) -> List[str]:
        """完整的生成和下载流程"""
        try:
            # 1. 提交生成任务
            if generation_type == "standard":
                result = self.generate_standard(**params)
            elif generation_type == "random":
                result = self.generate_random(**params)
            elif generation_type == "custom":
                result = self.generate_custom(**params)
            else:
                raise ValueError(f"不支持的生成类型: {generation_type}")

            if not result.get('success'):
                raise Exception(f"任务提交失败: {result.get('error', '未知错误')}")

            prompt_id = result['prompt_id']
            print(f"✅ 任务提交成功: {prompt_id}")

            # 2. 等待完成
            print("⏳ 等待生成完成...")
            final_status = self.wait_for_completion(prompt_id)

            # 3. 下载所有图片
            downloaded_files = []
            for i, img in enumerate(final_status['images']):
                filename = img['filename']
                base_name = os.path.splitext(filename)[0]
                save_path = os.path.join(save_dir, f"{base_name}_{i + 1}.webp")

                downloaded_path = self.download_image(
                    filename, save_path,
                    img.get('subfolder', ''),
                    img.get('type', 'output')
                )
                downloaded_files.append(downloaded_path)
                print(f"📥 已下载: {downloaded_path}")

            return downloaded_files

        except Exception as e:
            print(f"❌ 生成失败: {e}")
            raise


# 使用示例
if __name__ == "__main__":
    # 使用默认配置（包含API Key）
    client = BeautyAPIClient()

    # 或者自定义配置
    # client = BeautyAPIClient(
    #     api_base="https://gen1.diversityfaces.org",
    #     api_key="your_api_key_here"
    # )

    try:
        # 标准生成示例
        files = client.generate_and_download(
            generation_type="standard",
            style="清纯",
            age="22",
            nationality="日本",
            clothing="连衣裙",
            clothing_color="白色"
        )
        print(f"🎉 生成完成，共{len(files)}张图片")

    except Exception as e:
        if "API密钥" in str(e):
            print(f"❌ 认证错误: {e}")
            print("💡 请检查API密钥是否正确设置")
        else:
            print(f"❌ 其他错误: {e}")
