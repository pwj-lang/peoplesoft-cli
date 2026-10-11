# 已知问题与支持边界

服务端在 PANWX25 / Oracle / PeopleTools 8.60.10 验证；其他版本需检查原生类、字段及编译兼容性。当前包版本为 **1.5.0**，基于 rc.2 完成第二轮独立复验。空白环境首次安装核验延期至首次真实部署；首次安装若遇 180/74“找不到类”先查 Handler 与包依赖。历史修复见 [变更记录](../CHANGELOG.md)，发行条件见 [规划](release-roadmap.md)。

## 2026-10-11 已关闭的历史 BUG

| 问题 | 修复与验收 |
|---|---|
| 旧 PeopleCode 真正删除 | Page Activate、Record Field、Component/Record/Field 三层事件、AE Action 程序、应用类程序支持明确 delete-code；七个完整原生键删除后不存在，邻居/父定义保留，Project 为 Delete/Upgrade on/Done off。Page 关闭重开 AD 后 Activate 普通字重 |
| Record 属性显示 | C_AI_RF1010.COUNTRY 的 Required、Prompt Table Edit、COUNTRY_TBL 在 AD 属性对话框首次打开及关闭重开后均正确，无需额外服务器改动 |
| 弹出菜单运行 | C_AI_DP1011 的 COUNTRY 字段关联 C_AI_EXT_POPUP，浏览器点击 MAIN/FIRST 实际触发 ItemSelected，NAME 和消息框均显示 POPUP_OK_1011 |
| 查询输入保护 | CLI 与服务端分别限制输入；元数据确认 Record/Field，值及行数绑定；69 项直接 REST、八类字段输出及五项绑定过滤验收通过 |

空正文和仅含空白字符的 modify-code 已拒绝；使用 [明确删除流程](development-standards.md#peoplecode-真正删除)。`programExists` 判断原生程序是否存在，`hasPeopleCode` 仅描述正文，不可互换。

## 部署核验

SQL Handler 为 `C_META_DATA_PKG:MetaData:OperSqlDefn`。180/74“找不到类”先查 Handler/包依赖，明确的 401/403 或未授权才查权限。完整健康检查覆盖 PSTOKEN_GET 与全部 15 个元数据操作，见 [安装说明](01-auth-api.md)。

ObjectKeyResolver、PeopleCodeDeletion 和调用处理类必须一起导入。键解析不加载固定 Project，业务定义无需预先加入核心工程，详见 [开发规范](development-standards.md)。元数据删除与 Project 登记分步执行；登记失败会明确报告程序已删除的部分成功状态。

## 初版边界

仅支持同步 REST Provider、消息目录基准语言及已有 Portal 的内容维护；SOAP、Consumer、异步、多语言写入及新对象通用分页搜索后置。整份 Service/Menu/Portal 和所有门户文件夹删除关闭。

PeopleCode delete-code 删除一个程序定义；不删除 Record/Field/Page/Component、AE 的 Section/Step/Action 或应用类定义。菜单 ItemSelected 的删除使用菜单自己的接口。REST 多定义、菜单清理和 Project 登记分步保存，不承诺共同回滚；未知写结果先回读。

PANWX25 的原生 Menu API 未持久保存 Mit.AllowedActions 与 Mit.AddSearchRecName。这两项保留只读输出，CLI 和服务端均拒绝写入，防止假成功；其余受支持属性仍以保存后回读为准，见 [菜单](14-menu-defn-api.md)。

查询 filter.value 须为字符串，数字字段也传 `"104"` 而非 `104`；CLI 和直接 REST 均明确拒绝数字 JSON 值。Oracle 字段类型与输出边界见 [查询接口](09-query-record-api.md)。输入保护不等同于业务行级权限，见 [安全说明](../SECURITY.md)。

门户属性 Values 最多一个字符串，按属性语义容纳逻辑多值；不生成多条原生 AttrValue 行。新建重复 URL 的 CREF 由原生拒绝，第二入口用 Link；被 Link 引用的 CREF 删除受限。dry-run 不替代原生保存；部分 Save=false 可能没有详细 PSMessages，但必须报告失败。

内部批次 2.4.1 已修复服务操作遗漏 Serviceopr 关联，以及门户多条属性值造成导航崩溃。旧缺失关联可通过操作 modify 同值保存触发维护；旧多行属性先核对业务语义再改为单字符串。部署需完整修复包，门户验收使用 validate 加浏览器点击，不能只看 struct。
