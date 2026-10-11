# ps-cli

面向 PeopleSoft 元数据开发的中文 skill，提供 CLI、接口参考及可导入的 AD 文件工程。支持范围和使用流程见 [SKILL.md](SKILL.md)。

## 目录

- `scripts/`：环境管理、认证和 API 调用。
- `references/`：按开发场景组织的中文文档。
- `C_META_DATA_PKG/`：AD 原生导出的 XML/INI，保留编译内容和原始格式。
- `assets/examples/`：可调整后使用的 JSON 模板。

部署及授权见 [安装说明](references/01-auth-api.md)，开发前读取 [开发规范](references/development-standards.md)。服务端在 PANWX25 / PeopleTools 8.60.10 验证；其他版本需另行核验。

## 版本与维护

本包版本为 **1.5.0**，基于 rc.2 完成第二轮独立复验；后续目标为 **2.0.0**，见 [发布规划](references/release-roadmap.md)。旧 2.0.0～2.4.2 为未公开的内部实施编号，保留在 [变更记录](CHANGELOG.md)。本包原生工程有 110 条目、122 定义实例，包含 28 个运行必需类的源码与编译内容，本轮维护其中 17 类。

运行包只保留必要脚本、工程、文档和示例。临时导出、测试夹具、字节码及验收报告存放在 skill 外的开发工作区。文档以中文维护，命令、参数和原生对象名保留原文。

## 许可与安全

原创内容采用 [MIT 许可证](LICENSE)，许可证原文保留；Oracle 生成内容和第三方权利范围见 [来源与许可说明](NOTICE.md)。本项目与 Oracle 无隶属、赞助或认证关系。

使用者需拥有 PeopleSoft/PeopleTools 的使用及部署权限。部署前阅读 [安全说明](SECURITY.md) 和 [已知问题](references/known-code-issues.md)。
