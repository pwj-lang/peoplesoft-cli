# AI_OPER_SQL_DEFN API

通过 Integration Broker REST 接口查看、创建和修改 PeopleSoft SQL 定义。

## 接口地址

```
POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/{node}/AI_OPER_SQL_DEFN.v1/
```

## 请求头

| Header | 值 | 必填 |
|--------|-----|------|
| `Content-Type` | `application/json` | 是 |
| `PS_TOKEN` | 登录获取的 token | 是 |

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
        "dbType": "ORACLE",
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
| `statements[].dbType` | string | 数据库平台名称（如 "ORACLE"） |
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

统一 `code/message/data`：

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | int | 0=成功，非0=失败 |
| `message` | string | 成功固定 `"success"`，失败返回原因 |
| `data` | object | 成功时包含返回数据，失败时为 `{}` |

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
