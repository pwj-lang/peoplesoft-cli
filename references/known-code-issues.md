# 已知问题与支持边界

当前候选发行版：**2.0.0-rc.1**（2026-10-30，预发布）。已知缺陷和未验收项不因候选发布而关闭。结构见 [架构说明](architecture.md)，交付条件见 [发布规划](release-roadmap.md)。

2026-10-30 核心范围收敛：电子表格、旧 JSON Core、演示/探针、测试迁移项和原自建翻译定义均已移出。消息翻译复用交付组件/CI，精确单语言删除保留；实现及边界见 [消息目录](15-message-catalog-api.md#独立翻译)。

## 尚未关闭、未验收与延期项

| 类别 | 项目 | 当前边界 |
|---|---|---|
| 未关闭缺陷 | SOAP Validation=Y 间歇性 119,40 | 已通过调用使用 N，不能据此关闭 Y 的问题 |
| 历史待处理 | jt-dev 错误的 57 类型应用包工程条目 | panwx25 已修复验收，原环境未清理 |
| 验收缺口 | 读写拆分、门户解耦的跨环境实际删除 | 已核对原生导出 Delete 键，未证明目标端删除效果 |
| 验收缺口 | 空白环境首次安装、8.54/8.55 及其他平台组合 | 首次真实部署或目标版本实机另验 |
| 明确延期 | Fluid、CI 引用与多语言子结构、SOAP Consumer/异步 | 不在当前已交付范围 |
| 持续分批 | Page 控件属性 | 仅已验证的 Edit/DDL 属性；未知属性不实现 |
| 既有接口限制 | LanguageCd 头名 | IB 要求精确拼写；urllib 两条入口都会规格化，见 [认证](01-auth-api.md#认证) |

以下保留各对象的适用限制和历史修复证据；“版本控制”均不提供历史版本库或一键回滚。

2026-10-30 Java桥接增补：JSON与电子表格共用`C_COMMONS_PKG:JavaReflect`，热路径使用Java反射分配并复用参数数组，正常和异常均清空引用。panwx25的200个反射数组可回收，40,000次判型与20,000次AddProperty的GC后JVM堆未增长；24,000单元格写出回读通过。该有限观察不等于长期无泄漏或native RSS验证，其他PeopleTools/JDK/POI组合需复验。SXSSF仍不支持LoadFile/CloneSheet，GetRow不能取已刷出窗口的行。用法见[公共Java反射工具](01-auth-api.md#公共java反射工具)。

2026-10-30 JSON兼容层已部署：NativeApi、CustomApi、JavaApi在panwx25各通过20项接口检查、真实代码写入/回读和409验证，JSON专项147项断言通过。8.55.11是本层默认切换门槛，旧目标仍需目标客户端编译及整套元数据API验收，尚无8.54/8.55实机认证。NativeApi保留原生数字精度限制；JSON日期/时间为字符串；自研解析目前拒绝NUL转义并限制64层。配置及依赖见[JSON兼容层](01-auth-api.md#json-兼容层2026-10-30)。

2026-10-30 Service 删除已支持空 SOAP/REST Provider 服务；原有“整份 Service 删除未开放”仅为历史边界。非空服务仍拒绝。原生删除后事务回滚会留下部分进程的删除缓存，已通过恢复行VERSION与服务/系统代数推进修复；失败后应重读快照。实现与适用版本见 [Service 删除](12-service-defn-api.md#删除空-service2026-10-30)。

服务端在 PANWX25 / Oracle / PeopleTools 8.60.10 验证，当前工作区为 **2.0.0-dev.6**，未正式发行。dev.5 修复下述 Project 元数据差异；此前同步 SOAP Provider 和消息目录独立翻译的 AD/PIA、同环境原生迁移和主要流程验收沿用 dev.4 证据。SOAP 运行时 Schema 校验仍有下列未解决问题；原生 Copy 不清除缺席翻译，删除迁移须按 CLI 返回参数在目标环境重放，见 [消息目录](15-message-catalog-api.md)。CI 自定义 Methods 程序已实现；引用及 CI 多语言子结构后置。1.5.0 已正式发行，空白环境首次安装核验延期至首次真实部署。180/74“找不到类”先查 Handler 与依赖。历史见 [变更记录](../CHANGELOG.md)，发行条件见 [规划](release-roadmap.md)。

## Menu / CI / HTML / StyleSheet 原始版本（2026-10-29）

Menu 于2026-10-29补齐创建、结构/项目和 ItemSelected 全部写入的原始 expectedVersion、428/409、CLI精确上下文与冲突保稿，以及结构/代码交叉并发拒绝。需配套新版 OperMenuDefn、MenuCodeAdapter 和 CLI；用于并发覆盖检测，不提供历史库。详见 [Menu接口](14-menu-defn-api.md)。

CI于2026-10-29补齐所有写入的原始expectedVersion、428/409、CLI改稿保留及真实并发拒绝。需同时部署新版OperCIDefn、NativeAdapter和CLI；版本控制用于覆盖检测，未开放历史版本库、CI引用或多语言子结构编辑。详见[CI接口](17-ci-html-stylesheet-api.md)。

HTML/StyleSheet于2026-10-29补齐创建/修改的原始expectedVersion、428/409、CLI保稿和上下文快照。已部署panwx25并通过真实并发创建/修改、原生保存后异常回滚及正式端点检查；需配套OperHtmlDefn、OperStylesheetDefn、NativeAdapter编译工程和CLI。用于并发覆盖检测，不提供历史库；本轮未新增AD/PIA或跨环境迁移验收。见[版本范围](17-ci-html-stylesheet-api.md#html-与-stylesheet)。

## Page支持范围（2026-10-27，dev.6）

Page原始快照expectedVersion已实现，保护所有写操作；CLI冲突不自动取最新令牌覆盖。仅支持已验证的Edit/DDL控件属性，其他类型只读原始列；类型和条件边界见[Page](07-page-defn-api.md)。新增12属性已对照既有AD证据与数据库结果，本轮未做GUI/PIA运行验收。日期Time Zone仅证明持久化标志，不能推断日期运行时效果。未知位保留，不命名为已支持属性。后续按10–20属性批次收集和实现。

## Field / Record 版本与明确删除（2026-10-24 工作区更新）

新增全局 Field 与 Record 定义删除、Record 直接字段/子记录引用删除；Record delete-code 增加版本保护。所有写入（包括创建和 Build）须先读取 expectedVersion，旧客户端写入会被拒绝。需同步部署两处理类、Utility:DefinitionVersion 和 CLI；详见 [Record / Field](06-record-defn-api.md)。版本涵盖子记录及受影响祖先、程序和视图 SQL，冲突保留原稿，不自动覆盖。

定义删除保留物理表/视图；Field 仍用于 Record、Record 仍作子记录引用时拒绝直接删除。移除子记录字段可重建祖先展开并删除祖先上因此失效的事件程序，dry-run 返回完整影响键。删除整个 Field 时，其基准及语言标签由原生管理器清理；其他外部引用不自动重写。已在 PANWX25 / Oracle / PeopleTools 8.60.10 验证隔离定义删除；Label 父 Field Copy 的同环境回导见下段。跨数据库、空白环境和其他目标环境的完整迁移未验收。Oracle DDL 仍不能整体回滚。

Field Label 已另补 `deleteLabel` / `field delete-label`：精确删除标签、所属翻译及上下文，保留 Field；支持 expectedVersion、dry-run、恢复备份和独立回读。默认 Label 需指定已有替代，最后一个标签及 Record/展开Record/Page 显式引用拒绝删除。单标签删除沿用标签表维护并更新缓存版本，不能把 Label 子键交给整 Field 原生删除管理器。AD 已核验剩余标签与默认勾选；同环境原生回导已验证父 Field Copy 能移除目标多出的 Label，跨环境迁移后仍需回读。详见 [Label 契约](06-record-defn-api.md#field-label-添加修改和删除)。

Label 的新增/修改当前只维护基准标签；不能由单删会清理翻译推断可独立新增/编辑 Field Label 翻译。标签 ID 在外部业务数据或代码中的自定义引用不自动检查或重写。版本令牌用于检测并发覆盖，不提供历史版本库或一键回滚；删除备份用于人工恢复核对。

本次同时修复 Record 读空 Rowset 时的假字段/索引、事件筛选、嵌套子记录展开和无索引 Build 的假空索引循环。末字段删除后空 Record 可读取并修改属性。

## PSCLI-20261023-01：Project 比较报告与 AD 元数据差异（PANWX25 修复）

旧创建入口给 PROJECT:ProjectDefn 封装属性赋值，但 save() 未保存 KEEPTGT/REPORTFILTER，实际为 0/0；AD 基准为 31/16232832。相同 PeopleCode 文件与数据库差异下，仅改变报告过滤值，原生 Compare 分别生成 0/1 条差异项，修复值包含赋值 1→2 的逐行内容。创建现直接使用原生元数据定义保存；描述修改保留其他头属性，支持显式空字符串；历史项目需按其当前设置显式 `project modify NAME --ad-defaults`，不自动批量重置。

重复插入、写后自动登记会恢复 Unknown/Copy/Upgrade on/Done off；显式 Delete 使用 Delete/on/off。直接 API 默认 Upgrade 也为 on。实际成员修改同步维护头版本与时间，同值操作保持不变。取消旧 CopyProp 类型硬限制以匹配 AD 消息目录枚举保存；不扩大其目标复制语义。服务端补充项目名称/长度及键值长度校验；struct 新增 header 和比较状态，CLI 独立验证结果。新处理类与客户端须一起部署，旧客户端/旧服务端的组合不代表此修复已安装。

AD 报告覆盖的 9 种键及全部成员字段对照通过，扩展到 30 种 Project 类型的登记核验；原生代码差异报告已验证。图形界面的交互弹窗本轮未完成核验，不把原生报告通过写成 GUI 弹窗已验收。AD 报告尚无正向样本的项目多语言、ADS 绑定、SEC/WORK 临时数据等保持未验证；不据空表补写推测数据。

## SOAP 运行时 Schema 校验（未关闭）

专用同步 SOAP 接口在 Validation=N 下通过 SOAP 1.1、1.2 的真实请求/响应，用户名密码验证保持开启。Validation=Y 时曾间歇返回 119,40；重新生成独立 namespace 的消息 Schema 后仍复现，根因尚未确定。已通过的实际调用使用 N，不把 N 的成功当成 Y 已通过。需要运行时 XSD 校验的接口须另行验收；不能自动把已有接口切换为 N。SOAP Consumer 和异步不在本版支持范围。

## PSCLI-20261015-01：Application Packages 工程条目键值错误，AD 显示 Absent（panwx25 修复验收；原环境条目待清理）

- **发现日期 / 环境**：2026-10-15，`jt-dev`；工程 `C_FIX_PWJ_20261015_02`。
- **涉及范围**：`project insert-item` 的 Application Packages（`objectType=57`）登记、调用方键值组装及相关文档指引。Application Package PeopleCode（`objectType=58`）是另一种键结构；本次截图未证明 58 类型条目有同样问题。
- **状态**：dev.2 在 panwx25 实现 57 类型非 Delete 插入的原生定义存在性校验；三组错误路径拒绝、根包和一级子包正确键通过 API、原生导出和 Compare From File 验证，专用工程原生完整性检查为 0 个无效定义。dev.3 在 AD 打开专用工程的 C_META_DATA_PKG，可解析包和 MetaData/Utility 类树，未显示 Absent。原 jt-dev 错误工程未清理，不标记跨环境问题全部关闭。

### 现象与复现证据

修改类 `C_JT_PT:globalPay:outBound:GetPayEmployeeList` 后，调用方把应用包层级当作 57 类型的连续路径段，依次执行 `project insert-item C_FIX_PWJ_20261015_02`，参数如下：

| objectType | value1 | value2 | value3 | value4 |
|---|---|---|---|---|
| 57 | C_JT_PT | 空 | 空 | 空 |
| 57 | C_JT_PT | globalPay | 空 | 空 |
| 57 | C_JT_PT | globalPay | outBound | 空 |

三次调用均返回 `OK — item inserted`；`project struct --json` 也能回读以上条目，ObjectID 为 `104 / 116 / 117 / 0`，当时迁移标记为 `Copy / Upgrade on / Done off`。**插入成功及结构回读成功只证明工程中存在这些行，不能证明行所指向的原生定义存在。**

用户提供的 AD 截图中，上述三行均显示 `Source=Absent / Target=Absent`。同一截图通过原生 `Insert into Project → Application Packages`，按 `C_JT_PT` 搜索得到的正确显示形态是：

| Package | Root | Qualify Path |
|---|---|---|
| C_JT_PT | C_JT_PT | . |

该正确形态在工程列表中显示 `Same / Same`。这与此前插入的 `C_JT_PT / 空 / 空`、`C_JT_PT / globalPay / 空`、`C_JT_PT / globalPay / outBound` 不同。截图提供了原生显示证据；对应完整 ObjectID/ObjectValue、点号及空格的实际存储规则，仍需后续从原生插入后的工程或导出文件核实。

### 发现时的判断与待排查点（历史）

已确认调用方使用了错误的 57 类型键值，登记接口接受了这些不存在的定义引用，原先仅凭 `struct` 回读即判定工程登记通过的验收不充分。尚未完成源码级根因定位，不直接认定为单一 CLI 或服务端缺陷。

后续排查 `peoplesoft_api.py`、`C_META_DATA_PKG:Utility:CoreOperProjectDefn`、`C_META_DATA_PKG:Utility:ObjectKeyResolver`，以及 [Project 文档](11-oper-project-defn-api.md) 中 57 类型的说明：区分 Package / Root / Qualify Path 与 58 类型的根包、子包、类路径；核实原生键语义和定义存在性检查，修正调用示例及登记指引。

### 原修复验收清单（历史；当前状态见本节开头）

1. 从原生 AD 插入同一应用包后，取得完整键作为基准；明确根包和嵌套包的实际表示方式，不根据冒号路径推测 57 类型键值。
2. CLI/API 登记结果与原生键一致，关闭重开工程并执行原生 Compare/导出核验，存在于源端的定义不能再显示 `Source=Absent`；目标端确实不存在时允许 `Target=Absent`。
3. 对上述三组无效键的处理给出可验证结果：拒绝，或经明确约定转换为正确键，不能继续静默插入不存在的引用。
4. 核对 58 类型类程序条目及迁移标记不受修复影响；核实 57 类型包定义的复制范围，避免登记引入无关定义的迁移。
5. 历史错误工程条目另行按完整键清理并回读核对；本次记录不包含清理操作，不据此标记问题已解决。

## 2026-10-11 已关闭的历史 BUG

| 问题 | 修复与验收 |
|---|---|
| 旧 PeopleCode 真正删除 | Page Activate、Record Field、Component/Record/Field 三层事件、AE Action 程序、应用类程序支持明确 delete-code；七个完整原生键删除后不存在，邻居/父定义保留，Project 为 Delete/Upgrade on/Done off。Page 关闭重开 AD 后 Activate 普通字重 |
| Record 属性显示 | C_AI_RF1010.COUNTRY 的 Required、Prompt Table Edit、COUNTRY_TBL 在 AD 属性对话框首次打开及关闭重开后均正确，无需额外服务器改动 |
| 弹出菜单运行 | C_AI_DP1011 的 COUNTRY 字段关联 C_AI_EXT_POPUP，浏览器点击 MAIN/FIRST 实际触发 ItemSelected，NAME 和消息框均显示 POPUP_OK_1011 |
| 查询输入保护 | CLI 与服务端分别限制输入；元数据确认 Record/Field，值及行数绑定；69 项直接 REST、八类字段输出及五项绑定过滤验收通过 |

空正文和仅含空白字符的 modify-code 已拒绝；使用 [明确删除流程](development-standards.md#peoplecode-真正删除)。`programExists` 判断原生程序是否存在，`hasPeopleCode` 仅描述正文，不可互换。

## 部署核验

SQL 定义维护 Handler 为 `C_META_DATA_PKG:MetaData:Read:OperSqlDefn` / `C_META_DATA_PKG:MetaData:Write:OperSqlDefn`；SQL查询Handler为 `MetaData:Read:OperExecSql`，SQL写执行Handler为 `MetaData:Write:OperExecSqlWrite`。180/74“找不到类”先查 Handler/包依赖，明确的 401/403 或未授权才查权限。基本健康检查覆盖 PSTOKEN_GET 与全部 20 个必需操作，写操作可选探测，见 [安装说明](01-auth-api.md)。

## SQL 执行边界

只读 SELECT/WITH 和 SQL 定义执行、独立授权的单条 DML 已验收。SQL 定义写执行、DDL、PL/SQL、FOR UPDATE、多语句、BLOB、数据库级只读、语句级超时、幂等键及跨语句事务不支持。写操作默认关闭；部署须先 Build 审计表及 GUID 唯一索引。

SQL 类无法在零行结果中发现列数；未经 TO_CHAR 的数值 NULL 变成 0，数字/日期的格式和精度依赖 PeopleCode 转换。原生绑定可能去除尾部空格/换行，空字符串绑定为单个空格。WITH 查询需包装子查询，分号在注释/字面量中也禁止，注释里的 meta-SQL 同样拒绝。完整契约和容量限制见 [SQL 执行](10-sql-exec-api.md)；语法检查和直接审计表写入保护不能替代数据库权限，见 [安全说明](../SECURITY.md)。

ObjectKeyResolver、PeopleCodeDeletion 和调用处理类必须一起导入。键解析不加载固定 Project，业务定义无需预先加入核心工程，详见 [开发规范](development-standards.md)。元数据删除与 Project 登记分步执行；登记失败会明确报告程序已删除的部分成功状态。

## 服务与消息目录边界

支持同步 SOAP / REST Provider、消息目录基准消息及按语言独立维护文本/说明，以及已有 Portal 的内容维护。消息集名称翻译、Consumer、异步后置；八类列表支持前缀和游标分页。整份 Service/Menu/Portal 和所有门户文件夹删除关闭。

PeopleCode delete-code 删除一个程序定义；不删除 Record/Field/Page/Component 或 AE 的 Section/Step/Action。AE 结构另用 delete-section/delete-step/delete-action，全部写入要求原始版本，删除范围、静态引用保护和级联清理见 [AE](05-app-engine-api.md)。应用类/子包/根包定义另用应用包的 delete-class/delete-package/delete-root。菜单 ItemSelected 的删除使用菜单自己的接口。REST 多定义、菜单清理和 Project 登记分步保存，不承诺共同回滚；未知写结果先回读。

PANWX25 的原生 Menu API 未持久保存 Mit.AllowedActions 与 Mit.AddSearchRecName。这两项保留只读输出，CLI 和服务端均拒绝写入，防止假成功；其余受支持属性仍以保存后回读为准，见 [菜单](14-menu-defn-api.md)。

查询 filter.value 须为字符串，数字字段也传 `"104"` 而非 `104`；CLI 和直接 REST 均明确拒绝数字 JSON 值。Oracle 字段类型与输出边界见 [查询接口](09-query-record-api.md)。输入保护不等同于业务行级权限，见 [安全说明](../SECURITY.md)。

门户属性 Values 最多一个字符串，按属性语义容纳逻辑多值；不生成多条原生 AttrValue 行。新建重复 URL 的 CREF 由原生拒绝，第二入口用 Link；被 Link 引用的 CREF 删除受限。dry-run 不替代原生保存；部分 Save=false 可能没有详细 PSMessages，但必须报告失败。

内部批次 2.4.1 已修复服务操作遗漏 Serviceopr 关联，以及门户多条属性值造成导航崩溃。旧缺失关联可通过操作 modify 同值保存触发维护；旧多行属性先核对业务语义再改为单字符串。部署需完整修复包，门户验收使用 validate 加浏览器点击，不能只看 struct。

## 2.0 新定义边界

CI 支持定义属性、标准方法开关、Pit 映射和完整自定义 Methods PeopleCode 程序；删除代码会删除该程序内全部自定义函数，保留父 CI。函数签名解析、CI 引用和多语言子结构编辑未开放；后两项已明确后置。定义维护不执行 CI 业务方法，也不自动扩展业务权限。HTML 固定 ContType=4；StyleSheet 只写 StyleSheetType=2 且无父样式的自由格式定义。三类整份删除未开放。本环境已完成 AD 重开、受控样式效果及原生回导入；原生复制会将文本 LF 规范为 CRLF，迁移后须重新读快照，详见 [接口说明](17-ci-html-stylesheet-api.md)。
