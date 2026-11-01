---
name: ps-cli
description: "用 CLI 查询、创建和修改 PeopleSoft 定义；用于 PeopleCode、Application Designer 开发与排障"
license: "原创内容采用 MIT；适用范围见 LICENSE 和 NOTICE.md"
metadata:
  version: 2.0.3
  tags: [ps, peoplesoft, peoplecode, app-designer]
---

# PeopleSoft CLI

通过 Integration Broker REST API 查询和维护 PeopleSoft 定义、PeopleCode、工程及服务配置；支持业务数据/SQL 查询，SQL DML 单独授权。当前正式版为 **2.0.3**，遗留问题后续通过小版本修复。除 Skill / CLI 外，主要交付物是 MetaData API；Agent 或开发者须先自行把完整工程部署到目标 PeopleSoft 并配置认证、路由与权限，才能使用。API 也可由其他客户端独立调用。

用户要求安装本 Skill、导入新环境或部署服务端时，先按 [INSTALL.md](INSTALL.md) 执行：根目录 [install.example.json](install.example.json) 提供多环境模板，Agent 复制为本机 `install.local.json` 并给实际链接；用户只填需要的环境登录地址、用户名/密码，active_environment 可选择当前环境。完全空白的环境自动跳过，其余全部校验后一次合并，保留未列出的已有环境；任一已填写环境有误则全部不写入。重复安装保留填写内容与未变化的配置，安装助手 run 逐环境验收不切换用户当前环境；中断后核实状态继续。节点默认固定使用 `PSFT_HR`，不询问、不自动发现、不等待确认；已有自定义节点保留，高级覆盖仅按用户明确要求使用。Agent 发现 AD/目标版本、处理下载/依赖和部署，不要求用户查询版本、理解命令或逐项配置服务权限。填写副本不提交、不打包、不跨安装同步，不因讨论安装体验而创建示例环境。工具自身预置许可权/角色随安装交付；导入后仅提醒用户或管理员自行分配只读/读写角色，Agent 不自行授权、不根据填写文件选择角色，详见 [发现与填写](references/install-discovery.md)。首次部署从同一稳定版原生 AD 工程开始，不能依赖尚未安装的 API 自举；明确的本地安装请求仅安装本地。

实际开发或审查前读取 [开发规范](references/development-standards.md)，再按下表读取相关对象文档。部署、依赖和工具维护先读 [架构与交付边界](references/architecture.md)。

ps-cli 负责以 Application Designer 为主的开发定义，包含 Field XLAT、Record、Page、Component、PeopleCode 和 AE 程序。角色/许可权、用户授权、Process Definition、进程组及 Scheduler 的日常管理留给后续独立 ps-admin skill；工具自身的安装许可权及配套角色属于本工具交付范围，用户只分配对应角色。Project 迁移能力和 API 自身的授权校验继续保留。

## 确认环境和工作工程

以下命令在本 skill 目录执行；从其他目录调用时使用脚本绝对路径。

```powershell
python scripts/peoplesoft_api.py env list
python scripts/peoplesoft_api.py env current
python scripts/peoplesoft_api.py project current
python scripts/peoplesoft_api.py preflight --refresh
```

沿用用户指定的环境和已确认的 Project；`active_project` 只是上次选择，没有明确归属的写任务再确认。只读不登记工程。配置默认在 `%USERPROFILE%\.peoplesoft\config.json`，支持 `PEOPLESOFT_CONFIG`；节点默认 `PSFT_HR`，支持环境 `node` / `PEOPLESOFT_NODE`。显示环境名和用户名，隐藏密码和 Token。

- 路由缺失查部署；401/403 或明确未授权查权限；180/74“找不到类”查 Handler 和包依赖；连接/认证失败查环境。按 preflight 的 NEXT 处理。
- 安装完成后运行 `healthcheck --refresh`；认证及 20 个必需读取操作通过才报告基本安装就绪。它不证明写权限可用。查询探测默认 `JOB.EMPLID`，替换时选择索引字段。
- 已迁移环境使用 `env layout split`；未迁移环境保留 legacy。权限、部署或网络失败时不自动回退。SQL 写操作需先 Build 审计表和唯一索引、单独授权，再用 `--include-sql-write` 验证。详见 [安装与授权](references/01-auth-api.md)。

## 读取、修改和验证

1. 先读结构/正文，保存原始 `version` 快照；创建前也读取不存在名称。所有已开放的定义写入使用原始 `expectedVersion`，不能在保存前刷新基线掩盖冲突。
2. 正文和复杂补丁保存为 UTF-8 文件，通过 `--file` 等参数提交。`view-code` / `view-sql` 会下载工作副本和适用的 `.snapshot.json`；缓存不代替服务器当前状态。具体编码按对象文档，不能统一套 Base64。
3. 缺版本 428、冲突 409 时保留改稿及原快照，不自动换版本重试。结果不明先回读实际状态；保存、回读和工程登记分开报告，不能把部分成功当作整体回滚。
4. 成功后独立回读；写入按返回的完整键登记已确认的工程，已有成员也恢复 Unknown / Copy / Upgrade on / Done off。明确删除使用相应 Delete 键；自动登记范围见 [Project](references/11-oper-project-defn-api.md)。

`modify-code` 拒绝空白正文；删除程序使用 `delete-code`，删除类/包、Label、字段、AE 子对象或整份定义使用各自明确命令。先核对删除范围和快照，可用时先 `--dry-run`；真正删除须验证原生不存在及工程标记。Service / Service Operation 配置使用 `plan-configure`，整套操作删除及空 Service 删除使用 `plan-delete` 的完整原始计划。

```powershell
python scripts/peoplesoft_api.py search field EMPLID
python scripts/peoplesoft_api.py record struct MY_RECORD
python scripts/peoplesoft_api.py component struct JOB_DATA --deep
python scripts/peoplesoft_api.py project struct MY_PROJECT
```

参数以 `<命令> --help` 为准。对象限制和迁移语义必须读取对应参考，不把某类对象的删除或版本行为推广到其他对象。

维护工具部署工程 `C_META_DATA_PKG` 时只登记接口及实际运行依赖。电子表格、演示/探针、测试删除键和非运行兼容类留在各自工程；共用 JavaReflect 不意味着所有调用者都应进入核心工程。仅引用且未修改的系统标准 Field 不单独登记；Record 上的 Key/Required 等设置属于 Record，不是全局 Field 修改。消息翻译复用系统 `MESSAGE_CATALOG1` / `MESSAGE_CATALOG_CI`，不重新引入已退役的自建组件。

AD 导出 XML/INI 按原始字节交付，包括来源环境地址；不替换地址、TOOLSREL、源码、编译块或其他内容。定义变更先在 PeopleSoft 完成，再原生导出，复制与打包后核对原文件哈希。

## 按任务读取

| 任务 | 参考 |
|---|---|
| 安装 Skill、部署到新环境并验收 | [Agent 完整安装流程](INSTALL.md) |
| 认证、读写权限、原生导入导出参数 | [安装与授权](references/01-auth-api.md) |
| 维护工具、理解入口和公共依赖 | [架构与交付边界](references/architecture.md) |
| 搜索定义 | [搜索](references/02-search-defn-api.md) |
| 应用包、类与类代码 | [应用包](references/03-app-pkg-api.md) |
| SQL 定义与正文 | [SQL](references/04-sql-defn-api.md) |
| AE、Section、Step、Action | [AE](references/05-app-engine-api.md) |
| Field、Label、XLAT、Record、Build | [Record / Field](references/06-record-defn-api.md) |
| Page、控件、Component 创建/页面关联/属性及代码 | [Page / Component](references/07-page-defn-api.md) |
| 业务数据查询 | [Query Record](references/09-query-record-api.md) |
| SQL 查询、DML、审计和独立权限 | [SQL 执行](references/10-sql-exec-api.md) |
| Project、完整键和迁移标记 | [Project](references/11-oper-project-defn-api.md) |
| Service、Operation、Handler、Routing、WSDL | [服务](references/12-service-defn-api.md) |
| Menu、栏/项目与 ItemSelected | [Menu](references/14-menu-defn-api.md) |
| 消息目录、独立翻译 | [消息目录](references/15-message-catalog-api.md) |
| 门户 Folder、CREF、Link、权限 | [Portal](references/16-portal-registry-api.md) |
| CI / Methods、HTML、自由格式 StyleSheet | [CI / HTML / StyleSheet](references/17-ci-html-stylesheet-api.md) |
| 单一 SVG Image 定义 | [SVG Image](references/18-image-svg-api.md) |
| 未解决问题、未验收和延期范围 | [已知问题](references/known-code-issues.md) |
| 版本、分批交付与发行条件 | [发布规划](references/release-roadmap.md) |

主要开发版本为 PeopleTools 8.60，已在 Oracle / 8.60.10 验证；2.0.3 已在 Oracle / 8.55 验收部分读取、Service 长描述及版本保护，范围见 [PeopleTools 兼容记录](references/peopletools-compatibility.md)。其他功能、版本及补丁按目标编译、配置和所需功能逐项验证，不以 8.57 划硬门槛。“未验证”不等于“不支持”，也不保证大部分功能已经可用；以实际原生错误和验收结果报告可用范围。Page 属性按已有证据每批 10–20 项交付，Fluid 暂缓；SOAP Validation=Y 间歇性 119,40 未关闭；CI 引用和 CI 多语言子结构后置。正式发行不将这些问题或未验收项视为已解决。
