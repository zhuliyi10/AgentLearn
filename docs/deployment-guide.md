# Agent 学习项目 - 文档站点部署指南

本文档记录从本地搭建到线上部署的完整流程，包括评论系统和浏览量统计的集成。

---

## 一、技术栈

| 组件 | 说明 |
|------|------|
| **MkDocs + Material** | 静态文档站点生成器，Material 主题美观且功能丰富 |
| **GitHub Pages** | 免费托管，推送即部署 |
| **Giscus** | 基于 GitHub Discussions 的评论系统，支持 reactions |
| **Umami** | 隐私友好的网站流量统计工具 |

---

## 二、本地环境搭建

### 2.1 安装依赖

```bash
# 激活虚拟环境
source .venv/bin/activate

# 安装文档相关依赖
pip install mkdocs-material
```

### 2.2 本地预览

```bash
mkdocs serve
```

浏览器访问 `http://127.0.0.1:8000` 即可实时预览，修改文件后页面自动刷新。

### 2.3 本地构建

```bash
mkdocs build
```

构建产物输出到 `site/` 目录（已在 `.gitignore` 中忽略）。

---

## 三、项目结构

```
AgentLearn/
├── docs/                          # 文档源文件（MkDocs 读取此目录）
│   ├── index.md                   # 首页（项目总览）
│   ├── styles/
│   │   └── custom.css             # 自定义样式（隐藏 Material 水印）
│   ├── overrides/                 # MkDocs 主题覆盖
│   │   ├── main.html              # 主模板（集成 Umami 统计 + 评论区）
│   │   └── partials/
│   │       └── comments.html      # Giscus 评论组件
│   ├── 01_basics/                 # 阶段1 文档
│   ├── 02_tool_calling/           # 阶段2 文档
│   └── 03_agent_patterns/         # 阶段3 文档
├── .github/
│   └── workflows/
│       └── deploy-docs.yml        # GitHub Actions 自动部署工作流
├── mkdocs.yml                     # MkDocs 配置文件
├── pyproject.toml                 # Python 项目依赖
└── ...
```

---

## 四、GitHub Pages 部署

### 4.1 首次配置

1. **推送代码到 GitHub**

   ```bash
   git add -A
   git commit -m "feat: 添加文档站点"
   git push origin main
   ```

2. **启用 GitHub Pages**

   进入仓库 → **Settings** → **Pages** → **Source** 选择 **GitHub Actions**

3. **等待部署完成**

   推送后自动触发 `.github/workflows/deploy-docs.yml`，约 1-2 分钟后站点上线。

### 4.2 访问地址

```
https://<你的用户名>.github.io/AgentLearn/
```

### 4.3 后续更新

每次推送代码到 `main` 分支，GitHub Actions 会自动重新构建并部署，无需手动操作。

如需手动触发，可进入仓库 → **Actions** → **Deploy Docs to GitHub Pages** → **Run workflow**。

### 4.4 部署工作流说明

`.github/workflows/deploy-docs.yml` 的工作流程：

```
push 到 main 分支
    ↓
checkout 代码 + 安装 Python
    ↓
pip install mkdocs-material
    ↓
mkdocs build → 生成 site/ 目录
    ↓
上传构建产物 → 部署到 GitHub Pages
```

---

## 五、Giscus 评论系统集成

Giscus 基于 GitHub Discussions，访客可用 GitHub 账号评论和添加 emoji reactions。

### 5.1 前置条件

- 仓库为 **Public**
- 仓库已启用 **Discussions** 功能
- 已安装 [Giscus GitHub App](https://github.com/apps/giscus)

### 5.2 配置步骤

1. **启用 Discussions**

   仓库 → **Settings** → **Features** → 勾选 **Discussions**

2. **安装 Giscus App**

   访问 https://github.com/apps/giscus → 点击 **Install** → 选择目标仓库

3. **生成配置**

   访问 https://giscus.app ，填入仓库信息，选择 Discussion Category，复制生成的 `<script>` 代码。

4. **写入模板**

   将生成的脚本替换到 `docs/overrides/partials/comments.html` 中。

### 5.3 当前配置

| 参数 | 值 |
|------|-----|
| Repository | `zhuliyi10/AgentLearn` |
| Mapping | `pathname`（按页面路径匹配讨论） |
| Reactions | 已启用 |
| 主题 | `preferred_color_scheme`（跟随系统明暗模式） |
| 语言 | `zh-CN` |

---

## 六、Umami 浏览量统计

Umami 是开源、隐私友好的网站分析工具，可统计每页访问量、访客来源等。

### 6.1 注册与配置

1. 访问 https://cloud.umami.is 注册账号（免费）
2. 点击 **Add website**：
   - **Name**: `AgentLearn`
   - **Domain**: `zhuliyi10.github.io`（不带 http/https）
3. 创建后获得 Tracking Script

### 6.2 集成方式

将 Umami 的 `<script>` 标签添加到 `docs/overrides/main.html` 的 `extrahead` 块中，所有页面自动加载统计脚本。

### 6.3 查看数据

登录 https://cloud.umami.is 即可看到：
- 实时访客数
- 每页浏览量（Pageviews）
- 访客来源地区、设备类型
- 独立访客数（Unique visitors）

---

## 七、日常写作流程

### 7.1 新增一篇文档

1. 在 `docs/` 对应目录下创建 `.md` 文件
2. 在 `mkdocs.yml` 的 `nav` 中添加导航条目
3. 本地 `mkdocs serve` 预览
4. `git push` 自动部署

### 7.2 修改现有文档

1. 直接编辑 `docs/` 下的 `.md` 文件
2. 本地预览确认无误
3. `git push` 自动部署

### 7.3 本地预览命令速查

```bash
# 启动实时预览服务
mkdocs serve

# 指定端口
mkdocs serve -a 127.0.0.1:8080

# 构建静态站点
mkdocs build

# 严格模式构建（有 warning 则报错）
mkdocs build --strict
```

---

## 八、常见问题

### Q: 部署后页面 404？

确认已在仓库 Settings → Pages 中将 Source 设为 **GitHub Actions**，而非 "Deploy from a branch"。

### Q: 评论区不显示？

检查以下条件：
- 仓库 Discussions 功能已启用
- Giscus App 已安装到仓库
- `comments.html` 中的 `data-repo-id` 和 `data-category-id` 正确

### Q: Umami 没有数据？

- 确认 Tracking Script 已正确添加
- 部署到线上后才会开始统计（本地 localhost 不计入）
- 检查浏览器控制台是否有脚本加载错误

### Q: 如何自定义主题颜色？

编辑 `mkdocs.yml` 中的 `theme.palette`，可选颜色：`red`, `pink`, `purple`, `deep purple`, `indigo`, `blue`, `light blue`, `cyan`, `teal`, `green`, `light green`, `lime`, `yellow`, `amber`, `orange`, `deep orange`, `brown`, `grey`, `blue grey`, `black`。

---

## 九、参考链接

- [MkDocs 官方文档](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
- [Giscus 官网](https://giscus.app/)
- [Umami 官网](https://umami.is/)
