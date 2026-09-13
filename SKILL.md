---
name: ps-cli
description: "本 Skill 致力于让Agent可以通过Cli的方式对Peoplesoft系统进行开发和访问"
license: "MIT for original project materials; see LICENSE and NOTICE.md"
metadata:
  version: 1.0.0
  tags: [ps, peoplesoft, peoplecode, app-designer]
---

# 简介

本 Skill 致力于让Agent可以通过Cli的方式对Peoplesoft(后面简称ps)系统进行开发和访问，目前skill支持使用以下定义
- Record、Field、Page、Component、Project；
- Application Package、SQL、Application Engine；

## 使用步骤

### 1.确认环境

Skill支持开发者配置一个或多个环境，所以开发前先确认环境信息
1. 执行 `python scripts/peoplesoft_api.py env list` 和 `python scripts/peoplesoft_api.py env current`可获取环境列表和当前激活环境；
2. 确认环境名称、登录用户名和节点名即可，其余信息不要展示；
3. 如果没有配置环境，先明确告知用户对话中传递密码有泄露环境信息给模型服务商的风险。推荐用户自行写好 config.json（格式见「配置与认证」）；如果用户选择在会话中提供，则用 `python scripts/peoplesoft_api.py env init <name> --url <url> --username <user> --password-stdin` 从标准输入传入密码（不要写成命令行参数，会泄漏到进程列表和 shell 历史）。裸调 `env init` 在非交互环境无法填写，会直接报错并提示这条命令。
4. 若用户需要切换环境，用 `env use <name>` 切换，切换后重新检查环境信息。

**节点名要确认**：`env current` 输出里的 `node=` 是目标 PeopleSoft 的 IB 本地节点名。`PSFT_HR` 只是出厂默认，客户实施时大多会改名。不确定就问用户，或让对方在 `PeopleTools > 集成代理 > 集成设置 > 节点` 里取标记为 Local Node 的那条名称。配错会在第2步报 (158,505)，而那个报错**很容易被误判成接口没装**。

### 2.环境体检

确认环境后跑体检。它一次报告「从零到能用」还差什么，并给出下一步该做什么：
~~~powershell
python scripts\peoplesoft_api.py preflight --refresh
~~~

~~~text
Preflight: environment=hr-dev  node=PSFT_HR  user=xxx
  pia:    https://hr-dev.example.com
  config: C:\Users\xxx\.peoplesoft\config.json
  [1] 认证            OK
  [2] 接口可用性      FAIL    0/10 个 Service Operation 通过
  [3] 工作 Project    未设置

  FAIL 详情：
    AI_SEARCH_DEFN_POST — 授权不足 —— 参考 references/rest-authorization.md，...
NEXT: 接口已部署但授权不足。读 references/rest-authorization.md 完成授权，然后重跑本命令确认全部通过。
~~~

**照 `NEXT` 那一行走**，它只给一条最重要的下一步，不要自己另选路径。三种常见情况的判别：

| `[1]`/`[2]` 的报错 | 含义 | 去向 |
|---|---|---|
| 含 `节点名可能不正确` 或 `158,505` | 节点名配错，**不是**接口没装 | 修正 node 后重跑本命令 |
| 含 `接口未部署`（`Unable to find a Routing corresponding…`） | 节点名对，但元数据 Api 没导入 | `references/ad-cli-project-import.md` |
| 含 `授权不足` 或 `158,536` | 接口已装，账号没权限 | `references/rest-authorization.md` |
| 连不上 PIA / 用户名密码错误 | 环境配置问题 | 回第1步检查配置 |

三项全部 OK 才可报告环境就绪。授权完成后用 `healthcheck --refresh` 做最终验收（最后一行应为 `Health check passed: PSTOKEN_GET plus all 10 ps-metadata operations.`）。

> 体检与 `healthcheck` 都会读取一条真实业务数据（默认 `--query-record JOB --query-field EMPLID`，只取一行）。若当前环境敏感，用 `healthcheck` 的这两个参数换成合适的 Record/Field。

### 3.环境错误的处理办法

1.报错含 `节点名可能不正确` 或 `158,505`
用 `env init <name> ... --force --node <正确节点名>` 修正（或临时设环境变量 `PEOPLESOFT_NODE`），然后重跑 `preflight`。
**不要**在这一步去导入 AD 工程 —— 节点名错误时导入不会有任何改变。

2.报错含 `Unable to find a Routing corresponding`
参考文档：[references/ad-cli-project-import.md](references/ad-cli-project-import.md)。

3.报错含 `未经授权无法调用服务操作` 或 `158,536`
参考文档：[references/rest-authorization.md](references/rest-authorization.md)。

4.其它错误，按报错原文排查环境配置，回到第1步


### 4.确认工程

Project是开发需要交付的最终交付物，就跟Agent的工作区一样，所有定义的创建、修改都应在Project中完成
- Project由环境决定，每个环境有多个Project
- 先执行 `python scripts/peoplesoft_api.py project current` 查看当前环境上次使用的Project
- 没有记录、或用户要更换Project时，跟用户确认Project名称和描述后用 `project use <name>` 设为当前Project
- 更换Project时应检查Project是否在当前环境存在（`project struct <name>` 查不到会报错）
- 创建或修改定义时必须将相关定义插入Project，读取定义不插入Project；`project create/insert-item/modify` 成功后会**自动把它记为当前Project**


## 配置与认证

### 配置文件

默认配置位置：

- Windows：`%USERPROFILE%\.peoplesoft\config.json`
- 其他系统：`~/.peoplesoft/config.json`

也可以用以下环境变量指定位置：

- `PEOPLESOFT_DATA_DIR`：数据目录，默认 `%USERPROFILE%\.peoplesoft`，下面几项的默认值都基于它；
- `PEOPLESOFT_CONFIG`：配置文件路径；
- `PEOPLESOFT_CACHE_DIR`：PS_TOKEN 缓存目录，默认 `%USERPROFILE%\.peoplesoft\cache\`；
- `PEOPLESOFT_PROJECTS`：Project 状态文件路径，默认 `%USERPROFILE%\.peoplesoft\projects.json`；
- `PEOPLESOFT_NODE`：临时覆盖 IB 本地节点名（优先级高于 config.json 的 `node`）。

配置保存 PeopleSoft PIA 地址、账号信息和本地节点名：

```json
{
  "active_environment": "hr-dev",
  "environments": {
    "hr-dev": {
      "pia_base_url": "https://hr-dev.example.com",
      "username": "your_user",
      "password": "your_password",
      "node": "PSFT_HR"
    }
  }
}
```

`node` 是目标 PeopleSoft 的 IB 本地节点名（IB REST 网关 URL 里 `RESTListeningConnector/` 后面那一段）。缺省为出厂值 `PSFT_HR`；客户实施时大多改过名，必须按目标环境实际值填写，否则所有请求都会报 (158,505)。

Project 状态单独存放，按环境分节记录「上次使用的Project」，由 `project use` 和写操作自动维护：

```json
{
  "hr-dev": { "active_project": "MY_PROJECT" }
}
```

不要在回复中输出 PS_TOKEN 或密码。


### 环境和认证

```bash
python scripts/peoplesoft_api.py env list
python scripts/peoplesoft_api.py env current
python scripts/peoplesoft_api.py env use hr-dev
python scripts/peoplesoft_api.py env init hr-dev --url https://hr-dev.example.com --username your_user --password-stdin --node PSFT_HR
python scripts/peoplesoft_api.py auth
python scripts/peoplesoft_api.py preflight --refresh
python scripts/peoplesoft_api.py healthcheck --refresh
```

CLI 通过 `PSTOKEN.v1` 获取 PS_TOKEN，并在缓存有效时复用。认证失败时，先检查当前环境、PIA 地址、用户名和密码，再刷新 token；不要通过数据库连接绕过认证。

已有配置时，`env init <name>` 会新增环境，默认将新环境设为 active；需要保留原 active 环境时使用 `--keep-current`。

## 核心工作规则

### 1. 先读取，再修改，再验证

执行写操作时：

1. 先搜索并确认目标定义；
2. 读取当前结构、代码或属性；
3. 只提交明确需要的修改；
4. 重新读取结果验证修改已生效。

`modifyPeopleCode` 返回成功不代表服务器端代码一定已经更新，上传后必须再次使用 `viewPeopleCode` 验证。

### 2. 元数据修改必须纳入 Project

通过 API 创建或修改 Record、SQL Definition、Application Package/Class、Application Engine、Component、Page 等定义后，立即使用 `project insert-item` 将定义加入已经确认的当前工作 Project。没有通用默认 Project；写入前必须获得用户对该环境的 Project 选择。

CLI 的 `insert-item` 默认使用 `takeAction=1`，表示迁移时勾选 Upgrade。只有用户明确要求某定义不参与迁移时，才传 `--take-action 0`。

Project 的 object type、参数和限制见：[references/11-oper-project-defn-api.md](references/11-oper-project-defn-api.md)。

### 3. 创建 Record 时禁止猜字段 ID

用户没有明确给出字段 ID 时：

1. 先用 `search field` 查找候选字段；
2. 向用户展示候选字段名、类型和长度；
3. 用户确认字段映射后，才执行 Record 创建。

Record 引用的字段必须已经存在于 PeopleSoft 字段定义中，创建 Record 不会自动创建字段定义。

### 4. Code Review 使用 API 取得事实

审查 PeopleCode 时，如果需要确认 Record、Field 或 Component 结构，使用 `search`、`record struct` 或相应 API 查询，不要猜测，也不要反问用户充当系统字典。

### 5. 文本编码遵循接口文档

PeopleCode、SQL text、comment 等长文本的编码规则因接口和操作不同而可能不同。使用 CLI 时由脚本处理；直接构造 REST 请求时，必须读取对应的 `references/*-api.md`，不要自行假设使用 Base64、明文或统一的转义方式。

## 常用命令

```bash
# 搜索定义
python scripts/peoplesoft_api.py search record ABSV
python scripts/peoplesoft_api.py search field EMPLID
python scripts/peoplesoft_api.py search sql MY_SQL
python scripts/peoplesoft_api.py search apppkg C_META_DATA
python scripts/peoplesoft_api.py search project MY_PROJECT

# 查看和修改 PeopleCode/定义
python scripts/peoplesoft_api.py app-pkg view-code C_META_DATA_PKG "C_META_DATA_PKG:MetaData:OperAppPackage"
python scripts/peoplesoft_api.py record struct ABSV_ACCRUAL
python scripts/peoplesoft_api.py record view-code C_TEST_REC --fieldname EMPLID --event FieldChange
python scripts/peoplesoft_api.py sql view MY_SQL_001
python scripts/peoplesoft_api.py ae struct HPS_AE_SAL_CAL
python scripts/peoplesoft_api.py component struct JOB_DATA
python scripts/peoplesoft_api.py page struct C_AI_PJT_P1 --full --json

# 业务数据查询：唯一允许的查询路径
python scripts/peoplesoft_api.py query-record PS_JOB EMPLID,EMPL_RCD --filter '[{"field":"EMPLID","op":"=","value":"00001"}]' --max-rows 5

# Project 纳管
python scripts/peoplesoft_api.py project current
python scripts/peoplesoft_api.py project use MY_PROJECT
python scripts/peoplesoft_api.py project insert-item MY_PROJECT --object-type 0 --value1 ABSV_ACCRUAL
python scripts/peoplesoft_api.py project struct MY_PROJECT
```

完整命令参数通过 `python scripts/peoplesoft_api.py <command> --help` 或对应接口参考文档获取。

## 接口参考

按任务读取对应文档，不要默认加载全部参考资料：

| 任务 | 参考文档 |
|---|---|
| 登录和 token | [01-auth-api.md](references/01-auth-api.md) |
| PIA 接口授权 | [rest-authorization.md](references/rest-authorization.md) |
| 搜索 Record、Field、SQL、App Package、Project | [02-search-defn-api.md](references/02-search-defn-api.md) |
| Application Package 和 PeopleCode | [03-app-pkg-api.md](references/03-app-pkg-api.md) |
| SQL Definition | [04-sql-defn-api.md](references/04-sql-defn-api.md) |
| Application Engine | [05-app-engine-api.md](references/05-app-engine-api.md) |
| Record 创建、修改和 PeopleCode | [06-record-defn-api.md](references/06-record-defn-api.md) |
| Page 定义查询、创建和控件操作 | [07-page-defn-api.md](references/07-page-defn-api.md) |
| Component 查询 | [08-component-defn-api.md](references/08-component-defn-api.md) |
| 业务数据查询 | [09-query-record-api.md](references/09-query-record-api.md) |
| Field 批量查询 | [10-field-defn-api.md](references/10-field-defn-api.md) |
| Project 管理 | [11-oper-project-defn-api.md](references/11-oper-project-defn-api.md) |
| PeopleCode 常见陷阱 | [peoplecode-pitfalls.md](references/peoplecode-pitfalls.md) |
| Record 创建注意事项 | [record-create-pitfalls.md](references/record-create-pitfalls.md) |
| Page 结构参考 | [page-tables.md](references/page-tables.md) |
| Build Record 类型映射 | [build-record-type-mapping.md](references/build-record-type-mapping.md) |
| 已知接口问题 | [known-code-issues.md](references/known-code-issues.md) |

`AI_OPER_FIELD_DEFN` 是否可用，以当前服务器是否发布对应 Service Operation 为准。
