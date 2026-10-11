# SQL 定义

通过 Integration Broker REST 接口查看、创建和修改 PeopleSoft SQL 定义。

## 接口地址

```
POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/PSFT_HR/AI_OPER_SQL_DEFN.v1/
```

## 请求体公共参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `sqlId` | string | **是** | SQL 对象的唯一标识。可通过 SearchDefinition（definitionType=65）获取 |
| `operationType` | string | 否 | 操作类型，默认为 `"view"`。可选值：`"view"`、`"create"`、`"modify"` |

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
| `statements[].dbType` | string | 元数据字符码（默认 32；Oracle 专用 50；其余 49~55） |
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
