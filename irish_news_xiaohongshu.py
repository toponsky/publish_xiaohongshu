#!/usr/bin/env python3
"""
爱尔兰每日新闻 → 小红书 自动发布脚本
定时任务：每天 9:00 通过 n8n 或 cron 调用
"""

import os
import json
import time
import base64
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# ========== 配置 ==========
MCP_SERVER = "http://192.168.178.43:18060/mcp"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
RSS_URL = "https://www.rte.ie/feeds/rss/?index=/news/&limit=5"
LOCAL_OUTPUT = "/home/pi5/.openclaw/workspace/xhs_output"
MACMINI_OUTPUT = "/Users/yimingliu/xiaohongshu/images"
COVERAGE_DIR = "/home/pi5/.openclaw/workspace/xhs_coverage"  # 发布记录

# ========== MCP 工具调用 ==========
def mcp_init():
    """初始化 MCP session"""
    resp = requests.post(MCP_SERVER, json={
        "jsonrpc": "2.0", "id": 0, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "irish-news-bot", "version": "1.0"}
        }
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    session_id = resp.headers.get("Mcp-Session-Id", "")
    return session_id

def mcp_call(session_id, tool_name, arguments, timeout=120):
    """调用 MCP 工具"""
    resp = requests.post(MCP_SERVER, json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments}
    }, headers={"Mcp-Session-Id": session_id, "Content-Type": "application/json"}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise Exception(f"MCP error: {data['error']}")
    content = data.get("result", {}).get("content", [{}])[0].get("text", "")
    if not content:
        return {}
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        # 纯文本响应（如登录状态）
        return {"text": content}

# ========== OpenAI 工具 ==========
def openai(messages, model="gpt-4o", max_tokens=800):
    """调用 OpenAI API"""
    resp = requests.post("https://api.openai.com/v1/chat/completions", json={
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens
    }, headers={
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]

def generate_image(prompt, reference_image_url=None):
    """用 OpenAI gpt-image-1 生成图片，支持参考图"""
    payload = {
        "model": "gpt-image-1",
        "prompt": prompt,
        "n": 1,
        "size": "1024x1536"
    }
    if reference_image_url:
        payload["input_image_urls"] = [reference_image_url]
    resp = requests.post("https://api.openai.com/v1/images/generations", json=payload, headers={
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    image_base64 = data["data"][0].get("b64_json", "")
    if image_base64:
        return base64.b64decode(image_base64)
    image_url = data["data"][0]["url"]
    img_resp = requests.get(image_url, timeout=60)
    img_resp.raise_for_status()
    return img_resp.content

# ========== RSS 抓取 ==========
def fetch_rss():
    """抓取 RTE RSS 新闻"""
    resp = requests.get(RSS_URL, timeout=15)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    ns = {"media": "http://search.yahoo.com/mrss/"}
    items = []
    for item in root.findall("channel/item"):
        title = item.findtext("title", "").strip()
        desc = item.findtext("description", "").strip()
        link = item.findtext("link", "").strip()
        category = item.findtext("category", "").strip()
        # 尝试从 media:content 获取图片
        media_content = item.find("media:content", ns)
        image = ""
        if media_content is not None:
            image = media_content.get("url", "")
        if not image:
            media_thumb = item.find("media:thumbnail", ns)
            if media_thumb is not None:
                image = media_thumb.get("url", "")
        items.append({
            "title": title,
            "description": desc,
            "link": link,
            "category": category,
            "image": image
        })
    return items

# ========== 小红书文案生成 ==========
def generate_caption(news_item):
    """用 OpenAI 生成小红书文案"""
    system_prompt = """你是一个专业的小红书内容创作者，擅长将国际新闻改写成吸引人的中文小红书帖子。

规则：
- 标题：最多20个中文字/英文词，带 emoji，吸引眼球
- 正文：100-150字，语言生动活泼，适合小红书社区风格
- 标签：5-8个小红书热门话题标签（格式：#标签名）
- 结构：开头吸引人 → 核心内容 → 互动引导

输出纯JSON格式：
{"title": "...", "body": "...", "tags": ["#标签1", "#标签2", ...]}"""

    user_prompt = f"""请将以下爱尔兰新闻改写成小红书帖子：

标题：{news_item['title']}
摘要：{news_item['description']}
分类：{news_item['category']}
链接：{news_item['link']}

要求：
- 标题要吸引眼球，引发好奇心
- 正文结合爱尔兰当地视角，增加亲切感
- 标签要精准且有热度
- 正文末尾加上原文链接"""

    result_text = openai([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ], max_tokens=600)

    # 提取 JSON
    try:
        # 尝试找 JSON 代码块
        import re
        json_match = re.search(r'\{[^{}]*\}', result_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except:
        pass
    return {"title": news_item['title'][:20], "body": result_text, "tags": ["#爱尔兰", "#国际新闻"]}

# ========== 封面图生成 ==========
def generate_cover(caption, news_item):
    """生成小红书封面图：用RTE真实新闻图作为参考，生成文艺自然风格"""
    news_image = news_item.get("image", "")
    category = news_item.get("category", "新闻")
    
    prompt = f"""A beautiful vertical 3:4 magazine cover for a Chinese social media post about Irish news.
    
    Subject: Irish news — {caption['title']}
    Category: {category}
    
    Style: Elegant editorial photography aesthetic. Warm tones with subtle Irish green accents. 
    Cinematic composition, soft lighting, magazine-quality. Natural and authentic — NOT looking AI-generated.
    No text on the image. Keep it clean and sophisticated. The photo should look like it was taken by a professional photographer at RTE Ireland.
    
    If a reference photo is provided, use it as inspiration and maintain the photographic authenticity.
    Keep the image feeling real, warm, human — like a quality news magazine cover."""

    image_data = generate_image(prompt, reference_image_url=news_image if news_image else None)
    return image_data

# ========== 主流程 ==========
def wake_macmini():
    """Wake Mac Mini from sleep via Wake-on-LAN"""
    import socket
    MAC = "12:3b:6a:94:32:28"
    MAC_RAW = bytes.fromhex(MAC.replace(":", ""))
    packet = b'\xff' * 6 + MAC_RAW * 16
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(packet, ("192.168.178.43", 9))
    print(f"   🌅 唤醒 Mac Mini: {MAC}")

import sys
import os

DRY_RUN = "--dry-run" in sys.argv or os.environ.get("DRY_RUN") == "1"

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始执行...")

    # 0. 唤醒 Mac Mini（如果正在睡眠）
    print("🌅 唤醒 Mac Mini...")
    try:
        wake_macmini()
        time.sleep(15)  # 等待 Mac Mini 启动
    except Exception as e:
        print(f"   唤醒失败（可能已开机）: {e}")

    # 1. 初始化 MCP session
    print("📡 连接小红书 MCP...")
    session_id = mcp_init()
    print(f"   Session: {session_id[:20]}...")

    # 2. 检查登录状态
    print("🔐 检查登录状态...")
    login_status = mcp_call(session_id, "check_login_status", {})
    if "已登录" not in str(login_status):
        print(f"   ⚠️ 未登录: {login_status}")
        print("   请先扫码登录!")
        return

    # 3. 抓取新闻
    print("📰 抓取 RTE 新闻...")
    news_items = fetch_rss()
    print(f"   抓取到 {len(news_items)} 条新闻")
    top_news = news_items[0]
    print(f"   最新: {top_news['title']}")

    # 4. 生成小红书文案
    print("✍️ 生成小红书文案...")
    caption = generate_caption(top_news)
    print(f"   标题: {caption['title']}")
    print(f"   标签: {caption['tags']}")

    # 5. 生成封面图
    print("🎨 生成封面图...")
    os.makedirs(LOCAL_OUTPUT, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")
    img_data = generate_cover(caption, top_news)
    img_path = f"{LOCAL_OUTPUT}/cover-{timestamp}.png"
    with open(img_path, "wb") as f:
        f.write(img_data)
    print(f"   封面图已保存: {img_path}")

    # 5b. 把图片传到 Mac Mini（MCP 浏览器自动化需要 Mac 本地路径）
    print("📡 传输图片到 Mac Mini...")
    macmini_img_path = f"{MACMINI_OUTPUT}/cover-{timestamp}.png"
    import subprocess
    subprocess.run(["scp", img_path, f"yimingliu@MacMini:{macmini_img_path}"],
                   check=True, capture_output=True)
    print(f"   已传到 Mac Mini: {macmini_img_path}")

    print(f"\n⏭️  DRY RUN — 跳过发布步骤")
    print(f"   图片路径: {macmini_img_path}")
    print(f"   标题: {caption['title']}")
    print(f"   正文: {caption['body'][:100]}...")
    print(f"   标签: {caption['tags']}")
    print(f"\n✅ Dry run 完成! [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
    return

    # 以下为实际发布步骤（DRY RUN 时不执行）
    # 6. 发布小红书（用 Mac Mini 本地图片路径）
    print("📤 发布小红书（浏览器自动化，约60秒）...")
    full_content = caption['body'] + f"\n\n🔗 原文: {top_news['link']}\n\n📍 来源: RTE News Ireland"
    img_remote_path = f"{MACMINI_OUTPUT}/cover-{timestamp}.png"
    result = mcp_call(session_id, "publish_content", {
        "title": caption['title'],
        "content": full_content,
        "images": [macmini_img_path],  # Mac Mini 本地路径，MCP 浏览器需要
        "tags": [tag.lstrip('#') for tag in caption['tags']],
        "visibility": "公开可见",
        "is_original": False
    })

    print(f"   发布结果: {result}")

    # 7. 保存发布记录
    os.makedirs(COVERAGE_DIR, exist_ok=True)
    record = {
        "date": timestamp,
        "news": top_news,
        "caption": caption,
        "img_path": img_path,
        "publish_result": result
    }
    record_path = f"{COVERAGE_DIR}/{timestamp}.json"
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    print(f"   记录已保存: {record_path}")

    print(f"\n✅ 完成! [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")

if __name__ == "__main__":
    main()
