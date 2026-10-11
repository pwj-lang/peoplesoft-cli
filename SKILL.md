---
name: ps-cli
description: "用 CLI 查询、创建和修改 PeopleSoft 定义；用于 PeopleCode、Application Designer 开发与排障"
license: "原创内容采用 MIT；适用范围见 LICENSE 和 NOTICE.md"
metadata:
  version: 1.5.0
  tags: [ps, peoplesoft, peoplecode, app-designer]
---

# PeopleSoft CLI

通过 Integration Broker REST API 维护 Record、Field、Page、Component、Project、应用包、SQL、AE，以及服务、服务操作、菜单、消息目录和门户。

**开发前必读 [开发规范](references/development-standards.md)**，再按对象读取接口文档。当前限制见 [已知问题](references/known-code-issues.md)。

## 1. 确认环境

以下命令在本 skill 目录执行；从其他目录调用时使用脚本绝对路径。

```powershell
python scripts/peoplesoft_api.py env list
python scripts/peoplesoft_api.py env current
python scripts/peoplesoft_api.py env use <环境名>
python scripts/peoplesoft_api.py preflight --refresh
```

使用用户已指定的环境；显示环境名和用户名，隐藏密码及 Token。配置默认位于 `%USERPROFILE%\.peoplesoft\config.json`，可通过 `PEOPLESOFT_CONFIG` 覆盖。IB 节点默认 `PSFT_HR`，可用环境配置的 `node` 或 `PEOPLESOFT_NODE` 覆盖。

根据 preflight 的报错和 NEXT 处理：路由缺失查部署，401/403 或明确未授权查权限，180/74“找不到类”查 Handler 与包依赖，连接或认证失败查环境。流程见 [安装、认证与授权](references/01-auth-api.md)。完成安装后运行 `healthcheck --refresh`；PSTOKEN_GET 与全部 15 个元数据操作均通过才报告环境就绪。查询探测默认 `JOB.EMPLID`，替换字段时使用索引字段，避免全表扫描。

## 2. 确认工作 Project

```powershell
python scripts/peoplesoft_api.py project current
python scripts/peoplesoft_api.py project struct <项目名>
python scripts/peoplesoft_api.py project use <项目名>
```

沿用用户已确认的 Project；没有明确归属时再确认。`active_project` 按环境保存，只是上次选择。只读不登记；写入后核对完整条目，缺失才插入。Action、Upgrade、Done 的作用和命令见 [Project 管理](references/11-oper-project-defn-api.md)。

## 3. 执行并验证

先读现状，再提交所需修改，最后独立回读。PeopleCode、SQL 和复杂补丁优先存为 UTF-8 文件，再通过 `--file` 等参数提交；编码由 CLI 处理。结果不明时先查当前状态，不盲目重试写请求。modify-code 拒绝空白正文；真正删除程序使用 delete-code，核对原生 programExists 和 Project Delete 标记，见 [删除流程](references/development-standards.md#peoplecode-真正删除)。

```powershell
python scripts/peoplesoft_api.py search field EMPLID
python scripts/peoplesoft_api.py record struct MY_RECORD
python scripts/peoplesoft_api.py component struct JOB_DATA --deep
python scripts/peoplesoft_api.py page struct MY_PAGE --full --json
python scripts/peoplesoft_api.py project update-item MY_PROJECT --object-type 0 --value1 MY_RECORD --action Copy --upgrade on --done off
```

`view-code` / `view-sql` 自动缓存 UTF-8 工作副本，并输出路径；缓存不能代替服务器回读。参数详情使用 `<命令> --help`。

## 按需参考

| 任务 | 文档 |
|---|---|
| 安装、认证、授权、原生导入导出 | [01-auth-api.md](references/01-auth-api.md) |
| 搜索定义 | [02-search-defn-api.md](references/02-search-defn-api.md) |
| 应用包与类代码 | [03-app-pkg-api.md](references/03-app-pkg-api.md) |
| SQL 定义 | [04-sql-defn-api.md](references/04-sql-defn-api.md) |
| AE | [05-app-engine-api.md](references/05-app-engine-api.md) |
| Record、Field、Build | [06-record-defn-api.md](references/06-record-defn-api.md) |
| Page、Component 与页面结构 | [07-page-defn-api.md](references/07-page-defn-api.md) |
| 业务数据查询 | [09-query-record-api.md](references/09-query-record-api.md) |
| Project、迁移标记与完整键 | [11-oper-project-defn-api.md](references/11-oper-project-defn-api.md) |
| REST 服务、操作、版本、Handler、Routing、授权 | [12-service-defn-api.md](references/12-service-defn-api.md) |
| 菜单与 ItemSelected | [14-menu-defn-api.md](references/14-menu-defn-api.md) |
| 消息目录 | [15-message-catalog-api.md](references/15-message-catalog-api.md) |
| 门户文件夹、CREF、Link、属性与权限 | [16-portal-registry-api.md](references/16-portal-registry-api.md) |

维护工具本身时再读 [发布规划](references/release-roadmap.md)。本包版本为 1.5.0，基于 rc.2 完成第二轮独立复验；后续目标为 2.0.0。旧 2.x 为未公开的历史内部编号。日常编辑不升版，形成新验收包时才递增 dev/rc 后缀。
