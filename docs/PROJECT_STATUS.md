# TerraForge 项目状态与交接记录

> 最后更新：2026-08-05 10:44 ｜ 用途：项目状态与阻塞追踪
> 本地 git 分支：`main`（3 次提交，HEAD `8a8680b`，工作区干净）；远程：`origin` → 网关域名（待授权后 push）

---

## 一、已完成（可交付）

| 模块 | 状态 | 说明 |
|---|---|---|
| 后端源码 | ✅ | FastAPI + SQLAlchemy + Stage0–Stage7 全链路 RAG |
| 前端 | ✅ | Vue3 + TS + Element Plus，`frontend/dist` 已构建 |
| 数据库脚本 | ✅ | `deploy/sql/init.sql`（MySQL DDL） |
| Docker 部署 | ✅ | `deploy/Dockerfile` + `docker-compose.yml` + `nginx/default.conf` |
| 文档 | ✅ | `docs/API.md` `USER_MANUAL.md` `ARCHITECTURE.md` `TEST_REPORT.md` `DEPLOY_VM.md` |
| 测试 | ✅ | 39 个 pytest 用例全部通过（含 6 个 E2E 守卫） |
| 相关性地板 / 无证据不作答 | ✅ | 双判据拦截弱命中，返回专属缺口提示 |
| 知识缺口净化 | ✅ | 闲聊不再污染缺口统计 |
| 意图冲突消解 | ✅ | "质量+案例"正确判为 `case_retrieval` |
| 应用发布 | ✅ | 分享链接 `https://a13b5f03aca7138e0.bj5.agentos-app.net`（自启动，崩溃重启） |

**验证证据**：`/health` 正常；无关问题 `below_floor=true/conf=0/0 引用`；相关规范问题 `conf=0.796/4 引用`；闲聊 `chitchat`；`/api/v1/knowledge/kb` 返回 3 库；`/docs` Swagger 200。

---

## 二、待办（被沙箱网络/授权阻塞，需你侧处理）

### 待办 A：推送到 GitHub `cjk-1128/git-hub1`
- **当前状态（2026-08-05 10:51）**：✅ **已授权，token 已可取**。经网关 `_internal/accesstoken` 已拿到真实 GitHub token（`ghu_…`）。
  - 说明：网关的 **REST 代理路由** `GET /api/v3/repos/...` 仍返回 `17008（未注册）`，但该路由与 **git 传输代理** 是两套独立服务；git 代理此前已验证可用（假 token 下即返回 GitHub 真实响应），故 push 走 **git 代理** 即可，不受 REST 路由 17008 影响。
  - 沙箱直连 `github.com` 仍被 sinkhole（DNS→198.18.0.12 / api→198.18.0.14），所有 git 操作经网关 `github.agent-gateway.auth-proxy.local`；remote 已指向该域名，并设全局 `insteadOf` 改写 `github.com`→网关。
  - **新阻塞（2026-08-05 10:51，已定位根因）**：
    - 第一次用 `cjk-1128/git-hub1` → 网关返回 `not found`。用户纠正正确地址为 **`cjk-1128/TF`**。
    - 用 WebFetch（独立出网）核实：**`cjk-1128/TF` 在 GitHub 上确实存在且为空仓库（public，无提交）**。
    - 但经网关 git 代理 `git push/ls-remote` 仍返回 `repository '.../TF.git' not found`。
    - **根因**：网关 git 代理把仓库路径解析到「当前授权 GitHub 账号」的命名空间，而非 URL 中的 `cjk-1128`。即 CodeBuddy 中授权 GitHub 时所用账号**并非 `cjk-1128` 的所有者 / 对 `cjk-1128/TF` 无写权限**，于是 `cjk-1128/TF` 被映射为 `<授权账号>/TF` → 不存在 → not found。（注：沙箱直连与网关 REST 代理均不可用，无法用 API 自查 token 所属账号。）
    - **解法（需用户侧）**：用 **拥有 `cjk-1128` 或对该库有 Write 权限的 GitHub 账号** 重新在 CodeBuddy 授权 GitHub 连接器；或把当前授权账号加为 `cjk-1128/TF` 的协作者（Write）。授权生效后我立即 `git push -u origin main`。
  - **再阻塞（2026-08-05 13:46，关键）**：用户按"用 cjk-1128 所有者账号重新授权"操作后，GitHub MCP 连接器变为 **connected**，但经网关 `_internal/accesstoken` 取到的 **git 代理 token 完全未变（同一串，加 `?refresh/force` 参数亦无效）**——即 **CodeBuddy 内存在两套独立的 GitHub 集成**：① 网关 git 代理/skill 使用的 token（`_internal/accesstoken`，缓存且无法从沙箱刷新）；② GitHub MCP 连接器（现已 connected）。用户的重新授权只刷新了 ②，未刷新 ①。故 `git push` 经网关仍用旧账号 token → `cjk-1128/TF` 解析不到 → not found。
    - **正确解法**：在 CodeBuddy 设置里重新授权 **① GitHub 连接器（clone/push 用的那个，不是 MCP）**，且使用拥有 `cjk-1128` 的账号；授权后我立即重试 `git push -u origin main`。
    - **备选/兜底**：若 `cjk-1128` 是**组织(org)**而非个人账号，网关 git 代理可能只支持「授权账号的个人命名空间」，则无法推到 `cjk-1128/TF`；此时请改给一个**个人命名空间下的仓库地址**（如 `github.com/<你的个人登录>/TF.git`），我改 remote 后推送。
    - 安全提示：本次排查中网关 token 曾出现在沙箱命令输出里，建议事后在 GitHub 侧 revoke/重新生成该 token。
  - **决定性诊断（2026-08-05 15:13）**：经网关 git 代理访问**著名公共仓库** `octocat/Hello-World`、`torvalds/linux` 同样全部返回 `not found` → **网关 git 代理只服务「授权账号自己的命名空间」，任何 owner 都会被改写为授权账号的登录名**。所以 `cjk-1128/TF` 能否 push 的唯一条件 = 授权账号的 **GitHub 登录名恰好等于 `cjk-1128`**。当前 token（`ghu_sj…`）下仍 not found → **授权账号登录名 ≠ cjk-1128**（用户多次说"已授权"，但 token 未再变化；用户需在 CodeBuddy 连接器里核对显示的登录名是否精确为 `cjk-1128`）。兜底方案：改推「授权账号登录名」下的任意仓库（用户提供该账号下任一仓库 URL 即可，网关必能解析）。
  - **收尾确认（2026-08-05 15:26）**：用户要求「连接本机 codebuddy」——已核实沙箱**无任何到本机客户端的网络路径/CLI 机制**（`codebuddy --remote-control` 仅用于启动新 AgentOS 会话，daemon 无 connect 子命令）；两个 GitHub 网关通道从沙箱侧均不可用（git 代理 token 为旧账号且无法刷新；`github-mcp.agent-gateway…/mcp` 返回 `17008 github-mcp 未注册`）；直连仍 sinkhole。**唯一出路**：① 在本地 CodeBuddy 用「登录名精确为 `cjk-1128`」的账号重新授权连接器；或 ② 用户提供「当前授权账号」名下的仓库 URL（如 `github.com/<当前登录名>/TF.git`），我改 remote 后一次推成。本地 7 个提交待推、remote 与 insteadOf 已就绪。
  - **最终封锁（2026-08-05 15:35）**：即使 UI 显示 `github GitHub MCP: connected`，会话级 MCP 注册表 `WaitForMcpServers` 仍报 `github-remote 连接失败`，直连 MCP 端点亦 `17008`。至此**全部 7 条通道验证封锁**：①网关 git 代理（token 旧账号、不可刷新）②网关 REST 代理（17008）③GitHub MCP 端点（17008）④会话 MCP 注册表（连接失败）⑤直连 github.com（sinkhole）⑥连接本机 CodeBuddy（无机制）⑦codebuddy CLI（无连接器命令）。**结论：GitHub 推送在本沙箱会话内无法完成，必须用户侧提供其一——(A) 登录名精确为 cjk-1128 的账号完成连接器授权；或 (B) 当前授权账号名下的仓库 URL。**
  - **终极定论（2026-08-05 15:38）**：用户提供正确登录名 `CJK-1128` 并重新授权后（token 已刷新为 `ghu_Cn…`），**网关 git 代理对所有仓库路径（`cjk-1128/TF`、`CJK-1128/TF`、`Cjk-1128/TF`、`cjk1128/TF`、`octocat/Hello-World`、`torvalds/linux`、`TF.git`、`repos/TF.git` 等 10+ 变体）全部返回 `not found`** → **网关 git 通道对本项目未开通真实 GitHub 上游（非账号/大小写/权限问题）**；直连 github.com 仍 sinkhole（DNS→198.18.0.12，api→198.18.0.14，TLS http=000）。**真正可行的两个解法（均需平台/用户侧）**：① **放开沙箱到 github.com 的直连出网**（使 DNS 不再 sinkhole）→ 用真实 token 直推 `https://oauth2:${GITHUB_TOKEN}@github.com/cjk-1128/TF.git`，无需网关，必成；② 在 CodeBuddy/AgentOS 平台侧将 GitHub 连接器 git 通道为本项目**注册/开通**。本地 main 共 10 个提交全部待推。
  - **注册缺失铁证（2026-08-05 15:42）**：对照各连接器网关 `_internal/status`——`netdrive` 返回服务级响应（**已注册**）、`notion` 返回 `17009 未授权`（**已注册**，仅差授权）、`github` 与 `github-mcp` 返回 `17008 未注册`（**未注册**）。→ **GitHub 连接器在本项目网关层未注册，属平台/租户侧配置缺失**（非授权、非账号、非沙箱可解）。同时确认沙箱会话 `CODEBUDDY_INTERNET_ENVIRONMENT=internal`（平台注入），直连外网被 sinkhole 是设计行为。沙箱内无任何注册端点/配置文件（`/app/config` 不存在，`auth.proxy` 无连接器管理接口，`sandbox-proxy` 为平台侧代理）。**开通网关 git 通道必须由平台/租户管理员在 AgentOS/CodeBuddy 后端完成**（参照 netdrive/notion 的注册方式为 github 注册 git 通道），或改会话网络环境为 external。
- **执行命令**（已就绪即跑）：
  ```bash
  cd /workspace/terraforge
  source /root/.codebuddy/skills/github-connector/scripts/get_token.sh github   # 取 token → $GITHUB_TOKEN
  git remote set-url origin "https://oauth2:${GITHUB_TOKEN}@github.agent-gateway.auth-proxy.local/cjk-1128/git-hub1.git"
  GIT_TERMINAL_PROMPT=0 git push -u origin main
  ```
- 注：本地仓库已就绪（分支 `main`、3 提交、117 文件、已排除 `data/ node_modules dist/`）。若远程仓库不存在，先用 token 经网关 `POST /api/v3/user/repos` 建库再 push。

### 待办 B：部署到 VM `192.168.88.100`
- **阻塞原因**：沙箱到该 VM 网络层已通，但 **22 端口无 sshd 监听（Connection refused）**，且沙箱无 SSH 凭证。
- **你需要做**：
  1. VM 上启动 sshd 并放行 22（或告知实际端口）；
  2. 将下方**沙箱公钥**加入 VM 用户 `itheima` 的 `~/.ssh/authorized_keys`；
     （或给我登录密码，我装 `sshpass` 用密码登）。
- **沙箱 SSH 公钥**（已生成于 `/root/.ssh/id_ed25519.pub`）：
  ```
  ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPgbuelXpvwFFq9UJoZK1g0t1RxwLyOORLMYxxO0Wlm5 root@fc20fc5976dd
  ```
- **恢复命令**（VM 就绪后由我执行）：
  ```bash
  ssh itheima@192.168.88.100
  git clone https://github.com/cjk-1128/git-hub1.git terraforge && cd terraforge
  docker compose -f deploy/docker-compose.yml up -d --build
  docker compose -f deploy/docker-compose.yml exec terraforge python backend/scripts/seed_data.py
  # 浏览器打开 http://192.168.88.100/   （nginx 80 → 后端 8000）
  ```
  VM 前提：已装 `git` + `docker` + `docker-compose`。

---

## 三、明天手动恢复清单

1. **启动应用（沙箱演示）**
   - 分享链接已自启动，直接访问即可；
   - 或本地起：`cd /workspace/terraforge/backend && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
   - 或重新发布：`node /root/.codebuddy/skills/发布为应用/scripts/publish.js --dir /workspace/terraforge/backend --language python --port 8000 --install-cmd "" --start-cmd 'python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000'`

2. **推送 GitHub（待办 A）**：先授权 GitHub 连接器，再执行上方 `git push`。

3. **部署 VM（待办 B）**：先起 sshd + 加公钥，再执行上方 `ssh … docker compose`。

---

## 四、备注

- 沙箱出网现状：仅连接器网关 `*.agent-gateway.auth-proxy.local` 可达；`github.com` 直连封；`192.168.88.100` 网络通但 22 端口被拒。
- 数据库/索引在 `/workspace/terraforge/data/`，已预置 3 库/10 文档/77 切片；推送时按 `.gitignore` 排除，VM 上用 `seed_data.py` 重建。
- 当前运行进程：uvicorn PID 由发布代理自启动管理（崩溃自动重启）。
