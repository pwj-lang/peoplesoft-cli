# PeopleSoft CLI & MetaData API

[中文](#中文) · [English](#english) · [2.0.1 Release](https://github.com/pwj-lang/peoplesoft-cli/releases/tag/v.2.0.1)

## 让 Agent 安装 / Install with an agent

把下面这一句交给 Agent 即可，无需另存长提示词：

> 请安装并部署到我的 PeopleSoft 环境：https://github.com/pwj-lang/peoplesoft-cli

Agent 从 [INSTALL.md](INSTALL.md) 读取本地 Skill 安装、原生工程导入、编译、IB 配置、授权和验收流程，先发现已有配置，只询问缺失项。若只需本地 Skill，在请求中说明“只安装本地”。首次部署仍需要可用的目标环境、AD 客户端和相应账号权限。

Give your agent this repository URL and ask it to install and deploy. The agent should follow [INSTALL.md](INSTALL.md), discover existing settings, and ask only for missing information. Say “local skill only” if server deployment is not needed.

## 中文

面向 Agent 和开发者的 PeopleSoft 元数据开发工具，通过命令行查询和维护定义、PeopleCode、工程及 Integration Broker 服务。当前正式版为 **2.0.1**，已知问题将在后续小版本中持续修复。

### 两个主要交付物

- **ps-cli Skill / CLI**：Agent 开发指引、命令行工具、接口参考和请求示例，开发者也可以直接运行。
- **MetaData API**：部署在 PeopleSoft 内的服务端 API，通过 Integration Broker 提供元数据能力。随包的 `C_META_DATA_PKG/` 是完整 Application Designer 原生 XML / INI 工程，包含 PeopleCode 源码、编译内容和运行依赖。

**使用 CLI 前需将 MetaData API 部署到目标 PeopleSoft，并配置 Integration Broker、认证和权限。** Agent 可按 [完整安装流程](INSTALL.md) 执行这两部分；只复制 Skill 文件不会部署服务端。API 也可以独立于 Skill，由其他客户端调用。

调用关系：`Agent / 开发者 → Skill / CLI 或自有客户端 → MetaData API → PeopleSoft 定义`。

### PeopleTools 版本

| 版本 | 说明 |
|---|---|
| **8.60** | 主要开发版本；实际开发和验证环境为 Oracle / **PeopleTools 8.60.10** |
| **8.57 及更新版本** | 大部分功能预期可用；未逐版验证，需在目标环境编译、配置并核验所需功能 |
| **早于 8.57** | **未测试**，不保证兼容性 |

这里的版本号指 **PeopleTools**。8.60 的验证结果不等于对所有补丁、数据库和平台组合的认证。

### 命令行可以操作哪些定义

| 定义 / 命令 | 主要能力 |
|---|---|
| Application Package / `app-pkg` | 根包增删、子包、类结构及类 PeopleCode 查询和维护 |
| Field / `field` | 全局字段属性、Label、XLAT 全生效日期基准维护和已开放的明确删除 |
| Record / `record` | 结构、字段/子记录、索引、事件 PeopleCode、视图 SQL 和 Build |
| SQL / `sql` | SQL 定义、属性及正文维护 |
| Application Engine / `ae` | Section、Step、Action、PeopleCode 和 SQL 维护 |
| Page / `page` | 整页结构导出/回放（含 Grid / Scroll）、Activate PeopleCode；增量 Edit / DDL 控件属性 |
| Component / `component` | 组件创建、页面增删/关联、层级 PeopleCode、Internet / Toolbar / Pagebar 属性 |
| Menu / `menu` | 菜单栏、菜单项及 ItemSelected PeopleCode |
| Component Interface / `ci` | CI 属性、集合、映射及自定义 Methods PeopleCode |
| SVG Image / `image` | 单一 SVG 原生定义克隆、二进制指纹和双版本保护 |
| HTML / `html`；StyleSheet / `stylesheet` | HTML 和自由格式样式表的属性、正文维护 |
| Project / `project` | 工程属性、完整成员键、Copy / Delete 与比较/迁移标记 |
| Service / `service`；Service Operation / `service-op` | 服务、操作/版本、Handler、Routing、授权、REST / 同步 SOAP Provider、WSDL / XSD |
| Message Catalog / `message-catalog` | 消息集、消息正文/说明及独立语言翻译；复用系统 `MESSAGE_CATALOG1` / `MESSAGE_CATALOG_CI` |
| Portal Registry / `portal` | 门户 Folder、CREF、Link、关联及权限 |

还支持 `search` 定义搜索、`query-record` 业务数据查询，以及 `sql` 查询和单独授权的 SQL DML。各定义开放的创建、修改、删除单位不同，不表示每一种定义都能整份删除；参数和限制见 [SKILL.md](SKILL.md) 及对应对象参考。

整页回放与增量控件维护是不同路径：Grid / Scroll 通过 `page structure/apply` 重建；`page add-control` 的 Grid / Scroll 原型仍停用。详见 [Page 工作流](references/07-page-defn-api.md#201整页结构导出与回放)。本轮隔离业务验收证明所列工作流，不等于任意模块、业务算法或空白环境均已认证。

### 开始使用

1. 从 [Releases](https://github.com/pwj-lang/peoplesoft-cli/releases) 下载版本包，将 `ps-cli/` 安装到所用 Agent 的 skills 目录；开发者也可直接运行 CLI。
2. 按 [安装、认证与授权](references/01-auth-api.md) 将完整 `C_META_DATA_PKG` 工程部署到 PeopleSoft，配置节点、网关、Service Operations、Handler / Routing 及账号权限。定义读写分别由 `C_META_DATA_READ` / `C_META_DATA_WRITE` 提供，SQL DML 另行授权。
3. 配置并选中 CLI 目标环境，对本版部署选择 `split` 布局，运行预检和健康检查。CLI、文档与服务端工程使用同一版本。

在 `ps-cli/` 目录中运行：

```powershell
python scripts/peoplesoft_api.py --help
python scripts/peoplesoft_api.py env list
# 配置并选中目标环境后：
python scripts/peoplesoft_api.py env layout split
python scripts/peoplesoft_api.py preflight --refresh
python scripts/peoplesoft_api.py healthcheck --refresh
python scripts/peoplesoft_api.py search field EMPLID
python scripts/peoplesoft_api.py record struct JOB
```

公开工程中的环境专属 REST BaseURL 已替换为 `https://ps.example.invalid`，**部署时必须改为目标系统的实际地址**。认证及 20 项读取健康检查通过表示基本读取安装就绪；写权限和 SQL DML 需分别验证。写入使用读取时的原始 `expectedVersion`，冲突会拒绝覆盖。

### 目录与文档

| 位置 | 内容 |
|---|---|
| [SKILL.md](SKILL.md) | Agent 工作流程及对象参考入口 |
| `scripts/` | CLI、环境/认证管理和读写路由 |
| `C_META_DATA_PKG/` | 服务端 API 的完整 AD 原生工程及必要运行依赖 |
| `references/` | [安装说明](references/01-auth-api.md)、[架构](references/architecture.md)、[开发规范](references/development-standards.md)和对象接口 |
| `assets/examples/` | JSON 请求示例 |
| [已知问题](references/known-code-issues.md) / [发布规划](references/release-roadmap.md) / [变更记录](CHANGELOG.md) | 当前边界、后续安排及历史变更 |

核心工程仅交付 MetaData API 及实际运行依赖，不包含电子表格、演示/探针和测试定义。SOAP `Validation=Y` 的间歇性错误、跨环境及空白环境安装等未完成验证继续公开记录，后续通过小版本修复和补充验证。

## English

A PeopleSoft metadata development toolkit for agents and developers. Use the command line to inspect and maintain definitions, PeopleCode, projects, and Integration Broker services. **2.0.1 is the current stable release**; remaining issues will be addressed in subsequent minor and patch releases.

### Two main deliverables

- **ps-cli Skill / CLI**: agent instructions, command-line tools, API references, and request examples. Developers can also run the CLI directly.
- **MetaData API**: server-side APIs running inside PeopleSoft and exposed through Integration Broker. The included `C_META_DATA_PKG/` Application Designer XML / INI project contains PeopleCode source, compiled content, and runtime dependencies.

**Deploy the MetaData API and configure Integration Broker, authentication, and permissions before using the CLI.** An agent can follow the [complete installation workflow](INSTALL.md) for both parts; copying Skill files alone does not deploy the server. Other clients can use the APIs independently of the Skill.

Request path: `Agent / developer → Skill / CLI or custom client → MetaData API → PeopleSoft definitions`.

### PeopleTools compatibility

| Version | Status |
|---|---|
| **8.60** | Primary development version; developed and validated on Oracle / **PeopleTools 8.60.10** |
| **8.57 and later** | Most features are expected to work; individual releases have not all been tested. Compile, configure, and verify the required features on your target system |
| **Earlier than 8.57** | **Not tested**; compatibility is not guaranteed |

These version numbers refer to **PeopleTools**. Validation on 8.60 does not certify every patch, database, or platform combination.

### Definitions available from the command line

| Definition / command | Main capabilities |
|---|---|
| Application Package / `app-pkg` | Root package create/delete, subpackages, classes, and class PeopleCode |
| Field / `field` | Global field properties, labels, effective-dated base XLAT maintenance, and supported explicit deletion |
| Record / `record` | Structure, fields/subrecords, indexes, event PeopleCode, view SQL, and Build |
| SQL / `sql` | SQL definitions, properties, and statement text |
| Application Engine / `ae` | Sections, steps, actions, PeopleCode, and SQL |
| Page / `page` | Full-page export/replay including Grid / Scroll, Activate PeopleCode, and incremental Edit / DDL properties |
| Component / `component` | Component creation, page add/remove/associations, PeopleCode, and Internet / Toolbar / Pagebar settings |
| Menu / `menu` | Menu bars, items, and ItemSelected PeopleCode |
| Component Interface / `ci` | CI properties, collections, mappings, and custom Methods PeopleCode |
| SVG Image / `image` | Native single-SVG cloning, binary fingerprints, and source/target version guards |
| HTML / `html`; StyleSheet / `stylesheet` | Properties and content of HTML definitions and free-form stylesheets |
| Project / `project` | Properties, complete item keys, Copy / Delete, and comparison/migration flags |
| Service / `service`; Service Operation / `service-op` | Services, operation versions, handlers, routings, permissions, REST / synchronous SOAP providers, and WSDL / XSD |
| Message Catalog / `message-catalog` | Message sets, text/explanations, and individual translations using delivered `MESSAGE_CATALOG1` / `MESSAGE_CATALOG_CI` |
| Portal Registry / `portal` | Folders, CREFs, links, associations, and permissions |

Additional commands include definition search (`search`), business data queries (`query-record`), SQL queries, and separately authorized SQL DML (`sql`). Available create, update, and delete operations vary by definition; full-definition deletion is not available for every type. See [SKILL.md](SKILL.md) and the linked object references for parameters and limits.

Full-page replay and incremental control maintenance are separate paths. Use `page structure/apply` for Grid / Scroll; incremental Grid / Scroll prototypes remain disabled. See the [Page workflow](references/07-page-defn-api.md#201整页结构导出与回放). The isolated validation covers recorded workflows, not every module, business formula, or clean installation.

### Getting started

1. Download a versioned package from [Releases](https://github.com/pwj-lang/peoplesoft-cli/releases). Install `ps-cli/` in your agent's skills directory, or run the CLI directly.
2. Follow the [installation and authorization guide](references/01-auth-api.md) to deploy the complete `C_META_DATA_PKG` project. Configure the node, gateway, service operations, handlers/routings, and account permissions. Definition reads and writes use `C_META_DATA_READ` / `C_META_DATA_WRITE`; SQL DML requires separate authorization.
3. Configure and select the CLI target environment, choose the `split` layout for this deployment, and run preflight and health checks. Keep the CLI, documentation, and server project on the same version.

Run from the `ps-cli/` directory:

```powershell
python scripts/peoplesoft_api.py --help
python scripts/peoplesoft_api.py env list
# After configuring and selecting the target environment:
python scripts/peoplesoft_api.py env layout split
python scripts/peoplesoft_api.py preflight --refresh
python scripts/peoplesoft_api.py healthcheck --refresh
python scripts/peoplesoft_api.py search field EMPLID
python scripts/peoplesoft_api.py record struct JOB
```

Environment-specific REST BaseURLs in the public project use `https://ps.example.invalid`; **replace them with your target system's actual addresses during deployment**. Authentication and the 20 read health checks establish basic read readiness. Verify write permissions and SQL DML separately. Definition writes use the original `expectedVersion` returned by a read and reject conflicting changes.

### Files and documentation

| Location | Contents |
|---|---|
| [SKILL.md](SKILL.md) | Agent workflow and links to object references |
| `scripts/` | CLI, environment/authentication management, and read/write routing |
| `C_META_DATA_PKG/` | Complete native AD project for the server APIs and required runtime dependencies |
| `references/` | [Installation](references/01-auth-api.md), [architecture](references/architecture.md), [development rules](references/development-standards.md), and object APIs |
| `assets/examples/` | JSON request examples |
| [Known issues](references/known-code-issues.md) / [roadmap](references/release-roadmap.md) / [changelog](CHANGELOG.md) | Current limitations, planned work, and release history |

The core project contains the MetaData APIs and their actual runtime dependencies. Spreadsheet tools, demos, probes, and test definitions are excluded. Intermittent SOAP errors with `Validation=Y`, cross-environment migration, and clean-install validation remain documented for follow-up fixes and verification.

## License / 许可

Original content is licensed under [MIT](LICENSE). See [NOTICE.md](NOTICE.md) for Oracle-generated content and third-party rights, and [SECURITY.md](SECURITY.md) for deployment guidance. This project is not affiliated with, sponsored by, or certified by Oracle.

原创内容采用 [MIT](LICENSE)；Oracle 生成内容及第三方权利见 [NOTICE.md](NOTICE.md)，部署要求见 [SECURITY.md](SECURITY.md)。本项目与 Oracle 无隶属、赞助或认证关系。
