# REST 服务与服务操作

## 服务

REST：`AI_OPER_SERVICE_DEFN.v1/`；实际 Operation：`AI_OPER_SERVICE_DEFN_POST`；Handler：`C_META_DATA_PKG:MetaData:OperServiceDefn`。

首期可读取现有 Service，创建和修改 REST Provider Service。SOAP、REST Consumer、整份 Service 删除、改名和类型转换不开放。panwx25 / PeopleTools 8.60.10 已实测。

```powershell
python scripts/peoplesoft_api.py service struct C_MY_SERVICE --output D:\AI_Workspace\tmp\service-before.json
python scripts/peoplesoft_api.py service create C_MY_SERVICE --file D:\AI_Workspace\tmp\service.json --project MY_PROJECT
python scripts/peoplesoft_api.py service modify C_MY_SERVICE --file D:\AI_Workspace\tmp\patch.json --snapshot D:\AI_Workspace\tmp\service-before.json --project MY_PROJECT
```

创建文件示例：

```json
{"properties":{"Descr":"自定义 REST 服务","Ib_namespace":"http://xmlns.oracle.com/Enterprise/Tools/services","RestService":2}}
```

## 通用规则

以下规则适用于服务、服务操作、菜单、消息目录和门户接口：

```json
{"kind":"service","name":"C_MY_SERVICE","operationType":"modify","properties":{"Descr":"新说明"},"expectedState":"先前 view 返回的 stateToken","dryRun":true}
```

- `operationType`：`exists`、`view`、`struct`、`create`、`modify`。名称为不可改的键；create 不覆盖已有定义，modify 不创建缺失定义。
- 可写属性使用原生名称：`Ib_namespace`、`Ib_aliasname`、`Descr`、`Descrlong`、`LanguageCd`、`ObjectOwnerId`、`Psftservice_flag`、`Ptibappsrvgrp`、`Ptibapplname`、`OpenAPI`。`RestService` 只接受 2。`Ib_servicename` 为只读键。
- `Serviceopr` 对调用方只读。关联服务应创建操作或修改操作的 `Servicename`；2.4.1 会通过原生 ServiceDefn 同步这个列表并回读，不能假定 OperationDefn 原生保存会自动完成关联。不能直接向数组塞名称来伪造操作。
- `properties` 只列实际修改字段；省略保持原值，未知字段和 null 拒绝。新接口中的字符串是普通 JSON 字符串，**不要手工再调用 json_escape**。
- `collections` 按完整子键局部增改，省略条目不删除；空数组不代表清空。删除使用独立命令。
- `view/struct` 返回 `stateToken`；修改可传回 `expectedState`。它是服务端生成的状态字符串，覆盖文档列出的结构字段，并非文件哈希。CLI 写前自动获取；`--snapshot` 可使用之前保存的完整读取结果，包含环境校验。此检查不承诺跨定义事务或排除所有并发竞争。
- `--dry-run` 验证并构造变更，不调用 Save；不替代最终保存校验。真正保存返回 before/after，CLI 再通过独立请求核对，成功才输出 `verified:true`。
- 新五组 CLI 写入需要已确认的 `--project` 或当前环境的活动 Project。Service 登记 objectType=79。新条目 Copy/Upgrade=on/Done=off；已有条目保留 Upgrade，取消 Done，已删除后重建的条目改回 Copy。精确删除登记 Delete/Upgrade=on/Done=off。
- 定义保存、回读、Project 登记是分步执行；后一步失败不代表前一步回滚。保存状态不明时先回读；CLI 不会因写响应损坏而盲目重复提交。

底层使用 `%metadata:ServiceDefn:ServiceDefn_Manager`，编译源码和原生 AD 文件工程一起发布。其他 PeopleTools 版本需要重新验证原生类与字段兼容性。

## 服务操作

REST：`AI_OPER_SERVICE_OP.v1/`；Operation：`AI_OPER_SERVICE_OP_POST`。支持同步 REST Provider 的定义、版本、消息、URI、Application Class 处理程序、路由和指定现有 Permission List 的操作授权。SOAP、Consumer、异步、创建消息/节点/队列、业务 Handler 内容开发另行处理。

通用请求规则见 [Service 接口](12-service-defn-api.md)。`kind` 为 `operation/version/handler/routing/permission`。

| kind | 主键 | 可改结构 |
|---|---|---|
| operation | name=操作名 | Servicename、Defaultversion、Descr/Descrlong、ObjectOwnerId、Restmethod、Ib_aliasname、RestBaseurl、Userpwdreq、RequestStatus、ActiveDataGuard、ThinkTime、ConNav、RestOverride；Operationuritemplate |
| version | name=操作名，Versionname | Active_flag、Validation、Nr_flag、Syncnonblock、Export_flag、Multi_queue、Clientimplement、ExcludeToken、Descr/Descrlong、ObjectOwnerId；Oprverdfnparm、Oprvgenrtgparm |
| handler | name=操作名，Handlername | Handlerid=RQST、Handlertype=ApplicationClass、Active_flag、Seqnumber、Rollback_flag、Descr/Descrlong、ObjectOwnerId；Operationac |
| routing | name=路由名，Effdt=日期 | Eff_status、Sendernodename、Receivernodename、Operationname、Operationversion、Rtngtype=S、Restmethod、LocalIndication、Generated、Descr/Descrlong、ObjectOwnerId；Ibrtngsubdefn、Rtngdfnparm |
| permission | name=操作名，permissionList | access=4（Full）或 0（None）；仅该操作的权限行 |

`RestService=2`、`Rtngtype=S`；HTTP 方法接受 GET/POST/PUT/DELETE/PATCH。数值属性要求整数。各定义还保留原生 `LanguageCd` 字段。键不允许改名。Operation 的 `Operationhandler` 和 `Operationversion` 是只读派生列表；应创建对应子定义。

Service 的 Serviceopr 列表对调用方只读，但 **OperationDefn.SaveNewDefn/UpdateDefn 不会自动登记 Serviceopr**。2.4.1 在保存操作后通过原生 ServiceDefn 同步所属服务，修改 Servicename 时新增目标关联、移除原所属关联，删除操作时清理原关联；保留其他操作并独立回读。所属 Service 必须为 REST Provider。CLI 同时把受影响的 Service（79）登记到已确认 Project。只设置操作的 Servicename 会导致接口能调用、原生 struct 存在，但 PIA 搜索和许可权列表服务分组查不到；不能据此报告验收成功。

PIA 验收入口为 PeopleTools → Integration Broker → Integration Setup → **服务操作定义**（IB_OPERATION）。从搜索结果点击操作会进入 REST 视图。不要直接跳转普通 IB_SERVICE 搜索页后依据普通同步选项判断 REST 属性无效；例如 RequestStatus=P 在 REST 视图中是合法的“PeopleSoft 令牌”。Handler 和 Routing 在 REST 操作的“处理程序”“路由”页签查看；权限还须核对 C_MCP 等指定许可权列表的 Web 服务分组和完全访问状态。

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
python scripts/peoplesoft_api.py service-op create C_MY_POST --file D:\AI_Workspace\tmp\operation.json --project MY_PROJECT
python scripts/peoplesoft_api.py service-op create C_MY_POST --kind version --version v1 --file D:\AI_Workspace\tmp\version.json --project MY_PROJECT
python scripts/peoplesoft_api.py service-op modify C_MY_POST --kind handler --handler REQUESTHDLR --file D:\AI_Workspace\tmp\handler-patch.json --project MY_PROJECT
python scripts/peoplesoft_api.py service-op modify C_MY_ROUTE --kind routing --effdt 1900-01-01 --file D:\AI_Workspace\tmp\route-patch.json --project MY_PROJECT
python scripts/peoplesoft_api.py service-op view-permission C_MY_POST --permission-list MY_PERMISSION
python scripts/peoplesoft_api.py service-op set-permission C_MY_POST --permission-list MY_PERMISSION --access full --project MY_PROJECT
python scripts/peoplesoft_api.py service-op set-permission C_MY_POST --permission-list MY_PERMISSION --access none --project MY_PROJECT
python scripts/peoplesoft_api.py service-op validate C_MY_POST --permission-list MY_PERMISSION
```

完整链路可用 `configure-rest`，JSON 须有 operation/version/handler/routing 四节，每节提供 properties/collections；后三节还需 name，routing 可指定 effdt。可附 permissionList。版本名须对应 Defaultversion，路由须对应同一操作和版本。示例：[rest-provider.json](../assets/examples/rest-provider.json)。先建所属 Service 和处理类，调整消息、节点、地址、别名及 Project；不要照抄环境名或新建依赖。命令先 dry-run 所有定义，再分步保存、登记并回读全部关联。中途失败时先查已保存定义，**整个链路没有共同回滚承诺**。

```powershell
python scripts/peoplesoft_api.py service-op configure-rest C_MY_POST --file D:\AI_Workspace\tmp\rest.json --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py service-op configure-rest C_MY_POST --file D:\AI_Workspace\tmp\rest.json --project MY_PROJECT
python scripts/peoplesoft_api.py service-op plan-delete C_MY_POST --output D:\AI_Workspace\tmp\delete-plan.json
python scripts/peoplesoft_api.py service-op delete C_MY_POST --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py service-op delete C_MY_POST --project MY_PROJECT
```

操作删除先枚举其所有版本、处理程序和路由的全部生效日期，核对所属操作，再逐项删除并回读；同时清理该操作的权限行。保留所属 Service、共享 Message 和 Application Class。单独子定义删除使用 `--kind` 和完整键。`delete-child --file` 仅删除指定集合行，不等同于删除所引用的定义。

Project 类型：80=操作，82=版本，81=处理程序，83=路由。授权使用原生 PermissionListDefn 的 Awst 集合，原生保存负责权限列表版本；同请求以只读 Record 回读，CLI 在提交后独立核对。授权不把整份 Permission List 自动放入工程，部署其他环境必须重新向指定列表授予权限；操作的迁移不代表账号已授权。

`validate` 检查所属 Service 的操作关联、定义链路、活动状态、URI、消息绑定、处理类绑定和路由，可检查指定许可权。它不调用业务 endpoint，不证明自定义 Handler 的业务逻辑正确。实际连通性应调用专用无副作用测试 Handler。
