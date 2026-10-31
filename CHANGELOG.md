# 变更记录

## 2.0.1（2026-10-31，修复版）

- 补齐并修复 `page structure/apply` 整页结构回放：原始编辑基线、持久逻辑/原生 ID 映射、父/页派生引用、重复 ID 和容器层级校验、扩展子块保留、dry-run 回读及消息集编号精度。Grid/Scroll 通过整页回放验收；增量 add-control 的 Grid/Scroll 原型仍停用。
- 修复 Page 读取扩展空对象、索引字段遗漏和 Oracle DDL 等问题，并将组件/应用根包 CLI、Field XLAT 维护纳入本次修复版本。完整 C_META_DATA_PKG 原生工程包含最新编译结果，部署须同步 CLI 与服务端。


- 社保公积金完整隔离复刻补齐：单一 SVG Image 原生 `image struct/exists/clone`，源/目标双原始版本、BLOB 指纹、dry-run 回滚及工程登记；不扩称为任意图片格式或文件上传能力。
- 修复 Record 索引字段返回空数组、遗漏原生存储/平台属性、修改省略 fieldProperty 时覆盖既有位的问题；保留未映射 USEEDIT 位。Oracle DDL 按原生签名长度还原数字精度，并保留必填日期 NOT NULL。
- AE 创建/插入支持完整 JSON 属性，修复 Derived/Work 状态记录关联；维护源经服务器编译、完整原生导出后同步交付，核心仍为 301 成员 / 100 程序 / 38 操作。
- panwx25 的 C_XI_261031 隔离工程包含开发定义、代码、自定义依赖及独立测试数据；原生校验、计算保存/重开及 AE→CI 新有效日期同步均有独立证据。原模块的三种向上取整算法原有缺陷单独记录，复刻一致不代表算法正确。

- 新增 Field `list-xlat/add-xlat/modify-xlat/delete-xlat`：全部生效日期及语言行读取、基准值增改删、失效、dry-run、原始版本、XTM/SYS 缓存、完整类型 4 迁移键；Field 版本覆盖 XLAT，关联 Record 版本跟随 XLAT 头变化。
- 明确 ps-cli 开发定义与后续 ps-admin 的运行管理边界；角色/许可权、用户授权、Process Definition、进程组和 Scheduler 日常管理不列为 ps-cli 复刻能力缺口。
- 封装 `component create/add-page/remove-page`：原始快照、已有引用校验、多页文件创建、独立回读、保留未修改属性及完整工程登记。
- 新增 `app-pkg create-root` 与服务端 `createApplicationPackage`；不存在名称返回版本快照，防止同名创建/删除后复用旧基线。根包新增和既有 `delete-root` 均核对完整原生工程键，整包删除独立确认不存在。
- 修复 CoreOperPageDefn 完整结构读取中非 Edit/DDL 控件未初始化或串用扩展对象的问题。每个控件按自身 PNLFLDID 读取 PSPNLFIELDEXT，缺行返回空对象；普通模式继续仅为 Edit/DDL 解码读取扩展。
- panwx25 的两张社保报错页面及 JOB_DATA1 恢复读取；7 张页面、211 个控件、6,541 个扩展值与数据库核对通过，页面版本、定义和普通输出均不变。
- 更新编译后的完整原生工程及本地镜像、安装副本；未重新发行或覆盖历史 2.0.0 zip。

## 2.0.0（2026-10-31，正式发行）

- 将 rc.1 的现有能力正式发行；保留已知问题和未验收项，后续通过小版本修复与补充验证，不将发行状态当作问题已关闭。
- README 改为中英双语，简述命令行可维护的定义类型，并明确 Skill / CLI 与需自行部署的 MetaData API 是两个主要交付物。
- 标明 PeopleTools 8.60 为开发版本（Oracle / 8.60.10 验证），8.57 及更新版本大部分功能预期可用，早于 8.57 未测试。
- 沿用 rc.1 的 CLI、API 和完整编译工程；正式包、标签及校验和另行生成，保留候选版及 1.5.0 历史发行。

## 2.0.0-rc.1（2026-10-30，候选发行）

- 汇总 2.0 开发阶段的 SQL 查询/独立 DML、CI/HTML/StyleSheet、SOAP Provider 与消息翻译、原始版本保护、Page/Component 和精确删除能力。
- 核心收敛为 301 迁移成员、100 个运行程序；移出无关工具、测试/演示、旧 JSON Core、自建翻译定义及仅引用的标准 Field。
- 翻译复用交付 MESSAGE_CATALOG1 / MESSAGE_CATALOG_CI，保留精确单语言删除、dry-run、版本冲突和缓存更新。
- 公开包将 38 个环境专属 REST BaseURL 主机替换为占位地址，全部 PeopleCode 源码及编译块保持一致；修正安全说明并移除本机路径。
- 本次是 Pre-release：SOAP Validation=Y 的间歇性 119,40、跨环境/空白环境与旧 PeopleTools 验收仍未完成。1.5.0 保持最新稳定版，不覆盖历史包。


## 2026-10-30：移出仅引用的系统标准 Field（保持 dev.6）

- 从 C_META_DATA_PKG 移除 8 个未改的标准 Field 显式条目：AUDIT_ACTN、DESCR254、DESCRLONG、DTTM_STAMP、GUID、OPRID、ROW_COUNT、SQLTEXT。项目 309 → 301 成员，100 个运行程序不变。
- 保留 C_AI_SQLAUD Record 和其字段层属性，以及自定义 C_AE_ACTN_TYPE。完整 Field 属性快照与审计 Record 回读不变；本轮不写 Field/Record 定义，不删除定义。
- 补充工程登记规则，检查器拒绝将这些未修改的标准 Field 重新作为核心显式成员；原生关联实例不手工裁剪。同步原生工程和文档，历史 zip 不变。

## 2026-10-30：核心工程收敛与标准消息目录 CI（保持 dev.6）

- C_META_DATA_PKG 仅保留运行接口及依赖。移出电子表格 27 项、测试 13 项、旧 JSON Core 8 项，以及原自建翻译 Page/Component/CI/程序 4 项，共 52 个原成员；MetaData 历史正式迁移删除键保留。
- Demo、AcceptanceRestEcho、SoapProbe、空 DeletionProbe 移到 C_DEMO:MetaDataTest，更新 SOAP 测试 Handler；旧程序删除键和测试/退役定义在 C_META_TEST_261030 保留。电子表格仍由独立 C_SPREADSHEET 工程管理，旧 Core 归 JSON 自身工程。
- 消息翻译复用系统 MESSAGE_CATALOG1 / MESSAGE_CATALOG_CI 及事务语言设置；精确 Record 路径处理单语言删除和与基准完全相同的显式翻译，保留权限、原始版本、单事务、缓存更新和 dry-run。20 项实测通过。
- 检查器改为 100 个运行类 / 38 个操作，拒绝无关成员、测试空壳和退役组件，补充运行 CI 引用检查。原生工程和文档同步；未覆盖历史 zip，未创建正式发行。

## 2026-10-30：文档与维护入口整理（保持 dev.6）

- 精简 SKILL 与 README，集中环境、原始版本、冲突、回读和工程登记规则；按对象加载接口细节。
- 新增架构与交付边界，区分同名 AD Project / 应用包、读写入口、JSON / JavaReflect / 电子表格和门户业务包的归属。
- 发布规划与已知问题统一为 dev.6，区分未关闭缺陷、验收缺口和明确延期；安装文档中的旧工程数量标为历史基线。
- 本机开发项目新增当前状态、维护流程与证据索引；原交接记录保留。仅整理文档，不改变 API、PeopleCode 或原生工程，不重打历史 zip。

## 2026-10-30：公共Java反射与电子表格

- 新增C_COMMONS_PKG:JavaReflect，显式选择构造及方法签名，反射创建对象/数组，支持primitive装箱、可复用参数数组和成功/异常后的槽位清理；JSON和电子表格共用。
- JSON三个维护类与C_SPREADSHEET的16个程序完成改造，移除直接CreateJavaObject/CreateJavaArray热点。修复POI重载歧义、DataFormat接口错误构造、缺失接口方法、1基下标、行删除和工作簿/输出流清理。
- panwx25复验147项JSON、45项日期、三后端各20项接口健康检查和代码往返/409。新增82项断言；200个反射数组可回收，40,000次判型和20,000次AddProperty的GC后堆未增长；6,000行/24,000单元格写出回读通过。有限观察不视为长期或旧版本无泄漏证明。
- 公共工具与完整电子表格依赖统一归入C_META_DATA_PKG；保持dev.6，不覆盖历史zip。

## 2026-10-30：JSON兼容层

- C_META_DATA_PKG和PSTOKEN_GET统一使用C_JSON_API接口，由Factory集中选择NativeApi、CustomApi或JavaApi；统一登记C_META_DATA_PKG工程。
- Core实现迁至CustomApi，旧名称保留七个转发类；JavaApi补齐六个接口实现及org.json存储引擎。
- 原生引用集中到带版本指令的存储类；AUTO以8.55.11为门槛，旧版默认CustomApi，可手动指定JavaApi。
- 统一字符串转义和原始类型，修复数字文本、重复键、数组节点、emoji、非法数字、解析失败残留等差异；保留元数据旧请求字段的UnEscapeJSON协议与挂接后的填充行为。
- CLI代码回读比较忽略编译器生成的`/+ +/`注释，保留字符串字面量内容。
- 清除CommonUtil.UnEscapeJSON隐藏的原生JSON依赖，修复反斜杠占位词碰撞；15次跨后端代码往返通过，保留公共签名与请求编码协议。
- panwx25三后端各20项健康检查、真实PeopleCode往返/409以及147项JSON断言通过。旧版本实机尚待验收，保持dev.6，不覆盖历史zip。

## 2026-10-30：Service 删除集成

- 新增 service plan-delete/delete；只删空 SOAP/REST Provider 服务，不级联。
- 沿用 Write 操作及原权限，强制原始版本，核对 Serviceopr 与实际 ownedOperations；版本覆盖实际所属操作。
- dry-run、独立回读、工程79/Delete标记及失败恢复报告。
- 修复原生删除回滚后的删除缓存残留；逻辑属性恢复，定义/缓存版本推进并使旧计划失效。
- panwx25真实API/CLI、并发、回滚及Postman验证；保持dev.6，不覆盖历史zip。

2026-10-30 同日整理：`OperQueryRecord`、`OperExecSql` 移至 `C_META_DATA_PKG:MetaData:Read`，`OperExecSqlWrite` 移至 `C_META_DATA_PKG:MetaData:Write`；同步Handler和原生编译工程，删除旧RecordQuery/SqlExec子包。源码、URI和权限保持，SQL DML仍未授权。

## 2026-10-30 工作区更新：定义读写权限分离

- Service 拆为 C_META_DATA_READ / C_META_DATA_WRITE；16类定义各有独立 Read 操作，旧 AI_OPER 操作专用于写入，原空服务已删除。
- 入口位于 C_META_DATA_PKG:MetaData:Read / :Write，共享 Utility:MetadataAccess 与 CoreOper*；服务端动作白名单和逐调用实际许可权校验，保留原始版本保护。
- CLI 新增 env layout split|legacy，按环境路由查询；panwx25 的既有 C_MCP 权限保留，SQL DML 仍未授权。
- 验证及原生编译工程详见维护项目 read-write-20261030；本轮不升版、不重打历史zip，不声明其他环境或AD/PIA界面验收。

## 工作区更新（2026-10-29，四类定义版本保护）

- 新增 Utility:ManagedVersion 和 scripts/managed_operations.py，Service、Operation/Version/Handler/Routing/授权、消息集/消息/翻译、Portal 全部已开放写入强制原始expectedVersion。读取不存在状态，428/409、上下文快照、冲突保稿及全量范围版本保护已接入。
- configure-rest/configure-soap、整套操作删除使用完整原始计划，在单个服务端事务先核对所有版本再写入；禁止客户端中途取新版本。保留定义提交后回读/工程登记的部分成功报告。修正流程版本检查成功后非法子步骤的失败状态码，清除不可达的旧写入回退路径。
- panwx25 / Oracle / PeopleTools 8.60.10：隔离171项API、39项CLI，正式164项API、39项CLI，以及6项SOAP定义CLI、148个Postman请求/201断言通过。四类真实并发创建/修改、保存后异常回滚、关联目标与权限最后步骤竞争验证通过。
- 6个正式编译类新增/更新：ManagedVersion、CatalogLanguageAdapter和四个处理器。当前158成员/170实例/41程序，保留其他35程序；保持dev.6、不覆盖历史zip。版本控制为并发保护，不提供历史库，未新增AD/PIA或跨环境回导验收。


正式目标见 [发布规划](references/release-roadmap.md)。2.0.0-dev.6 是当前开发包；“内部实施记录”中的旧 2.x 是历史批次。

## 工作区更新（2026-10-29，独立 SQL / Project 版本保护）

- SQLType=0 的 create/modify 和 Project 的 createProject/modifyProject/insertItem/updateItem/deleteItem 全部要求原始 expectedVersion；读取不存在名称也返回 exists/version。缺少或空版本428、旧版本409，读取中变化拒绝。SQL令牌覆盖全部Statement正文、描述、翻译、哈希和删除行；Project覆盖头、完整成员/迁移/比较状态、删除与依赖/包含行。
- SRM/PJM及父行（Project另含成员行）锁内比较保存；Project去除内部提前提交，失败整次回滚。新增定义维护dry-run，SQL数据执行明确拒绝该参数。成功后独立回读完整目标和未修改内容。
- 新增scripts/sql_project_operations.py：结构及SQL工作副本快照绑定环境、服务器、节点、账号和完整键；缺快照拒绝，409另存最新内容且保留原稿，不自动重试。适配全部自动工程登记及删除程序登记；其他定义写前显式核对工程存在，避免新不存在快照语义造成部分保存。
- panwx25 / Oracle / PeopleTools 8.60.10：隔离和正式入口各通过57项真实API、44项真实CLI检查，真实并发创建/修改仅一方成功；两类原生保存后的异常注入回滚通过。正式Postman27请求/35断言通过。版本控制用于并发覆盖检测，不提供历史版本库；本轮未新增AD界面或跨环境迁移验收，保持dev.6。
- 补做10项正文/控制台/缺工程/执行参数检查、12轮快速SQL保存的原生/物理正文一致性，以及33项最终契约与清理检查；认证及20操作健康检查通过。保留SQL健康探针的不存在名称读取能力。7个SQL、6个Project夹具、2个临时类和2套接口/路由/权限已清理，部署辅助空工程保留。原生导出157成员/40程序，仅2个处理类变更，其余38程序保留，74项导出标记逐键恢复；共享源、release及安装副本同步，历史zip不覆盖。

## 工作区更新（2026-10-29，Menu 版本保护）

- Menu 的 create、modify、deleteChild、modifyCode、deleteCode 全部要求原始 expectedVersion，读取返回 menu1: 版本和 menuVersionControl=1；缺少/空版本428、过期409。令牌覆盖定义、栏/项目、多语言、删除/来源和菜单程序版本；PCM/MDM及父行锁内比较与保存。
- 新增 scripts/menu_operations.py：结构和精确 ItemSelected 快照绑定环境、服务器、节点、账号、菜单/栏/项目/事件；代码旁保存.snapshot.json。冲突另存最新内容并保留原稿和原快照，不自动重试。补齐 Menu 409 在通用写入恢复包装中的透传；删除备份和6/9类型完整工程登记沿用原生键。
- PANWX25 / Oracle / PeopleTools 8.60.10：81项隔离接口、38项CLI、8项正式端点实际写入/并发检查、21个Postman请求/30断言及全部20操作健康检查通过；另核对保存后冲突的本地部分成功报告。临时菜单/程序、类、接口、路由、权限和测试工程成员已清理，空测试工程保留。原生导出157成员/40程序，仅两个Menu程序变更，其余38程序保留并核对编译块；保持dev.6，不覆盖历史zip。未新增AD界面、业务页面运行或跨环境回导验收。

## 工作区更新（2026-10-29，HTML/StyleSheet 版本保护）

- 新增 scripts/content_operations.py，并将 HTML/StyleSheet 命令接入原始版本流程：先 struct、创建也读取不存在名称；结构与正文旁快照绑定环境、服务器、节点、账号、类型及名称。写入使用最初 expectedVersion，409保留原稿和快照、另存最新正文，不自动重试或换基线。
- 保存后独立回读内容和版本，再登记51名称/4或50名称完整工程键。已确认保存但回读冲突时保留409及部分成功报告；显式空文件仍可清空正文。
- OperHtmlDefn、OperStylesheetDefn和NativeAdapter已在panwx25编译部署；版本覆盖定义、翻译、正文BLOB、删除标记及CSS样式子结构。在CRM/SSM及父行锁内比较并保存，失败回滚。真实并发创建和修改均只允许一个请求成功；隔离故障注入已证明原生保存后异常会回滚正文、属性和版本。
- 隔离/正式入口各通过71项真实服务端和44项真实CLI检查；正式端点Postman18请求/26断言通过。另保留78项本机模拟CLI回归。12个临时定义及所属数据、3个隔离类、2套临时接口/路由/权限和测试工程成员已清理，空测试工程头保留。
- 原生完整工程导出仍为157成员/40程序；3个变更类的新源码和编译块已验证，其他37程序保留，73项导出改变的工程标记逐键恢复。同步共享源、release和已安装副本；保持dev.6，不重打历史zip。本轮未新增AD/PIA或跨环境迁移验收。

## 工作区更新（2026-10-29，CI 版本保护）

- CI 的 create、modify、deleteChild、modifyCode、deleteCode 全部要求原始 expectedVersion；读取返回 ci1: 版本和 ciVersionControl=1，缺版本428、冲突409。版本包含定义、映射、翻译行、删除标记和 Methods 程序；PCM/BCM及父行锁内比较与保存，失败回滚。
- 新增 scripts/ci_operations.py：结构及代码快照绑定环境、服务器、节点、账号、CI及类型；代码旁保存.snapshot.json，缺快照拒绝写入。409另存最新内容，保留原稿，不自动刷新版本重试；成功后独立回读并登记32/42类型完整工程键。
- PANWX25 / Oracle / PeopleTools 8.60.10 已通过隔离入口72项服务端和27项真实CLI检查、正式入口36项服务端和26项CLI检查、20个Postman请求/26断言及认证和全部20操作健康检查。覆盖实际并发、保存前竞争、失败回滚、dry-run与工程标记；临时CI、类、接口、路由、权限和工程成员已清理。未新增AD界面或跨环境迁移验收；保持dev.6编号，不覆盖历史zip。

## 工作区更新（2026-10-29，AE 版本保护与结构删除）

- AE 全部写入要求原始 expectedVersion；结构、代码及 SQL 返回 ae1: 版本和 aeVersionControl=1，缺版本428、冲突409。AEM/AES/PCM/SRM 锁内比较与保存，移除内部提前提交，失败回滚。
- 新增 ae delete-section/delete-step/delete-action，完整版本键、dry-run、静态 Call Section 引用保护、MAIN保护、原生 PeopleCode/SQL精确清理及 Copy/Delete 工程登记。struct 返回全部 Section，CLI 快照绑定环境与完整正文键，冲突保留改稿并另存最新结构。
- 修正实测阻断写入/删除验收的原有问题：SQL 新建空集合、精确 SQL 版本 upsert 与正文保留；State Record 原生字段和 Key 位、真实 Temp Table 类型；Call Section 参数次序与 Step 更新前加载。已有 Section 可新增独立市场/数据库/生效日期版本。
- PANWX25 / Oracle / PeopleTools 8.60.10：61项基础及70项深入检查、真实CLI工作流、29个Postman请求/34断言和全部20操作健康检查通过；覆盖九类Action、分支保留、级联、并发、失败回滚与工程标记。测试AE、临时类/接口/路由/权限和工程成员已清理。未运行业务AE任务或新增AD界面验收；保持dev.6编号，不覆盖历史zip。

## 工作区更新（2026-10-29，Component Toolbar 与 Pagebar）

- 补齐 Toolbar 18 个按钮、Disable Toolbar、Pagebar 四个链接和 Disable Pagebar 的 CLI/API 局部修改与语义回读；componentInternetPropertyVersion=2，兼容前七项属性。
- 按 AD 单变量证据处理 TBARBTNS、SHOWTBAR 的独立位及反向位；动作联动先于显式按钮设置，拒绝显示未启用动作的按钮。总开关保留子选项，未指定位保留。
- PANWX25 / PeopleTools 8.60.10 验证 AD 原始表回放、CLI、版本冲突和并发、Pagebar 组合及 AD 关闭重开；其他 Tools/数据库和 PIA 运行行为未验收。保持 dev.6 编号，历史 zip 不覆盖。

## 工作区更新（2026-10-28，Component Internet 属性 1～4）

- 新增 Primary Action、Default Search Action、Default Search/Lookup Type 和四个 Multi-Page Navigation 开关的 CLI 参数、服务端校验及原始字段/语义开关回读；能力标志为 componentInternetPropertyVersion=1，沿用 c1: 原始快照与工程登记。
- 按 AD 证据处理 Keyword Search 默认 Keyword Only、离开 Keyword Only 回退 Basic、默认动作不可用时的回退，以及 History 强制 Return、关闭 History 保留 Return。修正仍有其他搜索动作时错误切走 Search 的旧联动，保留所有其他工具栏/Pagebar 位。
- 最后一种搜索动作关闭时按 AD Internet 页保存禁用空白默认值 10；补齐 Component 错误响应的 JSON 转义，保证异常堆栈换行可被标准客户端解析。
- Toolbar 其余按钮与 Pagebar 未纳入本批；本批按 PANWX25 / PeopleTools 8.60.10 验证定义持久化及 AD 展示，不扩展到其他 Tools/数据库或 PIA 搜索运行行为。

## 工作区更新（2026-10-27，Component 属性与版本控制）

- 新增 Component 描述、注释、搜索记录、四种 Actions，以及已有页面 Hidden / Item Label / Folder Tab Label 局部修改；按 AD 样本处理搜索记录回退、工具栏动作位和主操作联动。
- Component 创建、修改和 PeopleCode 写入均要求原始版本；CLI 结构/代码快照绑定环境、账号、Component、Market 和程序键，冲突保存最新结构，不覆盖原稿。属性和程序写入独立回读后登记完整工程键。
- PANWX25 / PeopleTools 8.60.10 完成 AD 单变量、关闭重开回读、真实并发竞争、缺版本与旧版本拒绝、CLI 属性和 Component 级程序创建/删除、特殊字符注释检查。核心工程重新原生导出，保留编译块；其他 Tools / 数据库和 PIA 行为未验收。

## 2.0.0-dev.6（2026-10-27，Page版本保护与12项属性）

- Page全部写入要求expectedVersion，覆盖16张Page表及Activate；稳定读取和事务内比较，缺版本428、冲突409。修正PDM缓存/定义版本维护和长注释更新保留未指定Page头字段。
- CLI结构/代码原始快照绑定环境、账号和页面；冲突另存最新内容、保留原稿，独立回读后登记Copy/Delete工程键。
- 能力7加入Show Label、Enable When Page Display Only、Wrap、JavaScript、Generate HTML、Popup及六项数字/日期格式属性；按控件和字段类型限制。修正DDL清除Invisible和Disabled清Wrap联动，Page Field Name收紧18字符，高位解码避免Mod整数转换。
- 控件写入收敛到已有证据的Edit/DDL；未验证类型/属性拒绝，未知位保留，其他控件只读保留原始列。后续每批10–20属性。
- PANWX25/8.60.10：65项接口/并发检查、14项原始AD差异的16表对照、CLI结构与代码流程、Postman17请求19断言通过。原生编译和包含编译块的完整工程导出；无新增GUI/PIA验收，仍为开发包。

## 工作区更新（2026-10-25，Edit/DDL显式布局）

- 能力6新增标签位置及完整矩形、FIELDSIZETYPE尺寸模式和Custom整体平移；CLI检查能力、参数冲突，并独立核对主控件及标签边界和保留位。旧坐标参数保留逐列修改语义。
- 切换自动模式的字体测量、缓存推导与网格吸附尚未自动实现，要求显式提供原生边界。五类Item全部操作与Page版本保护继续，不构成任何Item完整验收或正式发行。

## 工作区更新（2026-10-25，DDL显示模式与提示字段）

- 能力5新增displayedText与promptField修改参数，模式切换保留共享格式位，切Xlat清提示字段；支持按Record字段派生提示表并显式指定列表显示字段。CLI检查服务器能力并独立回读，拒绝不适用或矛盾请求。
- 由AD保存15,84暴露的ADDRESS_TYPE固定Xlat默认缺口，现可用CLI显式配置有效Prompt模式/显示字段；完整新增默认、自动选择、其他条件与五类Item完整范围继续。

## 工作区更新（2026-10-25，Drop-Down Label 联动）

- 按DDL自身AD单变量证据实现No colon、First occurs only、标签三种对齐、None/Text/RFT长短切换、显式ID及恢复默认源；保留Xlat/Prompt位及默认选择，修复旧标签写入的不等价行为。能力标识4，CLI在能力3服务上拒绝DDL标签修改。
- 本次仅补已取得证据的标签联动，五类Item完整属性、布局与容器操作及Page版本控制继续；不形成正式发行包。

## 工作区更新（2026-10-25，Page 基准标签与 Edit Label 联动）

- 新增Edit/DDL按真实默认标签解析ID和基准长文字；修正默认ID不等于字段名的情况。Edit修改标签ID、默认选择、长短类型时同步文字；None/Text保留标签源，修正旧默认标志反向写入。
- 新增No colon、First occurs only、Label Alignment及Use Default Label参数，能力标识3；保留Record/Label共享位、明确拒绝不适用与冲突请求。三个默认标签、11项AD精确列差异重放、共享位组合及8项API原子拒绝通过；Edit/DDL首次新增98列除Page名与原始AD基线一致。
- 这是五类Item完整支持过程中的局部修复，全部属性、布局、容器子Item和Page版本保护继续；DDL已验证的标签修改语义由后续能力4补充。详见Page参考，仍未发行。

## 工作区更新（2026-10-24，Page 控件首批纠错与属性）

- 按 AD 单变量证据纠正 Page FIELDUSE：只读值1、显示控制值8；删除错误的 required/key 解码并拒绝 required 写入。新增 capability 标识、未知参数和二值参数校验；失败回滚。
- Edit/DDL 新增七项 Use/General 属性；补齐新增控件 EXT 基础行、字符0标志与标签边界0，DDL 默认改为 Xlat Short。CLI 先读能力、写后独立回读并登记工程，拒绝不适用参数和尚未支持的控件 dry-run。
- PANWX25 / 8.60.10：12项 CLI 与 AD 原始列差异重放、9项 API 拒绝、3项 CLI 拒绝、4项客户端检查通过；AD 打开控件并核对属性。完整五类 Item、默认标签/布局联动、容器子项、Page 版本冲突保护及最终运行验收继续进行；本批不代表任何 Item 完全支持，不创建正式发行包。

## 工作区更新（2026-10-24，Edit Record 属性第二批）

- Edit Box新增对齐、填充字符、Password/Input Only、Prompt Button、Auto Fill及Spell Check七项属性，能力标识2。按AD证据处理Spell Check与Prompt联动，Password关闭保留Input Only标志；拒绝矛盾请求和非Edit控件误用。
- CLI新增对应参数、按属性检查服务器能力，并验证DSPLFORMAT/FIELDUSETMP/EXT共享位保留；Basic与Record组合补丁不会覆盖其他指定值。14项AD列差异重放、共享位组合、8项API和2项CLI拒绝、3项新及4项既有客户端测试通过；其余Page长期范围继续。

## 工作区更新（2026-10-24，Field / Record 删除与并发版本）

- Field/Record 精确 struct、代码/SQL 读取返回作用域版本；全部写操作必须携带 expectedVersion，缺少返回428，冲突409。共享 DefinitionVersion 在 RDM/PCM/SRM 锁内校验，覆盖子记录、祖先及程序/视图SQL；批量Field先核对全部版本后原子写入。
- 新增 Field/Record 原生定义删除、Record 直接字段/子记录引用删除，Record 程序删除增加版本保护。返回完整迁移键，dry-run不写入；定义删除保留物理表/视图，引用中的Field/子记录拒绝直接删除。
- CLI新增field命令和record delete/delete-field，绑定身份与对象/事件/SQL变体的下载快照，冲突另存最新内容并保留原稿，写后独立回读与Copy/Delete工程登记；响应不明的Field写操作不自动重试。
- 修复Record读取空Rowset假字段/索引、事件过滤，以及嵌套子记录展开与顺序；末字段删除后保持空结构可编辑。验证与限制见Record/Field参考；工作区更新不创建正式Release或版本zip。

## 未发行工作区变更（2026-10-23，OperAppPackage）

- 新增应用类、子包子树和整个应用包删除；原 deletePeopleCode 保留类壳。子包删除规避当前原生 DeleteDefn 按根包删除的行为，精确维护语言行、删除标记及缓存版本。
- 结构和代码读取返回原生版本及 version 令牌，所有写操作必须传 expectedVersion；加锁后校验，冲突返回 409，缺版本返回 428。AD 保存同样使旧令牌失效。新增类附带代码编译失败会回滚类壳。
- CLI 保存环境绑定的结构/代码快照；冲突另存最新内容，保留本地改稿，不自动重试。写后验证完整 Project 键和 Copy/Delete 标记；OperAppPackage 自身通过 AD 编译保存，接口拒绝自修改和删除其祖先。
- 当前仅在 PANWX25 / Oracle / PeopleTools 8.60.10 验证，未新增正式 Release 或版本 zip。

## 2.0.0-dev.5（2026-10-23，Project AD 元数据一致性）

- Project 创建直接保存原生 KEEPTGT=31、REPORTFILTER=16232832、COMPARETYPE=1、TGTORIENTATION=0、COMMITLIMIT=50；修复封装属性未持久化导致的差异报告缺失。原生 PeopleCode 对照中，代码差异相同、只改变 REPORTFILTER，旧值报告 0 项、修复值 1 项，包含赋值 1→2 的逐行差异。
- 描述及注释局部更新保留全部未指定头属性，支持显式空字符串清空；新增 project modify --ad-defaults，按明确请求恢复五个默认选项，历史工程不批量重置。struct 新增全部头字段字符串表示、NODETYPE/SOURCESTATUS/TARGETSTATUS；长注释按 JSON 正确转义。
- 重复插入不新增成员，恢复 Unknown、Copy/on/off；显式 Delete 仍用 Delete/on/off，实际写入的自动登记采用相同行为。服务端默认 Upgrade=on，实际成员变化维护原生头版本、时间及操作人，同值更新不改头。保留复合键内部空格及 57 类型存在性校验。
- Action 接受 0～3，移除与 AD 消息目录 CopyProp 实测冲突的类型限制；Record/Field 以外仅验证枚举保存，未宣称目标库复制语义。补充名称、描述和键值长度校验；客户端创建、插入和修改均独立回读，旧处理类缺少新字段时不误报验证成功。
- PANWX25 / 8.60.10：AD 9 类完整成员字段对照、41 项在线断言、30 类 Project 登记和 55 项既有本地回归通过。图形交互弹窗未完成核验；项目多语言、ADS、SEC/WORK 等无正向基准的范围保留未验证。未创建正式发行或提交推送。

## 2.0.0-dev.4（2026-10-18，SOAP 与消息多语言）

- 同步 SOAP Provider 支持服务、操作、REQUEST/RESPONSE/可选 Z_FAULT、Application Class Handler、Routing 和指定现有列表授权；拒绝已有定义转换协议、异步及 SOAP 混用 REST URI/方法。新增 configure-soap 和只读 WSDL/XSD 导出，局部覆盖导出地址不修改全局 Target Location。
- Message Catalog 新增 --language，独立维护非基准语言的 text/explanation；缺失翻译显式返回 translationExists=false。完整快照覆盖基准消息和全部翻译，保留数字占位符及重复次数；删除最后一条翻译仍保留基准消息，类型 25 工程条目为 Copy。配套 C_META_MSG_LANG Page/Component/CI/SavePreChange 使用标准 PPC 缓存版本维护。
- PANWX25 / PeopleTools 8.60.10：翻译 CRUD、长说明/特殊字符、旧快照/占位符拒绝和 AD 无错误校验通过，交付 PIA 页面显示英语/法语且基准消息不变。SOAP PIA 搜索/服务关联/Handler/Routing/C_MCP 完全访问核对通过；原生文件工程回导后 SOAP 1.1/1.2 实际请求均 HTTP 200，缺少凭据被拒绝，WSDL 和两个 XSD 可解析。
- 19 项专用工程全类型原生比较零差异并回导；核心本批变更的 Page、Component、CI、Component PeopleCode 和应用包 PeopleCode 补做比较/回导。27 份维护源码及 11 个关联定义保持一致，六个工程成员和迁移标记恢复；另验证原生复制不会清除缺席翻译，删除结果新增目标环境重放参数；基础和相邻翻译保持不变。
- 修复 Page 新控件 FIELDNUM 使用 Record 字段序号导致滚动层级错误，新增 longEditBox；修复消息集显式首条编号 1 的创建；query-record 字符串按 JSON 正确转义，69 项直接查询回归及高精度数值/长 CLOB 通过。55 项既有本地回归与 8 项新增流程测试通过。
- 完整原生导出含 156 条目、168 实例、39 程序；36 个必需类、22 操作、98 项引用及新增组件依赖检查通过。SOAP 运行时 Schema 校验 Validation=Y 仍有间歇性 119,40；本次成功调用基线为 N，不声明该问题已解决。Consumer/异步、CI 引用及 CI 多语言子结构继续后置，空白环境安装未验收。未创建正式发行或执行提交/推送。

## 2.0.0-dev.3（2026-10-17，CI 自定义方法、迁移验收与失败恢复）

- 三类新定义完成 AD 关闭重开；CI 原生校验无错误，搜索键、集合映射和五个标准方法选项正确。StyleSheet 经实际 PIA 页面引用 PeopleSoft 缓存，计算颜色及中文反斜杠伪元素符合预期；临时页面控件已清理，原控件保留，未保存业务数据。
- CI 新增 view-code/modify-code/delete-code，按一个 CI 的完整 Methods 程序维护，写入核对 expectedCode 并原生编译，拒绝空白代码；明确删除前保存唯一备份，保留父 CI、标准方法和映射。19 项实际编译、冲突、删除、重建验证及 AD 重开通过；Project 类型 42，键为 CI/Methods（74/12）。CI 引用和多语言子结构按用户决定后置。
- 原 8 项新定义专用工程、151 项工具核心和 35 项成熟对象工程完成同环境原生 Copy From File，回读 26 份维护源码及 12 个成熟关联定义一致，五个工程成员与迁移标记恢复。CI 处理类改动后重新导出含编译内容的完整核心 XML，并对 37 个应用包程序和新增 CI Methods 程序补做原生比较/回导入；专用工程增为 9 项。文本 LF→CRLF 规范化按内容等价核验。成熟工程首次比较超时，保留 19 类无差异报告并只补跑剩余 Routing，未误报首次完整成功。
- CLI 写流程失败时输出并可保存 incomplete 恢复记录，列明已收到响应的写请求及最后请求；不自动回滚或重复提交。服务端 JSON 应用错误改为可捕获异常，使后续步骤拒绝也能被恢复流程报告。
- configure-rest 每步刷新快照时核对预检状态，拒绝非派生字段的并发修改，允许原生维护的关联列表更新。47 项既有本地回归、8 项新增恢复/并发/CI 程序测试及两种真实保存后的故障注入通过；80 项新 REST、21 组列表、15 项成熟对象拒绝保护和 8 组主要工作流复验通过。
- 本包仍为开发验收包，未创建正式发布、提交或推送。空白环境首次安装维持已确认的延期安排，原 jt-dev 错误工程未清理。

## 2.0.0-dev.2（2026-10-17，定义维护与列表分页开发包）

- 新增 ci/html/stylesheet 的读取、新增、局部修改；CI 支持标准方法开关、键/集合/字段映射及精确子项删除，StyleSheet 写入限定独立自由格式类型 2。新接口要求修改快照，保存后独立回读并登记确认的工程。
- 新增 AI_LIST_DEFN 和八类 list 命令，支持字面前缀、1..200 条游标分页和门户内容类型筛选；不改变旧 search 类型。
- 57 类型应用包非 Delete 工程插入核实原生存在性，拒绝把类路径段当作 Package/Root/Qualify Path。根包使用点号，一级子包使用冒号；历史错误工程未自动清理。
- panwx25 / Oracle / PeopleTools 8.60.10：80 项新接口 REST 回归、21 组列表验证、47 项本地回归和五类既有维护流程回归通过；PSTOKEN_GET + 20 操作健康检查通过，SQL 写权限保持关闭。原有三个工程保持不变。
- 原生导出 151 条目、163 实例、37 程序；26 份维护源码及编译块一致，35 个必需类和 22 个操作依赖通过。保留服务器 2026-10-14 已有的 MappingUtil 未知数据库类型拒绝修复；临时探针未进入包。
- AD 打开、StyleSheet 页面效果、三类完整迁移和五类成熟矩阵仍待验收；本包不代表正式 2.0 完成。

## 2.0.0-dev.1（2026-10-12，SQL 执行开发验收包）

- 新增 sql exec/run/write；SQL 文本和已登记普通 SQL 定义只读，写模式支持单条 INSERT/UPDATE/DELETE/MERGE。CLI 在 HTTP 前校验，服务端独立限制类型、绑定、语句、WHERE、meta-SQL 和结果容量；原有 SQL 定义维护命令兼容。
- 新增 OperExecSql、OperExecSqlWrite、SqlTextGuard 和两条独立授权的 REST 操作。SQL 定义通过原生 FetchSQL 选择当前数据库/as-of 正文，再分类执行同一文本；权限每次重新核对，写操作默认关闭。
- C_AI_SQLAUD 存储写入操作者、SQL 全文、绑定摘要和结果。DML 与成功审计共同提交；失败回滚后另存失败审计。审计故障注入、并发重复键和重复提交实际行为已验证，不提供自动重试或幂等保证。
- PANWX25 / Oracle / PeopleTools 8.60.10：113 项直接 REST、9 项平台/事务故障补验、14 项新增本地测试与 33 项既有本地回归通过。基本健康检查覆盖 PSTOKEN_GET + 16 个必需操作，可选写探测只拒绝空 SQL。
- 原生导出 131 条目、143 实例、33 个程序；20 个维护源码和编译块核验，原有 30 个程序源码保持一致，临时探针未进入包。配置未改；CI/HTML/StyleSheet 等 2.0 后续范围继续按规划推进。输出类型、NULL、绑定及安全边界见 [SQL 执行](references/10-sql-exec-api.md)。

## 1.5.0（2026-10-11）

基于 rc.2 完成第二轮独立复验并形成正式发行包，服务端工程与 CLI 运行逻辑保持 rc.2 基线；XML SHA-256 为 `a0ace30fe7b3ee24dee7fb44c2391368629280aa2c9ce570756ccd2a28a905ba`。

- 提供同步 REST 服务/服务操作、标准及弹出菜单、基准语言消息目录、已有门户的 Folder/CREF/Link 维护，以及完整键的 Project 登记和写后独立回读。
- 修复历史 PeopleCode 真正删除、查询动态 SQL 输入、Record 中间 Key/索引及属性显示、服务所属关联和门户属性导航问题；父定义与相邻程序保留，分步失败明确报告。
- 第二轮复验：28 个必需类服务器源码与包内逐字匹配，76 项自定义依赖引用解析；本地测试按 24 + 9 + 8 + 12 执行通过，另有 3 项闭包负例与 2 项 Page 离线 mock。69 项查询 REST、33 项拒绝保护、七类删除状态、七组主要工作流、完整健康检查及浏览器弹出菜单运行均通过，三个工程保持不变。
- 恢复 `.gitignore` 原有凭据、Token、运行报告和备份排除规则；正式包只含 30 个运行文件、工程、文档与示例，验证材料保留在维护工作区。
- 验证范围为 Oracle / PeopleTools 8.60.10。空白环境首次安装按已确认决定延期；SOAP/Consumer/异步、多语言、整份 Service/Menu/Portal 和门户文件夹删除后置，CI/HTML/StyleSheet 留待 2.0。

## 1.5.0-rc.2（2026-10-11，候选包，未正式发布）

候选包小修，服务端工程未变（XML 保持 rc.1 哈希 `a0ace30fe7b3ee24dee7fb44c2391368629280aa2c9ce570756ccd2a28a905ba`）。发布依赖检查新增**依赖闭包核验**：扫描全部 PeopleCode 源码的 `C_*:*` 类引用（含包级前缀）、`Record.C_*` 自定义记录与 `PS_C_*` 自定义表，未解析即失败；当前包 76 项引用全部解析，3 项负例回归通过。`query-record` 文档更正 `fields[].label` 当前固定为空（与实测一致）；`page modify-code` 对不存在的文件路径按内联正文处理，不再抛裸异常（离线 mock 两项通过）；`--timeout` 补进公共调用规则文档。PANWX25 健康检查（PSTOKEN_GET + 15 操作）与本地回归 41 项（validation 24、query guard 9、transport 8）复跑通过。正式 1.5.0 尚未发布。

## 1.5.0-rc.1（2026-10-11，候选包，未正式发布）

1.5.0 范围已收口。本包在 dev.3 基础上定版：重新执行原生导出（110 条目、122 实例、30 个 PCM；17 个维护类源码与编译块核验通过；清单无增删、程序内容无变化，仅导出元数据变化，XML SHA-256 更新为 `a0ace30fe7b3ee24dee7fb44c2391368629280aa2c9ce570756ccd2a28a905ba`），恢复导出改变的 16 个 Done 标记。PANWX25 健康检查（PSTOKEN_GET + 15 操作）与本地回归 41 项（validation 24、query guard 9、transport 8）通过，发布依赖检查通过。空白环境首次安装核验延期至首次真实部署（当前无可用空白环境）；安装证据为同环境原生比较/回导入、依赖与编译内容核验、授权与健康检查。正式 1.5.0 尚未发布。

## 1.5.0-dev.3（2026-10-11，未正式发布）

维护工具整理，服务端工程与数据契约未变：`C_META_DATA_PKG.XML` 保持 dev.2 哈希，未重新导出。bundle-check 从 skill 移出为维护侧 `tools\check_bundle.py`，必需类由 21 个补全到 28 个（补 OperProjectDefn、OperSqlDefn、SearchDefinition、Login、MappingUtil、RecordUseEdit、HttpUtil），并新增 PCM 源码/编译内容与操作处理程序绑定检查，6 项负例回归通过；新增 `tools\sync_skill.py` 管理共享源 → release 镜像、5 个 Agent 安装副本与打包的单向同步和差异检查。两处文档去掉对已移除命令的引用，SKILL.md、README、SECURITY、已知问题和发布规划同步版本字样。PANWX25 健康检查（PSTOKEN_GET + 15 操作）通过，本地回归 41 项通过（validation 24、query guard 9、transport 8）。正式 1.5.0 尚未发布。

## 1.5.0-dev.2（2026-10-11，最终验收包，未正式发布）

修复 dev.1 原生回导入复验暴露的 180,236：不存在程序的空值响应不再依赖 GetJsonNode 后 SetNull。Page、Record、Component、应用包保留空字符串正文及 programExists=false；七类连续五轮回读通过。重新编译并原生导出 110 条目/122 实例，17 个维护类源码与编译块核验，全部 30 个 PCM 实例均含源码和编译内容；再次完成同环境比较/回导入和工作流复验。共享、安装、发行目录均为 dev.2，dev.1 证据保留为历史记录。

删除快照唯一标识移至文件名前部，避免长类路径经 120 字符截断覆盖旧快照；12 项删除回归、合计 45 项本地回归通过。bundle-check 增加 CommonUtil、JsonUtil 依赖核验。正文不存在时允许 null/空字符串的旧客户端保持兼容；应使用 programExists 判断原生存在性。正式 1.5.0 尚未发布。

## 1.5.0-dev.1（2026-10-11，首轮验收包；回导入读取缺陷已由 dev.2 修复）

- query-record 的 CLI 与服务端限制名称、JSON 类型、操作符和参数边界；服务端核实字段归属并绑定值/行数，移除 Rowset 回退与空白占位行。69 项直接 REST 及字符、精确数值、日期/时间、空值、CLOB 验收通过。
- Page、Record Field、Component 三层、AE Action 和应用类程序新增 delete-code；删除前快照并核对完整原生键，删除后独立检查不存在，按完整 Project 键登记 Delete/Upgrade on/Done off。保留父定义和相邻程序，dry-run 不写入；登记失败报告部分成功。
- modify-code 在 CLI 和服务端拒绝空白代码；Component 的读、写、删正确转发 market。AD 重开确认 Page Activate 普通字重、Record Required/Prompt Table Edit/COUNTRY_TBL 正确，PIA 实际触发测试弹出菜单。
- 原生 Menu API 不能持久保存的 AllowedActions/AddSearchRecName 改为只读，CLI 与服务端提前拒绝写入。
- 原生导出 110 条目、122 定义实例，17 个维护类源码与编译内容核验；恢复本次导出改变的 16 个 Done 标记。共享、安装、发行目录同步同一包；版本统一为 1.5.0-dev.1，保留内部批次历史。
- 本地 44 项回归、空白/非法键/菜单属性 33 项直接 REST、认证及全部 15 个元数据操作健康检查通过。正式发布状态见规划；验收包不代表已发布 1.5.0。

## 内部实施记录

| 批次 | 日期 | 变更与验证 |
|---|---|---|
| 2.4.2 | 2026-10-11 | ObjectKeyResolver 使用未保存的空原生 ProjectDefn，NativeAdapter/MenuCodeAdapter 去除固定核心工程依赖；bundle-check 检查解析器。PANWX25 验证工程外菜单/代码、新名称、保存/删除和门户运行时；原生导出 109 条目、10 个编译类 |
| 2.4.1 | 2026-10-11 | 服务操作同步 Serviceopr，门户属性限制单字符串；初始化 CREF 默认属性并修复 Link URL，新增 portal validate。PIA 验证搜索、Handler、Routing、权限分组及目录/链接 |
| 2.4.0 | 2026-10-11 | 新增服务、服务操作、菜单、消息目录、门户五组命令；局部补丁、快照、dry-run、回读、工程登记；修复 JSON 转义，未知写结果不重试，健康检查扩至 15 操作。初版门户属性多值缺陷于 2.4.1 修复 |
| 2.3.1 | 2026-10-10 | CLI/PeopleCode 限制 CopyProp 仅 Record/Field；纠正此前组合测试无法证明各类型支持 CopyProp 的说明 |
| 2.3.0 | 2026-10-10 | Project Action/Upgrade/Done 独立/组合更新，完整键自动解析与保存回读；PANWX25 验证多类定义标记 |
| 2.2.0 | 2026-10-10 | Record 新普通字段 insertBefore，校验失败回滚并同步缓存/主索引；C_AI_KF1010 的 NAME 插于 COUNTRY/金额字段之间并设 Key，AD 导出验证 |
| 2.1.0 | 2026-10-10 | SQL 默认平台与未匹配假成功修复，代码/SQL 回读，Project 完整键，Record 缓存/索引和 Alter 复制检查，Page 空正文状态/full 读取。空正文处理未实现旧程序定义删除；原生导出 79 项，TOOLSREL=8.60.10 |
| 2.0.0 | 2026-09-18 | 当时统一本地内部编号；修正 REST 授权、代码工作副本缓存及缺少密码时的 preflight 报错，未公开发行 |

## 已公开的标签

- **1.0.1（2026-09-18）**：修正 README 通用 skill 定位，同步元数据版本。
- **1.0.0（2026-09-13）**：首次公开 skill、CLI、接口参考和 AD 文件工程。
