#!/usr/bin/env python3
"""查询 token 使用情况"""
import os
import sys
import time
import json
import requests

def format_num(n):
    """格式化数字，千分位"""
    return f"{int(n):,}"

def check_gpt_agent():
    """检查 gpt-agent 用量"""
    api_key = os.environ.get("GPT_AGENT_API_KEY", "")
    if not api_key:
        return None, "缺少 GPT_AGENT_API_KEY"
    
    ts = int(time.time() * 1000)
    resp = requests.get(
        f"https://huawei.llm-agent.cc/api/usage/token/?_ts={ts}",
        headers={"Authorization": f"Bearer {api_key}", "accept": "application/json"},
        timeout=15
    )
    if resp.status_code != 200:
        return None, f"API 错误: {resp.status_code}"
    
    data = resp.json()
    if not data.get("code"):
        return None, f"API 返回错误: {data}"
    
    d = data["data"]
    total = d["total_granted"]
    used = d["total_used"]
    avail = d["total_available"]
    pct = used / total * 100 if total > 0 else 0
    
    return {
        "provider": "gpt-agent",
        "total": total,
        "used": used,
        "available": avail,
        "percent": pct
    }, None

def main():
    # gpt-agent
    result, err = check_gpt_agent()
    if err:
        print(f"❌ gpt-agent: {err}")
    else:
        print(f"📊 gpt-agent")
        print(f"━━━━━━━━━━━━━━━━━━━━━")
        print(f"总量:   {format_num(result['total'])} tokens")
        print(f"已用:   {format_num(result['used'])} tokens")
        print(f"剩余:   {format_num(result['available'])} tokens")
        print(f"使用率: {result['percent']:.1f}%")
        print(f"━━━━━━━━━━━━━━━━━━━━━")
    
    print(f"\n⚠️ aisonnet: 需要登录 https://newapi.aisonnet.org/console 网页查看")

if __name__ == "__main__":
    main()