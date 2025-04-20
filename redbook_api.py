from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import requests
from bs4 import BeautifulSoup
import json
import re
import os
from urllib.parse import urlparse
from datetime import datetime
import time
from typing import List, Optional
import argparse

app = FastAPI(
    title="小红书内容抓取API",
    description="提供小红书笔记内容抓取服务",
    version="1.0.0"
)

class RedbookContent(BaseModel):
    title: str
    content: str
    images: List[str]
    url: str
    local_images: Optional[List[str]] = None

class RedbookRequest(BaseModel):
    url: str
    save_images: bool = True  # 是否保存图片到本地

class RedbookScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
    
    @staticmethod
    def extract_url(text: str) -> Optional[str]:
        """从分享文本中提取小红书链接"""
        xhs_pattern = r'http://xhslink\.com/[a-zA-Z0-9/]+\b'
        urls = re.findall(xhs_pattern, text)
        return urls[0] if urls else None
        
    def download_image(self, url: str, folder_path: str, index: int) -> Optional[str]:
        """下载图片并保存到指定文件夹"""
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            ext = os.path.splitext(urlparse(url).path)[1]
            if not ext:
                ext = '.jpg'
                
            filename = f'image_{index}{ext}'
            filepath = os.path.join(folder_path, filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return filename
        except Exception as e:
            print(f"下载图片失败 {url}: {e}")
            return None

    def get_content(self, url: str) -> Optional[dict]:
        """获取内容"""
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            title_meta = soup.find('meta', {'name': 'og:title'})
            title_text = title_meta['content'].replace(' - 小红书', '') if title_meta else "标题未找到"
            
            content_div = soup.find('div', {'id': 'detail-desc'})
            content_text = content_div.get_text(strip=True) if content_div else "正文未找到"
            
            images = []
            img_metas = soup.find_all('meta', {'name': 'og:image'})
            for img_meta in img_metas:
                if 'content' in img_meta.attrs:
                    images.append(img_meta['content'])
            
            return {
                'title': title_text,
                'content': content_text,
                'images': images,
                'url': url
            }
            
        except requests.RequestException as e:
            raise HTTPException(status_code=400, detail=f"请求出错: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"解析出错: {str(e)}")

scraper = RedbookScraper()

@app.post("/api/extract", response_model=RedbookContent)
async def extract_content(request: RedbookRequest):
    """
    从小红书链接或分享文本中提取内容
    
    - **url**: 小红书链接或分享文本
    - **save_images**: 是否保存图片到本地（默认为True）
    
    返回笔记内容，包括标题、正文、图片链接等
    """
    # 提取URL
    url = scraper.extract_url(request.url) if 'xhslink.com' in request.url else request.url
    if not url:
        raise HTTPException(status_code=400, detail="未找到有效的小红书链接")
    
    # 获取内容
    result = scraper.get_content(url)
    if not result:
        raise HTTPException(status_code=500, detail="内容获取失败")
    
    # 如果需要保存图片
    if request.save_images and result['images']:
        # 创建保存目录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_title = "".join(x for x in result['title'] if x.isalnum() or x in (' ', '-', '_'))
        folder_name = f"redbook_content_{timestamp}_{safe_title[:30]}"
        os.makedirs(folder_name, exist_ok=True)
        
        # 下载图片
        downloaded_images = []
        for i, img_url in enumerate(result['images'], 1):
            filename = scraper.download_image(img_url, folder_name, i)
            if filename:
                downloaded_images.append(os.path.join(folder_name, filename))
        
        result['local_images'] = downloaded_images
        
        # 保存元数据
        with open(os.path.join(folder_name, 'info.json'), 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    
    return result

@app.get("/")
async def root():
    """API根路径，返回简单的欢迎信息"""
    return {"message": "欢迎使用小红书内容抓取API"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='小红书内容抓取API服务')
    parser.add_argument('--port', type=int, default=8080, help='服务端口号（默认：8080）')
    parser.add_argument('--host', type=str, default="0.0.0.0", help='服务主机地址（默认：0.0.0.0）')
    args = parser.parse_args()
    
    print(f"启动服务器在 http://{args.host}:{args.port}")
    uvicorn.run("redbook_api:app", host=args.host, port=args.port, reload=True)