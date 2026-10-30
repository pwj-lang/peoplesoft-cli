# SQL 定义

读写分离部署：查询使用 `C_META_DATA_READ` 的对应 `AI_READ_*` URI，写入使用 `C_META_DATA_WRITE` 的原 `AI_OPER_*` URI；处理类分别位于 `C_META_DATA_PKG:MetaData:Read`、`:Write`。CLI 在 split 环境自动选择，完整映射及许可权配置见 [安装与读写分离](01-auth-api.md#读写分离2026-10-30)。下文参数/版本契约继续适用；旧混合 URI 的读取示例须改用对应 Read URI。

通过 Integration Broker REST 接口查看、创建和修改 PeopleSoft SQL 定义。

## 原始版本与冲突处理（2026-10-29）

SQLType=0 的 create、modify 必须携带原始 `expectedVersion`。view 对已存在和不存在名称都返回 `exists`、`version`（`sql1:` 前缀）和 `sqlVersionControl=1`；创建前也先读取不存在名称。版本覆盖定义头、所有 Market/DBType/EffDt/SeqNum 正文段、描述、翻译、哈希和删除标记。SRM 与父行锁内比较并保存；缺少/空版本返回428，旧版本返回409，失败回滚。读取过程中发生修改也返回409，需重新读取。

CLI 保存完整结构快照，下载的每个 `.sql` 旁保存 `.snapshot.json`，绑定环境、服务器、节点、账号、SQL 名称和精确 Statement 键。带正文文件修改时默认使用该文件旁的快照；显式 `--snapshot` 可选先前结构或对应正文快照。缺快照拒绝写入，不能使用保存前的新读取替换基线。409 时另存最新结构及正文，保留原稿和原快照且不自动重试。

```powershell
# 读取不存在名称后创建；statement.json 仅含 statements 业务数组
python scripts/peoplesoft_api.py sql view MY_SQL --output original.json
python scripts/peoplesoft_api.py sql create MY_SQL statement.json --snapshot original.json
# 已存在定义：使用 view 输出的正文文件及其 sidecar
python scripts/peoplesoft_api.py sql view MY_SQL
python scripts/peoplesoft_api.py sql modify MY_SQL --sqltext-file <下载的.sql> --market GBL --dbtype DEFAULT --effdt 1900-01-01
```

`--descr` 修改目标 Statement 描述，`--comment-file` 修改注释。创建和修改成功后独立回读完整 Statement 集合、正文及描述，原快照不自动推进；下一次编辑重新读取。`--dry-run` 在原生保存校验后回滚，不登记工程；此参数仅适用于定义维护，sql exec/run/write 会拒绝，不能用于数据执行。SQL 定义命令沿用手工 `project insert-item` 登记方式，先读取 Project 原始快照。

直接请求的示例需在 create/modify 中增加 `"expectedVersion":"<view 返回的原始 version>"`；可传 `dryRun:true`。成功写响应增加 `beforeVersion`、`version`、`sqlVersionControl`、`dryRun`。dry-run 响应的 version 描述回滚前的拟保存状态，不能作为后续写入基线。版本控制用于并发覆盖检测，不提供历史版本库。需配套新版编译后的 OperSqlDefn、Utility:DefinitionVersion 与 `scripts/sql_project_operations.py`；REST URI及权限不变。

执行数据查询使用 [sql exec/run](10-sql-exec-api.md)，单条 DML 使用单独授权的 sql write。本接口维护 SQL 定义，不授予数据执行权限；sql run 首期只读，按当前数据库与 as-of date 原生选择正文后校验。

## 接口地址

```
POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/PSFT_HR/AI_OPER_SQL_DEFN.v1/
```

## 请求体公共参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `sqlId` | string | **是** | SQL 对象的唯一标识。可通过 SearchDefinition（definitionType=65）获取 |
| `operationType` | string | 否 | 操作类型，默认为 `"view"`。可选值：`"view"`、`"create"`、`"modify"` |
| `expectedVersion` | string | 写入必填 | 先前 view 的原始 version；创建使用不存在状态的令牌 |
| `dryRun` | boolean | 否 | 默认false；定义写入执行校验后回滚 |

> 注意：此接口目前仅支持 SQL 类型 0（普通手工创建的 SQL 对象）。sqlType 由后端硬编码，不需要传。

## 各操作详解

### 1. view — 查看 SQL

无额外必填参数。返回 SQL 的基本信息及所有 Statement 行。

#### 响应 data 结构

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "sqlId": "MY_SQL_001",
    "sqlType": "0",
    "lastUpdate": "Last updated by: panwx, 2026/07/03 10:00:00",
    "statements": [
      {
        "market": "GBL",
        "dbType": "32",
        "effdt": "1900-01-01",
        "sqlText": "SELECT EMPLID, NAME FROM PS_EMPLOYEES WHERE EMPLID = :1",
        "descr": "Query employees",
        "comment": "Long description stored in DB (plain text, not encoded)"
      }
    ]
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `sqlId` | string | SQL 标识 |
| `sqlType` | string | SQL 类型（固定 `"0"`） |
| `lastUpdate` | string | 最后更新信息 |
| `statements` | array | Statement 行数组 |
| `statements[].market` | string | 市场（如 "GBL"） |
| `statements[].dbType` | number | 元数据字符码（默认 32；Oracle 专用 50；其余 49~55） |
| `statements[].effdt` | string | 生效日期 |
| `statements[].sqlText` | string | SQL 文本（JSON 转义） |
| `statements[].descr` | string | 描述 |
| `statements[].comment` | string | 长注释（JSON 转义） |

### 2. create — 创建 SQL

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `statements` | array | **是** | Statement 数组，至少一个元素。每项包含以下字段 |

每个 Statement 元素：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `market` | string | 否 | "GBL" | 市场 |
| `dbType` | string | 否 | "" (default) | 数据库类型名称（如 "ORACLE"），后端通过 MappingUtil.GetDbTypeCode 转码 |
| `effdt` | string | 否 | "1900-01-01" | 生效日期 |
| `sqlText` | string | **是** | — | SQL 文本（**JSON 转义**后传输） |
| `descr` | string | 否 | — | 描述 |
| `comment` | string | 否 | — | 长注释（JSON 转义后传输） |

### 3. modify — 修改 SQL

修改指定 market/dbType/effdt 匹配的 Statement 行。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `market` | string | **是** | 市场（定位要修改的 Statement） |
| `dbType` | string | **是** | 数据库类型（定位要修改的 Statement） |
| `effdt` | string | **是** | 生效日期（定位要修改的 Statement） |
| `sqlText` | string | 否 | 新的 SQL 文本（**JSON 转义**后传输） |
| `descr` | string | 否 | 新的描述 |
| `comment` | string | 否 | 新的长注释（**JSON 转义**后传输） |

## 响应格式

公共响应见 [安装说明](01-auth-api.md#公共调用规则)。

## 编码注意事项

- **create / modify 传入**：`sqlText` 和 `comment` 需 **JSON 转义**后传输，后端通过 `UnEscapeJSON` 自动解码
- **view 返回**：`sqlText` 和 `comment` 为 **JSON 转义**（CLOB 类型，特殊字符需转义）
- `descr` 为明文（VARCHAR 类型，无特殊字符风险）
- 后端会对 sqlText 做 `\s+` → 单空格 的空白规范化处理（create 和 modify 均适用）

## 完整示例

### 查看 SQL

```json
{
  "sqlId": "MY_SQL_001",
  "operationType": "view"
}
```

### 创建 SQL

```json
{
  "sqlId": "MY_SQL_002",
  "operationType": "create",
  "statements": [
    {
      "market": "GBL",
      "sqlText": "SELECT EMPLID, NAME FROM PS_EMPLOYEES"
    }
  ]
}
```

### 修改 SQL

```json
{
  "sqlId": "MY_SQL_001",
  "operationType": "modify",
  "market": "GBL",
  "dbType": "",
  "effdt": "1900-01-01",
  "sqlText": "SELECT EMPLID, NAME FROM PS_EMPLOYEES WHERE EMPLID = :1"
}
```

## 数据库类型选择和保存核验

输入 `""`、`DEFAULT`、`32` 均定位默认 Statement；ORACLE、2、50 均定位 Oracle 专用 Statement，不能用于默认行。其余兼容输入为 DB2/1/49、INFORMIX/3/51、DB2UNIX/4/52、TIMESTEN/5/53、SYBASE/6/54、MICROSOFT/7/55；CLI 还接受 SQLSERVER。未知值会报错。

modify 找不到完整 market/dbType/effdt 时返回错误，不再更新时间或假报成功。先 view 再按实际行定位。CLI 的 sql modify --sqltext-file 会自动回读并核对目标行和正文；仅修改描述/注释或直接调用 REST 时仍需自行回读。
