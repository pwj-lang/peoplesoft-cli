# 发布规划

更新日期：2026-10-30。正式顺序为 **1.5.0 → 2.0.0**；当前候选发行版为 **2.0.0-rc.1**，以 GitHub Pre-release 发布；尚未达到正式 2.0.0 的全部条件。1.5.0 是既有正式基线。历史实施和验收详情见 [变更记录](../CHANGELOG.md)，当前结构见 [架构与交付边界](architecture.md)。

## 当前交付状态

| 范围 | 当前结果 | 参考 |
|---|---|---|
| 1.5 五类能力 | Service、Service Operation、Menu、Message Catalog、Portal 初版及历史工具修复已发行 | [已知问题](known-code-issues.md) |
| SQL 执行 | 文本/定义只读查询；DML 独立权限、外层 WHERE 保护、审计和事务处理 | [SQL 执行](10-sql-exec-api.md) |
| CI / HTML / StyleSheet | 定义维护、CI 自定义 Methods、明确类型限制；已有 AD/PIA 和同环境回导证据 | [三类定义](17-ci-html-stylesheet-api.md) |
| SOAP / 消息多语言 | 同步 SOAP Provider、WSDL/XSD；消息翻译独立维护 | [服务](12-service-defn-api.md)、[消息目录](15-message-catalog-api.md) |
| Project / Field / Record / AE | 原生键、比较/迁移标记；原始版本及已开放删除单位 | [Project](11-oper-project-defn-api.md)、[Record](06-record-defn-api.md)、[AE](05-app-engine-api.md) |
| Page / Component | Page 原始版本及 12 项已有证据的属性；Component Internet / Toolbar / Pagebar | [Page / Component](07-page-defn-api.md) |
| 各定义并发保护 | 已开放写入口携带原始 expectedVersion、428/409、冲突保稿 | [开发规范](development-standards.md) |
| 读写拆分、公共依赖 | 两个 Service；JSON 三后端和必要 JavaReflect；电子表格、测试/演示和旧 Core 已移出；门户包解耦 | [架构](architecture.md) |
| 空 Service 删除 | 只删空 SOAP/REST Provider，原始计划、dry-run、失败恢复及工程 Delete 标记 | [Service 删除](12-service-defn-api.md#删除空-service2026-10-30) |

消息翻译当前复用交付 MESSAGE_CATALOG1 / MESSAGE_CATALOG_CI；原自建组件、CI、Page 及程序已移出核心工程。核心范围为接口及真实运行依赖。

上表描述工作区能力，不表示所有历史业务流程在当前基线重跑。当前主要验证环境为 panwx25 / Oracle / PeopleTools 8.60.10；候选包按新版本单独生成，不覆盖历史 dev.6 zip。

## 后续安排与边界

- **Page 小批次交付**：沿用用户 2026-10-27 确认的每批 10–20 属性安排；先收集原生/AD 证据，再实现并验收。没有依据的属性暂不支持，不自动穷举。Fluid 暂缓。
- **SOAP 未关闭问题**：Validation=Y 间歇性 119,40 仍需定位；已通过的 SOAP 1.1/1.2 调用使用 Validation=N。不能擅自关闭现有业务接口的校验。完整 2.0 发行前须实际关闭，或由用户明确调整承诺范围。
- **已明确后置**：SOAP Consumer/异步、CI 引用和 CI 多语言子结构；后者不包括已完成的 Message Catalog 翻译。未开放的整份定义或门户文件夹删除见对象文档，不再将空 Service 删除列为待实现。
- **迁移验收**：当前门户解耦和读写拆分的跨环境实际删除尚未证明；检查导出保留 Delete 键只证明清单完整。
- **目标版本**：8.54/8.55 仍需目标客户端重新编译、逐依赖核验及实机验收。JSON 后端的默认切换门槛不是整个 CLI 的版本认证。
- **首次安装**：1.5.0 空白环境首次安装已因无可用环境延期至首次真实部署；同环境比较/回导、依赖检查和健康检查保留为已有证据。
- **历史环境**：jt-dev 的错误应用包工程条目未清理，不能据 panwx25 修复宣布原环境已解决。

## 形成正式 2.0 的条件

1. 按最终承诺范围核对功能矩阵：查找/分页、属性与子对象、关联/权限、错误及部分成功处理、删除与迁移语义；对遗留问题明确关闭或经用户调整范围。
2. 对最终改动运行相应 CLI/API 回归；影响界面/行为的内容补 AD/PIA 验收，报告具体环境和未验证范围。
3. 原生导出完整工程及编译内容，检查依赖、Handler、TOOLSREL 与日志；在可恢复的验收环境执行适用的比较/回导和工作流。不能把导入成功等同于接口已授权。
4. CLI、文档、原生工程、release 镜像、安装副本与新验收包保持同一基线；保留历史包，不因一次文档整理创建正式发行。

## 编号规则

日常代码、文档或测试维护不升版；形成新部署验收包时递增 `2.0.0-dev.N`，范围完成后用 `2.0.0-rc.N`，验收通过再发 `2.0.0`。正式版兼容修复使用修订号。接口不兼容调整须说明迁移方式；新增对象本身不必改变既有契约。

1.5.0 沿用已有标签 `v.1.5.0`；本地旧 `2.0.0～2.4.2` 为未公开内部实施编号，不是已发布版本。当前 GitHub 状态以实际 Release 为准，本地工作区和 zip 文件名不能替代发行记录。
