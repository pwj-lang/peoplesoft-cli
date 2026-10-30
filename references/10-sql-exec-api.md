# SQL 执行

`2.0.0-dev.1` 新增；PANWX25 / Oracle / PeopleTools 8.60.10 已验收。常规按 Record/Field 查询优先用 [query-record](09-query-record-api.md)。这里用于受控环境的诊断查询和单条 DML，绕过业务组件的行级安全和字段权限。

## 调用

```powershell
python scripts/peoplesoft_api.py sql exec --sql "SELECT 1, 0 FROM DUAL" --columns '["one","zero"]'
python scripts/peoplesoft_api.py sql exec --file D:\work\query.sql --bind '["0001"]' --max-rows 200 --output D:\work\result.json
python scripts/peoplesoft_api.py sql run MY_SQL --bind '["0001"]'
python scripts/peoplesoft_api.py sql write --file D:\work\update.sql --bind '["new text","0001"]'
```

exec/write 必须且只能提供一个 `--sql` 或 `--file`。文件为 UTF-8，可带 BOM；run 使用已登记 SQL ID，首期只读。`--columns` 是 JSON 字符串数组，`--bind` 默认 `[]`。`--output` 保存完整响应 data；`--timeout` 只限制单次 HTTP 请求，不是数据库语句超时。原有 sql view/create/modify 命令保持兼容。

| 模式 | Service Operation | URI | Handler |
|---|---|---|---|
| 查询 | AI_EXEC_SQL_POST | AI_EXEC_SQL.v1/ | C_META_DATA_PKG:MetaData:Read:OperExecSql |
| 写入 | AI_EXEC_SQL_WRITE_POST | AI_EXEC_SQL_WRITE.v1/ | C_META_DATA_PKG:MetaData:Write:OperExecSqlWrite |

两条操作分别属于 `C_META_DATA_READ`（AI_EXEC_SQL_POST）和 `C_META_DATA_WRITE`（AI_EXEC_SQL_WRITE_POST），分别授权。写操作默认不授权；按需向指定现有 Permission List 授予 Full。不复用 SQL 定义维护操作的权限。服务器还会按 PS_TOKEN 用户，每次检查 PSAUTHWS 与角色/主许可权关联中的实际 Full 授权，防止 IB 缓存旧授权使撤销延迟生效。

## 查询契约

```json
{"sql":"SELECT EMPLID,TO_CHAR(EFFDT,'YYYY-MM-DD') FROM PS_JOB WHERE EMPLID=:1","binds":["0001"],"columns":["EMPLID","EFFDT"],"maxRows":200}
```

或者 `{"sqlId":"MY_SQL","binds":["0001"],"maxRows":200}`。SQL ID 限 1..30 位 ASCII 字母/数字/下划线，以字母开头；不区分大小写，只使用 SQLTYPE=0 的普通 SQL 定义。原生 FetchSQL 按当前数据库及 as-of date 选择正文，分类后执行同一份文本；不会先检查 default 行再执行另一条 Oracle 专用行。被选中的正文含 DML、meta-SQL 等不支持内容时返回 400。未选中的未来行不会执行。

```json
{"code":0,"message":"success","data":{"mode":"select","source":"sql","columns":[{"name":"EMPLID"},{"name":"EFFDT"}],"rows":[{"v":["0001","2020-01-01"]}],"rowCount":1,"truncated":false}}
```

source 为 sql/sqlId；定义查询另返回 sqlId。未指定列名时为 c1..cN，服务端不猜测 SQL 列名。有结果时标签数量必须一致，否则返回 400。**空结果无法从 SQL 类取得列数**：提供标签则保留标签，不验证其数量；未提供时 columns=[]。rows 始终为空数组而非占位空行。

maxRows 默认 200，范围 1..1000；多取一行探测后丢弃，超限才 truncated=true。SELECT 保持正文；因 PeopleCode SQL 类无法直接 Fetch WITH，以 SELECT * FROM (WITH ... SELECT ...) 包装 CTE 查询。执行前移除前导空白/注释，SELECT 内的正常 hint 保留；不自动添加 ROWNUM。返回行数不能限制扫描、排序成本。

所有值输出字符串，数字零保留为 "0"。普通字符、日期/时间、CLOB NULL 输出 ""；**未经 TO_CHAR 的数值型 NULL 在 PeopleCode 中变成 0，无法与数值零区分**。需要可靠 NULL、精度及日期格式时，在调用 SQL 中自行 TO_CHAR，例如 `TO_CHAR(amount,'TM9','NLS_NUMERIC_CHARACTERS=''.,''')`。服务端不逐列改写类型。

原生绑定到 Oracle 后，尾部空格/换行可能被去除，空字符串会成为单个空格；不把它当作 SQL NULL。需要保留尾部字符时可自行约定显式非空尾标记，再在 SQL 中用 SUBSTR 移除标记。绑定中的中文、引号、反斜杠、内嵌换行不拼接进 SQL；JSON 输出正确转义。

## 输入与结果边界

| 项 | 限制 |
|---|---|
| sql/sqlId | 必须二选一；sql 非空且 ≤20000 字符 |
| binds | ≤64 个 JSON 字符串，每项 ≤4000 字符；对应连续 :1..:n，可重复引用同一编号 |
| columns | 如提供，1..128 个非空字符串；每项 ≤128 字符 |
| 请求体 | ≤262144 字符；所有文本拒绝实际 NUL；字面量反斜杠加 u0000 不视为 NUL |
| 结果列 | 最多 128 列 |
| 单格 | 最多 65536 字符 |
| 响应 | 行内容序列化累计 ≤1000000 字符，最终 data ≤1048576 字符；是字符上限而非 UTF-8 字节上限 |

超出结果容量返回 999，不静默裁剪单格。1 MB 级返回在当前网关已实测；BLOB/二进制不承诺支持。所有请求拒绝未知属性和错误 JSON 类型。

SQL 仅一条语句。查询允许 SELECT/WITH，拒绝 DML、DDL、事务控制、PL/SQL 和 FOR UPDATE。**分号在字符串/注释内也禁止**。扫描器识别单引号、双引号、Oracle q 引号及注释；字符串中的普通 %（例如 LIKE 'A%'）可用。字符串外及注释/标识符中的 % 一律拒绝：实测 PeopleCode 会展开注释里的 meta-SQL，不能把注释当作安全豁免。

## DML 与审计

```json
{"sql":"UPDATE PS_C_AI_TEST SET DESCR=:1 WHERE EMPLID=:2","binds":["new text","0001"]}
```

```json
{"code":0,"message":"success","data":{"mode":"dml","statementType":"UPDATE","affectedRows":1,"auditId":"36-character-uuid"}}
```

允许 INSERT/UPDATE/DELETE/MERGE；写入必须提供 sql，sqlId 写入、DDL、RETURNING 和事务语句不支持。UPDATE/DELETE 要有**外层 WHERE**；SET 子查询中的 WHERE 不算。确需无外层 WHERE 时传 `allowAllRows:true`，CLI 对应 `--allow-all-rows`。该开关不绕过其他规则，WHERE 1=1 也不意味着业务范围安全。

SQL 类通过绑定数组执行一次，影响行数读取 RowsAffected；Execute() 本身返回布尔状态。未匹配 UPDATE/DELETE 返回 affectedRows=0，重复键返回 999。DML 与成功审计同事务提交；执行或成功审计失败，先回滚 DML，再单独提交失败审计。失败审计也失败时返回 999，说明 DML 已回滚、审计不可用。审计插入失败的回滚路径已做故障注入验证。

原生 Record **C_AI_SQLAUD**、物理表 **PS_C_AI_SQLAUD** 随工程导出，部署后须先 Build 创建表及 GUID 唯一索引，再授予写权限。

| 字段 | 含义 |
|---|---|
| GUID（Key） | auditId |
| OPRID / DTTM_STAMP | PS_TOKEN 用户 / 服务器时间 |
| DESCRLONG | 原始 SQL 全文；可能含 SQL 字面量中的敏感信息 |
| DESCR254 | 绑定数量、总字符数、allowAllRows；不记录绑定值 |
| ROW_COUNT | 成功影响行数；失败为 0 |
| AUDIT_ACTN | S=成功，F=失败 |
| SQLTEXT | 最多 2000 字符的执行错误；成功为空 |

校验和授权拒绝发生在 DML 之前，不创建审计行。工具拒绝直接引用该审计表的写 SQL；仍须由数据库权限控制同义词、函数和其他路径的访问，语法检查不构成审计防篡改保证。审计保留和清理由环境管理员制定。

每次明确提交都执行一次，不提供幂等键或跨语句事务。并发重复 INSERT 实测一个成功、一个重复键失败；两次 UPDATE 都会各自执行和审计。网络超时或响应不明时保存可能已完成，先按数据和审计核对，禁止盲目重试。

## 错误与部署

400=输入或所选定义正文不支持；999=执行/容量/审计失败，错误文本最多 2000 字符。Oracle 细节不保证出现：当前 SQL 类多返回 PeopleCode 2,280/2,125 等通用错误。IB 未授权通常 HTTP 403 文本；Handler 检测到已撤销权限时返回 JSON code=403（HTTP 200）。客户端据业务 code 判失败。

完整导入、Build、授权流程见 [安装说明](01-auth-api.md)。基本健康检查验证 PSTOKEN_GET + 20 个必需操作；写操作是可选项，仅在显式授权后运行：

```powershell
python scripts/peoplesoft_api.py healthcheck --refresh
python scripts/peoplesoft_api.py healthcheck --refresh --include-sql-write
```

可选探测仅发送空 sql，预期 400，绝不执行 DML。不给写权限时基本健康检查仍应通过。安全边界见 [SECURITY.md](../SECURITY.md#sql-执行的权限与事务边界)。
