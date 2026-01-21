import requests
from pathlib import Path
from typing import Optional


def word_to_pdf(word_file_path: str, output_pdf_path: Optional[str] = None) -> bytes:
    """
    将Word文件转换成PDF文件，调用远程服务
    
    Args:
        word_file_path: Word文件路径
        output_pdf_path: 可选，输出PDF文件路径。如果为None，则返回PDF字节数据
    
    Returns:
        如果output_pdf_path为None，返回PDF字节数据；否则返回None
    
    Raises:
        FileNotFoundError: 如果Word文件不存在
        requests.RequestException: 如果API调用失败
    """
    # 检查Word文件是否存在
    word_path = Path(word_file_path)
    if not word_path.exists():
        raise FileNotFoundError(f"Word文件不存在: {word_file_path}")
    
    # API地址
    api_url = "https://dcca.hhstu.edu.cn/transfer/api/convert-download"
    
    # 准备请求数据
    files = {
        'file': (
            word_path.name,
            open(word_path, 'rb'),
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    }
    
    headers = {
        'accept': 'application/json'
    }
    
    try:
        # 发送POST请求
        response = requests.post(api_url, files=files, headers=headers)
        response.raise_for_status()
        
        # 获取PDF数据
        pdf_data = response.content
        
        # 如果指定了输出路径，保存PDF文件
        if output_pdf_path:
            output_path = Path(output_pdf_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(pdf_data)
            return None
        
        return pdf_data
        
    finally:
        # 关闭文件句柄
        if 'file' in files and hasattr(files['file'][1], 'close'):
            files['file'][1].close()


if __name__ == "__main__":
    # 示例用法
    try:
        # 转换并保存到文件
        word_to_pdf(
            word_file_path="/Users/liuyuhua/PycharmProjects/simple-agents/files/2024高数习题册线面积分级数.docx",
            output_pdf_path="/Users/liuyuhua/PycharmProjects/simple-agents/files/2024高数习题册线面积分级数.pdf"
        )
        print("转换成功！PDF文件已保存。")
        
        # 或者获取PDF字节数据
        # pdf_data = word_to_pdf("example.docx")
        # print(f"转换成功！PDF数据大小: {len(pdf_data)} 字节")
        
    except Exception as e:
        print(f"转换失败: {e}")