# 变更记录

正式目标见 [发布规划](references/release-roadmap.md)。以下 2.x 是未公开的内部实施批次，不代表正式 2.0 已发布。

## 1.5.0（2026-10-11）

基于 rc.2 完成第二轮独立复验并形成正式发行包，服务端工程与 CLI 运行逻辑保持 rc.2 基线；XML SHA-256 为 `a0ace30fe7b3ee24dee7fb44c2391368629280aa2c9ce570756ccd2a28a905ba`。

- 提供同步 REST 服务/服务操作、标准及弹出菜单、基准语言消息目录、已有门户的 Folder/CREF/Link 维护，以及完整键的 Project 登记和写后独立回读。
- 修复历史 PeopleCode 真正删除、查询动态 SQL 输入、Record 中间 Key/索引及属性显示、服务所属关联和门户属性导航问题；父定义与相邻程序保留，分步失败明确报告。
- 第二轮复验：28 个必需类服务器源码与包内逐字匹配，76 项自定义依赖引用解析；本地测试按 24 + 9 + 8 + 12 执行通过，另有 3 项闭包负例与 2 项 Page 离线 mock。69 项查询 REST、33 项拒绝保护、七类删除状态、七组主要工作流、完整健康检查及浏览器弹出菜单运行均通过，三个工程保持不变。
- 恢复 `.gitignore` 原有凭据、Token、运行报告和备份排除规则；正式包只含 30 个运行文件、工程、文档与示例，验证材料保留在维护工作区。
- 验证范围为 Oracle / PeopleTools 8.60.10。空白环境首次安装按已确认决定延期；SOAP/Consumer/异步、多语言、整份 Service/Menu/Portal 和门户文件夹删除后置，CI/HTML/StyleSheet 留待 2.0。

## 1.5.0-rc.2（2026-10-11，候选包，未正式发布）

候选包小修，服务端工程未变（XML 保持 rc.1 哈希 `a0ace30fe7b3ee24dee7fb44c2391368629280aa2c9ce570756ccd2a28a905ba`）。发布依赖检查新增**依赖闭包核验**：扫描全部 PeopleCode 源码的 `C_*:*` 类引用（含包级前缀）、`Record.C_*` 自定义记录与 `PS_C_*` 自定义表，未解析即失败；当前包 76 项引用全部解析，3 项负例回归通过。`query-record` 文档更正 `fields[].label` 当前固定为空（与实测一致）；`page modify-code` 对不存在的文件路径按内联正文处理，不再抛裸异常（离线 mock 两项通过）；`--timeout` 补进公共调用规则文档。PANWX25 健康检查（PSTOKEN_GET + 15 操作）与本地回归 41 项（validation 24、query guard 9、transport 8）复跑通过。正式 1.5.0 尚未发布。

## 1.5.0-rc.1（2026-10-11，候选包，未正式发布）

1.5.0 范围已收口。本包在 dev.3 基础上定版：重新执行原生导出（110 条目、122 实例、30 个 PCM；17 个维护类源码与编译块核验通过；清单无增删、程序内容无变化，仅导出元数据变化，XML SHA-256 更新为 `a0ace30fe7b3ee24dee7fb44c2391368629280aa2c9ce570756ccd2a28a905ba`），恢复导出改变的 16 个 Done 标记。PANWX25 健康检查（PSTOKEN_GET + 15 操作）与本地回归 41 项（validation 24、query guard 9、transport 8）通过，发布依赖检查通过。空白环境首次安装核验延期至首次真实部署（当前无可用空白环境）；安装证据为同环境原生比较/回导入、依赖与编译内容核验、授权与健康检查。正式 1.5.0 尚未发布。

## 1.5.0-dev.3（2026-10-11，未正式发布）

维护工具整理，服务端工程与数据契约未变：`C_META_DATA_PKG.XML` 保持 dev.2 哈希，未重新导出。bundle-check 从 skill 移出为维护侧 `tools\check_bundle.py`，必需类由 21 个补全到 28 个（补 OperProjectDefn、OperSqlDefn、SearchDefinition、Login、MappingUtil、RecordUseEdit、HttpUtil），并新增 PCM 源码/编译内容与操作处理程序绑定检查，6 项负例回归通过；新增 `tools\sync_skill.py` 管理共享源 → release 镜像、5 个 Agent 安装副本与打包的单向同步和差异检查。两处文档去掉对已移除命令的引用，SKILL.md、README、SECURITY、已知问题和发布规划同步版本字样。PANWX25 健康检查（PSTOKEN_GET + 15 操作）通过，本地回归 41 项通过（validation 24、query guard 9、transport 8）。正式 1.5.0 尚未发布。

## 1.5.0-dev.2（2026-10-11，最终验收包，未正式发布）

修复 dev.1 原生回导入复验暴露的 180,236：不存在程序的空值响应不再依赖 GetJsonNode 后 SetNull。Page、Record、Component、应用包保留空字符串正文及 programExists=false；七类连续五轮回读通过。重新编译并原生导出 110 条目/122 实例，17 个维护类源码与编译块核验，全部 30 个 PCM 实例均含源码和编译内容；再次完成同环境比较/回导入和工作流复验。共享、安装、发行目录均为 dev.2，dev.1 证据保留为历史记录。

删除快照唯一标识移至文件名前部，避免长类路径经 120 字符截断覆盖旧快照；12 项删除回归、合计 45 项本地回归通过。bundle-check 增加 CommonUtil、JsonUtil 依赖核验。正文不存在时允许 null/空字符串的旧客户端保持兼容；应使用 programExists 判断原生存在性。正式 1.5.0 尚未发布。

## 1.5.0-dev.1（2026-10-11，首轮验收包；回导入读取缺陷已由 dev.2 修复）

- query-record 的 CLI 与服务端限制名称、JSON 类型、操作符和参数边界；服务端核实字段归属并绑定值/行数，移除 Rowset 回退与空白占位行。69 项直接 REST 及字符、精确数值、日期/时间、空值、CLOB 验收通过。
- Page、Record Field、Component 三层、AE Action 和应用类程序新增 delete-code；删除前快照并核对完整原生键，删除后独立检查不存在，按完整 Project 键登记 Delete/Upgrade on/Done off。保留父定义和相邻程序，dry-run 不写入；登记失败报告部分成功。
- modify-code 在 CLI 和服务端拒绝空白代码；Component 的读、写、删正确转发 market。AD 重开确认 Page Activate 普通字重、Record Required/Prompt Table Edit/COUNTRY_TBL 正确，PIA 实际触发测试弹出菜单。
- 原生 Menu API 不能持久保存的 AllowedActions/AddSearchRecName 改为只读，CLI 与服务端提前拒绝写入。
- 原生导出 110 条目、122 定义实例，17 个维护类源码与编译内容核验；恢复本次导出改变的 16 个 Done 标记。共享、安装、发行目录同步同一包；版本统一为 1.5.0-dev.1，保留内部批次历史。
- 本地 44 项回归、空白/非法键/菜单属性 33 项直接 REST、认证及全部 15 个元数据操作健康检查通过。正式发布状态见规划；验收包不代表已发布 1.5.0。

## 内部实施记录

| 批次 | 日期 | 变更与验证 |
|---|---|---|
| 2.4.2 | 2026-10-11 | ObjectKeyResolver 使用未保存的空原生 ProjectDefn，NativeAdapter/MenuCodeAdapter 去除固定核心工程依赖；bundle-check 检查解析器。PANWX25 验证工程外菜单/代码、新名称、保存/删除和门户运行时；原生导出 109 条目、10 个编译类 |
| 2.4.1 | 2026-10-11 | 服务操作同步 Serviceopr，门户属性限制单字符串；初始化 CREF 默认属性并修复 Link URL，新增 portal validate。PIA 验证搜索、Handler、Routing、权限分组及目录/链接 |
| 2.4.0 | 2026-10-11 | 新增服务、服务操作、菜单、消息目录、门户五组命令；局部补丁、快照、dry-run、回读、工程登记；修复 JSON 转义，未知写结果不重试，健康检查扩至 15 操作。初版门户属性多值缺陷于 2.4.1 修复 |
| 2.3.1 | 2026-10-10 | CLI/PeopleCode 限制 CopyProp 仅 Record/Field；纠正此前组合测试无法证明各类型支持 CopyProp 的说明 |
| 2.3.0 | 2026-10-10 | Project Action/Upgrade/Done 独立/组合更新，完整键自动解析与保存回读；PANWX25 验证多类定义标记 |
| 2.2.0 | 2026-10-10 | Record 新普通字段 insertBefore，校验失败回滚并同步缓存/主索引；C_AI_KF1010 的 NAME 插于 COUNTRY/金额字段之间并设 Key，AD 导出验证 |
| 2.1.0 | 2026-10-10 | SQL 默认平台与未匹配假成功修复，代码/SQL 回读，Project 完整键，Record 缓存/索引和 Alter 复制检查，Page 空正文状态/full 读取。空正文处理未实现旧程序定义删除；原生导出 79 项，TOOLSREL=8.60.10 |
| 2.0.0 | 2026-09-18 | 当时统一本地内部编号；修正 REST 授权、代码工作副本缓存及缺少密码时的 preflight 报错，未公开发行 |

## 已公开的标签

- **1.0.1（2026-09-18）**：修正 README 通用 skill 定位，同步元数据版本。
- **1.0.0（2026-09-13）**：首次公开 skill、CLI、接口参考和 AD 文件工程。
