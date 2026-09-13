# AI_SEARCH_DEFN API

通过 Integration Broker REST 接口搜索 PeopleSoft App Designer 定义。

## 接口地址

```
POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/{node}/AI_SEARCH_DEFN.v1/
```

## 请求头

| Header | 值 | 必填 |
|--------|-----|------|
| `Content-Type` | `application/json` | 是 |
| `PS_TOKEN` | 登录获取的 token | 是 |

## 请求体

```json
{
  "definitionType": 1,
  "definitionName": "ABSV"
}
```

## 全部参数说明

| 参数 | 类型 | 适用类型 | 必填 | 说明 |
|------|------|----------|------|------|
| `definitionType` | int | 全部 | **是** | 定义类型：1=Record, 2=Field, 65=SQL, 104=Application Package, 105=Project |
| `definitionName` | string | 全部 | 否 | 名称模糊搜索（自动追加 % 通配符） |
| `recordType` | int | 仅 Record (1) | 否 | 按 Record 类型编码过滤 |
| `recordDescr` | string | 仅 Record (1) | 否 | 按描述模糊搜索 Record |
| `fieldType` | int | 仅 Field (2) | 否 | 按字段类型编码过滤 |
| `appPackageDescr` | string | 仅 App Package (104) | 否 | 按描述模糊搜索应用包 |
| `sqlType` | int | 仅 SQL (65) | 否 | 按 SQL 类型编码过滤（0=普通SQL, 1=AE SQL, 2=视图SQL, 6=AE XSLT） |
| `sqlDescr` | string | 仅 SQL (65) | 否 | 按 SQL 文本内容模糊搜索（搜 PSSQLTEXTDEFN.SQLTEXT） |
| `projectDescr` | string | 仅 Project (105) | 否 | 按项目描述模糊搜索（搜 PSPROJECTDEFN.PROJECTDESCR） |

---

## 定义类型与各参数适用范围

```
definitionType=1 (Record)    → 支持: definitionName, recordType, recordDescr
definitionType=2 (Field)     → 支持: definitionName, fieldType
definitionType=65 (SQL)      → 支持: definitionName, sqlType, sqlDescr
definitionType=104 (App Pkg) → 支持: definitionName, appPackageDescr
definitionType=105 (Project)  → 支持: definitionName, projectDescr
```

---

## Record 类型编码 (recordType)

| 编码 | 类型 | 说明 |
|------|------|------|
| 0 | Table | 标准 SQL 表 |
| 1 | View | 视图 |
| 2 | SubRecord | 子记录（可复用的字段组） |
| 3 | Derived/Work | 派生/工作记录（仅内存使用，不建表） |
| 5 | SQL Table | SQL 表定义（自定义 SQL） |
| 6 | Dynamic View | 动态视图（运行时构建 SQL） |
| 7 | Temporary Table | 临时表（批处理使用） |

---

## 字段类型编码 (fieldType)

| 编码 | 类型 | 说明 |
|------|------|------|
| 0 | Character | 字符/字符串 |
| 1 | Long Character | 长字符（CLOB） |
| 2 | Number | 数字（整数/小数） |
| 3 | Signed Number | 有符号数字（可负） |
| 4 | Date | 日期 |
| 5 | Time | 时间 |
| 6 | Datetime | 日期时间 |
| 8 | Image / Attachment | 图片 / 附件 |
| 9 | Image Reference | 图片引用 |

---

## 响应格式

所有响应统一返回三个顶层字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | int | 0=成功，非0=失败 |
| `message` | string | 成功时固定为 `"success"`，失败时返回原因 |
| `data` | object | 成功时包含 Definition 数据，失败时为 `{}` |

### Record 查询成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [
      {
        "recordName": "ABSV_ACCRUAL",
        "recordDescr": "Vacation Accrual Record"
      }
    ]
  }
}
```

每个 Record 项包含 `recordName` 和 `recordDescr` 两个字段。

### Field 查询成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [
      {
        "fieldName": "EMPLID",
        "fieldType": 0,
        "length": 11
      }
    ]
  }
}
```

每个 Field 项包含 `fieldName`、`fieldType`（编码）和 `length`（长度）三个字段。

### App Package 查询成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [
      {
        "packageId": "MY_ROOT",
        "descr": "MY_ROOT Root Package"
      }
    ]
  }
}
```

每个 App Package 项包含 `packageId` 和 `descr` 两个字段。

---

## 请求示例汇总

### 1. 搜索所有名称含 ABSV 的 Record

```json
{
  "definitionType": 1,
  "definitionName": "ABSV"
}
```

### 2. 只查 Table 类型的 Record

```json
{
  "definitionType": 1,
  "definitionName": "ABSV",
  "recordType": 0
}
```

### 3. 查描述含 "Vacation" 的 Record

```json
{
  "definitionType": 1,
  "definitionName": "ABSV",
  "recordDescr": "Vacation"
}
```

### 4. 查描述含 "Vacation" 的 Table 类型 Record

```json
{
  "definitionType": 1,
  "definitionName": "ABSV",
  "recordType": 0,
  "recordDescr": "Vacation"
}
```

### 5. 搜索字段（按名称）

```json
{
  "definitionType": 2,
  "definitionName": "EMPLID"
}
```

### 6. 搜索指定类型的字段（按类型过滤）

```json
{
  "definitionType": 2,
  "definitionName": "EMPLID",
  "fieldType": 0
}
```

只查 Character 类型的字段。常用按类型查询场景：

| 需求 | fieldType 值 |
|------|-------------|
| 找所有字符型字段 | `"fieldType": 0` |
| 找所有数字型字段 | `"fieldType": 2` |
| 找所有日期型字段 | `"fieldType": 4` |
| 找所有日期时间字段 | `"fieldType": 6` |
| 找所有长文本字段（CLOB） | `"fieldType": 1` |

### 7. 搜索应用包（按名称）

```json
{
  "definitionType": 104,
  "definitionName": "MY_ROOT"
}
```

### 8. 搜索应用包（按描述过滤）

```json
{
  "definitionType": 104,
  "definitionName": "MY_ROOT",
  "appPackageDescr": "Root"
}
```

### 9. 列出所有 Record（不传名称返回全部）

```json
{
  "definitionType": 1
}
```

### 10. 搜索 SQL 定义（按名称）

```json
{
  "definitionType": 65,
  "definitionName": "MY_SQL"
}
```

### 11. 搜索指定类型的 SQL 定义

```json
{
  "definitionType": 65,
  "definitionName": "MY",
  "sqlType": 0
}
```

### SQL 查询成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [
      {
        "sqlId": "MY_SQL_001",
        "sqlType": 0
      }
    ]
  }
}
```

每个 SQL 项包含 `sqlId` 和 `sqlType` 两个字段。

### 12. 搜索 Project（按名称）

```json
{
  "definitionType": 105,
  "definitionName": "MY_PROJECT"
}
```

### 13. 搜索 Project（按描述过滤）

```json
{
  "definitionType": 105,
  "definitionName": "MY",
  "projectDescr": "Compare"
}
```

### Project 查询成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [
      {
        "projectName": "MY_PROJECT",
        "projectDescr": "Compare Project"
      }
    ]
  }
}
```

每个 Project 项包含 `projectName` 和 `projectDescr` 两个字段。

---

## 响应示例

### 成功 (搜索到数据)

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [
      {
        "recordName": "ABSV_ACCRUAL",
        "recordDescr": "Vacation Accrual Record"
      },
      {
        "recordName": "ABSV_ADDL_TBL",
        "recordDescr": "Vacation Bonus Entitlement"
      },
      {
        "recordName": "ABSV_PERIOD",
        "recordDescr": "Vacation Accrual Period"
      },
      {
        "recordName": "ABSV_PLAN_TBL",
        "recordDescr": "Vacation Plan Table"
      }
    ]
  }
}
```

### 成功 (未搜索到数据)

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

### 失败

```json
{
  "code": -1,
  "message": "Invalid definition type",
  "data": {}
}
```
