# Record、Field 与 Build

通过 Integration Broker REST 接口查看、创建、修改 Record 定义，Build/Alter 实体表，创建视图。

## 接口地址

```
POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/PSFT_HR/AI_OPER_RECORD_DEFN.v1/
```

> **URL 注意**：接口地址是 `AI_OPER_RECORD_DEFN.v1/`（不带 `_POST`）。

## 请求体参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `recordName` | string | **是** | Record 名称，必须精确匹配 |
| `operationType` | string | 否 | 操作类型，默认 `"struct"`。支持 `"struct"`、`"createRecord"`、`"modifyRecord"`、`"buildRecord"`、`"viewSQL"`、`"modifySQL"`、`"viewPeopleCode"`、`"modifyPeopleCode"`、`"deletePeopleCode"` |

### operationType 取值一览

| operationType | 说明 | 额外参数 |
|---------------|------|----------|
| `"struct"` | 查看 Record 结构 | 无 |
| `"createRecord"` | 创建新 Record | `recName`、`fields`、`tableSpace` |
| `"modifyRecord"` | 修改 Record（更新字段属性 / 新增字段） | `fields` |
| `"buildRecord"` | Build/alter/create view — 三个子选项 | `createTable`、`alterTable`、`createView`（三个数组） |
| `"viewPeopleCode"` | 查看 Record Field PeopleCode | `fieldName`、`event` |
| `"modifyPeopleCode"` | 修改/创建 Record Field PeopleCode；拒绝空白正文 | `fieldName`、`event`、`peoplecode` |
| `"deletePeopleCode"` | 真正删除一个 Record Field 事件程序 | `fieldName`、`event`、`expectedCode`；可选 `dryRun` |
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

`buildRecord` 取代了旧的独立 `alterRecord` 和 `createView` 操作类型。请求时使用三个数组分别传入每个选项包含的 Record 名：

```json
{
  "recordName": "C_ANY_REC",
  "operationType": "buildRecord",
  "createTable": ["C_TEST_REC"],
  "alterTable": ["C_TEST_REC2"],
  "createView": ["C_TEST_VIEW"]
}
```

三个数组均为可选，至少传一个。

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
    "peoplecode": "MessageBox(0, \"\", 0, 0, \"Hello!\");",
    "lastUpdate": "Last updated by: panwx, 2026/07/15 09:10:13"
  }
}
```

无代码时 `peoplecode` 和 `lastUpdate` 均为 `null`。

**modifyPeopleCode 请求示例**：
```json
{
  "recordName": "C_TEST_REC",
  "operationType": "modifyPeopleCode",
  "fieldName": "EMPLID",
  "event": "FieldChange",
  "peoplecode": "MessageBox(0, \"\", 0, 0, \"Hello!\");"
}
```

`peoplecode` 字段使用 JSON 转义（`EscapeJSON`/`UnEscapeJSON`），与 App Package 编码一致。编译错误会返回错误信息和位置。如果代码不存在则自动创建（`CreateDefn` + `SaveNewDefn`），已存在则更新（`GetDefnToUpdate` + `UpdateDefn`）。

## modifyRecord 操作

修改已存在的 Record 定义。字段属性为**全量替换**（客户端必须传完整的 `fieldProperty` 数组），v1 不做字段删除。

### 请求示例

```json
{
  "recordName": "C_TEST_REC",
  "operationType": "modifyRecord",
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

每个普通新字段可传 `insertBefore`，值为当前 Record 已存在的字段名。例如在 COUNTRY 与 C12_2483_AMOUNT 之间插入 NAME 并设为 Key：

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

### v1 限制

- 不删除字段
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
{"recordName":"C_TEST_REC2","operationType":"buildRecord","createTable":["C_TEST_REC2"]}
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
- labelId 未指定时传 null，避免用空字符串覆盖默认标签；fieldProperty 按接口枚举精确匹配，保留当前属性后再修改。
- Record 名最多 15 字符。子记录是占位符，Build 须在原位置递归展开其字段，不直接建 SUBRECORD 列。
- PSDBFIELD.LENGTH 是字节长度，不再次乘 4；Number 长度大于 18 或不大于 0 使用 NUMBER。有小数的 Signed Number 使用 DECIMAL(LENGTH-DECIMALPOS, DECIMALPOS)。
- CLOB/BLOB 排在普通列之后；索引使用 RECNAME 命名，而非 SQLTABLENAME；表空间与索引空间分开。View SQL 从 PSSQLTEXTDEFN 的 GBL/默认平台/最新生效日期读取。
- Oracle DDL 不能整体事务回滚；Alter 失败检查原表、临时表和错误，不能直接重跑覆盖。

## Field 批量查询

通过 Integration Broker REST 接口批量查询 PeopleSoft 字段定义（PSDBFIELD + PSDBFLDLABL）。

处理类： `C_META_DATA_PKG:MetaData:OperFieldDefn`

### 接口地址

```
POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/PSFT_HR/AI_OPER_FIELD_DEFN.v1/
```

### 服务操作

`AI_OPER_FIELD_DEFN_POST` — 需要在 PIA 中给用户授予 Execute 权限。

### 请求体

请求体是**纯 JSON 数组**（不是对象），元素为字段名：

```json
["EMPLID", "EFFDT", "LASTUPDDTTM"]
```

空字段名会被跳过（`All()` 判断）。

### 响应格式

公共响应见 [安装说明](01-auth-api.md#公共调用规则)。

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "fields": [
      {
        "fieldName": "EMPLID",
        "fieldType": "character",
        "fieldTypeCode": 0,
        "length": 11,
        "lastUpdate": "Last updated by: PPLSOFT, 2020/01/01 00:00:00",
        "comment": "Employee ID",
        "labels": [
          { "labelId": "EMPLID", "longName": "员工 ID", "shortName": "员工", "defaultLabel": "N" }
        ]
      }
    ]
  }
}
```

### fields 数组元素

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `fieldName` | string | 字段名 |
| `fieldType` | string | 类型名（MappingUtil.GetFieldTypeName 解码，FIELDTYPE + IMAGE_FMT） |
| `fieldTypeCode` | int | 原始 FIELDTYPE 编码（0=Char,1=LongChar,2=Number,3=SignedNumber,4=Date,5=Time,6=DateTime,8=Image/Attachment,9=ImageRef） |
| `length` | int | 字段长度（PSDBFIELD.LENGTH，字节长度） |
| `lastUpdate` | string | 最后更新人 + 时间 |
| `comment` | string | 长描述（DESCRLONG，明文返回） |
| `labels` | array | Label 列表（PSDBFLDLABL），每项含 labelId/longName/shortName/defaultLabel |

### 注意事项

- 与 AI_SEARCH_DEFN（`definitionType=2`）不同：本接口返回完整字段定义（含 label、comment、lastUpdate），Search 只返回 fieldName/fieldType/length 三字段
- comment 明文返回（未 JSON 转义）

## 删除 Record Field 程序

```powershell
python scripts/peoplesoft_api.py record delete-code MY_RECORD --fieldname COUNTRY --event FieldChange --project MY_PROJECT --dry-run
```

保留 Record 和 Field；同字段其他事件不受影响。viewPeopleCode 增加 programExists。省略 `--dry-run` 执行删除；支持 `--output`，见 [删除流程](development-standards.md#peoplecode-真正删除)。
