# 开发规范

通过本 skill 开发或审查 PeopleSoft 定义前必读。维护工具本身还需读取 [架构与交付边界](architecture.md) 和 [发布规划](release-roadmap.md)。对象的详细契约按下表加载。

## 环境、对象和工程

- 沿用用户已指定的环境和确认的 Project；`active_project` 仅提示上次选择，没有明确归属的写任务再确认。
- 修改前搜索并读取定义、代码与属性；通过 API 取得类型、事件和完整键。业务字段映射不明确时列出候选名称、类型和长度确认；已有明确映射核实后复用。Record 引用的 Field 必须已存在。复用未修改的系统标准 Field 不单独登记工程；Record 字段层的 Key/Required 等属性随 Record 迁移。只有新增或实际修改全局类型、长度、Label 等 Field 定义时才登记相应 Field。
- 只读不登记工程。创建/修改后以返回完整键重新 insert-item，即使成员已存在也恢复 Unknown / Copy / Upgrade on / Done off；只调整指定标记且保留比较结果时使用 update-item。
- 明确删除整个定义/程序使用 Delete/on/off；Label 单删登记父 Field Copy；Record 子字段删除的父 Record Copy，失效程序 Delete。按响应逐键处理，工程删成员不等于删定义。
- split 入口使用 MetaData:Read / MetaData:Write；内部 CoreOper* 不绑定 Handler。新增动作同步两侧白名单及 `scripts/metadata_routing.py`，新增类型同时补操作、权限、健康探测和完整编译工程。失败不退回旧混合入口。

维护 C_META_DATA_PKG 核心工程时只纳入实际运行依赖；测试/演示、电子表格及测试删除键留在辅助/独立工程。消息翻译复用交付 MESSAGE_CATALOG1 / MESSAGE_CATALOG_CI，不能恢复已退役的自建定义。

## 原始版本、保存和失败

所有已开放定义写入都使用先前读取的原始 expectedVersion；创建前也读取不存在名称。不能以保存前的新读取替代原始基线。正文工作副本旁的 `.snapshot.json` 或显式 `--snapshot` 需精确匹配对象、子键和程序。

| 对象 | 原始基线和特殊约束 | 契约 |
|---|---|---|
| 应用包 | 根包级 struct / 程序快照；当前执行的 OperAppPackage 只能在 AD 修改；类、子包、根包删除单位不同 | [应用包](03-app-pkg-api.md) |
| SQL / Project | SQLType=0 按精确 Statement；Project 按完整结构，全部写操作带版本。自动登记另读工程基线，不存在工程明确失败 | [SQL](04-sql-defn-api.md)、[Project](11-oper-project-defn-api.md) |
| Field / Record | struct；包括创建、Build、标签及子字段删除。代码/视图 SQL 使用精确正文快照 | [Record / Field](06-record-defn-api.md) |
| Page / Component | struct 或精确代码快照；Page 仅开放有证据的 Edit/DDL 属性，未知位保留；Component 含 Market 和层级键 | [Page / Component](07-page-defn-api.md) |
| AE | 结构或精确程序/SQL 快照；删除精确 Section/Market/DBType/EffDt/Step/Action，MAIN 和剩余静态调用引用拒绝 | [AE](05-app-engine-api.md) |
| Service / Operation | 先 view/struct；配置用 plan-configure，整套操作及空 Service 删除用 plan-delete。同一事务核对原始计划全部版本 | [服务](12-service-defn-api.md) |
| Menu | struct；ItemSelected 快照绑定 Menu/Bar/Item/Event | [Menu](14-menu-defn-api.md) |
| Message Catalog / Portal | view/struct，版本和配置/删除计划按对象接口；不能假设跨定义步骤共用事务 | [消息目录](15-message-catalog-api.md)、[Portal](16-portal-registry-api.md) |
| CI / HTML / StyleSheet | struct 或正文快照；CI Methods 另核原始 expectedCode；HTML/StyleSheet 限已支持类型 | [三类定义](17-ci-html-stylesheet-api.md) |

1. 保存写前结构或正文，仅提交任务所需修改。全量替换字段（如 fieldProperty）先合并原值；局部补丁省略项保持原值。CLI 业务补丁不覆盖操作、版本和 dryRun；直接 API 显式传入。
2. 正文/复杂 JSON 使用 UTF-8 文件。旧代码和新对象接口的编码不同，不能统一 Base64 或双重转义。
3. 保存后独立回读目标和关联，确认未指定属性保留。CLI 已验证正文无需重复同一检查；直接 API/自定义路径自行核验。
4. 428/409 保留改稿和原快照；需要时另存最新正文，不自动换基线重试。响应不明先回读当前状态，不盲目重发。
5. 编译、保存、回读或工程登记失败均如实报告。定义提交后回读/登记失败为部分成功，不能声称共同回滚。dry-run 只证明计划检查；Oracle DDL 不能整体回滚。

## 定义与子对象删除

Field 仍被 Record 使用时拒绝删除；Record 直接字段/子记录移除保留全局定义，按计划核对祖先展开、失效程序及相邻对象。定义删除不自动 DROP 物理表/视图，物理结构变更需要明确 Build/Alter。

Label 用 deleteLabel / field delete-label 精确删除；默认标签必须指定同字段已有替代，末标签及 Record/展开Record/Page 显式引用拒绝。先保存标签、翻译/上下文恢复数据并用 dry-run 核对；回读剩余标签和新默认。不能用整个 Field 原生删除管理器处理 Label 子键。

AE 删除仅清理对应完整键的程序、SQL 段和消息参数，保留其他分支；父定义与删除程序分别按响应登记。空 SOAP/REST Provider Service 可删除，非空服务及隐式级联拒绝。其他整份定义删除是否开放以对象契约为准。

## PeopleCode 真正删除

modify-code 拒绝空白正文；删除精确程序使用 delete-code，保留父定义和相邻程序。Page 为 Activate；Record 为 Record/Field/Event；Component 含 Market 和 Component/Record/Field 层级，指定 Field 必须指定 Record；AE 含全部版本键；应用类包含完整包路径并保留类壳。

| 程序 | Project objectType | 完整键要求 |
|---|---|---|
| Record Field | 8 | Record / Field / Event |
| AE | 43 | value2 含 Section+Market+数据库原生名+生效日期固定长度复合键；Step / OnExecute |
| Page | 44 | Page / Activate |
| Component / Record / Field | 46 / 47 / 48 | 保留 Market；48 的 value4 为固定长度 Field+Event |
| 应用类 | 58 | 根包至类按位置分段，未使用值保留原生返回形态 |
| CI Methods | 42 | CI / Methods，ObjectID 74 / 12；删除整份 Methods 程序，保留标准方法和映射 |

必须使用处理类返回的完整 objectId1～4 / objectValue1～4；不手拼 AE/Component 复合键，不统一把空字符串改为空格。Page/Record/Component/AE/应用包的旧接口使用 deletePeopleCode，expectedCode 按 CommonUtil 编码；Menu/CI 使用 deleteCode 和普通 JSON 正文，CLI 自动处理差异。

CLI 使用明确或已确认的 Project：先读正文和 programExists，保存 UTF-8 快照，再以 expectedCode 及适用版本校验。服务端通过原生 PeopleCodeProgram_Manager.DeleteDefn 后验证不存在；CLI 独立回读并登记 Delete/on/off。缺快照、过期或不存在的程序拒绝；程序已删但登记失败如实报告，不盲目重删。`--dry-run` 不删除/登记；响应正文空不代表不存在，核对 programExists。

## PeopleCode 实现和原生键

- 应用类的外部 Declare Function 放在 end-class 后、方法实现前，不能放在 import 与 class 声明之间。
- 类内私有调用用 `%This.MethodName(...)`，REM 注释以分号结束。CreateRowset(Record.X) 的独立 Rowset 初始有一行空行，构造数组前确认复用/插入位置。
- 独立 IB 上下文优先 `&rec.GetField(Field.X).Value` 赋值；方法返回值先存局部变量再判断，保留编译错误及位置。
- 嵌套 Evaluate、块内 Local、JSON 数字/跨方法传值的历史差异按当前 Tools 实测；必要时改为 If、方法顶部声明或明确参数类型，不能推广为全部版本的语言限制。
- JSON 和电子表格 Java 热路径复用 JavaReflect 的明确签名、装箱和参数清理，不重新引入直接创建热点；配置及示例见 [架构](architecture.md)。

复用 `Utility:ObjectKeyResolver`，不要为解析编号加载固定 Project 或创建真实临时工程。它用 `%metadata:ProjectDefn:ProjectDefn_Manager.CreateDefn()` 创建不保存的空 ProjectDefn，调用原生 GetObjectIDs；实例内复用，不跨请求全局缓存。

GetObjectIDs 接收非负 objectType 和四位置字符串数组，返回四个 ObjectID，主键类型为正，未用位置可为 0；不能省位/改序。ObjectID 是键类型，解析成功不证明定义存在。Menu 程序按菜单/栏/项目/事件，Portal 按 PortalName/RefType/ObjName/空白。NativeAdapter 与 MenuCodeAdapter 统一调用解析器；完整交付包含三者。业务定义不必属于核心工程，实际登记使用用户确认的 Project。

## 验收、工作副本与维护

报告具体环境、对象和完整定位、修改值、回读结果及失败阶段。API 成功只证明对应阶段；服务关联/路由/权限用 PIA，门户用 validate 加实际导航，外部 Record 修改后关闭重开 AD。BUG 只在复现条件消失且相关验收通过后关闭；未验证、暂不支持、明确延期分别记录。

服务端源码修改后原生导出完整工程并核对日志、依赖、TOOLSREL 和编译内容；不能只替换 XML 正文或沿用旧编译块。[安装与导出](01-auth-api.md) 给出步骤。

view-code/view-sql 缓存优先 PEOPLESOFT_TMP_DIR，通常为工作区 tmp；从 skill 运行时默认系统临时目录的 peoplesoft 子目录。以命令输出路径为准，缓存不视为服务器当前状态。

共享源是唯一 skill 编辑位置；维护源码和证据在开发项目，release / 安装副本通过同步工具更新。临时导出、夹具、日志、字节码和验收报告不进运行包。文档中文维护，保留命令/协议/许可原文；先复用主题文档。密码、Token 不写入代码、日志、回复或工程。
