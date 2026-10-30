# SOAP / REST 服务与服务操作

读写分离部署：查询使用 `C_META_DATA_READ` 的对应 `AI_READ_*` URI，写入使用 `C_META_DATA_WRITE` 的原 `AI_OPER_*` URI；处理类分别位于 `C_META_DATA_PKG:MetaData:Read`、`:Write`。CLI 在 split 环境自动选择，完整映射及许可权配置见 [安装与读写分离](01-auth-api.md#读写分离2026-10-30)。下文参数/版本契约继续适用；旧混合 URI 的读取示例须改用对应 Read URI。

## 原始版本保护（2026-10-29）

Service 的 create/modify，以及 Operation、Version、Handler、Routing、操作授权的全部已开放写入，均必须携带先前读取的 `expectedVersion`。view/struct/exists 对不存在名称也返回版本，标记为 `managedVersionControl=1`，并返回精确 `versionKeys`；Service 前缀 `svc1:`，服务操作及子定义/授权为 `ib1:`。缺少或空版本428，过期409；读取期间变化也拒绝。此能力不提供历史版本库。

Service 令牌覆盖定义、翻译、所属操作关联及删除等原生行。Operation 根令牌覆盖全部所属版本、消息绑定、Handler、Routing（含各生效日期）、授权及所涉及 Permission List 的头；子定义按精确键保护自身原生行，授权还覆盖对应 Permission List 头及全部操作授权行。关联或其他授权变化也可能使根快照失效。写入在 OPRM/OPRVM/OPRHM/RTDM/SRVM/CLM 的固定锁顺序内校验和保存，失败回滚。

CLI 的 view/struct 自动保存绑定环境、服务器、节点、账号和完整键的原始快照。创建先读不存在名称，写入使用此前快照或 `--snapshot`；exists 不推进编辑缓存。409 保留原稿、补丁和原快照，另存最新状态且不重试。原有 stateToken/expectedState 只能作附加检查，不能替代 expectedVersion。

```powershell
python scripts/peoplesoft_api.py service struct C_MY_SERVICE --output service-original.json
python scripts/peoplesoft_api.py service create C_MY_SERVICE --file service.json --snapshot service-original.json --project MY_PROJECT
python scripts/peoplesoft_api.py service-op struct C_MY_POST --kind handler --handler REQUESTHDLR
python scripts/peoplesoft_api.py service-op modify C_MY_POST --kind handler --handler REQUESTHDLR --file handler.json --project MY_PROJECT
```

配置和整套删除不再由客户端逐步换用 fresh expectedState。`plan-configure --file` 保存 Operation/Version/Handler/Routing/Permission 完整原始计划；configure-rest/configure-soap 必须使用此计划。`plan-delete` 也保存根及全部目标。服务端 `operationType=workflow` 在同一事务中先校验根和每个步骤的原始版本，再依次执行；任一失败全部回滚。根版本还能检测计划后新加的子定义或授权。

```powershell
python scripts/peoplesoft_api.py service-op plan-configure C_MY_POST --file rest.json --project MY_PROJECT --output configure-original.json
python scripts/peoplesoft_api.py service-op configure-rest C_MY_POST --file rest.json --snapshot configure-original.json --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py service-op configure-rest C_MY_POST --file rest.json --snapshot configure-original.json --project MY_PROJECT
python scripts/peoplesoft_api.py service-op plan-delete C_MY_POST --output delete-original.json
python scripts/peoplesoft_api.py service-op delete C_MY_POST --snapshot delete-original.json --project MY_PROJECT
```

configure-soap 使用相同计划，recipe 明确 RestService=0。配置键、版本、路由日期或 Permission List 改变时重新生成计划。首次 dry-run 无缓存时可先生成只读计划；真正写入缺计划会拒绝。成功不推进原快照，下一次编辑重新读取。workflow 当前接受1–200个精确步骤；直接请求包含 kind=operation/name/expectedVersion/steps，每步也需完整键和 expectedVersion。

定义事务与 Project 登记仍分开：提交后独立回读，再登记完整工程键；回读或登记失败报告部分成功，不能重复整个事务。dry-run 不登记。需配套新版编译后的 Utility:ManagedVersion、CatalogLanguageAdapter、四个相关处理器和新版CLI（含 scripts/managed_operations.py）；URI和权限不变，旧客户端缺版本写入会被拒绝。


## 服务

REST：`AI_OPER_SERVICE_DEFN.v1/`；实际 Operation：`AI_OPER_SERVICE_DEFN_POST`；Handler：`C_META_DATA_PKG:MetaData:Read:OperServiceDefn` / `C_META_DATA_PKG:MetaData:Write:OperServiceDefn`。

可读取现有 Service，创建和修改同步 SOAP / REST Provider Service。空 Service 删除见下节；Consumer、改名和类型转换不开放。panwx25 / PeopleTools 8.60.10 已实测。

```powershell
python scripts/peoplesoft_api.py service struct C_MY_SERVICE --output D:\work\service-before.json
python scripts/peoplesoft_api.py service create C_MY_SERVICE --file D:\work\service.json --project MY_PROJECT
python scripts/peoplesoft_api.py service modify C_MY_SERVICE --file D:\work\patch.json --snapshot D:\work\service-before.json --project MY_PROJECT
```

创建文件示例：

```json
{"properties":{"Descr":"自定义 REST 服务","Ib_namespace":"http://xmlns.oracle.com/Enterprise/Tools/services","RestService":2}}
```

## 删除空 Service（2026-10-30）

已在 panwx25 / Oracle / PeopleTools 8.60.10 集成通用 Service 删除。限定 `RestService=0`（SOAP）或 `2`（REST Provider）的空服务；不级联删除 Service Operation、Message 或应用类。`Serviceopr` 有链接，或 `PSOPERATION.IB_SERVICENAME` 实际仍指向该服务时均拒绝，先删除/迁移操作再重新生成计划。

```powershell
python scripts/peoplesoft_api.py service plan-delete C_MY_SERVICE --output D:\work\service-delete-plan.json
python scripts/peoplesoft_api.py service delete C_MY_SERVICE --snapshot D:\work\service-delete-plan.json --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py service delete C_MY_SERVICE --snapshot D:\work\service-delete-plan.json --project MY_PROJECT
```

`plan-delete` 是只读操作，保存绑定环境/账号/完整键的原始计划，返回 `deletable`、`blockingOperations`、根定义及版本。非空服务可以生成计划供检查，但 delete 会拒绝；没有 `--cascade`、`--force` 或删除补丁。普通 `struct` 快照不能代替 CLI 删除计划。省略 `--snapshot` 时用该服务最近一次删除计划；首次无计划的 `--dry-run` 可先生成只读计划，实际删除仍须有原始计划。

分离部署中计划/回读走 `AI_READ_SERVICE_DEFN_POST`，删除走既有 Write 操作 `AI_OPER_SERVICE_DEFN_POST`；不新增操作和授权。Read 入口拒绝 delete，包括 delete dry-run。只有已有定义写权限的账号可以提交。其他未迁移环境须先安装配套编译工程；读取返回 `serviceDeleteVersion=1` 才代表安装了该能力。

直接 REST 仍使用 `AI_OPER_SERVICE_DEFN.v1/`，请求为普通 JSON：

```json
{"kind":"service","name":"C_MY_SERVICE","operationType":"delete","expectedVersion":"<先前读取的原始版本>","dryRun":true}
```

读取返回实际 `ownedOperations`，与原生 `Serviceopr` 链接分别核查。Service 版本令牌也覆盖实际所属 PSOPERATION 行，关联或所属操作变化会使旧快照失效。服务端在既有固定锁顺序下检查原始版本及空服务条件，再调用原生 ServiceDefn_Manager.DeleteDefn；缺版本428、过期409、非空/不存在/非法参数400。不能在提交前换成新版本以放行旧计划。

dry-run 不调用原生删除，CLI 独立核对服务及版本未变；实际删除后独立确认原生不存在，再登记 objectType=79、完整服务名、Delete/Upgrade on/Done off。保存、回读及工程登记是分步阶段，后续失败使用恢复报告确认实际状态，不能盲目重删。删除成功不更新原始计划，重复提交旧计划会被拒绝。

本工具版本的原生管理器会在事务回滚后留下进程内删除缓存。已补专门恢复：原生删除开始后若失败，先回滚定义内容，再推进恢复行的 VERSION 及服务/系统缓存代数，避免缓存继续把已恢复服务视为不存在。逻辑属性、翻译和关联恢复；版本可能前进，必须重新读取/生成计划，不保证失败后令牌不变。正常输入拒绝及成功 dry-run 不执行这一恢复。已验证3次故障注入、60次连续回读及随后正常删除；其他Tools/数据库仍需独立验证。

需同时部署新版 `Utility:NativeAdapter`、`Utility:ManagedVersion`、`MetaData:Write:OperServiceDefn` 和 CLI（object_operations.py、managed_operations.py）。服务版本覆盖范围扩大后，部署前保存的 Service 计划/快照可能409，保留原稿并重新检查后生成新计划。基本20项健康检查不变。

## 通用规则

以下规则适用于服务、服务操作、菜单、消息目录和门户接口：

```json
{"kind":"service","name":"C_MY_SERVICE","operationType":"modify","properties":{"Descr":"新说明"},"expectedVersion":"先前 view 返回的 version","dryRun":true}
```

- `operationType`：`exists`、`view`、`struct`、`create`、`modify`；空 Service 新增 `delete`，CLI 须先 `plan-delete`。名称为不可改的键；create 不覆盖已有定义，modify 不创建缺失定义。
- 可写属性使用原生名称：`Ib_namespace`、`Ib_aliasname`、`Descr`、`Descrlong`、`LanguageCd`、`ObjectOwnerId`、`Psftservice_flag`、`Ptibappsrvgrp`、`Ptibapplname`、`OpenAPI`。`RestService` 接受 0（SOAP）或 2（REST Provider），创建时默认 2；已有定义不能转换协议。`Ib_servicename` 为只读键。
- `Serviceopr` 对调用方只读。关联服务应创建操作或修改操作的 `Servicename`；2.4.1 会通过原生 ServiceDefn 同步这个列表并回读，不能假定 OperationDefn 原生保存会自动完成关联。不能直接向数组塞名称来伪造操作。
- `properties` 只列实际修改字段；省略保持原值，未知字段和 null 拒绝。新接口中的字符串是普通 JSON 字符串，**不要手工再调用 json_escape**。
- `collections` 按完整子键局部增改，省略条目不删除；空数组不代表清空。删除使用独立命令。
- `view/struct` 返回 stateToken 和原始 version；全部写入强制 expectedVersion。CLI 使用原始编辑快照，expectedState 只是可选附加检查，范围及流程见本文开头。
- `--dry-run` 验证并构造变更，不调用 Save；不替代最终保存校验。真正保存返回 before/after，CLI 再通过独立请求核对，成功才输出 `verified:true`。
- 新五组 CLI 写入需要已确认的 `--project` 或当前环境的活动 Project。Service 登记 objectType=79。新条目 Copy/Upgrade=on/Done=off；已有条目保留 Upgrade，取消 Done，已删除后重建的条目改回 Copy。精确删除登记 Delete/Upgrade=on/Done=off。
- 定义保存、回读、Project 登记是分步执行；后一步失败不代表前一步回滚。保存状态不明时先回读；CLI 不会因写响应损坏而盲目重复提交。

从 dev.3 起，写流程尝试保存后发生 API、回读或工程登记错误时，CLI 输出 `status=incomplete`、`verified=false`、`completedWrites` 和 `lastRequest`；`--output` 同时保存此恢复记录。步骤列表只含端点、完整定位、操作及阶段，不复制请求正文和快照令牌；error 保留原错误文本。`acknowledged` 只表示收到写响应；失败请求的 `unknown` 不能据此认定已回滚。先独立回读目标、关联和工程，再补做未完成步骤。预检和 dry-run 失败不会被写成已经保存。

底层使用 `%metadata:ServiceDefn:ServiceDefn_Manager`，编译源码和原生 AD 文件工程一起发布。其他 PeopleTools 版本需要重新验证原生类与字段兼容性。

## 服务操作

REST 维护端点：`AI_OPER_SERVICE_OP.v1/`；Operation：`AI_OPER_SERVICE_OP_POST`。支持同步 SOAP / REST Provider 的定义、版本、消息绑定、Application Class 处理程序、路由和指定现有 Permission List 的操作授权；URI 仅用于 REST。Consumer、异步、创建消息/节点/队列、业务 Handler 内容开发另行处理。

通用请求规则见 [Service 接口](12-service-defn-api.md)。`kind` 为 `operation/version/handler/routing/permission`。

| kind | 主键 | 可改结构 |
|---|---|---|
| operation | name=操作名 | Servicename、Defaultversion、Descr/Descrlong、ObjectOwnerId、Restmethod、Ib_aliasname、RestBaseurl、Userpwdreq、RequestStatus、ActiveDataGuard、ThinkTime、ConNav、RestOverride；Operationuritemplate |
| version | name=操作名，Versionname | Active_flag、Validation、Nr_flag、Syncnonblock、Export_flag、Multi_queue、Clientimplement、ExcludeToken、Descr/Descrlong、ObjectOwnerId；Oprverdfnparm、Oprvgenrtgparm |
| handler | name=操作名，Handlername | Handlerid=RQST、Handlertype=ApplicationClass、Active_flag、Seqnumber、Rollback_flag、Descr/Descrlong、ObjectOwnerId；Operationac |
| routing | name=路由名，Effdt=日期 | Eff_status、Sendernodename、Receivernodename、Operationname、Operationversion、Rtngtype=S、Restmethod、LocalIndication、Generated、Descr/Descrlong、ObjectOwnerId；Ibrtngsubdefn、Rtngdfnparm |
| permission | name=操作名，permissionList | access=4（Full）或 0（None）；仅该操作的权限行 |

`Rtngtype=S`。REST 使用 `RestService=2`，HTTP 方法接受 GET/POST/PUT/DELETE/PATCH；SOAP 使用 `RestService=0`，Restmethod、RestBaseurl 与 Operationuritemplate 必须为空，父 Service 协议须一致。数值属性要求整数。各定义还保留原生 `LanguageCd` 字段。键不允许改名。Operation 的 `Operationhandler` 和 `Operationversion` 是只读派生列表；应创建对应子定义。

Service 的 Serviceopr 列表对调用方只读，但 **OperationDefn.SaveNewDefn/UpdateDefn 不会自动登记 Serviceopr**。保存操作后通过原生 ServiceDefn 同步所属服务，修改 Servicename 时新增目标关联、移除原所属关联，删除操作时清理原关联；保留其他操作并独立回读。所属 Service 必须为协议一致的 SOAP / REST Provider。CLI 同时把受影响的 Service（79）登记到已确认 Project。只设置操作的 Servicename 会导致接口能调用、原生 struct 存在，但 PIA 搜索和许可权列表服务分组查不到；不能据此报告验收成功。

PIA 验收入口为 PeopleTools → Integration Broker → Integration Setup → **服务操作定义**（IB_OPERATION）。从搜索结果点击操作进入对应协议的视图。不要依据普通 SOAP 同步页面的选项判断 REST 属性无效；例如 RequestStatus=P 在 REST 视图中是合法的“PeopleSoft 令牌”。Handler 和 Routing 在操作的“处理程序”“路由”页签查看；权限还须核对指定许可权列表的 Web 服务分组和完全访问状态。

| 集合 | 完整子键 | 行字段 |
|---|---|---|
| Operationuritemplate | URISeq | URISeq、URITemplate、RootResource、Ibtransactionid |
| Oprverdfnparm | Parametername | Parametername、Messagename、Messageversion、HTTPStatusCode、ContentType、Queuename、Xfrmname、Outxfrmname |
| Oprvgenrtgparm | Parametername | Parametername、Routingdefnname |
| Operationac | Classname | Classname、Packageid、Packageroot、Qualifypath、Methodname=OnRequest |
| Ibrtngsubdefn | Seqnum | Seqnum、Direction、Rtngtype、Sendernodename、Receivernodename、Aliasname |
| Rtngdfnparm | Parametername | Parametername、Sendernodename、Receivernodename、Aliasname、Operationversion |

集合中的重复键拒绝；修改不存在的子键会新增，省略其他子项保留。Application Class 改为另一个类时先精确删除旧绑定，再添加新绑定，不能把两个 request class 误当作一个处理程序。Message 及其版本、Application Class、IB Node 和所属 Service 通过原生定义检查；不实例化或调用业务处理类来做检查。

```powershell
python scripts/peoplesoft_api.py service-op struct C_MY_POST
python scripts/peoplesoft_api.py service-op create C_MY_POST --file D:\work\operation.json --project MY_PROJECT
python scripts/peoplesoft_api.py service-op create C_MY_POST --kind version --version v1 --file D:\work\version.json --project MY_PROJECT
python scripts/peoplesoft_api.py service-op modify C_MY_POST --kind handler --handler REQUESTHDLR --file D:\work\handler-patch.json --project MY_PROJECT
python scripts/peoplesoft_api.py service-op modify C_MY_ROUTE --kind routing --effdt 1900-01-01 --file D:\work\route-patch.json --project MY_PROJECT
python scripts/peoplesoft_api.py service-op view-permission C_MY_POST --permission-list MY_PERMISSION
python scripts/peoplesoft_api.py service-op set-permission C_MY_POST --permission-list MY_PERMISSION --access full --project MY_PROJECT
python scripts/peoplesoft_api.py service-op set-permission C_MY_POST --permission-list MY_PERMISSION --access none --project MY_PROJECT
python scripts/peoplesoft_api.py service-op validate C_MY_POST --permission-list MY_PERMISSION
```

完整链路可用 `configure-rest`，JSON 须有 operation/version/handler/routing 四节，每节提供 properties/collections；后三节还需 name，routing 可指定 effdt。可附 permissionList。版本名须对应 Defaultversion，路由须对应同一操作和版本。示例：[rest-provider.json](../assets/examples/rest-provider.json)。先建所属 Service 和处理类，调整消息、节点、地址、别名及 Project；不要照抄环境名或新建依赖。先 plan-configure 保存完整原始计划，再 dry-run/提交同一事务，独立回读后登记工程。定义事务失败回滚，工程登记不与定义事务合并。

配置/删除使用计划中的原始 expectedVersion，在一次请求内先检查全部版本；不在步骤之间重新取版本放行。定义提交后的独立回读或工程登记错误仍按恢复报告处理。

```powershell
python scripts/peoplesoft_api.py service-op configure-rest C_MY_POST --file D:\work\rest.json --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py service-op configure-rest C_MY_POST --file D:\work\rest.json --project MY_PROJECT
python scripts/peoplesoft_api.py service-op plan-delete C_MY_POST --output D:\work\delete-plan.json
python scripts/peoplesoft_api.py service-op delete C_MY_POST --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py service-op delete C_MY_POST --project MY_PROJECT
```

操作删除先枚举其所有版本、处理程序和路由的全部生效日期，核对所属操作，再逐项删除并回读；同时清理该操作的权限行。保留所属 Service、共享 Message 和 Application Class。单独子定义删除使用 `--kind` 和完整键。`delete-child --file` 仅删除指定集合行，不等同于删除所引用的定义。

Project 类型：80=操作，82=版本，81=处理程序，83=路由。授权使用原生 PermissionListDefn 的 Awst 集合，原生保存负责权限列表版本；同请求以只读 Record 回读，CLI 在提交后独立核对。授权不把整份 Permission List 自动放入工程，部署其他环境必须重新向指定列表授予权限；操作的迁移不代表账号已授权。

`validate` 检查所属 Service 的操作关联、定义链路、活动状态、URI、消息绑定、处理类绑定和路由，可检查指定许可权。它不调用业务 endpoint，不证明自定义 Handler 的业务逻辑正确。实际连通性应调用专用无副作用测试 Handler。


## SOAP 配置与 WSDL

先创建 `RestService=0` 的 Service。使用 `assets/examples/soap-provider.json` 作为配置骨架，替换 Service、操作、已存在的 XML Message/Version、Application Class、Routing、节点和 Permission List：

```powershell
python scripts/peoplesoft_api.py service-op configure-soap C_MY_SOAP --file D:\work\soap-provider.json --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py service-op configure-soap C_MY_SOAP --file D:\work\soap-provider.json --project MY_PROJECT
python scripts/peoplesoft_api.py service-op validate C_MY_SOAP --permission-list MY_PERMISSION
python scripts/peoplesoft_api.py service wsdl C_MY_SERVICE --operation C_MY_SOAP --endpoint https://ps.example.com/PSIGW/PeopleSoftServiceListeningConnector --wsdl-file D:\work\soap\service.wsdl
```

SOAP 同步版本必须包含 REQUEST、RESPONSE，可选 Z_FAULT。消息必须已定义且拥有目标版本；WSDL 还要求有效 XML Schema。SOAP 绑定不使用 HTTPStatusCode/ContentType，保持 0/空字符串。Handler 为 ApplicationClass/RQST/OnRequest；版本、Handler、Routing 和权限仍按各自完整键维护。configure-soap 与 configure-rest 共用完整原始计划、服务端单事务及独立回读机制；Project 登记仍在定义提交之后执行。

`service wsdl` 是只读生成，不发布到 WSDL Repository，也不修改全局 Target Location。`--version` 可指定操作版本，省略则使用默认版本；`--secure` 采用服务器安全目标。`--endpoint` 只替换本次结果的 SOAP 地址。`--wsdl-file` 同时写出引用的 XSD，并把 schemaLocation 改为同目录相对文件；不同 Schema 共用相同 namespace 时拒绝歧义导出。JSON 结果包含原生 WSDL 和消息 schemas，可用 `--output` 保存。

panwx25 / 8.60.10 的专用无业务副作用接口已验证 SOAP 1.1（SOAPAction）和 SOAP 1.2（Content-Type action）请求/响应，使用 WS-Security UsernameToken，并保留原操作的用户验证设置。环境全局 Target Location 为占位值时，导出应明确提供实际 `--endpoint`。运行时 Schema 校验 `Validation=Y` 在本批夹具中出现间歇性 119,40，尚未关闭；已通过的实际调用基线为 `Validation=N`，不能据此声明服务器运行时 XSD 校验验收完成。模板不强制修改已有版本的 Validation 语义。
