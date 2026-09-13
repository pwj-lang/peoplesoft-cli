# ps-cli

`ps-cli` 是一个面向 Oracle PeopleSoft PeopleTools 元数据开发与访问的 Skill。它通过 Integration Broker REST API 和随附的 Application Designer 文件工程，支持查询及维护 Record、Field、Page、Component、Project、Application Package、SQL 和 Application Engine 等定义。

当前版本：`v.1.0.0`（首次公开发布；Skill 元数据版本为 `1.0.0`）。

## 主要内容

- `SKILL.md`：Skill 的入口说明和操作约束。
- `scripts/`：环境配置、认证和 REST API 命令行工具。
- `references/`：各类 PeopleTools 定义的接口说明。
- `C_META_DATA_PKG/`：使用 PeopleSoft Application Designer 导出的文件工程；为保证能够被 AD 识别和导入，发布时保持导出内容原样。
- `assets/authorization/`：REST 服务授权步骤的界面截图。

## 使用前提

- 合法获得并获准使用的 Oracle PeopleSoft/PeopleTools 环境。
- 具备部署 Application Designer Project 和配置 Integration Broker 的权限。
- 使用专用、最小权限账号，并优先在非生产环境验证。

详细安装和调用方式见 [SKILL.md](SKILL.md)。导入服务端 Project 时见 [AD 导入说明](references/ad-cli-project-import.md)，授权时见 [REST 授权说明](references/rest-authorization.md)。

## 项目来源

据维护者说明，本项目的 Skill 指令、命令行脚本、参考文档和自定义 PeopleCode 由维护者在 AI 辅助下独立编写、审阅和整合，没有从特定第三方项目复制代码。

`C_META_DATA_PKG` XML/INI 是由 Oracle PeopleSoft Application Designer 根据项目定义生成的文件工程，其中可能包含 PeopleTools 自动生成的技术元数据、交付对象标记或互操作所需的定义。界面截图来自维护者获准使用的 PeopleSoft 环境，仅用于说明授权步骤。

## 非官方声明

本项目是独立的个人开发项目，并非 Oracle 官方产品，与 Oracle Corporation 及其关联公司不存在隶属、赞助、认证或背书关系。

Oracle 和 PeopleSoft 是 Oracle Corporation 和/或其关联公司的商标。Oracle 软件、界面、交付对象及自动生成内容的权利仍归其各自权利人所有。使用者有责任确保其安装、导入、运行和再分发行为符合适用的 Oracle 许可协议及所在组织的政策。

Oracle 相关规则可参阅：

- [Oracle Legal Notices](https://docs.oracle.com/en-us/iaas/Content/legalnotices.htm)
- [Oracle Trademark Guidelines](https://www.oracle.com/legal/trademarks/)
- [Oracle Screenshot Usage](https://www.oracle.com/legal/copyright/)

## 许可证和安全性

维护者拥有权利的原创项目内容采用 MIT License；第三方、Oracle 相关内容和 AD 生成内容的适用范围见 [NOTICE.md](NOTICE.md)。

当前版本包含高权限元数据写入能力，并存在已知的动态 SQL 安全限制，不应直接暴露到互联网或提供给不受信任的调用者。部署前请阅读 [SECURITY.md](SECURITY.md)。
