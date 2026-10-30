# CI、HTML 与 StyleSheet 定义维护

读写分离部署：查询使用 `C_META_DATA_READ` 的对应 `AI_READ_*` URI，写入使用 `C_META_DATA_WRITE` 的原 `AI_OPER_*` URI；处理类分别位于 `C_META_DATA_PKG:MetaData:Read`、`:Write`。CLI 在 split 环境自动选择，完整映射及许可权配置见 [安装与读写分离](01-auth-api.md#读写分离2026-10-30)。下文参数/版本契约继续适用；旧混合 URI 的读取示例须改用对应 Read URI。

`2.0.0-dev.3` 开发范围，在 panwx25 / Oracle / PeopleTools 8.60.10 完成 REST 保存、独立回读、AD 关闭重开及同环境原生文件回导入；自由格式样式通过受控 PIA 页面验收。这些结果不代表正式 2.0 全范围已经完成。

## 公共约定

| 命令 | URI | kind | Project 类型与值 |
|---|---|---|---|
| html | AI_OPER_HTML_DEFN.v1/ | html | 51：名称 / 4 |
| stylesheet | AI_OPER_STYLESHEET_DEFN.v1/ | stylesheet | 50：名称 |
| ci | AI_OPER_CI_DEFN.v1/ | ci | 32：名称 |
| ci 的 Methods 程序 | AI_OPER_CI_DEFN.v1/ | ci | 42：CI 名称 / Methods（ObjectID 74 / 12） |

三条操作分别为 `AI_OPER_HTML_DEFN_POST`、`AI_OPER_STYLESHEET_DEFN_POST`、`AI_OPER_CI_DEFN_POST`，Handler 为 `C_META_DATA_PKG:MetaData:Read:OperHtmlDefn` / `C_META_DATA_PKG:MetaData:Write:OperHtmlDefn`、`OperStylesheetDefn`、`OperCIDefn`；共同依赖 `Utility:NativeAdapter`。安装和授权见 [安装说明](01-auth-api.md)。

支持 list、struct、exists、create、modify；CI 另有 delete-item、view-code、modify-code、delete-code。list 的前缀、游标与页容量见 [定义查找](02-search-defn-api.md#八类定义列表)。整份定义删除未开放。

直接 REST 使用 `kind/name/operationType`；属性放在 `properties`，子项放在 `collections`。HTML、StyleSheet和CI的创建与修改均须使用最初读取的 `expectedVersion`；CLI不会在写入时自动更换编辑基线。HTML/StyleSheet仍返回 `stateToken`，`expectedState`只作为可选附加条件。省略属性保持原值，不用 null 表示清空。

写入明确指定确认过的 `--project`，或沿用已确认的活动工程。先保存，再独立回读并验证所提交的属性和子项，最后登记 Project；任一阶段失败均返回错误，不把 HTTP 成功等同于全部完成。`--dry-run` 不保存、不登记；它不能替代 AD 和实际保存验收。

## HTML 与 StyleSheet

### 原始版本与冲突处理（2026-10-29）

需要同时部署新版编译后的 OperHtmlDefn、OperStylesheetDefn、NativeAdapter 和 `scripts/content_operations.py`，继续依赖 Utility:DefinitionVersion。已在panwx25 / Oracle / PeopleTools 8.60.10编译部署并通过正式入口真实验证；REST URI、操作和权限不变。旧服务端不能供新CLI绕过版本保护，旧客户端无版本写入会被新服务端拒绝。

`struct/view/exists` 返回 `version=html1:...` / `css1:...` 和 `htmlVersionControl=1` / `stylesheetVersionControl=1`；不存在名称也返回版本。`create/modify` 都须提交最初读取的 `expectedVersion`，缺失/空值返回应用响应428，过期返回409。`expectedState` 仅作为可选附加条件，不能替代版本。版本覆盖原生定义、全部翻译及正文 BLOB 分段、删除标记；CSS 另含样式属性及其子结构。翻译参与冲突检查不代表新增翻译编辑能力。在CRM（HTML/CSS）及SSM（CSS）和父行锁内比较并保存，异常回滚，dry-run不保存。真实并发创建和修改均只允许一方成功，另一方409；隔离故障注入已验证原生保存后异常会回滚正文、属性及版本。

不存在名称的版本包含CRM全局代数，用于保守识别创建/删除后又恢复不存在的情况；其他内容定义保存也可能使尚未执行的创建快照失效。此时须重新读取并审查，不能自动刷新版本后重试。

CLI先 `struct` 缓存绑定环境、服务器、节点、账号、类型和名称的结构快照；已有定义另输出 UTF-8 `.html/.css` 工作副本 `cachePath` 和文件旁的 `contentSnapshotPath`。修改下载文件使用其 `.snapshot.json`；任意自有文件使用先前结构缓存或显式 `--snapshot`。创建前同样读取不存在名称。写入不会使用保存前的新读取替换编辑基线，也不会在成功后自动刷新原快照。下一次编辑须重新 `struct`。

```powershell
# 创建前读取不存在名称；修改前读取当前结构
python scripts/peoplesoft_api.py html struct MY_HTML --output D:\work\html-original.json
python scripts/peoplesoft_api.py html create MY_HTML --content-file D:\work\page.html --snapshot D:\work\html-original.json --project MY_PROJECT
python scripts/peoplesoft_api.py stylesheet struct MY_CSS --output D:\work\css-original.json
python scripts/peoplesoft_api.py stylesheet modify MY_CSS --content-file D:\work\style.css --snapshot D:\work\css-original.json --project MY_PROJECT
```

409 时将最新结构和正文另存为唯一文件，保留本地稿件与原快照，不重试写入。保存后版本或内容回读不符、工程登记失败均报告已完成阶段；确认实际状态后再恢复。HTML 使用完整51类型名称/4键，CSS使用50类型名称键登记 Copy/Upgrade on/Done off。此版本控制用于并发覆盖检测，不提供历史版本库。

隔离入口及正式入口各通过71项真实服务端和44项真实CLI检查；另通过真实并发创建、原生保存后故障回滚和正式端点Postman18请求/26断言。临时定义、处理类、接口、路由及权限已清理；本轮未新增AD/PIA或跨环境迁移验收。以下历史AD/PIA结果属于此前实现，不作为本轮并发验收依据。

```powershell
python scripts/peoplesoft_api.py html struct MY_HTML
python scripts/peoplesoft_api.py html create MY_HTML --content-file D:\work\page.html --descr "页面片段" --project MY_PROJECT
python scripts/peoplesoft_api.py html struct MY_HTML
python scripts/peoplesoft_api.py html modify MY_HTML --content-file D:\work\page.html --project MY_PROJECT
python scripts/peoplesoft_api.py stylesheet struct MY_CSS
python scripts/peoplesoft_api.py stylesheet create MY_CSS --content-file D:\work\style.css --project MY_PROJECT
python scripts/peoplesoft_api.py stylesheet struct MY_CSS --output D:\work\css-snapshot.json
```

`--content-file` 读取 UTF-8（可带 BOM）；显式空文件表示清空正文。`--file` 则读取属性补丁 JSON，两者不能重复指定同一正文字段。

| 对象 | 可维护属性 | 边界 |
|---|---|---|
| HTML | Descr、LanguageCd、ObjectOwnerId、ContStrData | 原生 ContentDefn，ContType 固定为 4；ContName 不可更名 |
| StyleSheet | Descr、LanguageCd、ObjectOwnerId、ExtStyleSheetStr | 只写独立自由格式样式：StyleSheetType=2、ParentStyleSheet 为空；StyleSheetName 不可更名 |

StyleSheet 可读取原生类型信息；其他样式类型和父样式关系的写入明确拒绝。不要把对 CSS 文件的本地修改当成 PeopleTools 定义已保存。

本次 PIA 验收通过 HTML Area 中的 `%StyleSheet(C_AI_V2_CSS1017)` 引用实际 PeopleSoft 样式缓存，浏览器计算颜色为 `rgb(20, 80, 160)`，中文及反斜杠伪元素正确；验收后已移除临时控件，未保存业务数据。该检查中的 HTML 正文从定义读取后复制到常量 HTML Area，不声称验证了 GetHTMLText 动态绑定。

原生 Copy From File 会将文本 LF 规范为 CRLF。本环境 HTML/CSS 正文和 CI 长说明仅出现这一变化；迁移内容核对允许 LF/CRLF 等价，快照令牌仍根据实际正文变化，迁移后应重新读取快照。

## Component Interface

这里维护 **CI 定义**，不执行 CI.Get/Create/Save，不写业务数据。

```powershell
python scripts/peoplesoft_api.py ci struct MY_CI --output D:\work\ci.json
python scripts/peoplesoft_api.py ci create MY_CI --file D:\work\ci-definition.json --snapshot D:\work\ci.json --project MY_PROJECT
python scripts/peoplesoft_api.py ci struct MY_CI --output D:\work\ci-existing.json
python scripts/peoplesoft_api.py ci modify MY_CI --file D:\work\ci-patch.json --snapshot D:\work\ci-existing.json --project MY_PROJECT
# 删除映射前再次读取并审查结构
python scripts/peoplesoft_api.py ci struct MY_CI --output D:\work\ci-delete.json
python scripts/peoplesoft_api.py ci delete-item MY_CI --file D:\work\ci-delete-item.json --snapshot D:\work\ci-delete.json --project MY_PROJECT --dry-run
```

定义属性：BcDisplayName、BcDescr、BcPanelGroup、BcMarket、BcMenuName、BcSearchRec、BcAddSearchRec、StandardMethods、Descrlong、LanguageCd、ObjectOwnerId。BcName 为不可变名称。StandardMethods 是原生标准方法的 0..31 位掩码；各位含义以 AD 当前定义为准。

`Pit` 是原生的扁平键、集合和属性映射，按正整数 `Seq` 定位；未出现的项保持不变。可维护的原生字段为 PropertyType、ParentCollection、BcItemName、Seq、Access、ScrollLevel、ScrollNum、ScrollName、RecName、SubRecName、FieldName、ShortComment、DevicePersistence。PropertyType 仅接受已验证的 1..5；名称和滚动定位应从当前定义或 AD 基准读取，不猜编码。原生自动生成的 SyncId 不作为可编辑字段。

局部修改映射说明：

```json
{"collections":{"Pit":[{"Seq":50,"ShortComment":"维护说明"}]}}
```

删除精确项：

```json
{"collections":{"Pit":[{"Seq":50}]}}
```

新增映射需提供完整的原生字段及正确滚动定位。服务端检查组件/Market、Record/Field、搜索键所属 Record、组件页面及子页面中的 Record、父集合存在性与集合环；删除集合前先处理其子项。保存使用原生 ValidateDefn 和 SaveNewDefn/UpdateDefn。

### 原始版本与冲突处理（2026-10-29）

`struct/view/exists/viewCode` 返回 `version="ci1:..."` 和 `ciVersionControl=1`。不存在名称的 `struct/exists` 也返回版本，创建前必须先读取。版本包含名称、当前语言、原生 CI 定义、Pit 映射、全部翻译行、删除标记和 Methods 原生程序版本；任一部分改变会使原快照失效。翻译行参与冲突检查，不代表开放翻译编辑。

所有写入 `create/modify/deleteChild/modifyCode/deleteCode` 必须提交最初读取的 `expectedVersion`。缺失或空字符串返回应用响应 `code=428`，旧版本返回 `code=409`；不是只判断 HTTP 状态。`expectedState` 对 CI 仅保留为可选的额外条件，不能替代 `expectedVersion`；Methods 仍另需原始 `expectedCode`。新服务端拒绝旧客户端的无版本写入，旧服务端也不能供新 CLI 绕过版本保护。

CLI 的结构缓存、代码旁 `.snapshot.json` 和 `--output` JSON 绑定环境、服务器、节点、账号、CI 名称及结构/Methods 类型。结构写入使用先前 `struct` 的快照；代码修改默认使用输入文件旁的快照，代码删除使用先前 `view-code` 的快照，也可显式 `--snapshot`。缺快照拒绝写入，不能以保存前的新读取代替编辑时的版本。

发生409时，CLI将最新结构及适用的Methods正文另存为唯一文件，保留原稿和原快照，不自动重试。应人工比较、合并后重新建立编辑基线；保存后发现其他写入也会报告冲突及已完成阶段，不能把重试当作恢复。成功写入后，下一次独立编辑应重新读取。

服务端在同一事务的 PCM、BCM 及已有父定义行锁内比较和保存；失败回滚，dry-run不保存、不登记。版本控制用于并发覆盖检测，不提供历史版本库、分支或回滚命令。PANWX25 / Oracle / PeopleTools 8.60.10 已验证真实并发只能一方成功；本轮未新增 AD 界面或跨环境迁移验收。

### 自定义方法 PeopleCode

用户已明确将自定义方法 PeopleCode 纳入 2.0，CI 引用和多语言子结构后置。自定义方法以一个 CI 的完整 `Methods` 程序维护；先读取并保留所有函数，再修改整段正文。不能把某一个函数的正文直接覆盖整个程序，也不通过 Pit 类型 6 创建方法。

```powershell
python scripts/peoplesoft_api.py ci view-code MY_CI --output D:\work\ci-methods.json
python scripts/peoplesoft_api.py ci modify-code MY_CI --file D:\work\ci-methods.pcode --snapshot D:\work\ci-methods.json --project MY_PROJECT
# 删除整个 Methods 前重新读取并审查
python scripts/peoplesoft_api.py ci view-code MY_CI --output D:\work\ci-methods-delete.json
python scripts/peoplesoft_api.py ci delete-code MY_CI --snapshot D:\work\ci-methods-delete.json --project MY_PROJECT --output D:\work\deleted.json
```

正文文件为 UTF-8，可带 BOM。`view-code` 输出 `cachePath` 和 `snapshotPath`；编辑下载文件后，CLI 提交原快照的 `expectedVersion` 和 `expectedCode`，也可用 `--snapshot` 指定先前 view-code 的 JSON。服务端要求父 CI 存在，并拒绝缺失或过期快照、空白正文和编译错误。原生 UpdateProgram 编译后保存，CLI 独立回读整段代码并核对 Project 42 的 Copy/Upgrade on/Done off。`--dry-run` 可以编译检查，但不保存或登记。

直接 REST 使用 `viewCode/modifyCode/deleteCode`，字段为 `kind="ci"`、`name`、`operationType`、`expectedVersion`、`expectedCode`、`peoplecode`、`dryRun`。正文和快照是普通 JSON 字符串，不能套用旧接口的 CommonUtil 入参编码。viewCode 返回 `programExists`、整段 `peoplecode`、版本和完整 `projectItem`；不提供函数签名解析。

`delete-code` 真正删除完整 Methods 程序及其中所有自定义函数，保留 CI 定义、标准方法开关和映射。CLI 删除前保存唯一 UTF-8 备份，结果的 `snapshotPath` 指向该文件；删除后核对原生不存在，登记 42 类型 Delete/Upgrade on/Done off。重复删除报不存在；失败后的恢复记录包含备份路径和已完成写入阶段。备份、快照和迁移后的正文均须重新核实，不能盲目重试。

定义维护不会调用自定义业务方法，也不自动扩展 CI 运行权限。代码编译与 AD 展示检查不代表业务方法已通过运行验收；方法执行和业务授权由使用方另行验证。
