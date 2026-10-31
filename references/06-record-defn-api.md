# Record、Field 与 Build

读写分离部署：查询使用 `C_META_DATA_READ` 的对应 `AI_READ_*` URI，写入使用 `C_META_DATA_WRITE` 的原 `AI_OPER_*` URI；处理类分别位于 `C_META_DATA_PKG:MetaData:Read`、`:Write`。CLI 在 split 环境自动选择，完整映射及许可权配置见 [安装与读写分离](01-auth-api.md#读写分离2026-10-30)。下文参数/版本契约继续适用；旧混合 URI 的读取示例须改用对应 Read URI。

通过 Integration Broker REST 接口维护 Record、全局 Field、Field Label 和 Record 程序，执行定义删除、版本校验及 Build/Alter。CLI 示例在 ps-cli 根目录运行；直接 API 示例中的版本值是占位文字，必须换成此前读取的原始令牌。

## Field / Record 版本快照与删除（2026-10-24 工作区更新）

此节要求同时部署 `OperFieldDefn`、`OperRecordDefn`、`Utility:DefinitionVersion` 和新版 CLI。这里的版本控制是并发覆盖保护，不是代码历史仓库。

Record `struct`、`viewPeopleCode`、`viewSQL` 返回不透明 `version`（r1:）；结构另有原生 `recordVersion`，程序读取另有 `programVersion`。Field 查询的每项返回 `version`（f1:）和原生 `fieldVersion`；精确查询可传 `{"operationType":"struct","fieldName":"MY_FIELD"}`，根级同时返回 `exists/version`。Record/Field 不存在时精确 struct 仍返回 `exists=false` 和可用于创建的版本令牌。

所有写操作必须携带先前读取的 `expectedVersion`，包括创建和 Build。Field create/modify 的批次在每个 fields 元素携带各自令牌；单元素也可使用根级 expectedVersion。批次先在同一锁内校验全部版本、名称及重复项，再执行写入；任一失败整体回滚。创建前先读取不存在的精确名称，缺席令牌对 RDM 变化保守失效，防止期间创建/删除后误用旧基线。

Field 令牌覆盖完整定义、基准及多语言标签、定义翻译、上下文标签和 XLAT 定义/全部生效日期/语言行。没有 XLAT 头时还包含 XTM 分配器代数，防止新增再删除后复用旧基线；其他 XLAT 更新也可能让这种快照保守失效。Record 令牌覆盖完整结构、索引、DDL 参数、依赖字段和 XLAT 头版本、子记录、全部 Record 程序及视图 SQL；子记录内容/程序改变使父 Record 快照失效，影响父展开或程序的子记录删除也核对祖先版本。排序后计算 SHA-256，不使用 MAX(version) 代替完整集合。服务端获取 RDM/PCM/SRM 分配行锁后重新核对；XLAT 写入另锁 XTM，直到保存/删除完成才提交。AD 原生保存同样使旧快照失效；一致读取前后版本不同返回冲突。

| 响应体 code | 含义 |
|---|---|
| 428 | 缺少/空 expectedVersion；先读取结构或代码 |
| 409 | 版本冲突，本次写入被拒绝；保留改稿，读取最新内容后合并 |
| 404 | 非创建操作的 Record 不存在 |
| 400 | 名称、依赖、程序编译、操作或其他参数校验失败 |

这些是 JSON 响应体 code。不要用 HTTP 200 判断成功，不自动重试冲突或响应不明的写入。Oracle Build/Alter 的 DDL 会隐式提交，版本只保护开始时的定义，不能将多步 DDL 说成可整体回滚。

### 新增删除操作

| 接口 / operationType | 必需定位 | 语义与工程标记 |
|---|---|---|
| Field / deleteField | fieldName、expectedVersion | 删除全局 Field 定义及原生所属标签/语言数据；仍有 XLAT 或被 Record 使用时拒绝；类型 2 / Delete |
| Field / deleteLabel | fieldName、labelId、expectedVersion | 删除单个基准 Label 及其翻译/上下文，保留 Field；至少留一个 Label，默认 Label 需指定 replacementLabelId，Record/Page 显式引用时拒绝；父 Field 类型 2 / Copy |
| Record / deleteRecord | recordName、expectedVersion | 原生删除 Record、所属字段/索引等元数据、Record 程序和 type 2 视图 SQL；类型 0、8、65 / Delete |
| Record / deleteRecordField | recordName、fieldName、expectedVersion | 移除一个直接字段或子记录引用，保留全局 Field 和子记录定义；原生重建展开字段、编号、索引及依赖父记录，清理因此消失的 Record 事件程序；保留 Record 类型 0 / Copy，程序类型 8 / Delete |
| Record / deletePeopleCode | recordName、fieldName、event、expectedVersion、expectedCode | 真正删除一个精确程序，保留 Record、Field 和相邻事件；类型 8 / Delete |

删除均支持 `dryRun=true`，返回完整 `projectItems`（程序单删沿用 projectItem）、deleted/dryRun。dry-run 不改变版本或工程。只删除定义元数据，不执行 DROP TABLE/VIEW，也不删除物理表数据；物理结构调整需另行 Build/Alter。仍被引用的子记录定义拒绝删除；继承字段须在所属子记录中删除，不能将父 Record 的展开项当作直接字段删除。删除子记录字段可影响祖先记录的展开和程序，计划会列出这些完整工程键。

整个 Field 定义删除使用 `%metadata:RecordFieldDefn:RecordFieldDefn_Manager`；单个 Label 走标签维护并更新缓存版本；Record 与字段集合使用 `RecordDefn_Manager` 的原生保存/删除；程序使用 PeopleCodeProgram_Manager.DeleteDefn。只在 PANWX25 / Oracle / PeopleTools 8.60.10 验证。外部业务引用不会被重写；调用方需按删除计划检查依赖。

### CLI 工作流

```powershell
python scripts/peoplesoft_api.py field struct MY_FIELD --json
python scripts/peoplesoft_api.py field modify MY_FIELD field-patch.json --project MY_PROJECT
python scripts/peoplesoft_api.py field delete MY_FIELD --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py field delete-label MY_FIELD --label-id OLD_LABEL --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py record struct MY_RECORD --json
python scripts/peoplesoft_api.py record delete-field MY_RECORD --fieldname MY_FIELD --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py record delete MY_RECORD --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py record view-code MY_RECORD --fieldname MY_FIELD --event FieldChange
python scripts/peoplesoft_api.py record modify-code MY_RECORD downloaded.pcode --project MY_PROJECT --fieldname MY_FIELD --event FieldChange
python scripts/peoplesoft_api.py record view-sql MY_VIEW
python scripts/peoplesoft_api.py record modify-sql MY_VIEW downloaded.sql --project MY_PROJECT
```

省略 --dry-run 才删除。create 前也先执行精确 struct。Field CLI 每次写一个名称，JSON 可为单字段对象或仅含该字段的 fields 数组；服务端仍支持带逐项版本的批次。Record 属性修改可省略 fields。Build 每次只选 createTable/alterTable/createView 之一，数组仅含 recordName 本身，不能用一个 Record 的版本执行其他对象的 DDL。

结构写默认使用上次 struct 保存的版本快照，--snapshot 可指定原文件；代码/SQL 修改必须使用输入文件旁的 .snapshot.json 或显式指定原下载快照，绑定环境、服务器、节点、账号、对象及精确事件/SQL 变体。不能临时取最新结构版本提交旧代码。409 会另存 conflict_* 最新结构及目标代码/SQL，原稿、原快照保留且不自动重试。成功后独立回读并登记 Copy/Delete、Upgrade on、Done off，已有工程成员也重设比较状态。

删除前保存唯一 JSON 备份，Record 包含受影响程序和视图 SQL；--output 保存结果。定义已成功而验证/工程登记失败时明确报告部分成功，registration_pending 文件保存完整恢复键，只补验证/登记，勿重复删除。定义删除和工程迁移是不同阶段，完整目标库 Delete/Copy 重放仍须在目标环境验收。

## 接口地址

```
POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/PSFT_HR/AI_OPER_RECORD_DEFN.v1/
```

> **URL 注意**：接口地址是 `AI_OPER_RECORD_DEFN.v1/`（不带 `_POST`）。

## 请求体参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `recordName` | string | **是** | Record 名称，必须精确匹配 |
| `expectedVersion` | string | 所有写入必填 | 原样使用先前 struct / viewPeopleCode / viewSQL 返回的 version |
| `operationType` | string | 否 | 操作类型，默认 `"struct"`。支持 `"struct"`、`"createRecord"`、`"modifyRecord"`、`"buildRecord"`、`"viewSQL"`、`"modifySQL"`、`"viewPeopleCode"`、`"modifyPeopleCode"`、`"deletePeopleCode"`、`"deleteRecord"`、`"deleteRecordField"` |

### operationType 取值一览

| operationType | 说明 | 额外参数 |
|---------------|------|----------|
| `"struct"` | 查看 Record 结构 | 无 |
| `"createRecord"` | 创建新 Record | `recName`、`fields`、`tableSpace` |
| `"modifyRecord"` | 修改 Record（更新字段属性 / 新增字段） | 可选 `fields` |
| `"buildRecord"` | Build / Alter / 创建视图，每次选一个动作 | createTable、alterTable、createView 三个数组中只传一个，内容仅为 recordName |
| `"viewPeopleCode"` | 查看 Record Field PeopleCode | `fieldName`、`event` |
| `"modifyPeopleCode"` | 修改/创建 Record Field PeopleCode；拒绝空白正文 | `fieldName`、`event`、`peoplecode` |
| `"deletePeopleCode"` | 真正删除一个 Record Field 事件程序 | `fieldName`、`event`、`expectedCode`；可选 `dryRun` |
| `"deleteRecord"` | 删除 Record 定义及所属程序/视图 SQL，保留物理对象 | 可选 dryRun |
| `"deleteRecordField"` | 删除一个直接字段或子记录引用，保留全局定义 | fieldName；可选 dryRun |
| `"viewSQL"` | 查看 View 的 SQL 正文（PSSQLTEXTDEFN, SQLTYPE=2） | 无 |
| `"modifySQL"` | 编辑/新建 View 的 SQL 正文（upsert） | `sqlText`、`market`、`dbType`、`effdt`、`descr`、`comment` |

### Record Audit 选项（RECUSE 字段）

Record 的审计选项（Record Audit）存储在 `PSRECDEFN.RECUSE` 字段。客户端通过 `auditOption`（字符串数组）读写，服务端做位掩码转换，**不再暴露原始数字**。

| Audit Option | 位值 | 说明 |
|--------------|------|------|
| `Add` | 1 | 新增审计 |
| `Change` | 2 | 变更审计 |
| `Delete` | 4 | 删除审计 |
| `Selective` | 8 | 选择性审计 |

- `struct` 返回 `auditOption`（数组，按位值降序，如 Add+Change=3 → `["Change","Add"]`）。
- `createRecord` 接收 `auditOption` 数组（**取代原 `recUse` 数字入参**），服务端用 `RecordUseEdit.GetRecuseByRecordUseProperty` 累加为 `RECUSE`。
- **双向校验**：勾选任意 `auditOption` 必须提供 `auditRecName`；提供 `auditRecName` 必须至少勾选一个 `auditOption`。

### buildRecord 操作说明

`buildRecord` 通过 createTable、alterTable、createView 数组选择一个动作，每次只能操作 recordName 本身，必须携带其快照版本。

```json
{"recordName":"C_TEST_REC","operationType":"buildRecord","expectedVersion":"r1:先前读取的原快照令牌","createTable":["C_TEST_REC"]}
```

### viewSQL / modifySQL 操作

读写 View 的 SQL 正文。View 的 SQL 存储在 `PSSQLTEXTDEFN`，`SQLID` = Record 名，`SQLTYPE = 2`（区别于普通 SQL 的 type 0）。底层复用 `%metadata:SqlRepositoryDefn` 类（与 `OperSqlDefn` 一致，只是 SQLTYPE 不同）。

**viewSQL 请求示例**：
```json
{
  "recordName": "C_SI_ROLE_OPR_V",
  "operationType": "viewSQL"
}
```

**viewSQL 响应示例**：
```json
{
  "code": 0,
  "data": {
    "recordName": "C_SI_ROLE_OPR_V",
    "exists": "true",
    "version": "r1:服务器返回的不透明令牌",
    "sqlType": "2",
    "lastUpdate": "Last updated by: panwx, 2025/12/08 10:22:55",
    "statements": [
      {
        "market": "GBL",
        "dbType": 32,
        "effdt": "1900-01-01",
        "sqlText": "SELECT N.ROLEUSER, N.ROLENAME, M.DESCR FROM PSROLEUSER N, PSROLEDEFN M WHERE ...",
        "descr": "",
        "comment": ""
      }
    ]
  }
}
```

SQL 不存在时 `exists = "false"`，`statements = []`。

**modifySQL 请求示例**（upsert：SQL 不存在则新建，存在则按 market/dbType/effdt 匹配更新）：
```json
{
  "recordName": "C_TEST_VIEW1",
  "operationType": "modifySQL",
  "expectedVersion": "r1:先前读取的原快照令牌",
  "market": "GBL",
  "dbType": "",
  "effdt": "1900-01-01",
  "sqlText": "SELECT N.ROLEUSER, N.ROLENAME, M.DESCR FROM PSROLEUSER N, PSROLEDEFN M WHERE N.ROLENAME = M.ROLENAME"
}
```

参数说明：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `sqlText` | string | **是** | — | SELECT 正文（JSON 转义），不含 `CREATE VIEW` 前缀 |
| `market` | string | 否 | GBL | 市场 |
| `dbType` | string | 否 | ""（default） | 数据库平台，`""`→32（空格，default） |
| `effdt` | string | 否 | 1900-01-01 | 生效日期 |
| `descr` | string | 否 | — | 描述 |
| `comment` | string | 否 | — | 长注释（JSON 转义） |

> `dbType` 内部通过 `MappingUtil.GetDbTypeCode` 转码：`""`→32（空格）、`"2"`→50（Oracle）等。View 默认平台用 32（即 `DBTYPE=' '`），与 `createView` 读取条件一致。

### viewPeopleCode / modifyPeopleCode 操作

读写 Record Field Level 的 PeopleCode。使用 `%metadata:PeopleCodeProgram:PeopleCodeProgram_Manager` 类的 `GetProgram`/`UpdateProgram` 方法（不直接操作 PSPCMPROG/PSPCMTXT 表）。

**viewPeopleCode 请求示例**：
```json
{
  "recordName": "C_TEST_REC",
  "operationType": "viewPeopleCode",
  "fieldName": "EMPLID",
  "event": "FieldChange"
}
```

**viewPeopleCode 响应示例**：
```json
{
  "code": 0,
  "data": {
    "recordName": "C_TEST_REC",
    "fieldName": "EMPLID",
    "event": "FieldChange",
    "programExists": true,
    "programVersion": 12345,
    "version": "r1:服务器返回的不透明令牌",
    "peoplecode": "MessageBox(0, \"\", 0, 0, \"Hello!\");",
    "lastUpdate": "Last updated by: panwx, 2026/07/15 09:10:13"
  }
}
```

程序不存在时 programExists=false，当前实现的 peoplecode 和 lastUpdate 为空字符串；兼容旧响应时也可能见到 null。判断原生程序存在性使用 programExists，不能以正文是否为空代替。version 仍是所属 Record 的并发令牌，programVersion 不替代它。

**modifyPeopleCode 请求示例**：
```json
{
  "recordName": "C_TEST_REC",
  "operationType": "modifyPeopleCode",
  "expectedVersion": "r1:先前读取的原快照令牌",
  "fieldName": "EMPLID",
  "event": "FieldChange",
  "peoplecode": "MessageBox(0, \"\", 0, 0, \"Hello!\");"
}
```

`peoplecode` 字段使用 JSON 转义（`EscapeJSON`/`UnEscapeJSON`），与 App Package 编码一致。编译错误会返回错误信息和位置。如果代码不存在则自动创建（`CreateDefn` + `SaveNewDefn`），已存在则更新（`GetDefnToUpdate` + `UpdateDefn`）。

## createRecord 操作

完整重建索引前检查 `indexes[].indexFields`：按 `keyCount` 返回有序的 `fieldName/ascDesc`，并包含 `activeFlag/custKeyOrder`。不能把非空索引的空键数组当作有效导出。创建时主索引 `_` 由 Record 的 Key 字段生成，业务补丁只另外提供自定义索引，避免重复主索引。

先读取计划名称的 struct，确认 exists=false，并保留其缺席版本。创建请求中的 recordName 与 recName 必须相同，Record 名最多15字符；引用的全局 Field 必须已存在。下面以 Derived/Work（类型2）为例，不执行物理 Build：

```json
{
  "operationType":"createRecord",
  "recordName":"MY_RECORD",
  "recName":"MY_RECORD",
  "expectedVersion":"r1:不存在名称的原快照令牌",
  "recordType":2,
  "tableSpace":[],
  "fields":[{"fieldName":"MY_FIELD","subRecord":"N","fieldProperty":[]}]
}
```

CLI 文件只保留 recName、recordType、tableSpace、fields 等业务属性；不放 operationType、expectedVersion 或 dryRun。先 `record struct MY_RECORD --json`，再 `record create MY_RECORD record-create.json --project MY_PROJECT`，CLI 从原结构快照补入版本和 recordName。创建失败不会自动创建缺失的 Field。

## modifyRecord 操作

整份定义重建可回读并复制 `optTrigFlag`、`tableSpace[].tempTblInstance` 和 `fields[].unmappedUseEdit`。后者仅允许未解码的 USEEDIT 位，不接受 Key 等已命名属性位；它用于原生元数据保真，不声明这些未知位的 UI 含义。修改已存在字段时未提供它则保留旧未知位。`optTrigFlag/tempTblInstance` 仅为 Y/N；tableSpace 修改须定位已有的 spaceName/dbName。`indexes` 修改目前只更新已有 indexId 的九种平台标记（0/1），不据此新增/删除索引或改变键列。

修改已存在的 Record 定义。传入 fieldProperty 时，该数组是对应属性位的完整目标值，不能只传新增的一项；省略 fieldProperty 则保留原值。modifyRecord 未出现的字段保留；移除字段使用显式 deleteRecordField / record delete-field。

### 请求示例

```json
{
  "recordName": "C_TEST_REC",
  "operationType": "modifyRecord",
  "expectedVersion": "r1:先前读取的原快照令牌",
  "fields": [
    {"fieldName": "EMPLID", "subRecord": "N", "fieldProperty": ["Key", "RequiredField", "SearchKey"]},
    {"fieldName": "NEW_FLD", "subRecord": "N", "fieldProperty": ["RequiredField"]}
  ]
}
```

### 行为规则

| 场景 | 行为 |
|------|------|
| 字段已在 Record 中 | 更新 `USEEDIT`/`USEEDIT2`/`EDITTABLE`/`DEFGUICONTROL`/`LABEL_ID`/`DEFRECNAME`/`DEFFIELDNAME`（请求未提供的列保持 DB 现值） |
| 字段不在 Record 中 | 默认追加到末尾；普通新字段可用 `insertBefore` 指定插到已有字段之前，后续字段编号顺延（`editTable`/`labelId`/`defaultPageControl`/`defaultRecName`/`defaultFieldName` 可随请求指定） |
| 未在 `fields` 中出现的字段 | 保持不变 |
| `descr`/`comment` 等 Record 级属性 | 可选，传入则更新 |

### 按位置插入新字段

每个普通新字段可传 `insertBefore`，值为当前 Record 已存在的字段名。例如在 COUNTRY 与 C12_2483_AMOUNT 之间插入 NAME 并设为 Key。以下是 CLI 补丁文件，不是完整 REST 请求；直接 API 还需根级 recordName、operationType、expectedVersion：

```json
{
  "fields": [
    {"fieldName": "NAME", "fieldProperty": ["Key"], "insertBefore": "C12_2483_AMOUNT"}
  ]
}
```

保存为 UTF-8 JSON 文件后执行 `record modify C_AI_KF1010 <file>`。服务端在 RDM 锁内顺延 FIELDNUM、插入新字段、重建展开字段并同步主索引；除编号顺延外，已有字段属性保持原值。未指定 insertBefore 时仍追加到末尾。同一请求的多个新字段插在相同目标前时按请求顺序排列。

insertBefore 目标必须已存在于 Record 中，不能为空；不支持借此移动已有字段或插入子记录引用。请求中重复 fieldName、错误目标或其他字段校验失败会整体回滚，不会先插入部分字段。此操作仅修改定义；实体表结构仍需另行 Build/Alter。

### 缓存、主索引与版本同步

modifyRecord 在 RDM 锁内重建当前 Record 的 PSRECFIELDDB，更新定义版本和 RDM/SYS 缓存版本，并在同一事务中同步实体 Record（类型 0/7）的主索引 `_`。Key/DuplicateOrderKey 的加入、移除、降序和唯一性都会同步；自定义主键顺序保留仍存在的键并追加新键，其他索引保持原样。非实体 Record 不创建主索引。元数据失败会回滚。

物理表和索引仍需另行 Build/Alter。Build/Alter 会按 ASCDESC 生成降序索引；Alter 使用展开字段复制公共列，复制失败或行数不一致会中止并保留原表。Oracle DDL 不能作为整体事务回滚；失败后可能留有临时表，仍应检查原表和错误详情。

### 字段组合校验（createRecord/modifyRecord 均生效）

`fieldProperty` 请求经过 `RecordUseEdit.ValidateFieldProperty` 校验，规则按已核实的 Application Designer 属性组合实现：GUI 中置灰（不可勾选）的组合会被拒绝，返回 400 并逐字段列出原因；任一字段校验失败则整个请求不写库（先全量校验、后统一写库）。

- **依赖链**：SearchKey 需要 Key；SearchEdit 需要 SearchKey；DescendingKey 需要 Key/AlternateSearchKey/SearchKey 之一；DefaultSearchField 需要 SearchKey/AlternateSearchKey
- **互斥**：FromSearchField 与 ThroughSearchField；四种 Table Edit（Yes/NoTableEdit、PromptTableEdit、TranslateTableEdit、1/0TableEdit）互斥
- **类型限制**：Auto-Update 仅 date/time/datetime；RequiredField 不支持 long character/image/imageReference/attachment；Key/搜索组/Audit 组不支持 long character/image/attachment（imageReference 支持）；ReasonableDate 仅 date；Yes/NoTableEdit 仅 character；1/0TableEdit 仅 number/signed number；PromptTableEdit 位仅 character/number（date/time/datetime 只能填 editTable，不写位）；EnableAutocompleteWhenUsedInSearchRecord 仅 character
- **前置条件**：EnableAutocomplete 需要 Default Page Control = Edit Box/System Default；DisableAutocompleteForThisField 需要字段已配置提示表（`editTable` 非空）；DisplayInAutocompleteWindow 需要 ListBoxItem 且不是搜索项（勾 SearchKey/AltSearchKey 时 AD 会自动清空它）；PersistInMenu 需要 ListBoxItem；TranslateTableEdit 需要字段本身有翻译值（PSXLATDEFN 有记录）
- **其它**：InMemory 被拒绝（需 Oracle In-Memory 列存储选项，本环境 GUI 中置灰）；子记录引用字段（SUBRECORD=Y）不可带 fieldProperty；未知属性名与内部标记 `RegularField`（默认 Label 位）被拒绝

`defaultPageControl` 取值：`"System Default"`(99)、`"Edit Box"`(4) 或数字代码；其它控件名的代码未确认，暂不接受。

### 其余限制

- 字段删除使用显式 deleteRecordField / record delete-field，见上节
- 不支持任意重排已有字段；新增普通字段可按 insertBefore 插入
- 不修改 Record 类型
- 常量默认值（Constant Default）暂不支持写入

## buildRecord 操作

根据 Record 定义创建或修改数据库对象；已验证的规则如下，不能推定覆盖全部 AD Build 选项。

### 生成规则

| 项目 | 规则 |
|------|------|
| 表名 | `PS_<RECNAME>`，若 `PSRECDEFN.SQLTABLENAME` 非空则用后者 |
| 表空间 | 取自 `PSRECTBLSPC.DDLSPACENAME` |
| 索引名 | `PS_<RECNAME>`（主键）或 `PS<INDEXID><RECNAME>` |
| 索引表空间 | 固定 `PSINDEX` |
| STORAGE | `INITIAL 40000 NEXT 100000 MAXEXTENTS UNLIMITED PCTINCREASE 0` |
| Table PCT | `PCTFREE 10 PCTUSED 80` |
| Index | `PCTFREE 10 PARALLEL NOLOGGING` + `ALTER INDEX NOPARALLEL LOGGING` |
| CLOB/BLOB | 自动排在字段列表末尾 |

### PeopleSoft -> Oracle 类型映射

| PS 类型 | FIELDTYPE | Oracle 类型 | NULL |
|---------|-----------|------------|------|
| Character | 0 | VARCHAR2(len) | NOT NULL |
| Long Character | 1 | CLOB | nullable |
| Number (len <= 4) | 2 | SMALLINT | NOT NULL |
| Number (5-9) | 2 | INTEGER | NOT NULL |
| Number (10-18) | 2 | NUMBER(len) | NOT NULL |
| Signed Number (有小数) | 3 | DECIMAL(prec, scale) | NOT NULL |
| Signed Number (无小数) | 3 | SMALLINT/INTEGER/NUMBER | NOT NULL |
| Date | 4 | DATE | nullable |
| Time | 5 | TIMESTAMP | nullable |
| DateTime | 6 | TIMESTAMP | nullable |
| Image/Attachment | 8 | BLOB | nullable |
| Image Reference | 9 | VARCHAR2(len) | NOT NULL |

> **关键**：`PSDBFIELD.LENGTH` 在 PeopleCode SQLExec 中返回**字节长度**。Signed Number 需读取 `DECIMALPOS` 确定小数位数。

### 请求示例

```json
{"recordName":"C_TEST_REC2","operationType":"buildRecord","expectedVersion":"r1:先前读取的原快照令牌","createTable":["C_TEST_REC2"]}
```

---

## USEEDIT / USEEDIT2 位标志参考

> 以下是 AD 显示标志及 PSRECFIELD 位值参考；提交属性名使用 struct 的 fieldProperty 原值，不能用显示标签或位表猜接口枚举。

### USEEDIT 位标志表

| 标志 | 十进制 | 十六进制 | 说明 |
|------|--------|----------|------|
| Key | 1 | 0x000001 | 主键 |
| Duplicate Order Key | 2 | 0x000002 | 重复键排序 |
| System Maintained | 4 | 0x000004 | 系统维护 |
| Field Add | 8 | 0x000008 | 字段添加审计 |
| Alternate Search Key | 16 | 0x000010 | 备用搜索键 |
| List Box Item | 32 | 0x000020 | 列表框项 |
| Descending Key | 64 | 0x000040 | 降序键 |
| Field Change | 128 | 0x000080 | 字段变更审计 |
| Required | 256 | 0x000100 | 必填 |
| Translate Table Edit | 512 | 0x000200 | Translate Table 编辑 |
| Field Delete | 1024 | 0x000400 | 字段删除审计 |
| Search Key | 2048 | 0x000800 | 搜索键 |
| YES/NO Table Edit | 8192 | 0x002000 | Yes/No 翻译表 |
| Prompt Table Edit | 16384 | 0x004000 | 提示表编辑 |
| Auto-Update | 32768 | 0x008000 | 自动更新 |
| From Search Field | 262144 | 0x040000 | From 搜索 |
| Through Search Field | 524288 | 0x080000 | Through 搜索 |
| Disable Advanced Search | 2097152 | 0x200000 | 禁用高级搜索 |
| (base value) | 8388608 | - | 基值，始终存在 |
| Default Search Field | 16777216 | 0x01000000 | 默认搜索字段 |
| Allow Search Events | 134217728 | 0x08000000 | 提示框搜索事件 |
| Search Edit | 268435456 | 0x10000000 | 搜索编辑 |

### USEEDIT2 位标志表

| 标志 | 十进制 | 说明 |
|------|--------|------|
| Do Not trace Value | 8388608 | 不追踪字段值变化 |
| In Memory | 524288 | 仅内存不持久化 |
| Disable Autocomplete | 65536 | 禁用自动完成 |
| Persist in Menu | 负数 | 菜单中持久化（bit 31） |

## 创建与 Build 注意事项

- 创建须同时提供一致的 recordName、recName，以及 tableSpace 数组（可为 []，元素为 spaceName/dbName）；省略 tableSpace 可能触发空对象错误。
- 不修改 Record 字段的显式标签时省略 labelId；不要用空字符串代替省略项。fieldProperty 按接口枚举精确匹配，提供时使用完整目标属性数组。
- Record 名最多 15 字符。子记录是占位符，Build 须在原位置递归展开其字段，不直接建 SUBRECORD 列。
- PSDBFIELD.LENGTH 是字节长度，不再次乘 4；Number 长度大于 18 或不大于 0 使用 NUMBER。有小数的 Signed Number 使用 DECIMAL(LENGTH-DECIMALPOS, DECIMALPOS)。
- CLOB/BLOB 排在普通列之后；索引使用 RECNAME 命名，而非 SQLTABLENAME；表空间与索引空间分开。View SQL 从 PSSQLTEXTDEFN 的 GBL/默认平台/最新生效日期读取。
- Oracle DDL 不能整体事务回滚；Alter 失败检查原表、临时表和错误，不能直接重跑覆盖。

<a id="field-批量查询"></a>

## Field 定义与 Label

处理类：`C_META_DATA_PKG:MetaData:Read:OperFieldDefn` / `C_META_DATA_PKG:MetaData:Write:OperFieldDefn`。全局 Field 定义和 Record 中使用的字段是两个维护对象：`field delete` 删除全局定义；`record delete-field` 只移除 Record 中的字段或子记录引用。

### 接口地址与权限

```text
POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/PSFT_HR/AI_OPER_FIELD_DEFN.v1/
```

请求头沿用 `Content-Type: application/json` 和 `PS_TOKEN`；服务操作为 `AI_OPER_FIELD_DEFN_POST`。Label 单删复用该操作和权限，不增加 Service Operation；认证和授权见 [安装说明](01-auth-api.md)。

### Field operationType 与请求参数

| operationType | 定位与参数 | 行为 |
|---|---|---|
| `struct` / `query` | `fieldName`，或字符串数组 `fields` | 精确读取或批量读取；默认操作为 query |
| `createField`（别名 create） | 非空对象数组 `fields`，每项 fieldName、类型、length、labels、expectedVersion | 新建全局 Field；先读取不存在名称的快照 |
| `modifyField`（别名 modify） | 非空对象数组 `fields`，每项 fieldName、expectedVersion 及待改属性 | 局部修改；labels 按 labelId 添加或更新 |
| `deleteField` | 根级 fieldName、expectedVersion；可选 dryRun | 删除整个 Field 及所属标签/语言，Record 使用中拒绝 |
| `deleteLabel` | 根级 fieldName、labelId、expectedVersion；可选 replacementLabelId、dryRun | 单标签删除，保留 Field；详见下文 |

Field 名称最多18字符，精确 API 请求使用大写字母开头、后续大写字母/数字/下划线；CLI 将名称转为大写。创建/修改的单元素 fields 可在根级携带 expectedVersion；多元素批次必须每项带自己的令牌。Field 查询的 `fields` 是字符串数组，创建/修改的 `fields` 是对象数组，不能混用。删除操作每次只接受一个根级精确目标。

### 精确读取与批量查询

需要创建、修改或删除时，优先精确读取；不存在也返回 `exists=false` 和可用于创建的缺席版本：

```json
{"operationType":"struct","fieldName":"MY_FIELD"}
```

精确响应节选：

```json
{
  "code": 0,
  "data": {
    "fieldName": "MY_FIELD",
    "exists": true,
    "version": "f1:服务器返回的不透明令牌",
    "fields": [{
      "fieldName": "MY_FIELD",
      "fieldType": "character",
      "fieldTypeCode": 0,
      "length": 10,
      "fieldVersion": 12345,
      "version": "f1:服务器返回的不透明令牌",
      "labels": [{"labelId":"MY_FIELD","longName":"主标签","shortName":"主标签","defaultLabel":1}]
    }]
  }
}
```

批量查询支持对象形式：

```json
{"operationType":"query","fields":["EMPLID","EFFDT","LASTUPDDTTM"]}
```

也兼容旧版纯 JSON 字符串数组：

```json
["EMPLID", "EFFDT", "LASTUPDDTTM"]
```

批量结果的每个 Field 自带 version；缺失名称不出现在 fields 中，不能用缺失的批量项推导创建令牌。空字段名会被跳过。相较 AI_SEARCH_DEFN，本接口返回定义属性、标签和版本；Search 结果不能作为写入快照。

### Field 创建和修改

以下是直接 API 请求示例；其中令牌必须替换为对应目标先前读取的 version。

```json
{
  "operationType": "createField",
  "expectedVersion": "f1:不存在名称的原快照令牌",
  "fields": [{
    "fieldName": "MY_FIELD",
    "fieldType": "character",
    "length": 10,
    "labels": [{"labelId":"MY_FIELD","longName":"主标签","shortName":"主标签","defaultLabel":1}]
  }]
}
```

常用写入属性：

| 属性 | 类型与约束 | 创建/修改说明 |
|---|---|---|
| fieldName | string，最多18字符 | 必填，不用于重命名已有定义 |
| fieldType / fieldTypeCode | 类型名或数字类型码，两者同时提供须一致 | 创建必填其一；类型码见上文 Oracle 类型表 |
| length | number，不能为负 | 创建须提供；attachment 可省略；按定义字节长度处理 |
| decimalPos | number | 小数位；未传保持现值 |
| comment | string | 长描述；CLI 自动处理所需编码 |
| labels | 非空对象数组 | 创建必填；修改时可省略以保留原标签 |

其他结构属性以 struct 的 `format/formatLength/imageFmt/formatFamily/dispFmtName/defCntryYr/imeMode/kbLayout/objectOwnerId/fldNotUsed/auxFlagMask` 为准，不能直接把完整查询结果当作补丁提交。`version/fieldVersion/lastUpdate` 是只读状态；请求并发基线只用 expectedVersion。

批次成功返回 affectedCount、fields 中各目标的新 version，以及全局 Field 的完整 Copy 工程键。任一元素校验失败整体回滚。`modifyField` 至少提供一项可修改属性；未出现的 Field 属性保持原值。

CLI 的输入文件是业务属性对象，CLI 自动补 operationType、名称及快照版本。不要把完整 REST 请求体当成 CLI JSON 文件。例如新建时把下列内容保存为 `field-create.json`：

```json
{
  "fieldType": "character",
  "length": 10,
  "labels": [{"labelId":"MY_FIELD","longName":"主标签","shortName":"主标签","defaultLabel":1}]
}
```

```powershell
python scripts/peoplesoft_api.py field struct MY_FIELD --json
python scripts/peoplesoft_api.py field create MY_FIELD field-create.json --project MY_PROJECT
```

创建前这次 struct 应返回 exists=false；同名定义存在时先核对目标，不覆盖创建。成功写入后 CLI 保存新快照，后续可继续局部修改；如果另开编辑过程，先读取其编辑基线。

### Field 查询属性

| 字段 | 类型 | 说明 |
|---|---|---|
| fieldName | string | 全局字段名 |
| fieldType / fieldTypeCode | string / number | 类型名及 FIELDTYPE 编码，Image/Attachment 另结合 imageFmt |
| length / decimalPos | number | 长度和小数位；length 是定义字节长度 |
| fieldVersion | number | 原生定义版本，用于核对，不替代 expectedVersion |
| version | string | f1: 不透明并发令牌，写入时原样携带 |
| lastUpdate / comment | string | 最后更新信息和长描述 |
| labels | array | 基准标签列表，含 labelId、longName、shortName、defaultLabel |

### Field XLAT 翻译值（2026-10-31）

XLAT 是 Field 的枚举翻译值，与 Label、消息目录多语言不同。本批复用 Field Read/Write 操作，需同时部署 `CoreOperFieldDefn`、`DefinitionVersion`、Field Write 白名单及新版 CLI。精确 struct 根级和 Field 项返回 `xlatMaintenanceVersion=1`；每项 `xlatValues` 返回全部历史日期，不只返回今天有效行，包含 `fieldValue/effdt/effStatus/longName/shortName/lastUpdate/translations`。translations 保留显式语言代码及长短文本。

XLAT 属性的原生含义参见 [Oracle：Translate (XLAT) Table Entries](https://docs.oracle.com/en/applications/peoplesoft/peopletools/8.63/component-interfaces/understanding-translate-xlat-table-entries.html)；本实现的直接环境证据以 panwx25 / PeopleTools 8.60.10 实测为准。

```powershell
python scripts/peoplesoft_api.py field list-xlat MY_FIELD
python scripts/peoplesoft_api.py field add-xlat MY_FIELD --value A --long-name "已批准" --project MY_PROJECT
python scripts/peoplesoft_api.py field modify-xlat MY_FIELD --value A --effdt 1900-01-01 --short-name "批准" --status I --project MY_PROJECT
python scripts/peoplesoft_api.py field add-xlat MY_FIELD --value A --effdt 2030-01-01 --long-name "新版本说明" --project MY_PROJECT
python scripts/peoplesoft_api.py field delete-xlat MY_FIELD --value A --effdt 1900-01-01 --project MY_PROJECT --dry-run
```

`struct` 或 `list-xlat` 保存原始 Field 快照；写入要求该快照，可显式 `--snapshot`。成功后缓存新版本；409 保留原文件，另存最新结构，不自动重试。所有 XLAT 写入支持 `--dry-run`、`--output`；dry-run 校验后不改数据、版本或工程。`list-xlat` 只读，不登记工程。

| API operationType | 行为 |
|---|---|
| addXlat | 新建精确 `(fieldName,fieldValue,effdt)`；不能覆盖已有行 |
| modifyXlat | 修改精确已有行；省略文本/状态保持原值，不能借此改键 |
| deleteXlat | 删除一个精确生效日期及其相关语言行，保留同值其他日期和相邻值 |

直接 API 在根级传 `fieldName/fieldValue/effdt/expectedVersion`，add/modify 另接受 `longName/shortName/effStatus`，可选 `dryRun`；文本为普通 JSON 字符串，不套用 Field comment 的二次转义。CLI 可用位置文件替代业务属性参数，文件仅接受 `fieldValue/effdt/longName/shortName/effStatus`，相同属性不能同时由文件和参数提供。不能注入名称、操作、版本或 dryRun。

限定 Character Field、定义长度 1–4；值非空且不超过字段长度，大小写保留，不能以空格结尾。longName/shortName 非空、最长 30/10 字符，不接受尾随空格；服务端在原生 Record 赋值前校验，避免字段自动截断。新增必须提供 longName，省略 shortName 时取 longName 前 10 字符；effStatus 只能为 A/I，新增默认 A。新增日期默认 1900-01-01；修改、删除必须明确指定精确日期，API 一律提供 YYYY-MM-DD。修改日期使用新增日期行并按需删除旧行，不隐式重命名。

维护基准 XLAT 值；当前可读取并保留已有多语言行，不提供单语言编辑命令。修改基准文本/状态不清除语言行；删除基准行级联限定同一完整键的语言行，CLI 删除前保存完整结构备份。失效使用 `--status I`；操作不改历史业务表数据。

服务端锁内校验版本及 Translate 定义访问权，复用交付 `PSXLATDEFN.FIELDNAME.FieldFormula` 的 TranslatePSLOCK/TranslateUpdateVersions 更新 XTM/SYS 和 XLAT 头版本。新增后在提交前验证实际行键；末行删除清理空头。Record 使用 TranslateTableEdit 时拒绝删除最后一个 XLAT 行；Field 类型/长度修改不能使已有值失效，删除整个 Field 前先明确删除其 XLAT。

返回完整 type 4 工程键：Field(6)、Value(22)、EffDt(21)，value3 为 YYYY-MM-DD。新增/修改登记 Copy，删除该日期登记 Delete，均 Upgrade on/Done off；XLAT 操作不把父 Field 置 Delete。panwx25 已验证原生导出、Copy 及精确 Delete 同环境回放，其他目标迁移仍需验收。字段本身的创建/修改仍按 type 2 单独登记。

### Field Label 添加、修改和删除

`createField` / `modifyField` 的 `fields[].labels` 按 `(fieldName,labelId)` 添加或更新；`longName`、`shortName`、`defaultLabel` 中未传的属性保持原值。`defaultLabel` 为数字 0/1。省略标签不会删除，`labels: []` 不合法，修改 labelId 会新增标签。

单个 Label 使用 Field 接口 `AI_OPER_FIELD_DEFN.v1/` 的 `deleteLabel`：

```json
{
  "operationType": "deleteLabel",
  "fieldName": "MY_FIELD",
  "labelId": "OLD_LABEL",
  "expectedVersion": "f1:先前读取的令牌",
  "dryRun": true
}
```

删除默认标签还需 `replacementLabelId`，必须是同一 Field 上的已有不同标签；CLI 为 `--replacement-label-id NEW_LABEL`。不能删除最后一个标签，非默认标签不接受替代参数。Record、展开 Record 或 Page 的显式 LABEL_ID 引用会阻止删除；不自动修改引用。不存在的 Field/Label、非法替代参数返回 400；缺失版本 428，冲突 409。

成功响应包含 `fieldName/labelId/replacementLabelId/deleted/dryRun/version`、匹配的语言和上下文行数、`labelBackup/translations/contexts` 恢复数据，以及父 Field 的完整 Copy 工程键。恢复数组保留原生列名和字符串值。删除翻译限定 FIELDNAME/LABEL_ID；上下文限定 RECNAME=PSDBFLDLABL 及相同字段、标签键。其他标签、Field 定义翻译及引用保留。dry-run 验证同一规则且不更新版本、定义或工程；真正删除更新原生 Field/RDM/SYS 缓存版本。不得把父 Field 标记 Delete，也不得用原生 RecordFieldDefn_Manager.DeleteDefn 删除标签：本环境中该管理器忽略102子键，会删除整个 Field。

CLI 先 `field struct MY_FIELD --json`，再 `field delete-label MY_FIELD --label-id OLD_LABEL`；使用原结构快照并保存完整标签备份，删除后独立回读目标缺席、其余标签及默认替代正确，再登记父 Field Copy。PANWX25 / Oracle / PeopleTools 8.60.10 同环境原生回导已验证：父 Field Copy 会移除目标定义多出的 Label，保留其余标签。其他目标环境迁移后仍需回读核对；不额外登记 Label 子键 Delete。原生比较可能添加标签差异成员，比较和复制的工程变更需单独核对。


#### Label 参数与添加、修改示例

| 参数 | 类型 | 约束 |
|---|---|---|
| labelId | string | 必填，非空，最多18字符；服务端转为大写；可包含已支持的连字符，不能套用 Field 名称的字符限制 |
| longName | string | 最多30字符；已有标签省略时保留原值 |
| shortName | string | 最多15字符；已有标签省略时保留原值 |
| defaultLabel | number | 只能为0或1，不能传字符串 Y/N、true/false |

CLI 添加标签时的 `label-add.json`（不包含 REST 操作和版本）：

```json
{"labels":[{"labelId":"ALT_LABEL","longName":"备用标签","shortName":"备用","defaultLabel":0}]}
```

CLI 修改现有标签时的 `label-modify.json`：

```json
{"labels":[{"labelId":"ALT_LABEL","longName":"调整后的备用标签"}]}
```

```powershell
python scripts/peoplesoft_api.py field struct MY_FIELD --json
python scripts/peoplesoft_api.py field modify MY_FIELD label-add.json --project MY_PROJECT
python scripts/peoplesoft_api.py field modify MY_FIELD label-modify.json --project MY_PROJECT
```

第二次只修改 longName，保留原 shortName/defaultLabel。CLI 文件中的 labelId 使用标准大写值。新增标签不传文本时采用空白值，不传 defaultLabel 时为0；已有标签省略属性保持原值。原 upsert 不自动把其他标签的默认标志清零；需要切换默认时，在同一修改请求明确将旧标签设0、新标签设1，或在删除旧默认标签时使用 replacementLabelId。

#### 普通标签删除和默认标签替换

```powershell
python scripts/peoplesoft_api.py field struct MY_FIELD --json
python scripts/peoplesoft_api.py field delete-label MY_FIELD --label-id ALT_LABEL --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py field delete-label MY_FIELD --label-id ALT_LABEL --project MY_PROJECT --output label-delete-result.json
```

删除默认标签时，替代标签必须事先存在。对应直接 API 请求：

```json
{
  "operationType":"deleteLabel",
  "fieldName":"MY_FIELD",
  "labelId":"OLD_DEFAULT",
  "replacementLabelId":"NEW_DEFAULT",
  "expectedVersion":"f1:删除前的原快照令牌",
  "dryRun":false
}
```

对应 CLI：

```powershell
python scripts/peoplesoft_api.py field struct MY_FIELD --json
python scripts/peoplesoft_api.py field delete-label MY_FIELD --label-id OLD_DEFAULT --replacement-label-id NEW_DEFAULT --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py field delete-label MY_FIELD --label-id OLD_DEFAULT --replacement-label-id NEW_DEFAULT --project MY_PROJECT
```

#### deleteLabel 响应与失败处理

成功响应的 data 结构示例（普通标签，无翻译/上下文）：

```json
{
  "fieldName":"MY_FIELD",
  "labelId":"ALT_LABEL",
  "replacementLabelId":"",
  "languageRowCount":0,
  "contextRowCount":0,
  "deleted":true,
  "dryRun":false,
  "version":"f1:删除后的新令牌",
  "labelBackup":{"labelId":"ALT_LABEL","longName":"备用标签","shortName":"备用","defaultLabel":0},
  "translations":[],
  "contexts":[],
  "projectItems":[{
    "objectType":2,"deleted":false,
    "objectId1":6,"objectValue1":"MY_FIELD",
    "objectId2":0,"objectValue2":"",
    "objectId3":0,"objectValue3":"",
    "objectId4":0,"objectValue4":""
  }]
}
```

这里根级 deleted=true 表示标签已删除，工程条目的 deleted=false 表示父 Field 使用 Copy。dry-run 的 deleted=false、dryRun=true，version 保持原值；行数与恢复数据描述将被删除的数据。CLI 结果另含 snapshotPath、readbackVerified、project 等本地验证信息，不能将其当作原始服务端字段。

| 情况 | 结果与处理 |
|---|---|
| 缺少/空 expectedVersion | 响应体428；先读取编辑基线 |
| 期间有定义、标签、语言或上下文变化 | 响应体409；本次删除未执行，保留原快照，读取新内容后人工合并决定 |
| 最后一个标签、默认替代不合法、目标不存在 | 响应体400；修正请求，不循环重试 |
| Record / 展开Record / Page 显式引用 | 响应体400；先按实际需求修改引用，再重新读取 Field 快照；不会自动替换引用 |
| 请求超时或响应无法解析 | 先回读当前定义及工程，核对是否已删除，不直接重复请求 |
| 已确认写入但回读/工程登记失败 | 按已保存的完整恢复键补验证/登记；父 Field 应为 Copy/on/off，不重复删除 |

翻译和上下文当前可随标签删除，不能据此推断接口支持独立新增/修改翻译；labels upsert 维护的是基准标签。外部业务数据或代码中自行保存的 Label ID 不自动检查或重写。

## Record 定义、字段与程序删除

### 删除整个 Record 定义

```json
{"operationType":"deleteRecord","recordName":"MY_RECORD","expectedVersion":"r1:原结构快照令牌","dryRun":true}
```

```powershell
python scripts/peoplesoft_api.py record struct MY_RECORD --json
python scripts/peoplesoft_api.py record delete MY_RECORD --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py record delete MY_RECORD --project MY_PROJECT --output record-delete-result.json
```

删除定义及其原生所属元数据、程序和视图SQL，保留全局 Field、物理表/视图及数据。仍被其他 Record 作为子记录引用时拒绝。按计划中的类型0/8/65等完整键登记 Delete；不要只登记 Record 而遗漏所属程序/SQL。

### 删除 Record 中的字段或子记录引用

```json
{"operationType":"deleteRecordField","recordName":"MY_RECORD","fieldName":"MY_FIELD","expectedVersion":"r1:原结构快照令牌","dryRun":true}
```

```powershell
python scripts/peoplesoft_api.py record struct MY_RECORD --json
python scripts/peoplesoft_api.py record delete-field MY_RECORD --fieldname MY_FIELD --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py record delete-field MY_RECORD --fieldname MY_FIELD --project MY_PROJECT
```

fieldName 必须定位本 Record 的直接字段或直接子记录引用；展开继承项须到其所属子记录修改。保留全局 Field 和子记录定义，原生重建字段编号、展开、索引及必要祖先，清理因此消失的程序。父/祖先 Record 用 Copy，受影响程序用 Delete；完整影响范围以 projectItems 为准。物理列不会随定义字段移除自动删除。

### 删除 Record Field 程序

```powershell
python scripts/peoplesoft_api.py record struct MY_RECORD --json
python scripts/peoplesoft_api.py record delete-code MY_RECORD --fieldname COUNTRY --event FieldChange --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py record delete-code MY_RECORD --fieldname COUNTRY --event FieldChange --project MY_PROJECT
```

保留 Record 和 Field；同字段其他事件不受影响。直接 API 的 operationType=deletePeopleCode，除 recordName/fieldName/event 外，还需 expectedVersion 和 expectedCode（原完整程序正文，按公共编码约定提交），可选 dryRun。程序正文和版本必须属于同一编辑基线；CLI 会读取精确程序、确认其版本与原结构快照相同，再保存备份并删除。

以 viewPeopleCode 的 programExists 核对原生存在性，删除成功后应为false；按返回的完整程序键登记类型8 Delete/on/off。省略 `--dry-run` 执行删除；支持 `--output`。程序不存在或重复删除会被拒绝，不能通过空白 modify-code 表达删除。见 [删除流程](development-standards.md#peoplecode-真正删除)。

三类删除均先读取原结构快照；dry-run 不改变定义、版本或工程，若期间有其他修改，正式删除返回409。CLI 保存唯一备份并独立回读；超时、验证失败或工程登记失败按上文规则先查实际状态，不循环重删。
