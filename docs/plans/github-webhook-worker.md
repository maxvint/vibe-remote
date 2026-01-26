# GitHub Webhook Worker (Cloudflare)

独立部署的 Cloudflare Worker，用于接收 GitHub Webhook 并转发给 Vibe Remote。

## 架构

```
GitHub → Cloudflare Worker → KV Storage ← Vibe Remote (拉取)
```

## 项目结构

```
vibe-github-webhook/
├── wrangler.toml
├── src/
│   ├── index.ts          # Worker 入口
│   ├── webhook.ts        # Webhook 处理
│   ├── auth.ts           # 签名验证 & API 认证
│   └── types.ts          # 类型定义
├── package.json
└── README.md
```

## 核心代码

### wrangler.toml

```toml
name = "vibe-github-webhook"
main = "src/index.ts"
compatibility_date = "2024-01-01"

[[kv_namespaces]]
binding = "EVENTS"
id = "your-kv-namespace-id"

[vars]
TRIGGER_KEYWORD = "@Codeholic"

# 敏感配置通过 secrets 设置
# wrangler secret put GITHUB_WEBHOOK_SECRET
# wrangler secret put API_TOKEN
```

### src/index.ts

```typescript
import { verifyWebhookSignature, verifyApiToken } from './auth';
import { handleWebhook } from './webhook';
import { GitHubEvent } from './types';

export interface Env {
  EVENTS: KVNamespace;
  GITHUB_WEBHOOK_SECRET: string;
  API_TOKEN: string;
  TRIGGER_KEYWORD: string;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // CORS headers
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Hub-Signature-256',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    try {
      // GitHub Webhook 入口
      if (url.pathname === '/webhook' && request.method === 'POST') {
        return await handleWebhookRequest(request, env, corsHeaders);
      }

      // Vibe Remote 拉取接口
      if (url.pathname === '/events' && request.method === 'GET') {
        return await handleGetEvents(request, env, corsHeaders);
      }

      // 标记事件已处理
      if (url.pathname.startsWith('/events/') && request.method === 'DELETE') {
        return await handleDeleteEvent(request, env, corsHeaders);
      }

      // 健康检查
      if (url.pathname === '/health') {
        return new Response(JSON.stringify({ status: 'ok' }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }

      return new Response('Not Found', { status: 404, headers: corsHeaders });
    } catch (error) {
      console.error('Worker error:', error);
      return new Response(JSON.stringify({ error: 'Internal Server Error' }), {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }
  },
};

// POST /webhook - 接收 GitHub Webhook
async function handleWebhookRequest(
  request: Request,
  env: Env,
  corsHeaders: Record<string, string>
): Promise<Response> {
  const signature = request.headers.get('X-Hub-Signature-256');
  const body = await request.text();

  // 验证签名
  if (!signature || !(await verifyWebhookSignature(body, signature, env.GITHUB_WEBHOOK_SECRET))) {
    return new Response(JSON.stringify({ error: 'Invalid signature' }), {
      status: 401,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  const event = request.headers.get('X-GitHub-Event');
  const payload = JSON.parse(body);

  // 只处理 issue_comment 事件
  if (event !== 'issue_comment' || payload.action !== 'created') {
    return new Response(JSON.stringify({ ok: true, skipped: true }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  // 检查触发词
  const commentBody = payload.comment?.body || '';
  if (!commentBody.includes(env.TRIGGER_KEYWORD)) {
    return new Response(JSON.stringify({ ok: true, skipped: true, reason: 'no_trigger' }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  // 提取指令（去除触发词）
  const instruction = commentBody
    .replace(new RegExp(`${env.TRIGGER_KEYWORD}\\s*`, 'g'), '')
    .trim();

  // 构建事件对象
  const githubEvent: GitHubEvent = {
    id: crypto.randomUUID(),
    type: 'issue_comment',
    repo: payload.repository.full_name,
    issue_number: payload.issue.number,
    issue_title: payload.issue.title,
    issue_body: payload.issue.body,
    comment_id: payload.comment.id,
    comment_url: payload.comment.html_url,
    user: payload.comment.user.login,
    instruction,
    created_at: new Date().toISOString(),
    status: 'pending',
  };

  // 写入 KV (TTL 24小时)
  await env.EVENTS.put(`event:${githubEvent.id}`, JSON.stringify(githubEvent), {
    expirationTtl: 86400,
  });

  console.log(`Event stored: ${githubEvent.id} from ${githubEvent.repo}#${githubEvent.issue_number}`);

  return new Response(JSON.stringify({ ok: true, event_id: githubEvent.id }), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  });
}

// GET /events - 获取待处理事件
async function handleGetEvents(
  request: Request,
  env: Env,
  corsHeaders: Record<string, string>
): Promise<Response> {
  // 验证 API Token
  if (!verifyApiToken(request, env.API_TOKEN)) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  // 列出所有事件
  const list = await env.EVENTS.list({ prefix: 'event:' });
  const events: GitHubEvent[] = [];

  for (const key of list.keys) {
    const value = await env.EVENTS.get(key.name);
    if (value) {
      const event = JSON.parse(value) as GitHubEvent;
      if (event.status === 'pending') {
        events.push(event);
      }
    }
  }

  // 按时间排序
  events.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

  return new Response(JSON.stringify({ events }), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  });
}

// DELETE /events/:id - 标记事件已处理
async function handleDeleteEvent(
  request: Request,
  env: Env,
  corsHeaders: Record<string, string>
): Promise<Response> {
  if (!verifyApiToken(request, env.API_TOKEN)) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  const url = new URL(request.url);
  const eventId = url.pathname.split('/').pop();

  if (!eventId) {
    return new Response(JSON.stringify({ error: 'Missing event ID' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  await env.EVENTS.delete(`event:${eventId}`);

  return new Response(JSON.stringify({ ok: true, deleted: eventId }), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  });
}
```

### src/auth.ts

```typescript
// 验证 GitHub Webhook 签名
export async function verifyWebhookSignature(
  payload: string,
  signature: string,
  secret: string
): Promise<boolean> {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );

  const signatureBuffer = await crypto.subtle.sign('HMAC', key, encoder.encode(payload));
  const expectedSignature = 'sha256=' + arrayBufferToHex(signatureBuffer);

  return signature === expectedSignature;
}

// 验证 API Token
export function verifyApiToken(request: Request, expectedToken: string): boolean {
  const authHeader = request.headers.get('Authorization');
  if (!authHeader) return false;

  const token = authHeader.replace('Bearer ', '');
  return token === expectedToken;
}

function arrayBufferToHex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}
```

### src/types.ts

```typescript
export interface GitHubEvent {
  id: string;
  type: 'issue_comment' | 'issue';
  repo: string;
  issue_number: number;
  issue_title: string;
  issue_body: string;
  comment_id?: number;
  comment_url?: string;
  user: string;
  instruction: string;
  created_at: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
}
```

### package.json

```json
{
  "name": "vibe-github-webhook",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "wrangler dev",
    "deploy": "wrangler deploy",
    "tail": "wrangler tail"
  },
  "devDependencies": {
    "@cloudflare/workers-types": "^4.20240117.0",
    "typescript": "^5.3.3",
    "wrangler": "^3.24.0"
  }
}
```

## 部署步骤

### 1. 创建 Cloudflare 账户和 KV Namespace

```bash
# 安装 wrangler
npm install -g wrangler

# 登录
wrangler login

# 创建 KV namespace
wrangler kv:namespace create "EVENTS"
# 记下返回的 id，填入 wrangler.toml
```

### 2. 配置 Secrets

```bash
# GitHub Webhook Secret
wrangler secret put GITHUB_WEBHOOK_SECRET
# 输入: your-webhook-secret

# API Token (供 Vibe Remote 访问)
wrangler secret put API_TOKEN
# 输入: your-random-api-token
```

### 3. 部署

```bash
npm install
npm run deploy
```

部署后获得 URL: `https://vibe-github-webhook.your-account.workers.dev`

### 4. 配置 GitHub App Webhook

在 GitHub App 设置中:
- Webhook URL: `https://vibe-github-webhook.your-account.workers.dev/webhook`
- Secret: 与 `GITHUB_WEBHOOK_SECRET` 相同

## Vibe Remote 集成

在 Vibe Remote 中添加事件消费逻辑：

```python
# modules/im/github/consumer.py

import asyncio
import httpx
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class GitHubEvent:
    id: str
    type: str
    repo: str
    issue_number: int
    issue_title: str
    issue_body: str
    comment_id: Optional[int]
    comment_url: Optional[str]
    user: str
    instruction: str
    created_at: str
    status: str

class CloudflareEventConsumer:
    def __init__(self, worker_url: str, api_token: str, interval: int = 5):
        self.worker_url = worker_url.rstrip('/')
        self.api_token = api_token
        self.interval = interval
        self._running = False

    async def fetch_events(self) -> List[GitHubEvent]:
        """从 Cloudflare Worker 获取待处理事件"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.worker_url}/events",
                headers={"Authorization": f"Bearer {self.api_token}"},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return [GitHubEvent(**e) for e in data.get("events", [])]

    async def mark_completed(self, event_id: str) -> None:
        """标记事件已处理"""
        async with httpx.AsyncClient() as client:
            await client.delete(
                f"{self.worker_url}/events/{event_id}",
                headers={"Authorization": f"Bearer {self.api_token}"},
                timeout=10.0,
            )

    async def start(self, callback):
        """启动事件消费循环"""
        self._running = True
        while self._running:
            try:
                events = await self.fetch_events()
                for event in events:
                    await callback(event)
                    await self.mark_completed(event.id)
            except Exception as e:
                print(f"Event consumer error: {e}")
            await asyncio.sleep(self.interval)

    def stop(self):
        self._running = False
```

### 配置示例

```yaml
# config.yaml
github:
  # Cloudflare Worker 配置
  worker_url: "https://vibe-github-webhook.your-account.workers.dev"
  api_token: "your-api-token"
  fetch_interval: 5  # 秒

  # GitHub App 配置 (用于回复)
  app_id: "123456"
  private_key_path: "/path/to/private-key.pem"
```

## 安全考虑

1. **Webhook 签名验证** - 确保请求来自 GitHub
2. **API Token** - 保护事件拉取接口
3. **KV TTL** - 24小时自动过期，防止数据堆积
4. **Rate Limiting** - Cloudflare 有内置保护

## 成本估算

Cloudflare Workers 免费计划:
- 100,000 请求/天
- 10ms CPU 时间/请求
- KV: 100,000 读/天, 1,000 写/天

对于个人/小团队使用完全足够。
