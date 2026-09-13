# BuildRecord 完整参考

## PeopleSoft → Oracle 类型映射

### GetFieldOracleType 逻辑

| PS FIELDTYPE | 名称 | 条件 | Oracle 类型 | NULL |
|-------------|------|------|------------|------|
| 0 | Character | — | `VARCHAR2(len)` | NOT NULL |
| 1 | Long Character | — | `CLOB` | nullable |
| 2 | Number | LEN ≤ 4 | `SMALLINT` | NOT NULL |
| 2 | Number | 5 ≤ LEN ≤ 9 | `INTEGER` | NOT NULL |
| 2 | Number | 10 ≤ LEN ≤ 18 | `NUMBER(len)` | NOT NULL |
| 2 | Number | LEN > 18 或 ≤ 0 | `NUMBER` | NOT NULL |
| 3 | Signed Number | DECIMALPOS > 0 | `DECIMAL(LEN-DECIMALPOS, DECIMALPOS)` | NOT NULL |
| 3 | Signed Number | DECIMALPOS = 0 | 同 Number 规则 | NOT NULL |
| 4 | Date | — | `DATE` | nullable |
| 5 | Time | — | `TIMESTAMP` | nullable |
| 6 | DateTime | — | `TIMESTAMP` | nullable |
| 8 | Image/Attachment | — | `BLOB` | nullable |
| 9 | Image Reference | — | `VARCHAR2(len)` | NOT NULL |

> **关键**：`PSDBFIELD.LENGTH` 在 PeopleCode SQLExec 中返回**字节长度**，不要再乘 4。
> Signed Number 的 `DECIMALPOS` 从小数位数，精度 = LENGTH - DECIMALPOS。

## DDL 模式

### CREATE TABLE

```sql
CREATE TABLE PS_<RECNAME> (
  <NON_CLOB_BLOB_FIELDS>,
  <CLOB_FIELDS>,
  <BLOB_FIELDS>
) TABLESPACE <DDLSPACENAME> STORAGE (INITIAL 40000 NEXT 100000 MAXEXTENTS UNLIMITED PCTINCREASE 0) PCTFREE 10 PCTUSED 80
```

- 字段顺序：非 CLOB/BLOB 按 FIELDNUM 排 → CLOB → BLOB（与 AD 行为一致）
- 表名：PSRECDEFN.SQLTABLENAME 或默认 `PS_<RECNAME>`
- 表空间：取自 PSRECTBLSPC.DDLSPACENAME
- STORAGE/PCTFREE/PCTUSED：PeopleSoft 标准默认值
- **无 SYSADM 前缀**（与 AD 一致）

### CREATE INDEX

```sql
CREATE [UNIQUE] INDEX PS<IDX><RECNAME>
ON PS_<RECNAME> (<FIELDS>)
TABLESPACE PSINDEX STORAGE (INITIAL 40000 NEXT 100000 MAXEXTENTS UNLIMITED PCTINCREASE 0) PCTFREE 10 PARALLEL NOLOGGING
```

```sql
ALTER INDEX PS<IDX><RECNAME> NOPARALLEL LOGGING
```

- 索引名：`PS<INDEXID><RECNAME>`，主键 `_` → `PS_<RECNAME>`
- UNIQUE：PSINDEXDEFN.UNIQUEFLAG = 1
- 索引表空间：固定 `PSINDEX`
- KEYPOSN 排序
- PARALLEL NOLOGGING 后跟 ALTER INDEX NOPARALLEL LOGGING

### CREATE VIEW

```sql
CREATE OR REPLACE VIEW PS_<RECNAME> (<COLUMNS>) AS <SQL_BODY>
```

- 列列表：从 PSRECFIELD 按 FIELDNUM 取（含子记录展开）
- SQL Body：从 PSSQLTEXTDEFN 读取（SQLID = RECNAME, MARKET='GBL', DBTYPE=' ', 最新 EFFDT）
- 视图名：PSRECDEFN.SQLTABLENAME 或默认 `PS_<RECNAME>`

## 与 AD Build 的对齐状态

| 项目 | AD | REST API | 状态 |
|------|-----|----------|------|
| Number 类型 | SMALLINT/INTEGER/NUMBER | 同 | ✅ |
| Signed Number | DECIMAL(prec,scale) | 同 | ✅ |
| Time 类型 | TIMESTAMP | TIMESTAMP | ✅ |
| CLOB/BLOB 排序 | 末尾 | 末尾 | ✅ |
| SYSADM 前缀 | 无 | 无 | ✅ |
| STORAGE 子句 | 有 | 有 | ✅ |
| PCTFREE/PCTUSED | 有 | 有 | ✅ |
| PARALLEL NOLOGGING | 有 | 有 | ✅ |
| ALTER INDEX | 有 | 有 | ✅ |
| View 读取 SQL | PSSQLTEXTDEFN | 同 | ✅ |

仅格式差异（单行 vs 多行、tIMESTAMP vs TIMESTAMP 大小写）为 Oracle 内部存储行为，DDL 语义完全一致。
