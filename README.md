# ps-cli

面向 PeopleSoft 元数据开发和受控 SQL 执行的中文 skill，包含 CLI、接口参考、JSON 示例及带编译内容的 AD 原生文件工程。

当前为 **2.0.0-rc.1 候选版**，最新稳定版为 **1.5.0**。本候选版已验证 Oracle / PeopleTools 8.60.10；SOAP Validation=Y 的间歇性错误及跨环境迁移仍有未完成验证，详见 [已知问题](references/known-code-issues.md)。

## 从哪里开始

| 目的 | 入口 |
|---|---|
| 使用 CLI 完成开发任务 | [SKILL.md](SKILL.md) |
| 安装、授权、迁移、健康检查 | [安装说明](references/01-auth-api.md) |
| 理解工程、包结构及公共依赖 | [架构与交付边界](references/architecture.md) |
| 修改或审查定义 | [开发规范](references/development-standards.md) |
| 查支持边界和遗留问题 | [已知问题](references/known-code-issues.md) |
| 查后续交付与版本安排 | [发布规划](references/release-roadmap.md) |
| 查历史变更 | [CHANGELOG.md](CHANGELOG.md) |

## 目录与交付

| 目录 | 用途 |
|---|---|
| `scripts/` | CLI、环境/认证管理、对象命令及读写路由 |
| `references/` | 对象接口、开发规范、部署、支持边界和规划 |
| `C_META_DATA_PKG/` | AD 原生 XML / INI，包含源码及编译内容；不手改编译块 |
| `assets/examples/` | JSON 请求示例 |

核心 AD 工程 `C_META_DATA_PKG` 仅包含元数据接口及运行依赖：元数据处理类、所需的 `C_JSON_API` 三后端及 `C_COMMONS_PKG`。电子表格、旧 JSON Core 转发、演示/探针和测试迁移条目均不在核心工程。`C_META_DATA_PKG` 同时是元数据应用根包名，两者范围不同。门户业务包 `C_PORTAL_PKG` 已解耦。消息翻译复用系统组件 `MESSAGE_CATALOG1` 和标准 `MESSAGE_CATALOG_CI`，原自建页面/组件/CI 已移出核心工程。包职责及迁移顺序见 [架构说明](references/architecture.md)。

panwx25 使用 `C_META_DATA_READ` / `C_META_DATA_WRITE` 两个 Service；CLI 按环境选择 split / legacy，SQL DML 仍单独授权。当前验证环境为 panwx25 / Oracle / PeopleTools 8.60.10，其他版本需另行编译和验收。

## 安装与维护

从对应的 [GitHub Release](https://github.com/pwj-lang/peoplesoft-cli/releases) 下载版本包，将 ps-cli 目录安装到所用 Agent 的 skills 目录。CLI、参考文档与服务端工程需采用同一版本，安装及旧版迁移详见安装说明。

公开包保留原生导出的定义、全部 PeopleCode 源码和编译内容，仅将 38 个操作的环境专属 REST BaseURL 主机替换为 `https://ps.example.invalid`。导入目标后按本环境配置节点及 BaseURL，再授权并运行健康检查；不要把占位地址直接用于真实服务。原始代码和编译块未修改，公开包与服务器原始导出具有不同的完整文件哈希。

本包只保留 CLI、工程、文档和示例，配置、凭据、测试夹具及运行报告不随包分发。服务端修改后重新原生编译导出；版本安排见发布规划。

## 许可与安全

原创内容采用 [MIT](LICENSE)；Oracle 生成内容和第三方权利范围见 [来源与许可说明](NOTICE.md)。本项目与 Oracle 无隶属、赞助或认证关系。部署及使用要求见 [安全说明](SECURITY.md)。
