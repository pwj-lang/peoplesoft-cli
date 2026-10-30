# 安装、认证与授权

当前结构和交付范围见 [架构与交付边界](architecture.md)。下文按轮次给出的工程数量属于历史验收基线；安装以随包原生 XML / INI 的实际清单为准。

MetaData API 是本项目的主要交付物之一。Agent 或开发者必须先把完整工程部署到目标 PeopleSoft，配置 Integration Broker、认证及权限，再使用 Skill / CLI 或其他 API 客户端；仅安装 Skill 不会自动部署服务端。主要开发版本为 PeopleTools 8.60（Oracle / 8.60.10 验证），8.57 及更新版本大部分功能预期可用，早于 8.57 未测试。

## 读写分离（2026-10-30）

panwx25 已把原 `C_META_DATA_SERVICE` 拆为两个 REST Service；原服务为空后通过原生管理器删除。工程仍为 `C_META_DATA_PKG`。

| Service | 入口应用子包 | 适用权限 |
|---|---|---|
| `C_META_DATA_READ` | `C_META_DATA_PKG:MetaData:Read` | 定义查询、结构、代码读取、列表、搜索及已有数据/SQL查询 |
| `C_META_DATA_WRITE` | `C_META_DATA_PKG:MetaData:Write` | 定义创建、修改、删除、Build、工程登记；SQL DML 单独授权 |

只读许可权列表只授予所需 Read 操作 Full；需要定义读写的列表同时授予所需 Read 和 Write 操作 Full。写操作的 Full 不隐含查询操作的 Full。两者均需保留认证操作 `PSTOKEN_GET` 的实际授权。查询与SQL查询类也统一放在 `MetaData:Read`，SQL写执行类放在 `MetaData:Write`；原 `RecordQuery`、`SqlExec` 子包已删除；`PSTOKEN_GET` 仍使用现有认证包。不要向只需定义查询的列表额外授予数据查询或任意 SQL 查询。

16 类原混合定义入口各新增一个 `AI_READ_*_POST` 操作；原 `AI_OPER_*_POST` 名称和 URI 保留为专用写入口。其他已有只读操作移动到 Read 服务；`AI_EXEC_SQL_WRITE_POST` 移动到 Write 服务，仍默认不授权，不能因需要定义写权限就执行该服务的“完全访问（全部）”。panwx25 的既有 `C_MCP` 定义权限保留，新增相应查询权限；其 SQL DML access=0 保持不变。

每个分离入口按精确 `operationType` 白名单分派：Read 拒绝写入及写入 dry-run，Write 拒绝定义查询，未知操作也拒绝。拒绝返回 JSON code=403，发生在共享引擎之前。入口还在每次调用按 PS_TOKEN 当前用户核对该操作的实际 Full 权限，撤权不依赖 IB 缓存刷新。`Utility:MetadataAccess` 为公共校验，`Utility:CoreOper*` 为共享内部实现，未作为 Handler 绑定；原来的根级混合 Handler 已删除。原 `expectedVersion`、428/409、事务和写后回读契约保留。

| 定义 | Read Service Operation | 读取 URI | Write Service Operation | 写入 URI |
|---|---|---|---|---|
| `APP_ENGINE` | `AI_READ_APP_ENGINE_POST` | `AI_READ_APP_ENGINE.v1/` | `AI_OPER_APP_ENGINE_POST` | `AI_OPER_APP_ENGINE.v1/` |
| `APP_PKG` | `AI_READ_APP_PKG_POST` | `AI_READ_APP_PKG.v1/` | `AI_OPER_APP_PKG_POST` | `AI_OPER_APP_PKG_POST.v1/` |
| `COMPONENT_DEFN` | `AI_READ_COMPONENT_DEFN_POST` | `AI_READ_COMPONENT_DEFN.v1/` | `AI_OPER_COMPONENT_DEFN_POST` | `AI_OPER_COMPONENT_DEFN.v1/` |
| `FIELD_DEFN` | `AI_READ_FIELD_DEFN_POST` | `AI_READ_FIELD_DEFN.v1/` | `AI_OPER_FIELD_DEFN_POST` | `AI_OPER_FIELD_DEFN.v1/` |
| `PAGE_DEFN` | `AI_READ_PAGE_DEFN_POST` | `AI_READ_PAGE_DEFN.v1/` | `AI_OPER_PAGE_DEFN_POST` | `AI_OPER_PAGE_DEFN.v1/` |
| `PROJECT_DEFN` | `AI_READ_PROJECT_DEFN_POST` | `AI_READ_PROJECT_DEFN.v1/` | `AI_OPER_PROJECT_DEFN_POST` | `AI_OPER_PROJECT_DEFN.v1/` |
| `RECORD_DEFN` | `AI_READ_RECORD_DEFN_POST` | `AI_READ_RECORD_DEFN.v1/` | `AI_OPER_RECORD_DEFN_POST` | `AI_OPER_RECORD_DEFN.v1/` |
| `SQL_DEFN` | `AI_READ_SQL_DEFN_POST` | `AI_READ_SQL_DEFN.v1/` | `AI_OPER_SQL_DEFN_POST` | `AI_OPER_SQL_DEFN.v1/` |
| `SERVICE_DEFN` | `AI_READ_SERVICE_DEFN_POST` | `AI_READ_SERVICE_DEFN.v1/` | `AI_OPER_SERVICE_DEFN_POST` | `AI_OPER_SERVICE_DEFN.v1/` |
| `SERVICE_OP` | `AI_READ_SERVICE_OP_POST` | `AI_READ_SERVICE_OP.v1/` | `AI_OPER_SERVICE_OP_POST` | `AI_OPER_SERVICE_OP.v1/` |
| `MENU_DEFN` | `AI_READ_MENU_DEFN_POST` | `AI_READ_MENU_DEFN.v1/` | `AI_OPER_MENU_DEFN_POST` | `AI_OPER_MENU_DEFN.v1/` |
| `MESSAGE_CATALOG` | `AI_READ_MESSAGE_CATALOG_POST` | `AI_READ_MESSAGE_CATALOG.v1/` | `AI_OPER_MESSAGE_CATALOG_POST` | `AI_OPER_MESSAGE_CATALOG.v1/` |
| `PORTAL_REGISTRY` | `AI_READ_PORTAL_REGISTRY_POST` | `AI_READ_PORTAL_REGISTRY.v1/` | `AI_OPER_PORTAL_REGISTRY_POST` | `AI_OPER_PORTAL_REGISTRY.v1/` |
| `HTML_DEFN` | `AI_READ_HTML_DEFN_POST` | `AI_READ_HTML_DEFN.v1/` | `AI_OPER_HTML_DEFN_POST` | `AI_OPER_HTML_DEFN.v1/` |
| `STYLESHEET_DEFN` | `AI_READ_STYLESHEET_DEFN_POST` | `AI_READ_STYLESHEET_DEFN.v1/` | `AI_OPER_STYLESHEET_DEFN_POST` | `AI_OPER_STYLESHEET_DEFN.v1/` |
| `CI_DEFN` | `AI_READ_CI_DEFN_POST` | `AI_READ_CI_DEFN.v1/` | `AI_OPER_CI_DEFN_POST` | `AI_OPER_CI_DEFN.v1/` |

所有 URI 均相对于 `/PSIGW/RESTListeningConnector/<节点>/`。两组仍使用 HTTP POST；不能用 HTTP 动词判定读写。各主题文档中的请求参数和正文编码继续适用，分离部署的直接读取请求须使用本表 Read URI。应用类完整路径为 `C_META_DATA_PKG:MetaData:Read:<原类名>` 与 `C_META_DATA_PKG:MetaData:Write:<原类名>`。

CLI 按环境选择布局，命令用法保持不变：

```powershell
python scripts/peoplesoft_api.py env use panwx25
python scripts/peoplesoft_api.py env layout split
python scripts/peoplesoft_api.py healthcheck --refresh
```

`env layout` 查看当前环境的 `metadata_api_layout`；`env layout legacy` 用于尚未迁移的旧环境。未配置的已有环境默认 legacy，只有 panwx25 已切换 split。split 不会在 Read 接口未部署、403 或网络错误时回退旧混合入口。基本 healthcheck 仅验证认证与20个读取操作，因此只读账号可以通过；它不声称写权限可用。

升级要同时导入完整新编译工程、迁移旧入口及设置目标许可权，然后切换 CLI 布局。原生工程含旧类/服务的 Delete 迁移键；不要只更新脚本或只移动 Service。权限列表本身不随核心工程迁移，目标环境必须重新按所需操作授权。历史安装/验收段落中的“URI/权限不变”仅描述当时的版本保护更新，不适用于本次拆分。

panwx25 读写拆分当轮验收（历史基线）：320项直接API/CLI路由检查、真实Field CRUD及版本/撤权恢复；Postman 119请求/202断言；20项读取健康检查。完整原生工程277迁移条目、270实例、74程序、71必需类，已核对51个新类的源码和编译内容，恢复203项导出标记。未新增AD/PIA界面或跨环境回导验收。

同日路径整理当轮的完整工程为280迁移条目（24个Delete）、268实例、74程序。OperQueryRecord与OperExecSql归入MetaData:Read，OperExecSqlWrite归入MetaData:Write，旧RecordQuery/SqlExec子包已删除；74程序源码保留，URI/服务/权限保持，20项健康检查通过。

Service 删除增补需同时安装新版 NativeAdapter、ManagedVersion、MetaData:Write:OperServiceDefn 和 CLI（object_operations.py、managed_operations.py）；不增加 Service Operation 或基本授权。Service 读取新增 serviceDeleteVersion=1 与 ownedOperations；旧编辑快照可能因扩大版本范围而409。用法与回滚后版本变化见 [Service 删除](12-service-defn-api.md#删除空-service2026-10-30)。

## 核心工程范围（2026-10-30 收敛）

核心工程仅含 MetaData 接口和运行依赖。C_SPREADSHEET、旧 JSON Core 转发、演示/探针及测试迁移条目已归入各自工程。消息翻译使用交付的 MESSAGE_CATALOG1 / MESSAGE_CATALOG_CI，原 C_META_MSG_LANG 页面、组件、CI、SavePreChange 已移出核心工程。不能仅因共享 JavaReflect 或历史统一导出就重新纳入无关定义。完整归属见 [架构](architecture.md)。

## 公共调用规则

CLI 负责环境、PS_TOKEN 和文本编码。直接调用 REST 时使用 `Content-Type: application/json`、`PS_TOKEN`；接口地址中的 `PSFT_HR` 换成目标环境节点。通常返回 `code/message/data`，`code=0` 表示请求成功，实际写入还须独立回读。各接口的正文编码及特殊返回结构见对应文档。所有子命令支持 `--timeout <秒>` 限制单个 API 请求的超时（默认不限；网关无响应时使用）。

## 安装

先运行 `preflight --refresh`。路由缺失时核对接口部署；180/74“找不到类”核对 Handler 与完整包，不按授权失败处理。

导入使用根目录下 `C_META_DATA_PKG/` 的 XML/INI。公开发行包仅把 38 处环境专属 OPRM.RestBaseurl 主机替换为 `https://ps.example.invalid`，PeopleCode 源码及编译内容保持原生导出；目标安装必须按实际节点和主机配置 REST BaseURL，且不能照搬占位地址。核实 pside.exe 路径、数据库类型/名称、PeopleSoft 用户及 TOOLSREL；Oracle 数据库连接名可参考本机 tnsnames.ora。凭据只从配置读入内存，不写入脚本、日志或回复。

下面变量使用实际配置；`$psFileRoot` 是包含项目目录的父目录，不能直接指向 XML 或 `C_META_DATA_PKG` 目录。日志目录需先创建。

```powershell
$psAd = '<pside.exe 绝对路径>'
$psDbType = 'ORACLE'
$psDbName = '<目标数据库>'
$psUser = '<PeopleSoft 用户>'
$psPassword = '<从本地配置读取的密码>'
$psFileRoot = '<skill 根目录>'
$psProject = 'C_META_DATA_PKG'
$psReport = '<比较报告目录>'
$psLog = '<本次操作的独立日志路径>'

# Compare From File：先比较，检查目标自定义修改及冲突
& $psAd -CT $psDbType -CD $psDbName -CO $psUser -CP $psPassword `
  -FP $psFileRoot -PJFC $psProject `
  -CMXML 1 -ROD $psReport -LF $psLog -HIDE -QUIET -SS -SN

# Copy From File：在已授权范围内导入；冲突先明确处理方式
& $psAd -CT $psDbType -CD $psDbName -CO $psUser -CP $psPassword `
  -FP $psFileRoot -PJFF $psProject -RST 1 -OVW 1 `
  -LF $psLog -HIDE -QUIET -SS -SN
```

目标缺少定义通常是待新增内容；两端均有自定义修改则需处理冲突。`-RST 1` 重置 Done；`-OVW 1` 覆盖目标 Project，必须符合已确认的导入范围。日志需出现已处理条目及成功完成标记。

导入后只 Build 需要创建或调整的 Record。1.5.0 的历史 Build 设置为 Create Tables、Alter Tables、Create Views 打开，Create Indexes、Create Triggers 及其他选项关闭；该设置不能直接用于新的 SQL 审计记录。2.0.0-dev.1 在授予 SQL 写权限前，须对新 Record **C_AI_SQLAUD** 创建物理表 **PS_C_AI_SQLAUD** 及 **GUID 唯一索引**（Create Indexes 打开），核验主键唯一、两个长文本字段和其他字段类型。已有表保留数据，用经过核对的 Alter/索引操作；不要再次执行会 Drop/Recreate 表的 record build createTable，也不要对整份工程盲目 Create Tables。

核对本机 RDM Build Settings；验证环境的注册表位置为 `HKCU\Software\PeopleSoft\PeopleTools\Release8.40\RDM Build Settings`，`ExecuteOption=3` 表示执行 SQL 并生成脚本，不推定所有版本都相同。下面命令仅适用于已审查 Build 设置及工程中所有 Record 的情况：

```powershell
& $psAd -CT $psDbType -CD $psDbName -CO $psUser -CP $psPassword `
  -PJB $psProject -LF $psLog -HIDE -QUIET -SS -SN
```

检查 Build 日志的错误、警告和 SQL 是否实际执行。工程导入不等于接口已授权。

## 认证

CLI 通过 PSTOKEN.v1 获取 PS_TOKEN，并复用本地缓存：

```powershell
python scripts/peoplesoft_api.py auth --refresh
python scripts/peoplesoft_api.py env init <环境名> --url <PIA地址> --username <用户> --password-stdin
```

默认配置为 `%USERPROFILE%\.peoplesoft\config.json`；PEOPLESOFT_CONFIG 可指定其他路径。认证失败先核对当前环境、PIA 地址、用户和密码，再刷新 Token，不绕过认证直连数据库。

直接接口为 `GET {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/<节点>/PSTOKEN.v1/`。请求头 Authorization 使用 Basic 编码的 username:password，可选 LanguageCd（ZHS/ENG）；编码后的凭据同样不得展示。成功 data 包含 psToken、userid、description、language。服务端有效期以单点登录配置为准；本工具缓存 11 小时，授权变化后使用 --refresh。

**LanguageCd 在传输层区分大小写**：Handler 用 `IBConnectorInfo` 的连接器属性名与字面量 `LanguageCd` 比对，IB 只在 HTTP 头逐字写成 `LanguageCd` 时才把它映射进去。写成 `Languagecd`/`LANGUAGECD`/`languagecd` 不会报错，而是被当成没有指定语言、照常返回登录成功。`urllib` 的两条入口都会把键名规格化——`Request(headers={...})` 走 `add_header()`、`add_unredirected_header()` 也各自执行 `key.capitalize()`，都无法发出 `LanguageCd`；要验证「不支持的语言」分支只能用 `http.client` 的 `putheader()` 或裸 socket（panwx25 实测：`putheader`/裸 socket 写 `LanguageCd` → code=1「不支持的语言：ZZZ」，`urllib` 两条入口与任何其他拼写 → code=0 success）。这是 IB 行为，与本包的迁移无关；换语言前先按精确拼写发一次失败用例确认链路。

## 授权

使用用户已确认的专用 Permission List，不默认选 PTPT1000。已有授权沿用；缺少目标权限列表时才确认。初始安装授权可在已获准的浏览器会话中完成：

1. 打开 **PeopleTools → 安全性 → 许可权与角色 → 许可权列表**，搜索并打开指定列表。
2. 切换 **Web 服务** 页签。按所需权限选入 `C_META_DATA_READ`，需要定义写入时再选入 `C_META_DATA_WRITE`；分别编辑所需操作。
3. 在操作权限窗口找到 `PSTOKEN_GET`；若显示接口别名，则对应 `PSTOKEN.v1`。设置为 **完全访问**。
4. 按任务分别给所需 Read / Write 操作设置 **完全访问**，核对全部分页/滚动区域；保存权限窗口，再保存许可权列表。不要对无关服务使用“完全访问（全部）”。
5. 基本安装验收需覆盖下列 20 个操作；账号必须通过自身角色/许可权关联实际取得该列表。SQL 写执行是单独可选授权，不在基本要求内。

```text
AI_READ_APP_ENGINE_POST
AI_READ_APP_PKG_POST
AI_READ_COMPONENT_DEFN_POST
AI_READ_FIELD_DEFN_POST
AI_READ_PAGE_DEFN_POST
AI_READ_PROJECT_DEFN_POST
AI_READ_RECORD_DEFN_POST
AI_READ_SQL_DEFN_POST
AI_READ_SERVICE_DEFN_POST
AI_READ_SERVICE_OP_POST
AI_READ_MENU_DEFN_POST
AI_READ_MESSAGE_CATALOG_POST
AI_READ_PORTAL_REGISTRY_POST
AI_QUERY_RECORD_POST
AI_SEARCH_DEFN_POST
AI_EXEC_SQL_POST
AI_READ_HTML_DEFN_POST
AI_READ_STYLESHEET_DEFN_POST
AI_READ_CI_DEFN_POST
AI_LIST_DEFN_POST
```

```powershell
python scripts/peoplesoft_api.py healthcheck --refresh
```

PSTOKEN_GET 与全部 20 个必需操作均为 PASS 才报告基本安装成功；有意采用部分授权时如实说明可用范围。Token 成功但接口未授权时核对对应操作，重新导入工程不能代替授权。

**AI_EXEC_SQL_WRITE_POST 默认不授权**。需要写执行时先完成上面的审计表/唯一索引 Build，再给指定现有列表授予 Full，运行 `healthcheck --refresh --include-sql-write`：PSTOKEN_GET + 21 操作应通过，写探测仅发送空 SQL并预期 400。撤销后 Handler 每次检查实际许可权并返回 code=403，IB 原始未授权可能是 HTTP 403；基本健康检查仍不要求此权限。部署和安全边界见 [SQL 执行](10-sql-exec-api.md)。

已部署且已授权的 `service-op set-permission` 可为指定现有列表设置某个同步 SOAP / REST Provider 操作的 Full/None，见 [服务操作](12-service-defn-api.md#服务操作)；它不能创建列表或代替初始授权。

独立消息翻译还需完整导入工程内的 `C_META_MSG_LANG` Page、Component/GBL、Component Interface 和 SavePreChange PeopleCode，以及 `CatalogLanguageAdapter`。执行账户需取得该 CI 的 Get/Save 权限；沿用目标环境已有权限列表，按需配置，不扩大其他 CI 权限。只有新版 CLI 或只有处理类都不足以启用翻译写入。翻译通过现有消息目录 REST 操作进入，不增加基本健康检查操作数。

## JSON 兼容层（2026-10-30）

`C_META_DATA_PKG` 的请求、响应、工具类及令牌入口都使用 `C_JSON_API` 的接口类型。统一工程仍叫 `C_META_DATA_PKG`，包含JSON根包、六个接口、Factory、Scalar、三个运行后端；旧Core名称的转发类保留在独立C_JSON_API工程，不随核心工程交付；不要只导入元数据根包而漏掉JSON依赖。`PSTOKEN_GET` 的Handler现为 `C_COMMONS_PKG:Login:Login`（子包 `C_COMMONS_PKG:Login`），原URI、认证方式和权限保持。

| Factory.DefaultBackend | 行为与依赖 |
|---|---|
| `AUTO`（默认） | 目标编译版本低于8.55.11选CustomApi；从8.55.11起选NativeApi |
| `CustomApi` | PeopleCode解析及输出，不需要原生JSON类或org.json；通用值类型识别使用PeopleTools自带Java桥及JDK标准类 |
| `NativeApi` | 内置JSON解析和输出；原生引用集中在带版本编译指令的NativeApi:JSONStorage |
| `JavaApi` | org.json的JSONTokener/JSONStringer；应用服务器须已加载兼容目标JVM的org.json jar |

8.55不能一概视为可用：本兼容层沿用项目此前记录，以8.55.11作为启用门槛，8.55.00–8.55.10默认CustomApi。选择依据为目标编译环境的 `#ToolsRel`，不引用旧版可能没有的 `%ToolsRelease`。版本指令语法见[Oracle说明](https://docs.oracle.com/cd/F30998_01/pt858pbr2/eng/pt/tpcl/langref_DirectivePeopleCodeFunctionsAndConstructs.html)。

安装者可在 `C_JSON_API:Factory` 修改唯一配置常量 `DefaultBackend`，编译保存后新请求使用指定实现。配置JavaApi前先用一个Factory实例调用 `SetBackend("JavaApi")` 并运行解析/构建检查；缺类或jar时明确失败，不自动换实现。jar必须与应用服务器JVM兼容，修改classpath后按该环境规程重启相关domain。切换后重新获取编辑快照。

原生工程由8.60.10实际编译导出。部署旧版时使用目标版本客户端导入并重新编译工程，使Factory和NativeApi:JSONStorage的条件分支针对目标版本生效；不要手改XML版本号或沿用8.60编译内容伪装成旧版包。仍须逐项验证目标系统的 `%metadata` 类、记录列和其他PeopleTools差异。

**实测范围**：panwx25 / Oracle / PeopleTools8.60.10，三种后端各20个读取操作、令牌刷新、PeopleCode精确回读及409拒绝；另147项JSON断言。未在8.54/8.55实机验证。NativeApi沿用原生浮点精度限制；需大整数/高精度文本往返时选CustomApi或通过目标org.json版本验证的JavaApi。日期/时间以字符串输出；自研严格校验目前拒绝NUL转义，解析深度上限64。接口名称对齐[Oracle 8.57 JSON类文档](https://docs.oracle.com/cd/F28299_01/pt857pbr3/eng/pt/tpcr/langref_JsonArrayClassMethods.html)。

依赖 `C_COMMONS_PKG:CommonUtil` 的Unicode反转义也已改用兼容接口，公开方法和旧请求字段编码保持；15次跨后端代码往返验证了Unicode、路径、转义、引号及原占位词。完整工程检查强制动态选择所需的全部JSON类存在，并拒绝带版本指令的NativeApi存储类以外的原生JSON依赖。

## 门户包解耦（2026-10-30）

统一工程 `C_META_DATA_PKG` 不再包含任何 `C_PORTAL_PKG` 成员。门户业务包属另一条产品线，本工程不拥有它；门户侧只保留 `Interfaces:GetMenu` 及其静态依赖的旧版 `Util:JsonUtil`（两者源码未改动）。`tools/check_bundle.py` 现在会拒绝工程清单里残留的门户成员。

| 原位置 | 现位置 |
|---|---|
| `C_PORTAL_PKG:Interfaces:Login` | `C_COMMONS_PKG:Login:Login`（`PSTOKEN_GET` 的 Handler） |
| `C_PORTAL_PKG:Util:CommonUtil` | `C_COMMONS_PKG:CommonUtil` |
| `C_PORTAL_PKG:Util:HttpUtil` | `C_COMMONS_PKG:HttpClient:HttpUtil` |
| `C_META_DATA_PKG:Utility:JsonUtil` | `C_JSON_API:JsonUtil` |
| `C_PORTAL_PKG:Util:JsonUtil` | 保留在门户包，只服务 `GetMenu`，不要用兼容层替换其原生 JsonObject 签名 |

panwx25 已删除 `C_PORTAL_PKG:Interfaces:Login`、`C_PORTAL_PKG:Util:CommonUtil`、`C_PORTAL_PKG:Util:HttpUtil`、`C_PORTAL_PKG:Util:HttpTest`、`C_PORTAL_PKG:Util:JSONObject` 及 MetaData 旧副本 `C_META_DATA_PKG:MetaData:Read:Login`、`C_META_DATA_PKG:Utility:JsonUtil`。前五个的 Delete 迁移标记在辅助工程 `C_PORTAL_MOVE_261030`（5 条 58/Delete + 2 条父包 57/Copy + `C_DEMO:SonClass`），MetaData 旧副本的 Delete 标记留在 `C_META_DATA_PKG`。父包节点不能省：删除响应的 57/Copy 让目标端的包定义把已删类从类清单里去掉，只发 58/Delete 会在目标留下指向不存在程序的类条目；该工程已用原生 Copy To File 导出核对，5 条 Delete 与 2 条包节点都在清单里。迁移顺序是：先导统一工程，再导 `C_PORTAL_MOVE_261030`，最后把 `PSTOKEN_GET` Handler 切到 `C_COMMONS_PKG:Login:Login`；原生的绑定键是 `Classname`，`Packageid`/`Packageroot`/`Qualifypath` 必须一起改，只改其中一部分会让 Handler 指向不存在的类。

工程登记要覆盖父包：直接登记类只写 58 条目，`C_COMMONS_PKG` 根、`C_COMMONS_PKG:HttpClient`、`C_COMMONS_PKG:Login`、`C_JSON_API` 根须分别登记 57。`C_DEMO:SonClass` 原先继承 `C_PORTAL_PKG:Util:HttpTest`，已改为直接 `implements PS_PT:Integration:IRequestHandler`，去掉空父构造器，`OnRequest` 仍返回空 Message。

## 公共Java反射工具

`C_COMMONS_PKG:JavaReflect`供JSON和独立电子表格工程复用，作为JSON运行依赖包含在核心工程；这不要求把电子表格类一起纳入核心工程。它通过Java反射分配对象和数组，避免热路径直接调用PeopleCode的CreateJavaObject/CreateJavaArray。CustomApi的JSONStorage复用Scalar，Scalar复用判型数组，检查后立即清空引用槽位。

```peoplecode
import C_COMMONS_PKG:JavaReflect;
Local C_COMMONS_PKG:JavaReflect &java = create C_COMMONS_PKG:JavaReflect();
Local JavaObject &value = &java.NewObject("java.awt.Color", CreateArray("int", "int", "int"), CreateArrayAny(12, 34, 56));
Local JavaObject &args = &java.NewArray("java.lang.Object", 1);
```

NewObject接收Java类名、明确的构造参数类型数组和CreateArrayAny值数组；无参使用CreateArrayRept("", 0)与CreateArrayAny()。NewArray接收元素类名及长度，Java下标从0开始。ClassName保留`10`和`"10"`的运行时区别；IntegerObject/PrimitiveObject处理基本类型装箱。Call按明确签名调用public方法；高频方法缓存Method及参数数组，再用Invoke，调用成功或失败均清空参数槽位。

工具通过系统类加载器查找类，第三方jar仍由部署者配置；反射不代替资源的close/dispose，不把可变参数数组放入跨请求全局缓存。C_SPREADSHEET的XSSF/SXSSF已统一使用此工具并修复重载、下标及资源清理问题；SXSSF仍不支持加载现有文件和克隆Sheet，读取仅限未刷出的窗口。

panwx25复验三后端各20项接口、147项JSON及45项日期断言。新增82项工具/电子表格/内存断言，200个反射数组可回收；40,000次判型和20,000次AddProperty后，本次GC后JVM堆未增长。6,000行/24,000单元格实际写出回读通过。此为有限运行观察，不构成长期或跨PeopleTools/JDK版本的无泄漏保证。

## 原生导出

四类定义版本保护须同时安装编译后的 Utility:ManagedVersion、CatalogLanguageAdapter、MetaData:OperServiceDefn、OperServiceOperation、OperMessageCatalog、OperPortalRegistry，以及新版CLI（scripts/managed_operations.py、object_operations.py）。URI和原权限不变；旧客户端无expectedVersion写入会拒绝。需更新完整原生工程和父包清单，不能仅替换XML正文。配置/删除需按[原始计划工作流](12-service-defn-api.md#原始版本保护2026-10-29)重新生成快照；基本healthcheck不能单独证明并发语义。

独立 SQL / Project 版本保护需配套新版编译后的 `MetaData:OperSqlDefn`、`MetaData:OperProjectDefn`、`Utility:DefinitionVersion` 与新版CLI（含 `scripts/sql_project_operations.py` 及其他定义的工程存在性检查）。旧客户端无expectedVersion写入会被拒绝；URI、服务操作与权限不变。安装后按 [SQL](04-sql-defn-api.md) / [Project](11-oper-project-defn-api.md) 核对能力、428/409、dry-run与隔离实际保存。不能仅替换XML正文或仅更新脚本。

HTML/StyleSheet版本保护需要同时安装新版编译后的OperHtmlDefn、OperStylesheetDefn、NativeAdapter和CLI（scripts/content_operations.py），继续依赖Utility:DefinitionVersion。已在panwx25验证428/409、dry-run、真实并发创建/修改及保存后异常回滚；REST URI和正式权限不变。部署后核对能力标记与完整原生编译工程，不能只替换XML正文。见 [版本契约](17-ci-html-stylesheet-api.md#html-与-stylesheet)。

Menu 版本保护需同时部署新版编译后的 `MetaData:OperMenuDefn`、`Utility:MenuCodeAdapter` 和 CLI（含 `scripts/menu_operations.py`），继续依赖 `Utility:DefinitionVersion`、`NativeAdapter`、`ObjectKeyResolver`。旧客户端缺 `expectedVersion` 的写入会被拒绝；REST URI、操作和权限不变。按 [Menu版本工作流](14-menu-defn-api.md#原始版本与冲突处理2026-10-29) 核对能力标记、428/409、dry-run 和隔离对象实际保存。

CI 版本保护需同时部署新版编译后的 `MetaData:OperCIDefn`、`Utility:NativeAdapter` 和 CLI（含 `scripts/ci_operations.py`），继续依赖 `Utility:DefinitionVersion`。REST URI与权限不变，不增加服务操作；仅更新客户端或XML正文不能启用。新服务端拒绝无原始expectedVersion的写入，安装后按 [CI版本工作流](17-ci-html-stylesheet-api.md) 验证读取能力、428/409、dry-run和隔离对象实际保存。

Field/Record 的版本与删除更新还需包含 `C_META_DATA_PKG:Utility:DefinitionVersion`、`MetaData:OperFieldDefn`、`MetaData:OperRecordDefn` 三个程序及父包清单。仅更新客户端不能启用 expectedVersion；旧客户端写入会被新版服务端拒绝。

Field Label 的 `deleteLabel` 复用 `AI_OPER_FIELD_DEFN_POST`、既有 REST URI 和权限，不增加服务操作；需使用包含 DeleteLabelCli 的新版 OperFieldDefn 编译程序。仅有新版 CLI、旧处理类或只改 XML 正文都不足以启用。安装后先执行基本 healthcheck，再按 [Field / Label 工作流](06-record-defn-api.md#field-定义与-label) 在隔离测试定义上核对 dry-run、版本拒绝、实际删除、父 Field 保留及工程 Copy 标记；20操作健康检查只证明基本操作可达，不单独证明 Label 删除语义。

CLI 当前没有 `project export` 子命令，使用 AD 的 Copy To File：

```powershell
& $psAd -CT $psDbType -CD $psDbName -CO $psUser -CP $psPassword `
  -PJTF $psProject -FP $psFileRoot -LF $psLog -HIDE -QUIET -SS -SN
```

先导出到新的目录，检查退出码、日志、XML/INI、完整键清单和 TOOLSREL，再替换发布工程。源码变更须先在服务器编译并回读，不能仅修改 XML 的 peoplecode_text 而沿用旧编译块。

PANWX25 / PeopleTools 8.60.10 的 `-HIDE -QUIET` 成功/失败均可能没有标准输出；成功退出码为 0，不存在项目为 8，具体错误写入 `-LF` 日志。日志按 BOM 或 UTF-16LE 读取，不能仅凭没有输出判断成功。报告退出码、导出目录和具体错误。导出会更新 Done，标记语义见 [Project 管理](11-oper-project-defn-api.md)。

命令依据见 [Oracle 原生复制说明](https://docs.oracle.com/cd/F44947_01/pt858pbr3/eng/pt/tlcm/task_CopyingDefinitionsUsingTheCommandLine.html)。

### dev.6 Page 处理类与客户端配套

Page并发保护和能力7需要同时安装新版OperPageDefn编译程序与CLI（含scripts/page_operations.py），继续依赖Utility:DefinitionVersion。直接接口和旧客户端缺expectedVersion返回428。版本字段和原始快照用法见[Page参考](07-page-defn-api.md)。

Component 属性和版本保护需要配套新版编译后的 `OperComponentDefn` 与 CLI（含 `scripts/component_operations.py`），并继续依赖 `Utility:DefinitionVersion`。旧客户端的 Component 写请求缺版本会被拒绝。安装后按 [Component 参考](07-page-defn-api.md#component-接口) 在隔离对象上核对快照、冲突、属性及 AD 回读。
