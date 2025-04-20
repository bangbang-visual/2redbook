import requests
from bs4 import BeautifulSoup
import json
import re
import os
from urllib.parse import urlparse
from datetime import datetime
import time

class RedbookScraper:
    def __init__(self):
        # 设置请求头，模拟浏览器访问
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
    
    @staticmethod
    def extract_url(text):
        """从分享文本中提取小红书链接"""
        # 匹配http://xhslink.com/开头的链接
        xhs_pattern = r'http://xhslink\.com/[a-zA-Z0-9/]+\b'
        urls = re.findall(xhs_pattern, text)
        return urls[0] if urls else None
        
    def download_image(self, url, folder_path, index):
        """下载图片并保存到指定文件夹"""
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            # 从URL中获取文件扩展名，如果没有则默认为jpg
            ext = os.path.splitext(urlparse(url).path)[1]
            if not ext:
                ext = '.jpg'
                
            # 构建文件名：图片序号
            filename = f'image_{index}{ext}'
            filepath = os.path.join(folder_path, filename)
            
            # 保存图片
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return filename
        except Exception as e:
            print(f"下载图片失败 {url}: {e}")
            return None

    def get_content(self, url):
        try:
            # 发送GET请求获取页面内容
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()  # 检查请求是否成功
            
            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取标题 - 从meta标签
            title_meta = soup.find('meta', {'name': 'og:title'})
            title_text = title_meta['content'].replace(' - 小红书', '') if title_meta else "标题未找到"
            
            # 提取正文内容 - 从detail-desc
            content_div = soup.find('div', {'id': 'detail-desc'})
            if content_div:
                content_text = content_div.get_text(strip=True)
            else:
                content_text = "正文未找到"
            
            # 提取图片链接 - 从meta标签
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
            print(f"请求出错: {e}")
            return None
        except Exception as e:
            print(f"解析出错: {e}")
            return None

    def process_url(self, url, base_folder):
        """处理单个URL"""
        result = self.get_content(url)
        if result:
            # 使用标题作为文件夹名（移除非法字符）
            safe_title = "".join(x for x in result['title'] if x.isalnum() or x in (' ', '-', '_'))
            folder_name = os.path.join(base_folder, safe_title[:50])  # 限制文件夹名长度
            os.makedirs(folder_name, exist_ok=True)
            
            # 下载图片
            print(f"\n开始下载 '{result['title']}' 的图片...")
            downloaded_images = []
            for i, img_url in enumerate(result['images'], 1):
                print(f"正在下载第 {i}/{len(result['images'])} 张图片...")
                filename = self.download_image(img_url, folder_name, i)
                if filename:
                    downloaded_images.append(filename)
            
            # 更新结果并保存
            result['local_images'] = downloaded_images
            json_path = os.path.join(folder_name, 'info.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            print(f"内容已保存到: {folder_name}")
            return True
        return False

def main():
    scraper = RedbookScraper()
    
    print("请粘贴小红书分享文本或直接输入链接：")
    text = input().strip()
    
    # 尝试提取URL
    url = scraper.extract_url(text) if 'xhslink.com' in text else text
    
    if not url:
        print("未找到有效的链接！")
        return
        
    print(f"\n找到链接: {url}")
    
    # 创建主文件夹
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_folder = f"redbook_content_{timestamp}"
    os.makedirs(base_folder, exist_ok=True)
    
    print("\n开始处理...")
    if scraper.process_url(url, base_folder):
        print("\n处理完成！")
    else:
        print("\n处理失败！")

if __name__ == "__main__":
    main() 