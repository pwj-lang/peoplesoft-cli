# 业务数据查询

通过 Integration Broker REST 查询业务数据。处理类：`C_META_DATA_PKG:RecordQuery:OperQueryRecord`。Operation 名为 `AI_QUERY_RECORD_POST`，实际 URI 去掉 `_POST`：

```text
POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/PSFT_HR/AI_QUERY_RECORD.v1/
```

认证和公共响应见 [安装说明](01-auth-api.md#公共调用规则)。本实现仅在 PANWX25 / Oracle / PeopleTools 8.60.10 验收。

## 请求参数

| 参数 | 类型 | 约束 |
|---|---|---|
| record | string | 必填，单一 ASCII 名称；逻辑 Record（如 JOB）或 PSRECDEFN 中登记的物理表/视图名（如 PS_JOB） |
| fields | array of string | 必填，1～64 个不重复字段；每个字段须属于指定 Record |
| filter | array of object | 可省略，最多 50 项；各项仅含 field、op、value，条件以 AND 连接 |
| maxRows | integer | 默认 200，<=0 使用 200，上限 1000；不得传字符串、布尔或非整数 |

Record/Field 名称为 1～128 个字符，首字符 A～Z，其余仅 A～Z、0～9、下划线；输入转大写。不允许 schema、表达式、注释或任意 SQL。物理名称映射到多个 Record 时须指定逻辑名。只支持具有物理表/视图的 Record 类型 0、1、6、7。

| filter 字段 | 类型 | 约束 |
|---|---|---|
| field | string | 同样验证名称与 Record 归属，不要求出现在 fields 中 |
| op | string | `=`、`!=`、`<>`、`>`、`>=`、`<`、`<=`、`LIKE`、`NOT LIKE` |
| value | string | 最多 4000 字符，无 NUL；数字字段也传 `"104"`，不接受数字 JSON 值 `104` |

CLI 在认证及 HTTP 前检查，服务端独立重复类型/边界检查并核实元数据；绕过 CLI 的非法请求也返回 code=400。过滤值及 ROWNUM 限额通过 CreateSQL 的 Array of Any 绑定，不作为 SQL 文本拼接。引号、中文、前导零与控制字符不会按分隔符拆列。查询失败直接报错，不回退到 Rowset.Fill。

```powershell
python scripts/peoplesoft_api.py query-record JOB EMPLID,EMPL_RCD --filter '[{"field":"EMPLID","op":"=","value":"0001"}]' --max-rows 100
```

复杂 filter 可存为 UTF-8 JSON 文件，将文件路径传给 `--filter`。

## 输出与类型

data 含 record（请求名称转大写）、fields（按请求顺序的 name/label/type；**label 当前固定为空字符串**，保留字段，尚未从 PSDBFLDLABL 读取标签）、rows（每行 `{v:[字符串值]}`）及 rowCount。无匹配记录时 rows=[]、rowCount=0，不生成空白占位行。

支持 PSDBFIELD.FIELDTYPE 0、1、2、3、4、5、6、9，即 character、long character、number、signed number、date、time、datetime、imageReference。拒绝 image/BLOB 及未验收的类型。查询与过滤字段均应用类型检查。

- 所有值为字符串；数据库 NULL 返回空字符串，无法与真实空字符串区分。
- 数值由 Oracle TO_CHAR(TM9) 按固定小数分隔符输出，避免 PeopleCode 数值转换损失精度；调用方自行选择 Decimal 等精确类型。
- 日期/时间由 Oracle TO_CHAR 使用环境默认格式，未规定跨环境统一 ISO 格式。
- CLOB 按列读取，实测 6000 多字符、中文、引号、Char(31)、换行和 TAB 完整保留；不将多列串接后拆分。

```json
{"code":0,"message":"success","data":{"record":"JOB","fields":[{"name":"EMPLID","label":"","type":"character"}],"rows":[{"v":["0001"]}],"rowCount":1}}
```

行数限制控制返回量，不能保证扫描成本；优先使用索引条件。输入保护未增加业务组件的行级安全或字段权限，调用者权限及 Access ID 边界见 [安全说明](../SECURITY.md)。
