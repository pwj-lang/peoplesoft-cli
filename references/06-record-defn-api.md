# AI_OPER_RECORD_DEFN API

通过 Integration Broker REST 接口查看、创建、修改 Record 定义，Build/Alter 实体表，创建视图。

## 接口地址

```
POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/{node}/AI_OPER_RECORD_DEFN.v1/
```

> **URL 注意**：接口地址是 `AI_OPER_RECORD_DEFN.v1/`（不带 `_POST`）。

## 请求体参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `recordName` | string | **是** | Record 名称，必须精确匹配 |
| `operationType` | string | 否 | 操作类型，默认 `"struct"`。支持 `"struct"`、`"createRecord"`、`"modifyRecord"`、`"buildRecord"`、`"viewSQL"`、`"modifySQL"`、`"viewPeopleCode"`、`"modifyPeopleCode"` |

### operationType 取值一览

| operationType | 说明 | 额外参数 |
|---------------|------|----------|
| `"struct"` | 查看 Record 结构 | 无 |
| `"createRecord"` | 创建新 Record | `recName`、`fields`、`tableSpace` |
| `"modifyRecord"` | 修改 Record（更新字段属性 / 新增字段） | `fields` |
| `"buildRecord"` | Build/alter/create view — 三个子选项 | `createTable`、`alterTable`、`createView`（三个数组） |
| `"viewPeopleCode"` | 查看 Record Field PeopleCode | `fieldName`、`event` |
| `"modifyPeopleCode"` | 修改/创建 Record Field PeopleCode | `fieldName`、`event`、`peoplecode` |
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

**PeopleCode Key 结构**：

PeopleCode 的 `%metadata:PeopleCodeProgram:PeopleCodeProgram_Manager` 使用分层 Key 结构来定位不同类型的 PeopleCode 程序。不同定义类型使用不同的 Key 层级和 KeyClass 常量：

| 定义类型 | Key 层级（从外到内） | KeyClass 常量 |
|----------|---------------------|---------------|
| **Record Field** | Class_Record → Class_Field → Class_Method | Record + Field + Event |
| **App Package** | Class_Application_Package → Class_Application_Class → Class_Method | 包 + 类 + 方法 |
| **AE** | Class_Application_Engine → Class_Section → Class_Step → Class_Action → Class_Method (?) | AE + Section + Step + Action |
| **Page** | Class_Panel → Class_Field → Class_Method | Page + Field + Event |
| **Component** | 硬编码 10 + Market → Class_Record → Class_Field → Class_Method | 10 + Market + Record + Field + Event |

> 注意：Component 使用硬编码常量 `10`（`Class_PnlGrp` 编译时符号解析失败，只能直接用数值）。Market 是必填层，例如 GBL 对应 `39`。

```peoplecode
/* Record Field PeopleCode */
Local %metadata:Key &Key = create %metadata:Key(Key:Class_Record, &RecName);
&Key.AddItem(Key:Class_Field, &FieldName);
&Key.AddItem(Key:Class_Method, &Event);

/* Component PeopleCode — 必须包含 Market 层，否则 GetProgram 返回 DefnExists=false */
Local %metadata:Key &Key = create %metadata:Key(10, &CompName);
&Key.AddItem(39 /* GBL */, &Market);
&Key.AddItem(Key:Class_Record, &RecName);
&Key.AddItem(Key:Class_Field, &FieldName);
&Key.AddItem(Key:Class_Method, &Event);
```

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
| 字段不在 Record 中 | 追加到末尾（`editTable`/`labelId`/`defaultPageControl`/`defaultRecName`/`defaultFieldName` 可随请求指定） |
| 未在 `fields` 中出现的字段 | 保持不变 |
| `descr`/`comment` 等 Record 级属性 | 可选，传入则更新 |

### GUI 一致性校验（2026-09-05 新增，createRecord/modifyRecord 均生效）

`fieldProperty` 请求经过 `RecordUseEdit.ValidateFieldProperty` 校验，规则与 Application Designer 的 Record Field Properties 对话框**完全一致**：GUI 中置灰（不可勾选）的组合会被拒绝，返回 400 并逐字段列出原因；任一字段校验失败则整个请求不写库（先全量校验、后统一写库）。

- **依赖链**：SearchKey 需要 Key；SearchEdit 需要 SearchKey；DescendingKey 需要 Key/AlternateSearchKey/SearchKey 之一；DefaultSearchField 需要 SearchKey/AlternateSearchKey
- **互斥**：FromSearchField 与 ThroughSearchField；四种 Table Edit（Yes/NoTableEdit、PromptTableEdit、TranslateTableEdit、1/0TableEdit）互斥
- **类型限制**：Auto-Update 仅 date/time/datetime；RequiredField 不支持 long character/image/imageReference/attachment；Key/搜索组/Audit 组不支持 long character/image/attachment（imageReference 支持）；ReasonableDate 仅 date；Yes/NoTableEdit 仅 character；1/0TableEdit 仅 number/signed number；PromptTableEdit 位仅 character/number（date/time/datetime 只能填 editTable，不写位）；EnableAutocompleteWhenUsedInSearchRecord 仅 character
- **前置条件**：EnableAutocomplete 需要 Default Page Control = Edit Box/System Default；DisableAutocompleteForThisField 需要字段已配置提示表（`editTable` 非空）；DisplayInAutocompleteWindow 需要 ListBoxItem 且不是搜索项（勾 SearchKey/AltSearchKey 时 AD 会自动清空它）；PersistInMenu 需要 ListBoxItem；TranslateTableEdit 需要字段本身有翻译值（PSXLATDEFN 有记录）
- **其它**：InMemory 被拒绝（需 Oracle In-Memory 列存储选项，本环境 GUI 中置灰）；子记录引用字段（SUBRECORD=Y）不可带 fieldProperty；未知属性名与内部标记 `RegularField`（默认 Label 位）被拒绝

`defaultPageControl` 取值：`"System Default"`(99)、`"Edit Box"`(4) 或数字代码；其它控件名的代码未确认，暂不接受。

### v1 限制

- 不删除字段
- 不调整字段顺序
- 不修改 Record 类型
- 常量默认值（Constant Default）暂不支持写入

## buildRecord 操作

根据 Record 定义在数据库中创建实体表，与 AD 的 Build 操作等效。

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
{"recordName": "C_TEST_REC2", "operationType": "buildRecord"}
```

---

## 响应格式

统一 `code/message/data`。

## USEEDIT / USEEDIT2 位标志参考

> 来源：`RecFldProperty.txt` + PSRECFIELD 验证

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

### Python 位运算反推

```python
USEEDIT_FLAGS = {
    1: "Key", 2: "Duplicate Order Key", 4: "System Maintained",
    8: "Field Add", 16: "Alternate Search Key", 32: "List Box Item",
    64: "Descending Key", 128: "Field Change", 256: "Required",
    512: "TableEdit Translate Table Edit", 1024: "Field Delete",
    2048: "Search Key", 8192: "TableEdit YES/NO",
    16384: "TableEdit Prompt Table Edit", 32768: "Auto-Update",
    262144: "From Search Field", 524288: "Through Search Field",
    2097152: "Disable Advanced Search Options",
    8388608: "(base value)", 16777216: "Default Search Field",
    134217728: "Allow Search Events for Prompt Dialogs",
    268435456: "Search Edit",
}

USEEDIT2_FLAGS = {
    8388608: "Do Not trace Value", 524288: "In Memory",
    65536: "Disable Autocomplete for this field",
}

def decode_useredit(value):
    if value < 8388608: return ["ERROR"]
    flags = value - 8388608
    return [n for b, n in sorted(USEEDIT_FLAGS.items()) if b != 8388608 and flags & b]

def decode_useredit2(value):
    results = []
    if value < 0: results.append("Persist in Menu"); value &= 0x7FFFFFFF
    for b, n in sorted(USEEDIT2_FLAGS.items()):
        if value & b: results.append(n); value &= ~b
    return results
```
