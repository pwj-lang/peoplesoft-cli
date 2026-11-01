# Project 管理与迁移标记

读写分离部署：查询使用 `C_META_DATA_READ` 的对应 `AI_READ_*` URI，写入使用 `C_META_DATA_WRITE` 的原 `AI_OPER_*` URI；处理类分别位于 `C_META_DATA_PKG:MetaData:Read`、`:Write`。CLI 在 split 环境自动选择，完整映射及许可权配置见 [安装与读写分离](01-auth-api.md#读写分离2026-10-30)。下文参数/版本契约继续适用；旧混合 URI 的读取示例须改用对应 Read URI。

## 原始版本与冲突处理（2026-10-29）

createProject、modifyProject、insertItem、updateItem、deleteItem 全部要求原始 `expectedVersion`。struct 对存在和不存在名称都返回 `exists`、`version`（`prj1:`）及 `projectVersionControl=1`；创建前也先读取不存在名称。令牌覆盖工程头、全部完整成员键、Action/Upgrade/Done/比较状态及删除/依赖/包含更新行；不包含成员定义本身的正文。PJM、工程头和成员行锁内比较并保存，移除成员操作的提前 CommitWork，整次请求失败回滚。缺少/空版本428，过期409；同值成员更新不推进版本。

```powershell
python scripts/peoplesoft_api.py project struct MY_PROJECT --output original.json
python scripts/peoplesoft_api.py project modify MY_PROJECT --descr "New description" --snapshot original.json
# 每次新编辑重新读取，不能将保存前最新版本自动当作旧稿基线
python scripts/peoplesoft_api.py project struct MY_PROJECT
python scripts/peoplesoft_api.py project insert-item MY_PROJECT --object-type 30 --value1 MY_SQL --value2 0
```

CLI 的 struct 自动缓存绑定环境、服务器、节点、账号、类型和工程名称的完整结构快照；`--output` 保存的 JSON 可直接作为 `--snapshot`。全部写命令默认使用此前 struct 的缓存，缺快照拒绝写入；409 另存最新结构，保留原始快照，不自动刷新基线或重试。`--dry-run` 回滚拟保存内容，响应 version 不能作为后续基线；成功写后独立回读、核对指定和保留属性/成员，原快照不自动推进。

update-item/delete-item 可以省略全部 ObjectID，由原始快照精确解析唯一完整键；若显式传入则四个 ID 必须齐全。只按已提供的全部非空 Value 精确匹配，其他值视为空，不进行模糊匹配。直接 API 仍须传完整四个 ID/Value。

其他定义的自动工程登记作为独立的登记操作，先读取一次 Project 版本再提交，发生竞争不刷新重试；定义已保存但登记失败须按部分成功处理。所有定义写前的工程存在性检查显式校验 `exists=true`，不能将不存在状态快照当成可用工程。只读、use、dry-run 不登记成员，use 也核对工程存在。原生 Compare/Copy/导出会改变工程或标记，因此也会使原快照失效；导出后恢复标记须每个独立请求携带其原始版本。

需同时部署编译后的 OperProjectDefn、Utility:DefinitionVersion 和新版CLI（含 `scripts/sql_project_operations.py`）；旧客户端缺版本的写入将被拒绝，URI及权限不变。版本控制用于并发覆盖检测，不提供历史版本库。

通过 Integration Broker 管理 Application Designer 的 Project 定义和迁移条目。接口为 `POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/PSFT_HR/AI_OPER_PROJECT_DEFN.v1/`，请求头使用 `Content-Type: application/json` 和 `PS_TOKEN`。

## Agent 执行约定：先区分修改、删除程序与移除成员

以下行为以 **2.0.0-dev.5 客户端及对应服务端工程**为基线，已在 PANWX25 / Oracle / PeopleTools 8.60.10 验证。历史示例的环境、项目名和对象名不是新会话的默认目标；以用户本次已确认的环境和工程为准，不因读取本文自动切换环境或重做实验。

- 先查看 `env current`、`project current`，再对用户指定的工程执行 `project struct NAME --json`。`active_project` 只是本地上次选择；用户已指定目标时直接沿用，不重复确认。新建工程前精确核对是否已存在，不覆盖同名工程。**允许创建空 Project**，无需插入无关定义才能保存。
- 定义修改前读取实际结构或代码；代码文件是合并本次修改后的完整 UTF-8 正文，不能把新增方法片段当作整类正文覆盖。编译并回读成功后，再按下表处理工程条目。

| 用户意图 | 定义操作 | 工程操作与验收 |
|---|---|---|
| 新增 / 修改 PeopleCode 或定义 | 对应 create / modify / modify-code；保留未修改内容 | 自动登记的命令核对结果；旧命令显式 insert-item，已有成员也要重新登记。通常为 Unknown/Unknown、Copy/on/off |
| 只改 Action / Upgrade / Done | 不修改定义 | update-item；只改指定标记，保留 Source/Target 等未指定字段 |
| 真正删除整个 PeopleCode 程序 | delete-code，不能提交空白 modify-code | CLI 自动按删除响应的完整原生键登记 Delete/on/off；回读 programExists=false，父定义及无关条目保留 |
| 只删除一个方法，保留其他代码 | 删除该方法声明和实现后，用 modify-code 保存剩余完整正文 | 仍是 Copy/on/off；不能删除整个原生程序 |
| 删除 Field / Record 定义或 Record 中字段 | field delete、record delete / delete-field，按版本快照执行 | 全局定义 Delete；移除字段后的 Record 及依赖父记录 Copy；受影响程序 Delete；按响应完整键登记 |
| 只删除 Field 的某个 Label | field delete-label，保留全局 Field | 父 Field 完整键 Copy/on/off；标签删除响应根级 deleted=true 不表示父定义应标 Delete；独立回读标签缺席及父 Field 保留 |
| 只从工程移除一个成员 | 不修改定义 | project delete-item；不表示源端或目标端程序已删除 |

**删除程序后，不要再对该成员执行默认 insert-item。** 默认动作是 Copy，会把刚登记的 Delete 改回 Copy。只读、dry-run 也不登记。程序已删除但工程登记失败属于部分成功：先回读程序和工程，只补登记 / 修正 Delete 标记，不再次删除；需要插入缺失删除条目时显式指定 `--action Delete --upgrade on`，使用删除响应中的精确键。

Label 单删是父定义修改，使用服务端返回的 objectType=2、ObjectID1=6、ObjectValue1=FIELDNAME，ObjectID2～4=0、未用 ObjectValue 为 `""` 的全局 Field 键，不能自行把空字符串改成空格；不同次键可让原生解析器得到 Label 子键。CLI 会核对父 Copy 键并登记，不为单个标签增加 Delete 成员。不要调用整 Field 的原生 DeleteDefn 并附加 Label 次键：已验证的原生管理器忽略该次键，会删除整个 Field。参数和默认标签规则见 [Label 删除](06-record-defn-api.md#field-label-添加修改和删除)。

写入响应异常、超时或回读不符时，先核对实际保存状态，保留快照及完整键，不盲目重试。接口成功、成员存在、标记正确分别是不同验证层次，不能据此直接宣称 Compare、复制、Build 或运行成功。

## 只引用标准 Field 的工程范围

创建或修改 Record 时，未修改的系统标准 Field 只作为既有引用，不因被 Record 使用就单独 insert-item。Record 字段层的 Key、Required、Prompt 等设置属于 Record 定义，不能据此判断全局 Field 发生修改。新增自定义 Field 或实际修改全局 Field 属性/Label 时才登记该 Field。

C_AI_SQLAUD 使用的 AUDIT_ACTN、DESCR254、DESCRLONG、DTTM_STAMP、GUID、OPRID、ROW_COUNT、SQLTEXT 已从核心 Project 的 2 类型条目移除；这些全局定义和审计 Record 结构均未改变。自定义 C_AE_ACTN_TYPE 仍保留。原生文件可能仍包含 Record 关联的 Field 实例，不能用 XML 实例数量代替 Project 显式迁移清单，也不要手工裁剪原生 XML。

## 操作

所有操作必须传 `projectName`。省略 `operationType` 时默认 `createProject`。

| operationType | 参数 | 行为 |
|---|---|---|
| createProject | 可选 descr、comment | 创建项目；名称及 descr 不超过 30 字符；原生保存 AD 比较默认值 |
| modifyProject | 可选 descr、comment、adDefaults | 只修改显式传入的描述；空字符串清空；adDefaults=true 显式恢复 AD 比较默认值 |
| struct | projectName | 返回 header（全部头字段的字符串表示）、完整四组 objectId/objectValue、nodeType、sourceStatus、targetStatus 及迁移标记 |
| insertItem | objectType、objectValue1；按定义传 value2~4 | 新增或重新插入完整键；重设比较状态及迁移标记；重复键不新增行 |
| updateItem | objectType、objectId1~4、objectValue1~4；至少一个属性 | 按完整键更新 upgradeAction/takeAction/copyDone；未指定属性保持原值；条目不存在时报错 |
| deleteItem | objectType、objectId1~4、objectValue1~4 | 按完整键移除项目条目；不删除定义本身 |

`comment` 使用 JSON 转义后传输。

创建时写入 `KEEPTGT=31、REPORTFILTER=16232832、COMPARETYPE=1、TGTORIENTATION=0、COMMITLIMIT=50`，与 PANWX25 / PeopleTools 8.60.10 的 AD 空项目实测一致。旧实现给 PROJECT 封装属性赋值，但其 save() 没有保存 KEEPTGT/REPORTFILTER；REPORTFILTER=0 会抑制差异报告。修改描述现直接更新原生定义，保留提交限制、Change Project、发布信息及其他未指定属性。

历史工程不批量修改。先检查 `project struct NAME --json` 的 header，确认需要恢复默认设置时执行 `project modify NAME --ad-defaults`。此选项只重置上述五个数值选项，不改描述、成员或已有比较状态；有意定制的选项不要重置。header 的空格填充和数据库 NULL 会由 PeopleCode 字符串绑定表示为空字符串；复合键内部空格保留。严格数据库审计应使用原始 XML 快照。

新建后的最低核对项是上述五个默认值，以及本次应有的完整成员集合。不要固定比较历史 VERSION、时间或操作人；这些值随实际保存变化。比较报告不显示代码差异时，先检查 REPORTFILTER、精确程序键及程序是否原生存在，不能只凭工程树中有名称判断定义正确。

## Action、Upgrade、Done 的作用

这三个属性属于 **Project 中的定义条目**，用来控制后续复制/迁移。CLI 的 `update-item` 只保存这些标记；设置 Action 不会立即复制或删除定义，设置 Done 也不会执行迁移。

### Action：对目标定义执行什么操作

- **Copy**：将源定义复制到目标环境，目标已有定义时按复制规则更新它。Record 的 Copy 包含 Record Fields；Field 的 Copy 包含 Field Labels。项目中的其他定义和依赖仍需分别登记，不能认为 Copy 一个定义会自动带上所有依赖。
- **Delete**：在执行项目复制到目标数据库时，删除目标环境中的对应定义。设置 `--action Delete` 只是指定后续动作；`project delete-item` 则只移除项目成员，含义不同。
- **CopyProp**：Record（objectType=0）和 Field（objectType=2）的已验证语义为只复制部分属性，保留目标定义中的 Record Fields 或 Field Labels。AD 也允许消息目录成员保存 Action=3；保存该枚举不证明其他定义类型具有相同的属性复制语义。

| 定义 | Copy | CopyProp |
|---|---|---|
| Record | 复制 Record 定义及 Record Fields | 只复制 Record 本身的属性，不复制 Record Fields |
| Field | 复制 Field 定义及 Field Labels | 只复制 Field 定义，不复制 Field Labels |

2026-10-24 已在 PANWX25 / Oracle / PeopleTools 8.60.10 的隔离 Field 上验证：源定义删除一个 Label 后，用父 Field Copy 原生回导，会移除目标多出的该 Label，保留其他标签。迁移 Label 删除不能使用 CopyProp；也不能把父 Field 置为 Delete。其他目标环境复制后仍需回读目标标签和默认值。原生比较可自动增加 Label 差异成员，比较前保留工程成员和标记，比较后核对这些变化，不能把比较副作用当作 CLI 已登记内容。

例如，要把 `C_AI_KF1010` 新增的 NAME 字段及其 Key 设置迁移到目标 Record，不能仅对 Record 使用 CopyProp，因为它不复制 Record Fields。上述范围见 [Oracle PeopleTools 8.60 Lifecycle Management Guide，第 64 页](https://docs.oracle.com/cd/G10811_01/psft/pdf/pt860tlcm-b072024.pdf#page=64)。

### Upgrade：是否参与本次处理

勾选表示该条目允许参与复制，并按 Action 处理；未勾选表示跳过该条目。它是迁移条目的选择开关，不表示 PeopleTools 版本升级，也不表示定义已经升级成功。实际能否处理还取决于 Done 和本次选择的定义类型。见 [Oracle 的 Upgrade Workspace 说明](https://docs.oracle.com/cd/F52213_01/pt859pbr3/eng/pt/tlcm/UsingtheUpgradeWorkspace-0773e7.html)。

### Done：完成标记及是否需要再次处理

原生复制成功后会自动勾选 Done；保留这个标记时，后续复制通常会跳过已完成条目。取消 Done 表示允许再次处理，但仍需勾选 Upgrade。AD 中只能手动取消 Done；本 CLI 也支持直接设为 on，因此 `Done=1` 本身不能作为实际迁移成功的证据。见 [Oracle PeopleTools 8.60 Lifecycle Management Guide，第 22、93 页](https://docs.oracle.com/cd/G10811_01/psft/pdf/pt860tlcm-b072024.pdf#page=22)。

本次验证中，Copy Project to File 导出也会自动勾选 Done。此时只说明该次导出已处理条目，不能据此认定已导入目标环境，更不能认定已完成数据库 Build/Alter 或运行验证。CLI 的属性回读也只证明标记保存成功。

### 三个属性如何共同生效

对于 Copy、Delete、CopyProp，在本次已选择对应定义类型、且没有先重置 Done 的前提下：

| Upgrade | Done | 本次处理 |
|---|---|---|
| 不勾选 | 不勾选 | 跳过 |
| 不勾选 | 勾选 | 跳过 |
| 勾选 | 不勾选 | 具备处理条件，按 Action 执行 |
| 勾选 | 勾选 | 按已完成条目跳过 |

**重置 Done 会改变上表的前提。** 原生复制对话框的 `Reset Done Flags` 默认勾选，会在复制前清除 Done；原生 `pside.exe` 的 `-RST 1` 同样会先重置，`-RST 0` 保留 Done，省略该参数默认按 1 处理。重置 Done 不等于勾选 Upgrade，也不会改变 Action。见 [Oracle 第 85 页的复制选项](https://docs.oracle.com/cd/G10811_01/psft/pdf/pt860tlcm-b072024.pdf#page=85)和 [Oracle 命令行参数说明](https://docs.oracle.com/cd/F52213_01/pt859pbr3/eng/pt/tlcm/CommandLineParameters.html)。

Copy Project from File 还需确认使用哪份项目定义：选择 File 会使用导出文件中的 Project 及其迁移标记，并替换目标数据库中的 Project 定义；选择 Database 才保留并使用目标数据库现有的项目标记。因此，修改目标 Project 后，不能假设选择 File 的导入会遵循这些修改。见 [Oracle 的 Copy Project from File 说明](https://docs.oracle.com/en/applications/peoplesoft/peopletools/8.63/lifecycle-management-guide/copying-project-from-file.html)。

## 属性参数及约束

三个 Project 条目属性的对应关系如下：

| AD 属性 | API / PSPROJECTITEM 字段 | CLI 参数 | 编码 |
|---|---|---|---|
| Action | upgradeAction / UPGRADEACTION | --action Copy / Delete / CopyProp | 0 / 1 / 3 |
| Upgrade | takeAction / TAKEACTION | --upgrade on / off | 1=打勾，0=不打勾 |
| Done | copyDone / COPYDONE | --done on / off | 1=打勾，0=不打勾 |

CLI 的 Action 不区分大小写；复选框还接受 checked/unchecked、true/false、1/0。三个属性可单独或组合更新。数字参数 `--upgrade-action`、`--take-action`、`--copy-done` 仍可使用；同一属性的名称参数和数字参数不能同时传。历史 `upgradeAction=2`（None）仍兼容，名称参数仅提供 Copy、Delete、CopyProp。API 只接受整型编码，错误状态或小数会拒绝，整次请求回滚。

Action 统一接受 0～3；移除旧的 Record/Field 类型硬限制，因为 AD E27 已实测消息目录成员可保存 CopyProp=3。Record/Field 的复制范围见上表；没有把消息目录标记保存实验扩大为其目标库复制行为已验收。

insertItem 的服务端和 CLI 默认均为 `takeAction=1、upgradeAction=0、copyDone=0`。新增的 NODETYPE、SOURCESTATUS、TARGETSTATUS 均为 0。重复插入保留完整键和 NODETYPE，把 SOURCESTATUS/TARGETSTATUS 重置为 Unknown=0、COPYDONE 重置为 0，Action/Upgrade 使用本次显式值或默认 Copy/on。与 AD E24、E30 一致；成员内容本来已经相同则不改头版本或时间。只想局部改迁移标记并保留比较状态时使用 update-item。Done 在插入后用 update-item 设置。

直接调用 updateItem/deleteItem API 必须从 struct 回读完整键，四个 objectId 和四个 objectValue 都要传，空字符串也要显式传入。服务端将空值规范化为 PeopleTools 的单空格，并在 SelectByKey 后额外检查四个 Object ID；PSPROJECTITEM 主键本身不包含它们。删除请求不会为 SQL 自动补子类型，因此可以准确删除历史上 value2 为空的坏条目。不能只按对象名删除，也不要直连 SQL 清理。

## 对象类型

这里是 `PSPROJECTITEM.OBJECTTYPE`，与 Search 的 definitionType、PSPROJECTITEM 的 OBJECTID 都是不同编码。

| objectType | 类型 | objectValue1~4 |
|---|---|---|
| 0 | Record | value1=RECNAME |
| 2 | Field | value1=FIELDNAME |
| 4 | Translate Value | value1=字段名，value2=翻译值，value3=生效日期 |
| 5 | Page | value1=PNLNAME |
| 6 | Menu | value1=MENUNAME |
| 8 | Record Field PeopleCode | value1=Record，value2=Field，value3=Event |
| 43 / 44 | AE / Page PeopleCode | 使用删除处理类返回的完整键；AE value2 为原生复合键，Page value2=Activate |
| 46 / 47 / 48 | Component / Record / Field PeopleCode | 包含 Market；48 的 value4 合并固定长度 Field 与 Event |
| 9 | Menu PeopleCode | value1=菜单，value2=栏，value3=项目，value4=ItemSelected |
| 25 | Message Catalog Entry | value1=消息集号，value2=消息号 |
| 32 | Component Interface | value1=CI 名称 |
| 42 | Component Interface PeopleCode | value1=CI 名称，value2=Methods，ObjectID=74 / 12；完整程序独立于 32 类型父 CI |
| 53 | Permission List | value1=许可权名称；授权命令不自动登记整份列表 |
| 19 | Role | value1=角色名；可登记工程，旧 AD 的文件复制可能跳过，目标需独立核对 |
| 55 | Portal Registry Structure | value1=门户名称，value2=F/C，value3=对象名称 |
| 7 | Component | value1=PNLGRPNAME，value2=MARKET |
| 30 | SQL | value1=SQLID，value2=SQL 子类型：0=普通 SQL，1=AE 步骤 SQL，2=Record View SQL |
| 33 | Application Engine | value1=AE_APPLID；不要使用 31 |
| 34 | AE Section | value1=AE_APPLID、value2=Section；精确版本删除后仍有版本用 Copy，末版本删除用 Delete；Step/Action 没有独立工程类型，登记父 Section 及关联程序/SQL |
| 57 | Application Package 节点 | value1=Package，value2=Root，value3=Qualify Path；根包路径为 `.`，一级子包为 `:`；更深层从原生完整键读取 |
| 58 | Application Package PeopleCode | 路径按 value1~4 分段，根包在首位，类名在末位 |
| 79 / 80 | Service / Service Operation | value1=定义名称 |
| 81 | Service Operation Handler | value1=操作名，value2=Handlername |
| 82 | Service Operation Version | value1=操作名，value2=Versionname |
| 83 | Routing | value1=路由名，value2=生效日期 yyyy-MM-dd |

普通 SQL 插入时，CLI 和服务端都对省略或空的 value2 补 `0`；AE SQL 与 View SQL 必须分别显式传 `1`、`2`。子类型不匹配会使 AD 找不到定义。SQL 的 Search definitionType=65 不能作为 Project objectType；App Package 的 Search definitionType=104 也不能用于项目插入。

`2.0.0-dev.2` 对 57 类型的非 Delete 插入增加原生 AppPackageDefn.DefnExists 校验，拒绝不存在的包键；Delete 迁移条目允许源端已不存在。57 的 Package/Root/Qualify Path 与 58 的程序路径分段不同，例如：

```powershell
python scripts/peoplesoft_api.py project insert-item MY_PROJECT --object-type 57 --value1 C_META_DATA_PKG --value2 C_META_DATA_PKG --value3 .
python scripts/peoplesoft_api.py project insert-item MY_PROJECT --object-type 57 --value1 Utility --value2 C_META_DATA_PKG --value3 :
```

更深包的 Qualify Path 是父包路径，不是当前包的冒号类路径。插入成功和 struct 回读不等同于原生 Compare 通过；已有错误条目仍需用其完整八项键精确移除。HTML 为 objectType=51、value1=名称、value2=4；StyleSheet 为 50、value1=名称。

类 `C_META_DATA_PKG:MetaData:Write:OperRecordDefn` 的登记是 objectType=58、value1=C_META_DATA_PKG、value2=MetaData、value3=Write、value4=OperRecordDefn。Read 类将 value3 改为 Read。接口拒绝无法解析首个 objectId 的对象类型，但 struct 仍是项目原始条目列表，不能据此保证所有定义和依赖都真实存在；交付时还应核验原生 AD 导出或 Compare 结果。

## 应用类修改与删除：已验证的完整示例

2026-10-23 在 PANWX25 新建 `C_AI_20261023_01`，给已有类壳 `C_AI_TEST:Test:Test1` 添加 `ProjectProbe()`，返回工程名，随后按用户要求删除整个刚新增的程序。两阶段均独立回读，以下为**历史实测键，不是要求在新任务重放这些写操作**：

| 成员 | objectType | objectId1 / 2 / 3 / 4（本次实测） | value1 | value2 | value3 | value4 |
|---|---:|---|---|---|---|---|
| 根包 | 57 | 104 / 116 / 117 / 0 | C_AI_TEST | C_AI_TEST | `.` | 空 |
| 一级子包 | 57 | 104 / 116 / 117 / 0 | Test | C_AI_TEST | `:` | 空 |
| 类程序 | 58 | 104 / 105 / 107 / 0 | C_AI_TEST | Test | Test1 | 空 |

这里的“空”在 API struct 中为 `""`，数据库未使用的值通常存单个空格。**57 不是根包到类的路径分段；58 才按程序路径分段。** 不能把 `C_AI_TEST / Test / Test1` 当作 57 类型，也不能把完整冒号路径全放进 value1。ObjectID 只表示键类型，不是名称或 objectType；维护其他条目时从其 struct / 原生删除响应读取，不把本例编号推广到其他键。58 工程条目不另行追加底层程序的 OnExecute 事件。

本次修改后的三项均为 Source/Target=0/0、Action=0、Upgrade=1、Done=0。删除后仍有三个成员：**仅 58 类程序变为 Action=1、Upgrade=1、Done=0**；两条 57 包节点完全不变；原生 programExists=false，Test1 类壳及父包仍存在。删除程序不等于删除类壳，也不等于从工程移除该删除条目。

应用到新任务时：

1. 先 `app-pkg struct ROOT` 核对精确大小写和层级，再 `app-pkg view-code ROOT ROOT:Sub:Class` 读取代码。类壳存在但 programExists=false 是合法状态；不能仅凭空正文认定类不存在或重复 insert-class。原生存在性、空正文和类节点是否存在分开判断。
2. 用 UTF-8 文件保存完整类正文，再调用 `app-pkg modify-code`。**此旧命令只编译和回读代码，不自动登记工程；其 --project 参数不能当作 modify-code 自动登记开关。** 对应 58 条目必须显式 insert-item。
3. 只登记本次变更及实际需要迁移的包定义 / 依赖。下例演示根包、一级子包和程序的正确键，不要求每次改一个类都登记整棵包树或无关程序；更深包的 Qualify Path 从原生键读取。

以下命令在 skill 根目录执行；其他工作目录使用脚本绝对路径。`MY_PROJECT`、`MY_ROOT`、`Sub`、`MyClass` 和代码文件均需替换为本次已经核实的目标；工程已存在时不重复 create。

```powershell
python scripts/peoplesoft_api.py project create MY_PROJECT
python scripts/peoplesoft_api.py app-pkg view-code MY_ROOT MY_ROOT:Sub:MyClass
python scripts/peoplesoft_api.py app-pkg modify-code MY_ROOT MY_ROOT:Sub:MyClass C:\work\MyClass.peoplecode
python scripts/peoplesoft_api.py project insert-item MY_PROJECT --object-type 57 --value1 MY_ROOT --value2 MY_ROOT --value3 .
python scripts/peoplesoft_api.py project insert-item MY_PROJECT --object-type 57 --value1 Sub --value2 MY_ROOT --value3 :
python scripts/peoplesoft_api.py project insert-item MY_PROJECT --object-type 58 --value1 MY_ROOT --value2 Sub --value3 MyClass
python scripts/peoplesoft_api.py project struct MY_PROJECT --json
```

若用户要求删除整个程序，改用下面的独立流程；CLI 会保存唯一代码快照、核对 expectedCode、原生删除并独立回读，然后登记 Delete。成功后核对 programExists=false、父类 / 包仍存在、58 条目为 Delete/on/off，其他成员未变化。若删除后重新保存代码，再显式 insert-item 将 58 恢复为 Copy/on/off。

```powershell
python scripts/peoplesoft_api.py app-pkg delete-code MY_ROOT MY_ROOT:Sub:MyClass --project MY_PROJECT --output C:\work\delete-result.json
python scripts/peoplesoft_api.py project struct MY_PROJECT --json
python scripts/peoplesoft_api.py app-pkg struct MY_ROOT
```

其他 PeopleCode 删除单位、AE / Component 复合键及快照要求见 [PeopleCode 真正删除](development-standards.md#peoplecode-真正删除)。不手工拼接固定长度复合键，不合并内部空白，不把某个事件的删除扩大为整份父定义删除。

## CLI

```bash
python scripts/peoplesoft_api.py project current
python scripts/peoplesoft_api.py project struct MY_PROJECT
python scripts/peoplesoft_api.py project use MY_PROJECT
python scripts/peoplesoft_api.py project insert-item MY_PROJECT --object-type 30 --value1 MY_SQL --value2 0
python scripts/peoplesoft_api.py project insert-item MY_PROJECT --object-type 58 --value1 C_META_DATA_PKG --value2 MetaData --value3 OperRecordDefn
```

从 2.3.0 起，CLI update-item 可省略全部 ID，由 struct 解析完整键。必须指定 object-type、value1，以及所有非空的 value2~4，精确匹配唯一条目后才写入；未提供的 value 按空值匹配，不使用前缀或模糊匹配。修改前会读取三个属性，保存后回读核对目标值及未指定属性。成功输出具体条目和 Action、Upgrade、Done 的最终状态。所有 Project 定义类型共享此路径。

```bash
# 准备复制完整 Record：Copy 包含 Record Fields，取消 Done 以允许处理
python scripts/peoplesoft_api.py project update-item C_AI_EXPORT_20261010 --object-type 0 --value1 C_AI_KF1010 --action Copy --upgrade on --done off
# 仅复制 Record 属性：保留目标 Record Fields
python scripts/peoplesoft_api.py project update-item C_AI_EXPORT_20261010 --object-type 0 --value1 C_AI_KF1010 --action CopyProp --upgrade on --done off
# 仅取消 Done，Action 和 Upgrade 保持原值；Upgrade 原来未勾选时仍会跳过
python scripts/peoplesoft_api.py project update-item C_AI_EXPORT_20261010 --object-type 0 --value1 C_AI_KF1010 --done off
# 普通 SQL 的子类型必须明确指定
python scripts/peoplesoft_api.py project update-item C_AI_EXPORT_20261010 --object-type 30 --value1 C_AI_SF1010 --value2 0 --action Copy --upgrade off
python scripts/peoplesoft_api.py project struct C_AI_EXPORT_20261010 --json
```

也可显式提供全部四个 ID；只提供一部分会拒绝。delete-item 从原始 struct 快照精确解析唯一完整键，四个 ID 可以全部省略；显式传入时不能照抄其他定义的编号。下面演示显式完整键；用户要求移除成员时才执行，不用它替代 delete-code：

```powershell
$psStruct = python scripts/peoplesoft_api.py project struct MY_PROJECT --json | ConvertFrom-Json
$psMatches = @($psStruct.items | Where-Object {
  $_.objectType -eq 30 -and $_.objectValue1 -ceq 'MY_SQL' -and $_.objectValue2 -ceq '0' -and
  ($_.objectValue3 -ceq '' -or $_.objectValue3 -ceq ' ') -and
  ($_.objectValue4 -ceq '' -or $_.objectValue4 -ceq ' ')
})
if ($psMatches.Count -ne 1) { throw '必须精确匹配唯一成员' }
$psItem = $psMatches[0]
python scripts/peoplesoft_api.py project delete-item MY_PROJECT --object-type $psItem.objectType `
  --id1 $psItem.objectId1 --id2 $psItem.objectId2 --id3 $psItem.objectId3 --id4 $psItem.objectId4 `
  --value1 $psItem.objectValue1 --value2 $psItem.objectValue2
```

CLI 的 update-item/delete-item 对省略的 value 参数发送显式空字符串。删除历史坏条目时，空的 value2 应保持空，不能改成 0；否则会定位到正常条目。

`--done`/`copyDone` 和自动回读验证要求部署 2.3.0 服务端工程。仅升级 Python 脚本不足以增加服务端能力；旧服务端缺少 copyDone 回读时，CLI 会在写入前报错。

AD 元数据一致性修复要求客户端和完整服务端工程同时更新。仅替换 Python 无法修复项目头、重复插入或服务端默认值；客户端新增独立回读，拒绝把旧处理类保留的错误状态报告为成功。

## 响应及状态

接口统一返回 code/message/data；code=0 为成功。insertItem 的 data 包含 projectName、inserted（是否新增）、reinserted（是否已有同键）、changed（是否改变持久化内容）；inserted=false 不代表无变化。updateItem/deleteItem 分别返回 updated/deleted。成员实际修改会同时维护项目头原生版本、更新时间及操作人；同值更新不改头。错误返回非零 code 和原因，失败事务会回滚。

当前 Project 仅是 CLI 保存在 config.json 当前环境 active_project 中的上次选择，不是服务端的权威业务归属。create/insert-item/modify 成功后更新当前选择，struct/update-item/delete-item 不切换；use 核对服务端项目存在后写本地选择。项目有条目并不代表会迁移，还要核对正确的 Action、Upgrade、Done，以及本次复制是否重置 Done、是否选择该定义类型、使用哪份 Project 定义。

App Package 根包的首次创建仍需 AD；Project API 只登记项目条目，不负责创建根包或修复缺失定义。

service、service-op、menu、message-catalog、portal、ci、html、stylesheet 和新版 Component 属性/代码写入会自动重新登记已确认工程：Copy/Upgrade on/Done off，比较状态恢复 Unknown；精确删除使用 Delete/on/off，重建改回 Copy。其他旧命令按各自接口说明登记（delete-code 的自动删除登记除外），已有成员也需重新登记。只读和 dry-run 不登记。此行为表示需要再次迁移，不代表复制已经完成。删除菜单项也登记其已存在的所属程序删除。消息集/权限等数据的实际迁移还须检查原生导出能力与目标安全配置。

## 维护处理类与验证边界

- 创建 Project 使用原生元数据属性保存。仅给 `PROJECT:ProjectDefn` 封装的 m_iKeepTgt / m_iReportFilter 赋值不能证明其 save() 已持久化；必须回读实际 header。修改描述不应重新初始化其他选项；空字符串与省略参数分开处理。
- `Record.SelectByKey()` 未命中会清空 Record，包括刚设置的键。新增成员分支必须重新设置 PROJECTNAME、OBJECTTYPE 和四个 ObjectValue，再设置原生解析的四个 ObjectID 后 Insert；否则可能写出空工程名的孤立行。编号解析复用 ObjectKeyResolver，未使用解析槽为空字符串，存储空白与非空复合键保持各自原生语义。
- struct 的长描述 / 注释须正确 JSON 转义。测试成功响应还应核对返回值、完整键及未指定属性；不能只检查 code=0。
- 本环境已观察到并行原生 Compare / 标记恢复争用全局 PSLOCK 并产生 ORA-00060。原生导出、比较、回导及其标记恢复按串行执行；错误后先读实际状态再决定补做范围。退出码和“成功完成”日志之外，还要检查数据库错误及报告内容；部分类型的日志不能代表整轮成功。

截至 2026-10-23，AD 采集中的 9 类成员完整字段、扩展 30 类登记、真实 PeopleCode 差异报告，以及上述应用类创建代码 / 真正删除回读均已验证。REPORTFILTER 从 0 改为 16232832 的原生对照中，同一差异分别生成 0 / 1 项报告。**GUI 自动弹窗仍未单独验收**；30 类登记不等于 30 类目标迁移全部通过。项目多语言、ADS 正向绑定、瞬态 SEC/WORK、全部命名例外和 Copy To Database 等未测范围不写成已支持或永远不使用；不根据空快照补造元数据。
