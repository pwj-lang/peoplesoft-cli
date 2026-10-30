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

搜索不证明定义所有依赖有效；修改前再用对应 struct/view 读取完整定义。字段标签和属性批量查询见 [Record 与 Field](06-record-defn-api.md#精确读取与批量查询)。

## 八类定义列表

`2.0.0-dev.2` 新增 `AI_LIST_DEFN_POST`（URI `AI_LIST_DEFN.v1/`），独立授权；支持 service、operation、menu、catalog、portal、html、stylesheet、ci，不改变原有 search 的五类契约。

```powershell
python scripts/peoplesoft_api.py service list C_AI_ --limit 50
python scripts/peoplesoft_api.py service-op list AI_ --after AI_OPER_SQL_DEFN_POST --limit 50
python scripts/peoplesoft_api.py message-catalog list 325
python scripts/peoplesoft_api.py portal list C_AI_ --portal EMPLOYEE --type link
python scripts/peoplesoft_api.py ci list
```

名称参数是字面前缀，省略则列出全部；`%`、`_`、反斜杠均按字面处理，自动转大写。每页 `--limit` 为 1..200，默认 50；结果为 `list[{name,descr}]`、`hasMore`、`nextAfter`。仅在 hasMore=true 时，以 nextAfter 作为下一次 `--after`，保持前缀、门户和类型一致。无结果为空数组。消息集编号按字符串排序。

直接 REST 示例：`{"kind":"html","prefix":"C_AI_","after":"","limit":50}`。门户另传 PortalName 和 RefType=F/C；C 可用 IsLink=true/false 筛选 Link/CREF。CLI 的 folder/cref/link 会设置对应筛选。列表包含可读取的原生定义类型，写入范围仍受各维护接口限制；它不证明依赖有效，也不保证并发修改期间形成一致快照。
