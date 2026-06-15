# Cloudflare Pages 部署指南

## 概述

本SKILL支持将生成的HTML早报自动部署到Cloudflare Pages，实现：
- ✅ 公开访问URL（无需本地服务器）
- ✅ 全球CDN加速
- ✅ 历史版本保留（最近7天报告均可访问）
- ✅ 自定义域名绑定（可选）

---

## 一、首次配置（必须）

### 1.1 安装wrangler CLI

```bash
# 方式A：全局安装（推荐）
npm install -g wrangler

# 方式B：使用npx（无需安装）
npx wrangler --version
```

**验证安装：**
```bash
wrangler --version
# 输出示例：⛅️ wrangler 4.100.0
```

### 1.2 登录Cloudflare账号

```bash
# 执行登录命令
npx wrangler login
```

**登录流程：**
1. 浏览器自动打开授权页面
2. 选择或登录您的Cloudflare账号
3. 授权WorkBuddy访问
4. 回到终端显示登录成功

**验证登录：**
```bash
npx wrangler whoami
# 输出示例：
# ⛅️ wrangler 4.100.0
# Getting User settings...
# You are logged in with an OAuth token, associated with the email 'your@email.com'!
```

### 1.3 创建Cloudflare Pages项目（可选）

**方式A：首次部署时自动创建（推荐）**
- 部署脚本会自动创建名为 `stock-morning-brief` 的项目
- 无需手动操作

**方式B：手动创建**
1. 访问 [Cloudflare Pages控制台](https://dash.cloudflare.com/?to=/:account/pages)
2. 点击「Create a project」
3. 选择「Direct Upload」
4. 项目名填写：`stock-morning-brief`

---

## 二、部署HTML报告

### 2.1 基本用法

```bash
# 使用Python环境
PYTHON=/path/to/python3  # 或使用系统Python: python3

# 部署早报（保留历史）
$PYTHON scripts/deploy_to_cloudflare.py \
  --html ./tmp/morning_brief_2026-06-15.html \
  --project stock-morning-brief
```

**输出示例：**
```
[OK] wrangler 版本: 4.100.0
[OK] You are logged in with an OAuth token...
[INFO] 临时目录: /var/folders/.../T/tmp...
[OK] 已复制: ./tmp/morning_brief_2026-06-15.html → /var/folders/.../index.html
[INFO] 部署到 Cloudflare Pages: stock-morning-brief
[INFO] 部署目录: /var/folders/.../T/tmp...

[SUCCESS] 部署成功！
[URL] https://stock-morning-brief.pages.dev/2026-06-15/

============================================================
✅ 部署成功！访问: https://stock-morning-brief.pages.dev/2026-06-15/
   URL: https://stock-morning-brief.pages.dev/2026-06-15/
```

### 2.2 访问历史版本

**默认保留策略：**
- 每天的报告独立URL：`https://stock-morning-brief.pages.dev/2026-06-15/`
- 可访问最近7天的报告

**访问方式：**
- 今天早报：`https://stock-morning-brief.pages.dev/2026-06-15/`
- 昨天早报：`https://stock-morning-brief.pages.dev/2026-06-14/`
- 本周早报：直接修改URL中的日期即可

### 2.3 覆盖部署（不保留历史）

```bash
# 每次覆盖同一URL（适合测试）
$PYTHON scripts/deploy_to_cloudflare.py \
  --html ./tmp/morning_brief_2026-06-15.html \
  --project stock-morning-brief \
  --no-history

# 访问URL：https://stock-morning-brief.pages.dev/
```

---

## 三、自定义域名（可选）

### 3.1 绑定自定义域名

**前提：**
- 拥有域名并托管在Cloudflare（或修改DNS到Cloudflare）

**步骤：**
1. 访问 Cloudflare Pages 控制台
2. 选择项目 `stock-morning-brief`
3. 进入「Custom domains」
4. 点击「Set up a custom domain」
5. 输入域名：如 `stock.yourdomain.com`
6. 按提示添加DNS记录

**绑定后访问：**
- `https://stock.yourdomain.com/2026-06-15/`

---

## 四、常见问题

### Q1: 部署超时怎么办？

**原因：** 网络代理或Cloudflare服务慢

**解决：**
```bash
# 增加超时时间（脚本内置120秒）
# 或检查代理设置
export HTTP_PROXY=http://your-proxy:port
export HTTPS_PROXY=http://your-proxy:port
```

### Q2: 部署失败：`Not authorized`

**原因：** wrangler未登录或Token过期

**解决：**
```bash
# 重新登录
npx wrangler login

# 或使用API Token
export CLOUDFLARE_API_TOKEN=your_token
```

### Q3: 如何删除历史版本？

**方式A：Cloudflare控制台**
- 访问项目 → Deployments
- 手动删除旧部署

**方式B：wrangler CLI**
```bash
# 列出所有部署
npx wrangler pages deployment list --project-name=stock-morning-brief

# 删除特定部署
npx wrangler pages deployment delete <deployment-id> --project-name=stock-morning-brief
```

### Q4: 如何查看部署日志？

```bash
# 查看最近部署
npx wrangler pages deployment tail --project-name=stock-morning-brief

# 或访问控制台
# https://dash.cloudflare.com/:account/pages/view/stock-morning-brief
```

---

## 五、进阶用法

### 5.1 结合飞书推送

```bash
# Step 1: 部署到Cloudflare
$PYTHON scripts/deploy_to_cloudflare.py \
  --html ./tmp/morning_brief_2026-06-15.html > deploy_result.json

# Step 2: 解析URL并推送飞书
URL=$(cat deploy_result.json | python3 -c "import sys, json; print(json.load(sys.stdin)['url'])")

# Step 3: 推送到飞书（使用lark-cli）
lark-cli im send-message --msg_type text --content "今日早报已发布：$URL"
```

### 5.2 定时自动部署

**使用Automations（推荐）：**
- 在WorkBuddy中创建自动化任务
- 每交易日早8:00自动生成并部署早报

**配置示例：**
```json
{
  "name": "股市早报自动部署",
  "prompt": "生成今日股市早报并部署到Cloudflare",
  "scheduleType": "recurring",
  "rrule": "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR;BYHOUR=8;BYMINUTE=0"
}
```

---

## 六、成本说明

### Cloudflare Pages 免费额度

| 项目 | 免费额度 | 说明 |
|------|---------|------|
| 部署次数 | 500次/月 | 足够每日早报 |
| 带宽 | 无限 | 全球CDN免费 |
| 并发部署 | 1个 | 同时只能1个部署任务 |
| 自定义域名 | 无限 | 可绑定多个域名 |

**预估成本：**
- 每月22个交易日 × 1次部署 = **22次**
- 远低于500次免费额度
- **完全免费使用**

---

## 七、故障排查

### 7.1 日志级别

```bash
# 启用详细日志
export WRANGLER_LOG=debug

# 重新部署
npx wrangler pages deploy ./tmp --project-name=stock-morning-brief
```

### 7.2 常见错误码

| 错误 | 原因 | 解决 |
|------|------|------|
| `ENOTFOUND` | DNS解析失败 | 检查网络/代理 |
| `401 Unauthorized` | Token过期 | `wrangler login` |
| `404 Project not found` | 项目不存在 | 自动创建或手动创建 |
| `500 Internal Error` | Cloudflare服务异常 | 稍后重试 |

---

## 八、相关链接

- [Cloudflare Pages官方文档](https://developers.cloudflare.com/pages/)
- [wrangler CLI文档](https://developers.cloudflare.com/workers/wrangler/)
- [自定义域名配置](https://developers.cloudflare.com/pages/platform/custom-domains/)
- [部署限制说明](https://developers.cloudflare.com/pages/platform/limits/)
