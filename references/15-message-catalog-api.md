# 消息目录

读写分离部署：查询使用 `C_META_DATA_READ` 的对应 `AI_READ_*` URI，写入使用 `C_META_DATA_WRITE` 的原 `AI_OPER_*` URI；处理类分别位于 `C_META_DATA_PKG:MetaData:Read`、`:Write`。CLI 在 split 环境自动选择，完整映射及许可权配置见 [安装与读写分离](01-auth-api.md#读写分离2026-10-30)。下文参数/版本契约继续适用；旧混合 URI 的读取示例须改用对应 Read URI。

## 原始版本保护（2026-10-29）

createSet、基准消息 create/modify/delete、集合描述修改及独立翻译 create/modify/delete 全部要求原始 `expectedVersion`。读取不存在消息集也返回 exists=false、`version`（cat1:）、managedVersionControl=1 和 versionKeys。令牌覆盖整个集头、全部基准消息、所有翻译及集合语言行；相邻消息或其他语言变化也拒绝旧稿。PPC 锁内比较和保存，缺少/空版本428，过期409，失败回滚。

先 view/struct（创建也先读不存在名称），CLI 保存绑定环境、服务器、节点、账号和集合键的原始快照，独立翻译另绑定语言/消息号。写入使用此前缓存或 --snapshot；exists 不刷新缓存。409 保留文本文件和原快照，另存最新内容，不自动换基线或重试。缓存保存完整集合，--number 可限定显示；成功后重新读取再开始下一次编辑。

```powershell
python scripts/peoplesoft_api.py message-catalog view 32000 --output original.json
python scripts/peoplesoft_api.py message-catalog create-set 32000 --number 1 --text '第一条 %1' --snapshot original.json --project MY_PROJECT
python scripts/peoplesoft_api.py message-catalog view 32000 --language ENG --number 1
python scripts/peoplesoft_api.py message-catalog create 32000 --language ENG --number 1 --text 'First %1' --project MY_PROJECT
```

expectedState 只能作附加检查，不能替代 expectedVersion。需要新版编译后的 OperMessageCatalog、Utility:ManagedVersion、CatalogLanguageAdapter 及 scripts/managed_operations.py；当前使用系统 MESSAGE_CATALOG1 / MESSAGE_CATALOG_CI，复用标准 CI Get/Save 权限；原 C_META_MSG_LANG 自建定义不再需要。版本控制不提供历史库，整份消息集删除仍未开放。


REST：`AI_OPER_MESSAGE_CATALOG.v1/`；Operation：`AI_OPER_MESSAGE_CATALOG_POST`；kind=`catalog`，name 为消息集号字符串。基准消息和独立翻译均使用标准 MESSAGE_CATALOG_CI（系统组件 MESSAGE_CATALOG1），不再依赖随包自建组件。

支持消息集/消息读取、创建带首条消息的新集合、新增消息、局部修改、精确删除单条消息，以及消息正文和说明的独立多语言维护。删除整份消息集后置。PeopleTools 消息集 **1–999 只读**；号码均为 1–32767 整数。基准消息写入要求会话语言等于基准语言；翻译使用明确的 `--language`。

```powershell
python scripts/peoplesoft_api.py message-catalog view 32000 --output D:\work\catalog-before.json
python scripts/peoplesoft_api.py message-catalog view 32000 --number 10
python scripts/peoplesoft_api.py message-catalog create-set 32000 --number 1 --text '第一条消息：%1' --descr '自定义消息' --descr-short '自定义' --project MY_PROJECT
python scripts/peoplesoft_api.py message-catalog create 32000 --number 10 --text '处理失败：%1' --severity Error --explanation-file D:\work\explanation.txt --project MY_PROJECT
python scripts/peoplesoft_api.py message-catalog modify 32000 --number 10 --text-file D:\work\message.txt --severity Warning --project MY_PROJECT
python scripts/peoplesoft_api.py message-catalog delete 32000 --number 10 --project MY_PROJECT
```

API operationType：exists/view/struct/createSet/create/modify/delete。messageNumber 可指定；新增省略时由 CI 分配，响应返回**实际保存的 messageNumber**。createSet 要求 text，并填充 CI.Create 自带的首行，避免重复创建消息 1。

properties：text、explanation、severity（Message/Warning/Error/Cancel）、descr、descrShort。响应严重级别为 M/W/E/C。正文最多 100 字符，说明可含多行；保留 `%1` 等替换符。省略字段保持原值。仅修改消息集说明可以省略 --number；修改 text/explanation/severity 必须指定消息号。新接口文本是普通 JSON 字符串，CLI 已正确处理中文、引号、反斜杠、真实换行和字面量 `\n`。

保存依次经过 CI 方法和 Save，保留 CI PSMessages 错误。dry-run Cancel，不保存。stateToken 对整个消息集的支持字段校验，因此其他消息变化也会拒绝旧快照。

Project 登记 Message Catalog Entry=25，value1=消息集号、value2=消息号；修改集合说明登记现有消息。不能把登记成功视为数据已经迁移，具体文件导出能力需按目标 PeopleTools 的原生日志核验。

## 独立翻译

```powershell
python scripts/peoplesoft_api.py message-catalog view 32000 --number 10 --language ENG --output D:\work\translation.json
python scripts/peoplesoft_api.py message-catalog create 32000 --number 10 --language ENG --text 'Processing failed: %1' --project MY_PROJECT
python scripts/peoplesoft_api.py message-catalog modify 32000 --number 10 --language ENG --explanation-file D:\work\explanation-en.txt --project MY_PROJECT
python scripts/peoplesoft_api.py message-catalog delete 32000 --number 10 --language ENG --project MY_PROJECT
```

API 沿用 view/struct/exists/create/modify/delete，增加普通字符串 `language`，使用 PeopleSoft 语言代码（ENG、FRA 等）。必须是已定义的非基准语言。写入及 exists 要求精确 messageNumber；基准消息必须先存在。只允许 text 和 explanation，severity 与集合描述仍由基准消息维护。当前不维护消息集名称的翻译。

读取返回 `translationExists`；缺失翻译不会以基准文本冒充已存在翻译。`baseText/baseExplanation` 用于对照；`allTranslations` 和基准消息共同参与 stateToken，其他语言或相邻消息变化也会拒绝旧快照。翻译写入要求原始 expectedVersion，CLI 使用此前精确读取的快照；正文为 1–100 字符，必须保留基准正文的数字占位符及重复次数。

新增/修改将 `%Session.RegionalSettings.LanguageCd` 设为显式语言，再通过交付的 `MESSAGE_CATALOG_CI` Get/Save；正常、校验失败和异常路径均恢复原语言。panwx25 已实测法语/英语创建和局部修改不会覆盖基准及其他语言。事务语言属性见 [Oracle 文档](https://docs.oracle.com/en/applications/peoplesoft/peopletools/8.63/peoplecode-api-reference/languagecd-4.html)。

标准 CI 的 DeleteMessage 会删除整条基准消息和全部翻译，不能直接用于单语言删除。删除先通过标准 CI Get/Save 权限检查，再以 MESSAGE_SET_NBR / MESSAGE_NBR / LANGUAGE_CD 完整键执行原生 Record.Delete，并调用交付 TRANSLATE_WRK.VERSION 的 PPC 缓存版本函数。显式新翻译的文本/说明与基准完全相同时，标准 CI 可能不保存语言行；同一版本锁和事务内用精确 Record.Insert 保留显式存在语义。这些是元数据接口内部路径，不依赖通用 SQL DML 操作，也不改变其单独授权要求。

原始 expectedVersion、消息集锁、占位符、dry-run 和外层失败回滚保持。20 项真实检查覆盖多语言创建/局部修改、精确及末翻译删除、相同文本、基准/邻语保护、缓存版本、失败不写和 409；原 C_META_MSG_LANG 四项定义已移到辅助工程，不随核心部署。

删除翻译保留基准消息和其他语言，类型 25 工程条目保持 **Copy**；不能标记 Delete，否则原生迁移会删除基准消息。panwx25 原生 Copy From File 实测可恢复文件中的翻译，**不会清除文件中缺席的目标翻译**，即使显式选择全部语言也是如此。因此迁移删除时须保留源端删除结果，在目标环境先读取并核对消息及语言，再按结果中的 `translationMigration.replayArguments` 重放删除命令；每次仍使用目标库的新鲜快照。仅导入工程不代表翻译删除已迁移。CLI 删除结果包含这份重放提示，可用 `--output` 保存。

复制翻译时明确核对语言选择；`-LNG ALL` 可选择全部语言，但会改变该 Project 后续默认的语言选项，只对已确认的迁移工程使用。参数语义见 [Oracle 原生复制参数](https://docs.oracle.com/cd/F86650_01/pt859pbr5/eng/pt/tlcm/CommandLineParameters.html)。需同步部署新版编译后的 CatalogLanguageAdapter，并具备交付 MESSAGE_CATALOG_CI 的 Get/Save 权限；目标系统须已具备交付 MESSAGE_CATALOG1 组件。

CLI 在任何翻译写入前核对服务器返回的语言、基准语言、真实翻译标志和完整翻译快照；旧服务器若忽略 language，命令会在写请求前拒绝，防止把翻译正文写成基准消息。

[Oracle Message Catalog Methods](https://docs.oracle.com/cd/G10810_01/pt860pbr4/eng/pt/tpcr/MessageCatalogMethods.html?pli=ul_d625e740_tpcr)说明 AddMessage 的自动分配、Save 与 DeleteMessage；多语言维护必须另行验证，不能把当前会话的更新当作独立翻译保存。
