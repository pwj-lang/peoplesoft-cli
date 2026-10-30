# 安全说明

本工具用于受控开发与测试环境，具有元数据写入、数据库 DDL 和单条 DML 执行能力；不直接面向互联网或不受信任的调用者。

## 元数据读写权限

2026-10-30 起支持分离服务：只读列表授所需 C_META_DATA_READ 操作，定义读写列表同时授所需 C_META_DATA_READ 与 C_META_DATA_WRITE 操作。16类定义由 MetaData:Read / MetaData:Write 独立入口和精确动作白名单拦截，未知动作及错误入口上的 dry-run 均拒绝；每次核对该操作实际 Full 权限。原版本令牌、事务与写后核验继续适用。共享 Utility:CoreOper* 不是直接 Handler。SQL DML 仍须单独显式授权，禁止因需要定义写权限而给 Write 服务全部操作 Full。

Read 服务还包含原有数据与任意 SQL 查询；只需元数据读取的账号可以不授这些操作。分离定义 API 不等于数据库级只读，SQL函数副作用与组件行级权限边界仍见下文。部署/迁移及全部映射见 [安装说明](references/01-auth-api.md#读写分离2026-10-30)。

## 查询输入保护

2026-10-11 在 PANWX25 / Oracle / PeopleTools 8.60.10 修复并验收 `AI_QUERY_RECORD_POST` 的动态 SQL 输入缺陷。CLI 在认证和 HTTP 前校验；服务端另行校验 JSON 类型、单一名称、操作符、参数边界及字段归属，并从 PSRECDEFN 解析已登记的逻辑 Record 或物理表名。过滤值和行数使用 CreateSQL 绑定参数，不拼接值；取消 SQL 失败后的 Rowset.Fill 回退。

直接 REST 的非法请求返回 400，包括数字 JSON filter.value，不再依赖原生 GetString 抛错。69 项绕过 CLI 的回归通过；另以受控 SQL View 验证字符、长数值、小数、日期/时间、空值与 CLOB。部署须使用包含已编译 OperQueryRecord 的完整 1.5.0 或后续包，单独更新 CLI 无法保护直接调用。接口限制见 [业务查询](references/09-query-record-api.md)。

输入校验没有增加业务组件的行级安全或字段权限检查。查询、元数据及 DDL 使用 PeopleSoft 应用 Access ID 的权限，可能绕过组件处理；为可信用户配置专用最小权限列表，不需要查询时关闭该操作。行数上限限制返回量，不能替代索引过滤或限制数据库扫描成本。其他数据库和 PeopleTools 版本尚未验收。

## SQL 执行的权限与事务边界

2.0.0-dev.1 新增 AI_EXEC_SQL_POST 和 AI_EXEC_SQL_WRITE_POST，分别授权；与 SQL 定义维护操作的权限分开。写执行默认不授权，部署后先 Build C_AI_SQLAUD 表和 GUID 唯一索引，再按需给指定现有 Permission List 授予 Full。Handler 每次按 PS_TOKEN 用户重新核对许可权与角色/主列表关联，已撤销的授权不依赖 IB 缓存刷新。基本健康检查不要求写授权，可选写探测只发送空 SQL，验证拒绝输入，不执行 DML。

语法检查只降低误用面，不能保证数据库级只读。SELECT 调用有副作用的函数仍可能改变状态；同义词、触发器和数据库程序也不是文本扫描能完整约束的。所有 SQL 使用应用 Access ID 的权限，会绕过业务组件行级安全、字段权限及组件校验。环境管理员应核对 Access ID 的实际权限、函数权限和对象范围；需要数据库级只读时须在数据库侧落实。常规查询优先 query-record，它增加元数据校验，但同样不提供组件行级安全。

UPDATE/DELETE 要求外层 WHERE，无 WHERE 须显式 allowAllRows；WHERE 1=1 不能证明业务范围安全。DML 与成功审计共同提交，失败先回滚 DML，再单独提交失败审计；两条审计路径失败均返回错误。工具拒绝直接写 PS_C_AI_SQLAUD，但不构成完整的审计防篡改保证，其他访问路径仍需数据库权限控制。SQL 全文和执行错误可能包含敏感字面量及数据库结构；审计绑定摘要只含数量/字符数，不保存绑定值。结果、审计和错误不放入公开或共享日志，审计保留策略由管理员制定。

每次提交都执行一次，没有幂等键、跨语句事务或数据库语句超时。网络超时或响应无法解析时先核对数据及审计，不自动重试写请求。行数和响应容量上限不能限制扫描成本。契约、NULL/精度及原生绑定限制见 [SQL 执行](references/10-sql-exec-api.md)。

## 凭据与报告

密码、PS_TOKEN、环境配置、运行日志和备份不纳入发布包或 Git；示例使用占位符。重要写入前保存原定义，失败后核对实际状态。

SOAP 定义维护与 SOAP 接口调用使用各自的授权和认证配置；WSDL 生成不修改全局服务地址。`--endpoint` 导出不接受 URL 中的用户名/密码。消息翻译写入仅支持自定义消息集，要求原始 expectedVersion；新增/修改复用系统 MESSAGE_CATALOG_CI 的事务语言，精确删除及同基准显式翻译在标准 CI Get/Save 权限检查后使用受版本锁保护的原生 Record 路径，并发布 PPC 缓存版本。CI 权限按指定账户配置。它属于元数据维护能力，不提供面向最终业务用户的消息集权限隔离。

仓库提供 GitHub Security Advisories 时，安全问题通过私密通道报告，避免在公开问题中暴露敏感信息。

## dev.2 定义接口与列表

新增 AI_OPER_HTML_DEFN_POST、AI_OPER_STYLESHEET_DEFN_POST、AI_OPER_CI_DEFN_POST 和只读 AI_LIST_DEFN_POST，分别授权给指定现有许可权列表；维护接口包含元数据写入能力。三条定义写接口要求读取时的原始 expectedVersion，CLI 独立回读后登记确认的 Project。列表仅使用固定表/字段和绑定筛选，不接收任意 SQL。基本健康检查现覆盖 PSTOKEN_GET + 20 操作；SQL 写权限仍单独可选。
