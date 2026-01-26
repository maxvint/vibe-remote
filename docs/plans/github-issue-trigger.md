# GitHub Issue Trigger 功能设计文档

## 1. 功能概述

### 目标
在 GitHub Issue 中通过 `@Codeholic` 触发 AI Agent（OpenCode/Claude Code/Codex）执行任务，并将结果回复到 Issue 评论中。

### 用户流程
1. 用户在 GitHub Issue 中描述需求
2. 用户在评论中 `@Codeholic` 并附带具体指令
3. 系统检测到触发词，调用 AI Agent 执行任务
4. AI 执行过程中的日志/结果实时更新到 Issue 评论
5. 任务完成后，最终结果以评论形式回复

### 示例
```
Issue #42: Add user authentication feature

评论:
@Codeholic 请分析当前代码库的认证相关代码，并给出实现 OAuth2 登录的方案

Bot 回复:
🤖 正在分析代码库...
[执行日志]
...
✅ 分析完成，以下是实现方案：
...
```

---

## 2. 授权方案：GitHub App（推荐）

### 2.1 为什么选择 GitHub App

| 特性 | GitHub App | OAuth App |
|------|------------|-----------|
| Webhook | 内置，自动配置 | 需要手动配置每个仓库 |
| 权限 | 细粒度（只读/读写分离） | 粗粒度（repo scope 权限过大） |
| Token | 短期有效，自动刷新 | 长期有效，泄露风险高 |
| Rate Limit | 更高，随仓库数量扩展 | 固定 5000/小时 |
| 安装范围 | 可选择特定仓库 | 用户所有仓库 |
| 用户解绑 | App 继续工作 | Token 失效 |

**结论**: GitHub App 是官方推荐的现代集成方式，更安全、更灵活。

### 2.2 用户授权流程

```
┌─────────────────────────────────────────────────────────────┐
│                      Vibe Remote UI                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  GitHub 集成                                                 │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  [🔗 连接 GitHub]                                    │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  跳转到 GitHub App 安装页面                          │    │
│  │  用户选择要授权的仓库                                │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  已连接仓库:                                         │    │
│  │  ┌─────────────────────────────────────────────┐    │    │
│  │  │ ☑ myorg/frontend     [Claude ▼] [配置]     │    │    │
│  │  │ ☑ myorg/backend      [OpenCode ▼] [配置]   │    │    │
│  │  │ ☐ myorg/docs         (未启用)              │    │    │
│  │  └─────────────────────────────────────────────┘    │    │
│  │  [+ 添加更多仓库]                                    │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**流程步骤**:

1. **用户点击「连接 GitHub」**
   - 跳转到 GitHub App 安装页面
   - URL: `https://github.com/apps/vibe-codeholic/installations/new`

2. **用户在 GitHub 上选择仓库**
   - 可选择「所有仓库」或「指定仓库」
   - GitHub 自动配置 Webhook

3. **OAuth 回调**
   - GitHub 重定向回 Vibe Remote UI
   - 携带 `installation_id` 和 `code`

4. **获取 Installation Token**
   - 后端使用 App 私钥 + installation_id 获取 token
   - Token 用于访问用户授权的仓库

5. **UI 显示已授权仓库**
   - 列出所有已授权仓库
   - 用户可启用/禁用、配置 Agent

### 2.3 GitHub App 配置

需要创建一个 GitHub App，配置如下：

**基本信息**:
- App name: `Vibe Codeholic` (或自定义)
- Homepage URL: `https://github.com/cyhhao/vibe-remote`
- Callback URL: `http://localhost:5123/github/callback` (可配置)
- Webhook URL: `https://your-server.com/webhook/github`

**权限 (Permissions)**:
| 权限 | 级别 | 用途 |
|------|------|------|
| Issues | Read & Write | 读取 Issue、发表评论 |
| Contents | Read-only | 读取代码（用于 Agent 分析） |
| Metadata | Read-only | 获取仓库基本信息 |
| Pull requests | Read & Write | (可选) 支持 PR 触发 |

**事件订阅 (Events)**:
- Issue comment
- Issues
- (可选) Pull request review comment

### 2.4 Webhook 架构：Cloudflare Workers（推荐）

将 Webhook 接收器部署到 Cloudflare Workers，与主项目解耦：

```
┌─────────────────────────────────────────────────────────────────┐
│                         GitHub                                   │
│                           │                                      │
│                    Webhook Event                                 │
│                           │                                      │
└───────────────────────────┼─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              Cloudflare Workers (独立部署)                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ vibe-github-webhook                                      │    │
│  │  - 验证 Webhook 签名                                     │    │
│  │  - 解析事件，检测 @Codeholic                             │    │
│  │  - 写入 Cloudflare KV/Queue                             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Cloudflare KV                                            │    │
│  │  - 存储待处理事件                                        │    │
│  │  - TTL: 24h                                              │    │
│  └─────────────────────────────────────────────────────────┘    │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                      (拉取事件)
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              Vibe Remote (本地/内网)                             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ GitHub Event Consumer                                    │    │
│  │  - 从 KV 拉取事件                                        │    │
│  │  - 调用 Agent 处理                                       │    │
│  │  - 通过 GitHub API 回复                                  │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

**优势**:
- Cloudflare Workers 天然公网可访问
- 主服务无需暴露到公网
- 完全解耦，独立部署和扩展
- 免费额度：10万次请求/天
- 边缘网络，低延迟

**数据流**:
1. GitHub 发送 Webhook 到 Cloudflare Worker
2. Worker 验证签名、解析事件
3. 检测到 `@Codeholic` 后写入 KV
4. Vibe Remote 从 KV 拉取新事件
5. Agent 处理任务，通过 GitHub API 回复

### 2.5 Cloudflare Worker 设计

**项目结构** (独立仓库或 `cloudflare/` 目录):
```
vibe-github-webhook/
├── wrangler.toml        # Cloudflare 配置
├── src/
│   └── index.ts         # Worker 入口
├── package.json
└── README.md
```

**功能**:
1. `POST /webhook` - 接收 GitHub Webhook
2. `GET /events` - 获取待处理事件（供 Vibe Remote 轮询）
3. `DELETE /events/:id` - 标记事件已处理

**KV 数据结构**:
```json
{
  "key": "event:{uuid}",
  "value": {
    "id": "uuid",
    "type": "issue_comment",
    "repo": "owner/repo",
    "issue_number": 42,
    "comment_id": 123456,
    "user": "alice",
    "body": "@Codeholic 请分析这段代码",
    "created_at": "2025-01-25T10:00:00Z",
    "status": "pending"
  },
  "expiration_ttl": 86400
}
```

---

## 3. 架构设计

### 3.1 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         GitHub                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │  GitHub App  │    │    Issue     │    │   Webhook    │       │
│  │ Installation │───▶│   Comment    │───▶│    Event     │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
└─────────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Vibe Remote Server                            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ GitHub Module (modules/im/github/)                       │    │
│  │  ┌─────────────────────────────────────────────────┐    │    │
│  │  │ OAuth Handler                                    │    │    │
│  │  │  - GET /github/callback (OAuth 回调)            │    │    │
│  │  │  - GET /github/repos (获取已授权仓库)           │    │    │
│  │  └─────────────────────────────────────────────────┘    │    │
│  │  ┌─────────────────────────────────────────────────┐    │    │
│  │  │ Webhook Handler                                  │    │    │
│  │  │  - POST /webhook/github                         │    │    │
│  │  │  - Verify signature (X-Hub-Signature-256)       │    │    │
│  │  │  - Parse issue_comment.created                  │    │    │
│  │  │  - Check @Codeholic mention                     │    │    │
│  │  └─────────────────────────────────────────────────┘    │    │
│  │  ┌─────────────────────────────────────────────────┐    │    │
│  │  │ GitHub API Client                                │    │    │
│  │  │  - Get installation token                       │    │    │
│  │  │  - Create/edit issue comment                    │    │    │
│  │  │  - List repositories                            │    │    │
│  │  └─────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Existing Core System (unchanged)                         │    │
│  │  Controller → MessageHandler → AgentService              │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 模块结构

**Cloudflare Worker (独立部署)**:
```
vibe-github-webhook/              # 独立仓库或 cloudflare/ 目录
├── wrangler.toml                 # Cloudflare 配置
├── src/
│   ├── index.ts                  # Worker 入口
│   ├── auth.ts                   # 签名验证
│   └── types.ts                  # 类型定义
└── package.json
```

**Vibe Remote (主项目)**:
```
modules/im/
├── base.py              # 已有 - BaseIMClient 抽象
├── slack.py             # 已有 - Slack 实现
├── factory.py           # 已有 - 需扩展
└── github/              # 新增
    ├── __init__.py
    ├── client.py        # GitHubIMClient 实现
    ├── consumer.py      # Cloudflare KV 事件消费
    ├── app.py           # GitHub App 认证 (JWT + Installation Token)
    ├── api.py           # GitHub REST API 封装
    └── oauth.py         # OAuth 回调处理

config/
├── v2_config.py         # 需扩展 - 添加 GitHub 配置
└── v2_settings.py       # 需扩展 - 添加 GitHub 仓库设置

ui/src/components/steps/
└── GitHubConfig.tsx     # 新增 - GitHub 配置页面

vibe/
├── ui_server.py         # 需扩展 - 添加 GitHub OAuth 路由
└── api.py               # 需扩展 - 添加 GitHub API 端点
```

### 3.3 核心类设计

#### GitHubAppConfig（GitHub App 配置）

```python
@dataclass
class GitHubAppConfig:
    # GitHub App 凭证（从 GitHub App 设置页获取）
    app_id: str                           # GitHub App ID
    private_key: str                      # GitHub App 私钥 (PEM 格式)
    webhook_secret: str                   # Webhook 签名密钥

    # OAuth 设置
    client_id: str                        # OAuth Client ID
    client_secret: str                    # OAuth Client Secret
    callback_url: str = "http://localhost:5123/github/callback"

    # 触发设置
    trigger_keyword: str = "@Codeholic"   # 触发关键词
    trigger_on_issue_body: bool = False   # 是否在 Issue 正文中也触发

    # 默认 Agent 设置
    default_agent: str = "claude"
    default_cwd: str = ""                 # 留空则自动 clone 到临时目录


@dataclass
class GitHubRepoConfig:
    """单个仓库的配置（存储在 settings.json）"""
    repo: str                             # "owner/repo"
    installation_id: int                  # GitHub App Installation ID
    enabled: bool = True                  # 是否启用
    agent: str = "claude"                 # 使用的 Agent
    cwd: Optional[str] = None             # 工作目录（None = 自动 clone）
    allowed_users: List[str] = []         # 允许触发的用户（空=所有）
```

#### GitHubIMClient（IM 客户端）

```python
class GitHubIMClient(BaseIMClient):
    """GitHub Issue 作为 IM 平台的客户端实现"""

    def __init__(self, config: GitHubConfig):
        super().__init__(config)
        self.github = Github(config.token)
        self.webhook_server = None

    async def send_message(
        self,
        context: MessageContext,
        text: str,
        **kwargs
    ) -> str:
        """在 Issue 中发表评论"""
        repo = self.github.get_repo(context.platform_specific['repo'])
        issue = repo.get_issue(context.platform_specific['issue_number'])
        comment = issue.create_comment(self._format_message(text))
        return str(comment.id)

    async def edit_message(
        self,
        context: MessageContext,
        message_id: str,
        text: str,
        **kwargs
    ) -> bool:
        """编辑 Issue 评论"""
        repo = self.github.get_repo(context.platform_specific['repo'])
        issue = repo.get_issue(context.platform_specific['issue_number'])
        comment = issue.get_comment(int(message_id))
        comment.edit(self._format_message(text))
        return True

    def run(self):
        """启动事件消费循环，从 Cloudflare KV 拉取事件"""
        self._start_event_consumer()
```

#### MessageContext 映射

```python
# GitHub Issue → MessageContext
def create_context_from_issue_comment(event: dict) -> MessageContext:
    repo = event['repository']['full_name']
    issue_number = event['issue']['number']
    comment_id = event['comment']['id']
    user = event['comment']['user']['login']

    return MessageContext(
        user_id=user,
        channel_id=f"github:{repo}",
        thread_id=f"issue:{issue_number}",
        message_id=str(comment_id),
        platform_specific={
            'platform': 'github',
            'repo': repo,
            'issue_number': issue_number,
            'comment_id': comment_id,
            'issue_title': event['issue']['title'],
            'issue_body': event['issue']['body'],
            'comment_body': event['comment']['body'],
            'html_url': event['comment']['html_url'],
        }
    )
```

---

## 4. 实现步骤

### Phase 1: Cloudflare Worker (独立部署)

1. **创建 Cloudflare Worker 项目**
   ```
   vibe-github-webhook/
   ├── wrangler.toml
   ├── src/index.ts
   ├── src/auth.ts
   └── src/types.ts
   ```

2. **实现 Worker 核心功能**
   - `POST /webhook` - 接收 GitHub Webhook
   - 验证签名 (X-Hub-Signature-256)
   - 检测触发词 `@Codeholic`
   - 写入 Cloudflare KV

3. **实现轮询 API**
   - `GET /events` - 获取待处理事件
   - `DELETE /events/:id` - 标记已处理
   - Bearer Token 认证

4. **部署到 Cloudflare**
   - 创建 KV Namespace
   - 配置 Secrets
   - `wrangler deploy`

详见: [github-webhook-worker.md](./github-webhook-worker.md)

### Phase 2: GitHub App 配置

5. **创建 GitHub App**
   - 配置权限 (Issues: Read & Write, Contents: Read-only)
   - 设置 Webhook URL 指向 Cloudflare Worker
   - 获取 App ID, Client ID/Secret, Private Key

6. **实现 GitHub App 认证 (`modules/im/github/app.py`)**
   - JWT 生成（App ID + Private Key）
   - Installation Access Token 获取和缓存

### Phase 3: Vibe Remote 集成

7. **实现事件消费器 (`modules/im/github/consumer.py`)**
   - 从 Cloudflare KV 拉取事件
   - 转换为 `MessageContext`
   - 调用 Agent 处理

8. **实现 GitHubIMClient (`modules/im/github/client.py`)**
   - 继承 `BaseIMClient`
   - `send_message` - 通过 GitHub API 发表评论
   - `edit_message` - 编辑评论
   - GitHub Markdown 格式化

9. **实现配置模型**
   - 扩展 `config/v2_config.py` 添加 `GitHubConfig`
   - Cloudflare Worker URL, API Token
   - GitHub App 凭证

### Phase 4: OAuth 授权流程 (UI)

10. **实现 OAuth 端点 (`vibe/ui_server.py`)**
    - `GET /github/install` - 重定向到 GitHub App 安装页
    - `GET /github/callback` - OAuth 回调
    - `GET /github/repos` - 获取已授权仓库

11. **创建 GitHub 配置页面 (`ui/src/.../GitHubConfig.tsx`)**
    - 「连接 GitHub」按钮
    - 已授权仓库列表
    - 仓库启用/禁用、Agent 配置

### Phase 5: 增强功能

12. **工作目录管理**
    - 自动 clone 仓库到 `_tmp/github/{owner}/{repo}/`
    - 自动 pull 更新

13. **安全加固**
    - Rate limiting (每用户/每仓库)
    - 用户白名单
    - 敏感信息过滤

---

## 5. 配置示例

### 5.1 环境变量

```bash
# GitHub App 凭证
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY_PATH=/path/to/private-key.pem
GITHUB_WEBHOOK_SECRET=your-webhook-secret

# OAuth 凭证
GITHUB_CLIENT_ID=Iv1.xxxxxxxxxx
GITHUB_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxx

# 触发关键词
GITHUB_TRIGGER_KEYWORD=@Codeholic
```

### 5.2 config.yaml

```yaml
github:
  # GitHub App 配置
  app_id: ${GITHUB_APP_ID}
  private_key_path: ${GITHUB_APP_PRIVATE_KEY_PATH}
  webhook_secret: ${GITHUB_WEBHOOK_SECRET}

  # OAuth 配置
  client_id: ${GITHUB_CLIENT_ID}
  client_secret: ${GITHUB_CLIENT_SECRET}
  callback_url: "http://localhost:5123/github/callback"

  # 触发设置
  trigger_keyword: "@Codeholic"

  # 默认 Agent
  default_agent: "claude"
```

### 5.3 settings.json（自动生成）

用户通过 UI 授权后，仓库配置自动保存到 settings.json：

```json
{
  "github": {
    "installations": {
      "12345678": {
        "account": "myorg",
        "account_type": "Organization",
        "repos": {
          "myorg/frontend": {
            "enabled": true,
            "agent": "claude",
            "cwd": null,
            "allowed_users": []
          },
          "myorg/backend": {
            "enabled": true,
            "agent": "opencode",
            "cwd": "/home/user/projects/backend",
            "allowed_users": ["alice", "bob"]
          }
        }
      }
    }
  }
}
```

### 5.4 创建 GitHub App

1. 访问 https://github.com/settings/apps/new
2. 填写基本信息：
   - **App name**: `Vibe Codeholic`
   - **Homepage URL**: `https://github.com/cyhhao/vibe-remote`
   - **Callback URL**: `http://localhost:5123/github/callback`
   - **Webhook URL**: `https://your-server.com/webhook/github`（或 smee.io 代理地址）
   - **Webhook secret**: 生成一个随机字符串

3. 配置权限：
   - **Repository permissions**:
     - Issues: Read & Write
     - Contents: Read-only
     - Metadata: Read-only
   - **Subscribe to events**:
     - Issue comment
     - Issues

4. 创建后获取：
   - App ID
   - Client ID / Client Secret
   - 生成并下载 Private Key (.pem 文件)

---

## 6. 安全考虑

### 6.1 认证与授权

- **Webhook 签名验证**: 必须验证 `X-Hub-Signature-256` header
- **Token 权限最小化**: 只申请必要的权限（`repo`, `issues`）
- **仓库白名单**: 限制可触发的仓库范围
- **用户白名单**: 限制可触发的用户

### 6.2 工作目录隔离

- 每个仓库使用独立的工作目录
- 限制 Agent 的文件访问范围
- 定期清理临时目录

### 6.3 Rate Limiting

- 限制每用户/每仓库的触发频率
- 防止滥用和 DoS

### 6.4 敏感信息处理

- Token 不写入日志
- 结果中过滤敏感信息
- Issue 评论中不暴露内部错误详情

---

## 7. GitHub Markdown 格式适配

### 支持的格式

```markdown
# 标题

普通文本

`inline code`

​```python
# 代码块
def hello():
    print("world")
​```

> 引用

- 列表项

<details>
<summary>折叠内容（用于长日志）</summary>

详细内容...

</details>

✅ ❌ 🔄 状态图标
```

### 格式转换

```python
class GitHubFormatter(BaseMarkdownFormatter):
    """GitHub Markdown 格式化器"""

    def format_code_block(self, code: str, language: str = "") -> str:
        return f"```{language}\n{code}\n```"

    def format_collapsible(self, summary: str, content: str) -> str:
        return f"<details>\n<summary>{summary}</summary>\n\n{content}\n\n</details>"

    def format_status(self, status: str) -> str:
        icons = {
            'running': '🔄',
            'success': '✅',
            'error': '❌',
            'pending': '⏳',
        }
        return icons.get(status, '•')
```

---

## 8. 与现有系统的集成

### 8.1 复用现有组件

| 组件 | 复用方式 |
|------|----------|
| Controller | 完全复用，无需修改 |
| MessageHandler | 完全复用 |
| AgentService | 完全复用 |
| SessionManager | 复用，session key 使用 `github:{repo}:issue:{number}` |
| SettingsManager | 扩展支持 GitHub 特定设置 |

### 8.2 需要新增的组件

| 组件 | 说明 |
|------|------|
| GitHubIMClient | 实现 BaseIMClient 接口 |
| GitHubConfig | GitHub 特定配置 |
| GitHubFormatter | GitHub Markdown 格式化 |
| WebhookServer | 接收 GitHub 事件 |

### 8.3 需要修改的组件

| 组件 | 修改内容 |
|------|----------|
| IMFactory | 添加 GitHub 客户端创建逻辑 |
| v2_config.py | 添加 GitHubConfig |
| UI (可选) | 添加 GitHub 配置页面 |

---

## 9. 测试计划

### 单元测试

- [ ] Webhook 签名验证
- [ ] 事件解析
- [ ] 触发词检测
- [ ] MessageContext 创建
- [ ] GitHub API 调用 mock

### 集成测试

- [ ] 完整消息流程（Webhook → Agent → 回复）
- [ ] 消息编辑（日志更新）
- [ ] 错误处理

### E2E 测试

- [ ] 使用 smee.io 进行本地 webhook 测试
- [ ] 真实 GitHub 仓库测试

---

## 10. 里程碑

### M1: Cloudflare Worker
- 部署 Webhook 接收器到 Cloudflare
- 实现签名验证、触发词检测
- 实现 KV 存储和 API

### M2: Vibe Remote 集成
- 实现 Cloudflare KV 事件消费
- GitHub App 认证
- GitHubIMClient 实现
- 调用 Agent 并回复

### M3: UI 集成
- GitHub App OAuth 授权流程
- 仓库列表和配置页面

### M4: 增强功能
- 自动 clone 仓库
- 消息编辑（实时日志更新）
- 用户白名单

---

## 11. UI 设计参考

### GitHub 配置页面

```
┌─────────────────────────────────────────────────────────────┐
│  GitHub 集成                                                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  状态: ✅ 已连接                                             │
│  账户: myorg (Organization)                                  │
│  [断开连接]                                                  │
│                                                              │
│  ─────────────────────────────────────────────────────────  │
│                                                              │
│  已授权仓库                              [+ 添加更多仓库]     │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ myorg/frontend                                       │    │
│  │ ┌─────────────────────────────────────────────────┐ │    │
│  │ │ 启用: [✓]                                        │ │    │
│  │ │ Agent: [Claude Code ▼]                          │ │    │
│  │ │ 工作目录: [自动 Clone ▼]                         │ │    │
│  │ │ 允许用户: [所有用户 ▼]                           │ │    │
│  │ └─────────────────────────────────────────────────┘ │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ myorg/backend                                        │    │
│  │ ┌─────────────────────────────────────────────────┐ │    │
│  │ │ 启用: [✓]                                        │ │    │
│  │ │ Agent: [OpenCode ▼]                             │ │    │
│  │ │ 工作目录: [/home/user/backend]                  │ │    │
│  │ │ 允许用户: [alice, bob]                          │ │    │
│  │ └─────────────────────────────────────────────────┘ │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ─────────────────────────────────────────────────────────  │
│                                                              │
│  全局设置                                                    │
│  触发关键词: [@Codeholic          ]                         │
│  默认 Agent: [Claude Code ▼]                                │
│                                                              │
│  Webhook URL: https://your-server.com/webhook/github        │
│  [复制] [测试连接]                                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 12. 参考资料

### GitHub
- [GitHub Apps Documentation](https://docs.github.com/en/apps/creating-github-apps)
- [Differences between GitHub Apps and OAuth Apps](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps)
- [GitHub Webhooks Documentation](https://docs.github.com/en/webhooks)
- [Securing Webhooks](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)
- [GitHub REST API - Issues](https://docs.github.com/en/rest/issues)
- [Authenticating as a GitHub App](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app)

### Cloudflare Workers
- [Cloudflare Workers Documentation](https://developers.cloudflare.com/workers/)
- [Cloudflare KV](https://developers.cloudflare.com/kv/)
- [Wrangler CLI](https://developers.cloudflare.com/workers/wrangler/)

### Python Libraries
- [PyGithub Documentation](https://pygithub.readthedocs.io/)
- [httpx](https://www.python-httpx.org/) - Async HTTP client
- [PyJWT](https://pyjwt.readthedocs.io/) - JWT for GitHub App auth
