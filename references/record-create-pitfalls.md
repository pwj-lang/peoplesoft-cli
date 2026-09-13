# Record create 操作陷阱与注意事项

通过 `AI_OPER_RECORD_DEFN.v1` 创建和 Build Record 时的重要陷阱。

## 陷阱 0: 字段 ID 必须用户确认，禁止猜测（流程规范）

**创建 Record 时，若用户没有明确给出字段 ID，必须先查候选、让用户选择、确认后才构建。**

- 候选查询：`python scripts/peoplesoft_api.py search field <关键词>`（搜 PSDBFIELD 里已存在的字段）
- 呈现候选（字段名/类型/长度）→ 用户确认每个业务字段映射的字段 ID → 才执行 createRecord
- 若候选无合适字段，用户指定字段名；createRecord 不会自动创建字段定义
- 完整规范见 SKILL.md「开发准则 — 创建 Record 的字段 ID 确认规范」

## 陷阱 1: `recName` vs `recordName`

`OnRequest` 和 `CreateRecordCli` 读取不同的 JSON 键：

| 方法 | 读取的键 | 说明 |
|------|----------|------|
| `OnRequest` | `recordName` | 用于校验请求是否有效 |
| `CreateRecordCli` | `recName` | 用于设置 `RecDefn.RecName` |

**必须两个都传且值一致。**

## 陷阱 1b: createRecord 必须传 `tableSpace`（可空数组）

`CreateRecordCli` 无条件执行：

```peoplecode
&JTableSpace = &p_obj.GetJsonArray("tableSpace");
For &i = 1 To &JTableSpace.Size        /* tableSpace 缺失 → NULL.Size → (180,236) */
```

**必须传 `"tableSpace": []`**（空数组即可）。省略该字段会报：
`Error: First operand of . is NULL, so cannot access member Size. (180,236) ... Name:CreateRecordCli Statement:255`

非空时元素结构：`{"spaceName": "...", "dbName": "..."}`（DBNAME 用于多数据库，通常 `""`）。

## 陷阱 2: `labelId` 必须是 `null` 而非空字符串

PeopleCode 的 `None()` 只识别 `null`，不识别空字符串 `""`。传 `""` 导致基值 8388608 丢失，useEdit=0。

## 陷阱 3: `fieldProperty` 字符串必须精确匹配 RecordUseEdit 数组

属性名大小写敏感，必须完全匹配，否则被忽略。

## 陷阱 4: fieldProperty 往返 — 已修复

**✅ 已修复（2026-07-11）**：`GetFieldPropertyByUseEdit` 的 useEdit2 循环缺少减法导致多报属性的问题已修复。API 返回的 fieldProperty 可直接用于 createRecord 往返。

## buildRecord 操作陷阱

### 陷阱 5: SubRecord 字段必须展开

当 PSRECFIELD 中 `SUBRECORD = "Y"` 时，该字段不是数据库列，而是子记录占位符。**必须递归查询并展开子记录字段**，在原位置插入 CREATE TABLE。

```peoplecode
If &SubRecord = "Y" Then
   &RsSubFields = CreateRowset(Record.PSRECFIELD);
   &RsSubFields.Fill("WHERE RECNAME = :1 ORDER BY FIELDNUM", &FieldName);
   For &j = 1 To &RsSubFields.RowCount
      &OracleType = %This.GetFieldOracleType(&SubFieldName);
   End-For;
End-If;
```

### 陷阱 6: Time 类型映射为 TIMESTAMP

| PS FIELDTYPE | Oracle |
|-------------|--------|
| 4 (Date) | DATE |
| 5 (Time) | **TIMESTAMP** |
| 6 (DateTime) | TIMESTAMP |

Time **不是** VARCHAR2，也用不着 `(6)` 精度后缀。与 AD 的 DDL 保持一致。

### 陷阱 7: PSDBFIELD.LENGTH 已是字节长度

`PSDBFIELD.LENGTH` 在 PeopleCode SQLExec 中返回的是**字节长度**（含 UTF-8 倍数），不要再用 `*4` 乘数。

### 陷阱 8: Number 类型按范围细分

| LEN 范围 | Oracle 类型 |
|---------|------------|
| ≤ 4 | SMALLINT NOT NULL |
| 5-9 | INTEGER NOT NULL |
| 10-18 | NUMBER(len) NOT NULL |
| > 18 或 ≤ 0 | NUMBER NOT NULL |

Signed Number 额外读取 `DECIMALPOS`：若 > 0 → `DECIMAL(LEN-DECIMALPOS, DECIMALPOS) NOT NULL`。

### 陷阱 9: CLOB/BLOB 字段排到建表语句末尾

与 AD Build 行为一致，CREATE TABLE 中非 CLOB/BLOB 字段在前，CLOB 其次，BLOB 最后。不符合此顺序会导致与 AD 生成的 DDL 不一致。

### 陷阱 10: Build 表无需 SYSADM 前缀

AD Build 生成的 DDL 不带 schema 前缀，API 也不应加。但注意 Oracle 数据字典查询（如 `ALL_TAB_COLUMNS`）中的 `OWNER='SYSADM'` 不应移除。

### 陷阱 11: Record 名称最长 15 字符

PeopleSoft Record 名上限 15 字符，超出会报 `Failed to set value`。

### 陷阱 12: CreateView 的 SQL 必须从 PSSQLTEXTDEFN 读取

View Record 的 SQL 正文存储在 `PSSQLTEXTDEFN`（SQLID=Record名），不是从字段列表自动生成。API 应读取 `SQLTEXT`（CLOB），拼接 `CREATE OR REPLACE VIEW <name> (<cols>) AS <sql_body>`。

查询条件：`WHERE SQLID = :1 AND MARKET = 'GBL' AND DBTYPE = ' ' AND EFFDT = (SELECT MAX(EFFDT) ...)`

### 陷阱 13: PeopleCode JSON 响应可能含控制字符

PeopleCode 的 `ToString()` 或异常消息可能包含原始 `\r\n` 控制字符，直接放入 JSON 会导致客户端解析失败。客户端应做容错处理（regex 替换引号内的控制字符）。

### 陷阱 14: 索引名用 RECNAME 而非 SqlTableName

Oracle 索引命名约定 `PS<INDEXID><RECNAME>`：主键 `_` → `PS_<RECNAME>`，其他如 `A` → `PSA<RECNAME>`。使用 `&RecName`（来自参数），不是 `&SqlTableName`。

### 陷阱 15: 索引表空间固定 PSINDEX

所有索引 `TABLESPACE PSINDEX`，与数据表（取自 PSRECTBLSPC.DDLSPACENAME）分离。

### 陷阱 16: CreateSQL join 有 bind 兼容性问题

`CreateSQL("SELECT ... FROM A, B WHERE A.X = :1")` 报"绑定编号大于输入参数个数"。改用 `Rowset.Fill` 逐表查询。

### 陷阱 17: 私有方法调用需 %This. 前缀

PeopleCode 类内调用私有方法必须 `%This.MethodName(...)`，直接 `MethodName(...)` 报「未知函数」编译错误。

### 陷阱 18: modifyPeopleCode 成功后仍需验证

`modifyPeopleCode` 返回 `code=0` 不保证代码已更新。上次因编译失败（未声明方法），后续修复只给空方法加 `%This.` 前缀，实际代码未写入。**每次 modifyPeopleCode 后必须用 viewPeopleCode 验证服务器源码**。

