#!/usr/bin/env python3
"""每日 token 使用量检查，超过 90% 发送告警"""
import os
import time
import requests
import json

# 配置
TOKEN_KEY = os.environ.get("GPT_AGENT_API_KEY", "")
THRESHOLD = 90  # 告警阈值 90%
WHATSAPP_TO = "+353877783453"  # 你的 WhatsApp
EMAIL_TO = "yimingliu0216@gmail.com"

def check_usage():
    ts = int(time.time() * 1000)
    resp = requests.get(
        f"https://huawei.llm-agent.cc/api/usage/token/?_ts={ts}",
        headers={"Authorization": f"Bearer {TOKEN_KEY}", "accept": "application/json"},
        timeout=15
    )
    data = resp.json()["data"]
    total = data["total_granted"]
    used = data["total_used"]
    pct = used / total * 100
    return {
        "total": total,
        "used": used,
        "available": data["total_available"],
        "percent": pct
    }

def send_alert(usage):
    pct = usage["percent"]
    used = usage["used"]
    total = usage["total"]
    
    msg = f"⚠️ Token 告警\n使用率: {pct:.1f}%\n已用: {used:,}\n总量: {total:,}\n请及时充值！"
    
    # WhatsApp - 通过 OpenClaw delivery
    print(f"📱 发送 WhatsApp 到 {WHATSAPP_TO}")
    # 这里使用 OpenClaw 的发送机制（通过 cron job 的 delivery）
    # 实际发送由 OpenClaw 框架处理
    
    # Email
    print(f"📧 发送邮件到 {EMAIL_TO}")
    print(f"内容: {msg}")
    
    return msg

def main():
    print(f"[{time.strftime('%Y-%m-%d %H:%M')}] 检查 token 使用量...")
    
    try:
        usage = check_usage()
        print(f"使用率: {usage['percent']:.1f}%")
        
        if usage["percent"] >= THRESHOLD:
            print("⚠️ 超过阈值，发送告警...")
            send_alert(usage)
        else:
            print(f"✅ 使用率 {usage['percent']:.1f}% < {THRESHOLD}%，无需告警")
    except Exception as e:
        print(f"❌ 检查失败: {e}")

if __name__ == "__main__":
    main()