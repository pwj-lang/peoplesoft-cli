# 定义搜索

REST：`AI_SEARCH_DEFN.v1/`。认证与公共响应见 [安装说明](01-auth-api.md#公共调用规则)。搜索类型与 Project 的 objectType、ObjectID 不同，不能混用。

## 请求参数

| 参数 | 类型 | 用途 |
|---|---|---|
| definitionType | 整数，必填 | 1=Record，2=Field，65=SQL，104=应用包，105=Project |
| definitionName | 字符串 | 名称搜索，服务端追加 `%` 通配符；省略可列出全部 |
| recordType / recordDescr | 整数 / 字符串 | Record 类型 / 描述过滤 |
| fieldType | 整数 | Field 类型过滤 |
| appPackageDescr | 字符串 | 应用包描述过滤 |
| sqlType / sqlDescr | 整数 / 字符串 | SQL 子类型 / 正文搜索；0=普通 SQL，1=AE SQL，2=视图 SQL，6=AE XSLT |
| projectDescr | 字符串 | Project 描述过滤 |

```powershell
python scripts/peoplesoft_api.py search record ABSV
python scripts/peoplesoft_api.py search field EMPLID
python scripts/peoplesoft_api.py search sql MY_SQL
python scripts/peoplesoft_api.py search project MY_PROJECT
```

```json
{"definitionType":1,"definitionName":"ABSV","recordType":0,"recordDescr":"假期"}
```

## 类型编码

Record：0=表，1=视图，2=子记录，3=派生/工作记录，5=自定义 SQL 表，6=动态视图，7=临时表。

Field：0=字符，1=长字符，2=数字，3=有符号数字，4=日期，5=时间，6=日期时间，8=图片/附件，9=图片引用。

## 搜索结果

成功返回 `data.list`，各类型条目如下；无结果时 `data` 可为空对象，不等于请求失败。

| 类型 | 返回字段 |
|---|---|
| Record | recordName、recordDescr |
| Field | fieldName、fieldType、length |
| 应用包 | packageId、descr |
| SQL | sqlId、sqlType |
| Project | projectName、projectDescr |

搜索不证明定义所有依赖有效；修改前再用对应 struct/view 读取完整定义。字段标签和属性批量查询见 [Record 与 Field](06-record-defn-api.md#field-批量查询)。
