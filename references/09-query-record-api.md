# AI_QUERY_RECORD — 业务数据查询接口

通过 Integration Broker REST 接口查询 PeopleSoft 业务数据（**数据查询，非元数据操作**）。AI 查询业务数据时应使用本接口，不应绕过接口访问用户环境。

Handler: `C_META_DATA_PKG:RecordQuery:OperQueryRecord`

> **端点名注意**：Service Operation 注册名是 `AI_QUERY_RECORD_POST`（见 PSOPERATIONURI），
> 但 REST 监听器 URI 统一去掉 `_POST` 后缀 → 实际调用 `AI_QUERY_RECORD.v1/`。
> 与 AI_SEARCH_DEFN、AI_OPER_RECORD_DEFN 等端点命名规律一致。

## 接口地址

```
POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/{node}/AI_QUERY_RECORD.v1/
```

## 请求头

| Header | 值 | 必填 |
| --- | --- | --- |
| `Content-Type` | `application/json` | 是 |
| `PS_TOKEN` | 登录获取的 token | 是 |

## 请求体参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `record` | string | **是** | Record 名，如 `PS_JOB` |
| `fields` | array | **是** | 要查询的字段名数组，如 `["EMPLID","EMPL_RCD"]` |
| `filter` | array | 否 | 过滤条件数组，每项 `{field, op, value}`，条件之间 AND 连接 |
| `maxRows` | number | 否 | 最大返回行数，默认 200，<=0 时重置为 200 |

### filter 数组元素

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `field` | string | 字段名 |
| `op` | string | 操作符，如 `=`、`>`、`<`、`LIKE` 等 |
| `value` | string | 值。纯数字直接拼接，非数字单引号包裹并做 `'` → `''` 转义 |

> **⚠️ 实测 bug：`value` 传数字（number）会触发 `GetStringPtr() is called on non-string JSON value (262,2122)`**。
> 服务器端 `BuildWhereClause` 对非字符串 value 报错，`query-record` 直接 999。**value 必须传字符串**，即使过滤的是数字字段（如 `OBJECTTYPE`）也传 `"104"` 而不是 `104`。遇到此错把 value 改成字符串即可。

## 响应格式

统一 `code/message/data`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | int | 0=成功，非0=失败 |
| `message` | string | 成功固定 `"success"` |
| `data` | object | 成功时含 `record`/`fields`/`rows`/`rowCount` |

data 结构：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `record` | string | 查询的 Record 名 |
| `fields` | array | 字段元数据数组，每项 `{name, label, type}`（type 为 MappingUtil 解码后的类型名） |
| `rows` | array | 数据行数组，每项 `{v: [字段值数组]}`（按 fields 顺序） |
| `rowCount` | int | 实际返回行数 |

### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "record": "PS_JOB",
    "fields": [
      { "name": "EMPLID", "label": "员工 ID", "type": "character" },
      { "name": "EMPL_RCD", "label": "员工记录编号", "type": "number" }
    ],
    "rows": [
      { "v": ["0001", "0"] }
    ],
    "rowCount": 1
  }
}
```

## 请求示例

```json
{
  "record": "PS_JOB",
  "fields": ["EMPLID", "EMPL_RCD", "EFFDT"],
  "filter": [
    { "field": "EMPLID", "op": "=", "value": "0001" }
  ],
  "maxRows": 100
}
```

## 注意事项

- 元数据字段类型使用 `MappingUtil.GetFieldTypeName`（FIELDTYPE + FORMAT 解码）
- `v` 数组中的数值列以字符串返回，消费方按需要转换类型。
- 本接口用于业务数据查询，与元数据接口（`AI_OPER_*_DEFN`）用途不同。
