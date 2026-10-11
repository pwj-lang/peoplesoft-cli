# 消息目录

REST：`AI_OPER_MESSAGE_CATALOG.v1/`；Operation：`AI_OPER_MESSAGE_CATALOG_POST`；kind=`catalog`，name 为消息集号字符串。使用标准 MESSAGE_CATALOG_CI。

支持消息集/消息读取、创建带首条消息的新集合、新增消息、局部修改和精确删除单条消息。多语言维护、删除整份消息集后置。PeopleTools 消息集 **1–999 只读**；号码均为 1–32767 整数。写入要求当前会话语言等于基准语言；读取返回 language/baseLanguage，不提供独立翻译写入选项。

```powershell
python scripts/peoplesoft_api.py message-catalog view 32000 --output D:\AI_Workspace\tmp\catalog-before.json
python scripts/peoplesoft_api.py message-catalog view 32000 --number 10
python scripts/peoplesoft_api.py message-catalog create-set 32000 --number 1 --text '第一条消息：%1' --descr '自定义消息' --descr-short '自定义' --project MY_PROJECT
python scripts/peoplesoft_api.py message-catalog create 32000 --number 10 --text '处理失败：%1' --severity Error --explanation-file D:\AI_Workspace\tmp\explanation.txt --project MY_PROJECT
python scripts/peoplesoft_api.py message-catalog modify 32000 --number 10 --text-file D:\AI_Workspace\tmp\message.txt --severity Warning --project MY_PROJECT
python scripts/peoplesoft_api.py message-catalog delete 32000 --number 10 --project MY_PROJECT
```

API operationType：exists/view/struct/createSet/create/modify/delete。messageNumber 可指定；新增省略时由 CI 分配，响应返回**实际保存的 messageNumber**。createSet 要求 text，并填充 CI.Create 自带的首行，避免重复创建消息 1。

properties：text、explanation、severity（Message/Warning/Error/Cancel）、descr、descrShort。响应严重级别为 M/W/E/C。正文最多 100 字符，说明可含多行；保留 `%1` 等替换符。省略字段保持原值。仅修改消息集说明可以省略 --number；修改 text/explanation/severity 必须指定消息号。新接口文本是普通 JSON 字符串，CLI 已正确处理中文、引号、反斜杠、真实换行和字面量 `\n`。

保存依次经过 CI 方法和 Save，保留 CI PSMessages 错误。dry-run Cancel，不保存。stateToken 对整个消息集的支持字段校验，因此其他消息变化也会拒绝旧快照。

Project 登记 Message Catalog Entry=25，value1=消息集号、value2=消息号；修改集合说明登记现有消息。不能把登记成功视为数据已经迁移，具体文件导出能力需按目标 PeopleTools 的原生日志核验。

[Oracle Message Catalog Methods](https://docs.oracle.com/cd/G10810_01/pt860pbr4/eng/pt/tpcr/MessageCatalogMethods.html?pli=ul_d625e740_tpcr)说明 AddMessage 的自动分配、Save 与 DeleteMessage；多语言维护必须另行验证，不能把当前会话的更新当作独立翻译保存。
