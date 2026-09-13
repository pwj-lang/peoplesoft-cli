# AI_OPER_FIELD_DEFN — 批量查询字段定义

通过 Integration Broker REST 接口批量查询 PeopleSoft 字段定义（PSDBFIELD + PSDBFLDLABL）。

Handler: `C_META_DATA_PKG:MetaData:OperFieldDefn`

## 接口地址

```
POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/{node}/AI_OPER_FIELD_DEFN.v1/
```

## Service Operation

`AI_OPER_FIELD_DEFN_POST` — 需要在 PIA 中给用户授予 Execute 权限。

## 请求头

| Header | 值 | 必填 |
| --- | --- | --- |
| `Content-Type` | `application/json` | 是 |
| `PS_TOKEN` | 登录获取的 token | 是 |

## 请求体

请求体是**纯 JSON 数组**（不是对象），元素为字段名：

```json
["EMPLID", "EFFDT", "LASTUPDDTTM"]
```

空字段名会被跳过（`All()` 判断）。

## 响应格式

统一 `code/message/data`：

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

## 实现说明

- 一次 `WHERE FIELDNAME IN (...)` 批量查出所有字段，减少 IO
- 每个字段再查一次 PSDBFLDLABL 获取 Label 列表
- 字段类型经 MappingUtil 解码（IMAGE_FMT=16 时类型显示为 attachment，否则 image）

## 注意事项

- 与 AI_SEARCH_DEFN（`definitionType=2`）不同：本接口返回完整字段定义（含 label、comment、lastUpdate），Search 只返回 fieldName/fieldType/length 三字段
- comment 明文返回（未 JSON 转义）
