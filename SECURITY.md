# 安全说明

本工具用于受控开发与测试环境，具有元数据写入和数据库 DDL 能力；不直接面向互联网或不受信任的调用者。

## 查询输入保护

2026-10-11 在 PANWX25 / Oracle / PeopleTools 8.60.10 修复并验收 `AI_QUERY_RECORD_POST` 的动态 SQL 输入缺陷。CLI 在认证和 HTTP 前校验；服务端另行校验 JSON 类型、单一名称、操作符、参数边界及字段归属，并从 PSRECDEFN 解析已登记的逻辑 Record 或物理表名。过滤值和行数使用 CreateSQL 绑定参数，不拼接值；取消 SQL 失败后的 Rowset.Fill 回退。

直接 REST 的非法请求返回 400，包括数字 JSON filter.value，不再依赖原生 GetString 抛错。69 项绕过 CLI 的回归通过；另以受控 SQL View 验证字符、长数值、小数、日期/时间、空值与 CLOB。部署须使用包含已编译 OperQueryRecord 的完整 1.5.0 或后续包，单独更新 CLI 无法保护直接调用。接口限制见 [业务查询](references/09-query-record-api.md)。

输入校验没有增加业务组件的行级安全或字段权限检查。查询、元数据及 DDL 使用 PeopleSoft 应用 Access ID 的权限，可能绕过组件处理；为可信用户配置专用最小权限列表，不需要查询时关闭该操作。行数上限限制返回量，不能替代索引过滤或限制数据库扫描成本。其他数据库和 PeopleTools 版本尚未验收。

## 凭据与报告

密码、PS_TOKEN、环境配置、运行日志和备份不纳入发布包或 Git；示例使用占位符。重要写入前保存原定义，失败后核对实际状态。

仓库提供 GitHub Security Advisories 时，安全问题通过私密通道报告，避免在公开问题中暴露敏感信息。
