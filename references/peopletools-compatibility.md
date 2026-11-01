# PeopleTools 旧版本兼容与判定

本页记录随 2.0.3 稳定版交付的兼容修复。安装稳定版仍须使用同版 CLI 和原生工程。

## 2026-10-31：8.55 实机修复

同一份源码先在开发端 Oracle / 8.60.10 编译，再在 Oracle / 8.55 目标编译。已实测 Service、Service Operation、Portal Registry、消息目录读取，以及 Service 的长描述保存、dry-run 和原始版本冲突保护。本次结果不代表其他定义写入和全部 8.55 补丁均已验收。

### 结构判断

| 对象 | 8.55 目标实测 | 处理 |
|---|---|---|
| `PSSERVICE.DESCRLONG`、`PSOPERATION.DESCRLONG` | 记录字典和物理列均存在 | 保留完整长描述；修复版本快照中的旧版取值路径 |
| `PSPRSMHIDDEN` | 记录不存在 | 仅在缺少该可选记录时省略其版本数据；保留其余门户数据 |
| `PSIBOPRROOT`、`PSIBURITRAN`、`PSIBURITRNLANG`、`PSOPRURIDATA` | 记录不存在 | 与上项相同，不把缺少新记录误报为整个操作不可用 |
| Service 的应用服务/OpenAPI 属性、Operation URI 的事务属性 | 部分对应字段不存在 | 原生读取只请求目标实际具备的属性；不支持的写入属性明确拒绝 |
| `PSAESTEPDEFN.PTAE_LOGGING_SQL` | 字段不存在 | 遍历目标实际字段，仅存在时设置，避免静态引用的编译警告 |
| `MESSAGE_CATALOG_CI` | CI 不存在 | 动态引用消除编译警告；消息目录可读取，基准及翻译写入明确拒绝 |

`ManagedVersion.Rows` 保留表名白名单，从目标 `PSRECFIELDDB` 取得实际列并用 SQL Fetch 读取。包含完整 CLOB，不用前 4000 字替代长描述，也不把长描述放进 SQL 排序。仅上表五个已知可选记录允许缺席；必需记录缺失、字典与物理结构不一致等错误仍返回失败。

版本快照算法随修复更新，部署前取得的 Service / Operation / Portal / Catalog 编辑快照应重新读取；旧快照可能返回 409，不能自动换成最新版本覆盖保存。

### 引入版本的证据边界

- 这次的两个 `DESCRLONG` 不是“8.55 以后新增”的字段：目标 8.55 实体已直接证实存在。Oracle 的 [8.47→8.48 集成元数据迁移说明](https://docs.oracle.com/cd/E24150_01/pt851h2/eng/psbooks/tibr/htm/tibr27.htm) 还明确描述 8.48 Service 继承 long description；这支持长描述模型早已存在，不能据此断言两个物理列的精确首次交付补丁。
- Oracle [8.60 Search Technology](https://docs.oracle.com/cd/F70250_01/psft/pdf/pt860tpst-b092022.pdf) 明确列出 `PSPRSMHIDDEN`。本次 8.55 没有、8.60 有；尚未从官方版本差异清单或连续版本数据库确认它的首次引入版本。记录更新时间及早期文档搜索无命中都不能证明首次版本。
- 因而本次不写猜测的 `#ToolsRel >= ...` 门槛。按实际记录/字段能力判断，既兼容旧环境，也避免补丁或升级差异造成误判；已验证范围与尚未确认的版本沿革分别记录。

### 消息目录依赖

有交付 CI 时继续复用 `MESSAGE_CATALOG1` / `MESSAGE_CATALOG_CI` 的原生保存与授权检查。缺 CI 时只有元数据读取路径，返回 `messageCatalogWriteAvailable=false`；该标志只说明缺少写入依赖，不能作为当前用户名权限已通过的证明。不会为兼容而伪造系统 CI、跳过写权限或直接改写消息目录数据。

安装流程仍按 [INSTALL.md](../INSTALL.md) 执行。不能把某项尚未验证写成整版不支持，也不能把以上有限验收扩大为整个旧版本认证。
