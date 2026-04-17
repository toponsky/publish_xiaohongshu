---
name: token-usage-checker
description: |
  检查 AI token provider 的使用情况。用于查询 API 余额、已用额度、剩余额度。
  触发场景：用户问"余额还有多少"、"还剩多少 token"、"查询用量"、"token 使用情况"、"查看 API 配额"等。
  支持的 provider: gpt-agent (huawei.llm-agent.cc), aisonnet (newapi.aisonnet.org)
---

# Token Usage Checker

查询 AI token 提供商的剩余配额和使用情况。

## 支持的 Provider

| Provider | API 端点 | 认证方式 |
|----------|----------|----------|
| gpt-agent | https://huawei.llm-agent.cc/api/usage/token/ | Bearer token |
| aisonnet | 需要登录网页查看 | 用户名密码 |

## 使用方法

### gpt-agent

```bash
curl -s 'https://huawei.llm-agent.cc/api/usage/token/?_ts=<timestamp>' \
  -H 'Authorization: Bearer <API_KEY>' \
  -H 'accept: application/json'
```

返回字段：
- `total_granted`: 总分配额度
- `total_used`: 已使用
- `total_available`: 剩余可用
- `unlimited_quota`: 是否无限配额

**使用示例：**
```python
import requests

API_KEY = os.environ.get("GPT_AGENT_API_KEY", "sk-...")
resp = requests.get(
    f"https://huawei.llm-agent.cc/api/usage/token/?_ts={int(time.time()*1000)}",
    headers={"Authorization": f"Bearer {API_KEY}", "accept": "application/json"}
)
data = resp.json()["data"]
used_pct = data["total_used"] / data["total_granted"] * 100
print(f"总量: {data['total_granted']:,}")
print(f"已用: {data['total_used']:,}")
print(f"剩余: {data['total_available']:,}")
print(f"使用率: {used_pct:.1f}%")
```

### aisonnet

1. 登录 https://newapi.aisonnet.org/console
2. 在开发者工具 Network 面板查看 usage 相关 API
3. 或直接在网页上读取显示的额度信息

## 输出格式

查询结果应输出：
- 总量 (total granted)
- 已用 (used)
- 剩余 (available)
- 使用百分比

示例输出：
```
📊 gpt-agent 使用情况
━━━━━━━━━━━━━━━━━━━━━
总量:   799,964,143 tokens
已用:   135,977,965 tokens
剩余:   663,986,178 tokens
使用率: 17.0%
━━━━━━━━━━━━━━━━━━━━━
```