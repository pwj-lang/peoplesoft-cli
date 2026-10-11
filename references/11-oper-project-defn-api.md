# Project 管理与迁移标记

通过 Integration Broker 管理 Application Designer 的 Project 定义和迁移条目。接口为 `POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/PSFT_HR/AI_OPER_PROJECT_DEFN.v1/`，请求头使用 `Content-Type: application/json` 和 `PS_TOKEN`。

## 操作

所有操作必须传 `projectName`。省略 `operationType` 时默认 `createProject`。

| operationType | 参数 | 行为 |
|---|---|---|
| createProject | 可选 descr、comment | 创建项目；descr 不超过 30 字符 |
| modifyProject | 可选 descr、comment | 修改描述；未传的属性保持原值 |
| struct | projectName | 返回条目及完整的四组 objectId/objectValue、upgradeAction、takeAction、copyDone |
| insertItem | objectType、objectValue1；按定义传 value2~4 | 插入后提交；重复完整键返回 inserted=false，保留已有迁移标记 |
| updateItem | objectType、objectId1~4、objectValue1~4；至少一个属性 | 按完整键更新 upgradeAction/takeAction/copyDone；未指定属性保持原值；条目不存在时报错 |
| deleteItem | objectType、objectId1~4、objectValue1~4 | 按完整键移除项目条目；不删除定义本身 |

`comment` 使用 JSON 转义后传输。

## Action、Upgrade、Done 的作用

这三个属性属于 **Project 中的定义条目**，用来控制后续复制/迁移。CLI 的 `update-item` 只保存这些标记；设置 Action 不会立即复制或删除定义，设置 Done 也不会执行迁移。

### Action：对目标定义执行什么操作

- **Copy**：将源定义复制到目标环境，目标已有定义时按复制规则更新它。Record 的 Copy 包含 Record Fields；Field 的 Copy 包含 Field Labels。项目中的其他定义和依赖仍需分别登记，不能认为 Copy 一个定义会自动带上所有依赖。
- **Delete**：在执行项目复制到目标数据库时，删除目标环境中的对应定义。设置 `--action Delete` 只是指定后续动作；`project delete-item` 则只移除项目成员，含义不同。
- **CopyProp**：只复制部分属性，用于保留目标定义中的 Record Fields 或 Field Labels；仅 Record（objectType=0）和 Field（objectType=2）支持。

| 定义 | Copy | CopyProp |
|---|---|---|
| Record | 复制 Record 定义及 Record Fields | 只复制 Record 本身的属性，不复制 Record Fields |
| Field | 复制 Field 定义及 Field Labels | 只复制 Field 定义，不复制 Field Labels |

例如，要把 `C_AI_KF1010` 新增的 NAME 字段及其 Key 设置迁移到目标 Record，不能仅对 Record 使用 CopyProp，因为它不复制 Record Fields。上述范围见 [Oracle PeopleTools 8.60 Lifecycle Management Guide，第 64 页](https://docs.oracle.com/cd/G10811_01/psft/pdf/pt860tlcm-b072024.pdf#page=64)。

### Upgrade：是否参与本次处理

勾选表示该条目允许参与复制，并按 Action 处理；未勾选表示跳过该条目。它是迁移条目的选择开关，不表示 PeopleTools 版本升级，也不表示定义已经升级成功。实际能否处理还取决于 Done 和本次选择的定义类型。见 [Oracle 的 Upgrade Workspace 说明](https://docs.oracle.com/cd/F52213_01/pt859pbr3/eng/pt/tlcm/UsingtheUpgradeWorkspace-0773e7.html)。

### Done：完成标记及是否需要再次处理

原生复制成功后会自动勾选 Done；保留这个标记时，后续复制通常会跳过已完成条目。取消 Done 表示允许再次处理，但仍需勾选 Upgrade。AD 中只能手动取消 Done；本 CLI 也支持直接设为 on，因此 `Done=1` 本身不能作为实际迁移成功的证据。见 [Oracle PeopleTools 8.60 Lifecycle Management Guide，第 22、93 页](https://docs.oracle.com/cd/G10811_01/psft/pdf/pt860tlcm-b072024.pdf#page=22)。

本次验证中，Copy Project to File 导出也会自动勾选 Done。此时只说明该次导出已处理条目，不能据此认定已导入目标环境，更不能认定已完成数据库 Build/Alter 或运行验证。CLI 的属性回读也只证明标记保存成功。

### 三个属性如何共同生效

对于 Copy、Delete、CopyProp，在本次已选择对应定义类型、且没有先重置 Done 的前提下：

| Upgrade | Done | 本次处理 |
|---|---|---|
| 不勾选 | 不勾选 | 跳过 |
| 不勾选 | 勾选 | 跳过 |
| 勾选 | 不勾选 | 具备处理条件，按 Action 执行 |
| 勾选 | 勾选 | 按已完成条目跳过 |

**重置 Done 会改变上表的前提。** 原生复制对话框的 `Reset Done Flags` 默认勾选，会在复制前清除 Done；原生 `pside.exe` 的 `-RST 1` 同样会先重置，`-RST 0` 保留 Done，省略该参数默认按 1 处理。重置 Done 不等于勾选 Upgrade，也不会改变 Action。见 [Oracle 第 85 页的复制选项](https://docs.oracle.com/cd/G10811_01/psft/pdf/pt860tlcm-b072024.pdf#page=85)和 [Oracle 命令行参数说明](https://docs.oracle.com/cd/F52213_01/pt859pbr3/eng/pt/tlcm/CommandLineParameters.html)。

Copy Project from File 还需确认使用哪份项目定义：选择 File 会使用导出文件中的 Project 及其迁移标记，并替换目标数据库中的 Project 定义；选择 Database 才保留并使用目标数据库现有的项目标记。因此，修改目标 Project 后，不能假设选择 File 的导入会遵循这些修改。见 [Oracle 的 Copy Project from File 说明](https://docs.oracle.com/en/applications/peoplesoft/peopletools/8.63/lifecycle-management-guide/copying-project-from-file.html)。

## 属性参数及约束

三个 Project 条目属性的对应关系如下：

| AD 属性 | API / PSPROJECTITEM 字段 | CLI 参数 | 编码 |
|---|---|---|---|
| Action | upgradeAction / UPGRADEACTION | --action Copy / Delete / CopyProp | 0 / 1 / 3 |
| Upgrade | takeAction / TAKEACTION | --upgrade on / off | 1=打勾，0=不打勾 |
| Done | copyDone / COPYDONE | --done on / off | 1=打勾，0=不打勾 |

CLI 的 Action 不区分大小写；复选框还接受 checked/unchecked、true/false、1/0。三个属性可单独或组合更新。数字参数 `--upgrade-action`、`--take-action`、`--copy-done` 仍可使用；同一属性的名称参数和数字参数不能同时传。历史 `upgradeAction=2`（None）仍兼容，名称参数仅提供 Copy、Delete、CopyProp。API 只接受整型编码，错误状态或小数会拒绝，整次请求回滚。

**CopyProp 仅适用于 Record（objectType=0）和 Field（objectType=2）。** 2.3.1 起，PeopleCode 的 insertItem 和 updateItem 使用同一个校验，其他类型传 upgradeAction=3 返回错误；CLI 的名称参数和数字参数也都会提前拒绝。即使 Upgrade 未勾选，也不能设置非法 CopyProp；与 Upgrade/Done 组合提交时，整次请求失败，原有条目及属性保持不变。

insertItem 的服务端默认 takeAction=0、upgradeAction=0、copyDone=0；CLI 默认显式传 takeAction=1。Done 在插入后用 update-item 设置。重复插入不会修改已有条目的标记，需调用 updateItem。

直接调用 updateItem/deleteItem API 必须从 struct 回读完整键，四个 objectId 和四个 objectValue 都要传，空字符串也要显式传入。服务端将空值规范化为 PeopleTools 的单空格，并在 SelectByKey 后额外检查四个 Object ID；PSPROJECTITEM 主键本身不包含它们。删除请求不会为 SQL 自动补子类型，因此可以准确删除历史上 value2 为空的坏条目。不能只按对象名删除，也不要直连 SQL 清理。

## 对象类型

这里是 `PSPROJECTITEM.OBJECTTYPE`，与 Search 的 definitionType、PSPROJECTITEM 的 OBJECTID 都是不同编码。

| objectType | 类型 | objectValue1~4 |
|---|---|---|
| 0 | Record | value1=RECNAME |
| 2 | Field | value1=FIELDNAME |
| 4 | Translate Value | value1=字段名，value2=翻译值，value3=生效日期 |
| 5 | Page | value1=PNLNAME |
| 6 | Menu | value1=MENUNAME |
| 8 | Record Field PeopleCode | value1=Record，value2=Field，value3=Event |
| 43 / 44 | AE / Page PeopleCode | 使用删除处理类返回的完整键；AE value2 为原生复合键，Page value2=Activate |
| 46 / 47 / 48 | Component / Record / Field PeopleCode | 包含 Market；48 的 value4 合并固定长度 Field 与 Event |
| 9 | Menu PeopleCode | value1=菜单，value2=栏，value3=项目，value4=ItemSelected |
| 25 | Message Catalog Entry | value1=消息集号，value2=消息号 |
| 32 | Component Interface | value1=CI 名称 |
| 53 | Permission List | value1=许可权名称；授权命令不自动登记整份列表 |
| 55 | Portal Registry Structure | value1=门户名称，value2=F/C，value3=对象名称 |
| 7 | Component | value1=PNLGRPNAME，value2=MARKET |
| 30 | SQL | value1=SQLID，value2=SQL 子类型：0=普通 SQL，1=AE 步骤 SQL，2=Record View SQL |
| 33 | Application Engine | value1=AE_APPLID；不要使用 31 |
| 57 | Application Package 节点 | 按 AD 导出或已有项目中对应节点的完整路径登记 |
| 58 | Application Package PeopleCode | 路径按 value1~4 分段，根包在首位，类名在末位 |
| 79 / 80 | Service / Service Operation | value1=定义名称 |
| 81 | Service Operation Handler | value1=操作名，value2=Handlername |
| 82 | Service Operation Version | value1=操作名，value2=Versionname |
| 83 | Routing | value1=路由名，value2=生效日期 yyyy-MM-dd |

普通 SQL 插入时，CLI 和服务端都对省略或空的 value2 补 `0`；AE SQL 与 View SQL 必须分别显式传 `1`、`2`。子类型不匹配会使 AD 找不到定义。SQL 的 Search definitionType=65 不能作为 Project objectType；App Package 的 Search definitionType=104 也不能用于项目插入。

类 `C_META_DATA_PKG:MetaData:OperRecordDefn` 的登记是 objectType=58、value1=C_META_DATA_PKG、value2=MetaData、value3=OperRecordDefn。更深的路径继续使用 value4。接口拒绝无法解析首个 objectId 的对象类型，但 struct 仍是项目原始条目列表，不能据此保证所有定义和依赖都真实存在；交付时还应核验原生 AD 导出或 Compare 结果。

## CLI

```bash
python scripts/peoplesoft_api.py project current
python scripts/peoplesoft_api.py project struct MY_PROJECT
python scripts/peoplesoft_api.py project use MY_PROJECT
python scripts/peoplesoft_api.py project insert-item MY_PROJECT --object-type 30 --value1 MY_SQL --value2 0
python scripts/peoplesoft_api.py project insert-item MY_PROJECT --object-type 58 --value1 C_META_DATA_PKG --value2 MetaData --value3 OperRecordDefn
```

从 2.3.0 起，CLI update-item 可省略全部 ID，由 struct 解析完整键。必须指定 object-type、value1，以及所有非空的 value2~4，精确匹配唯一条目后才写入；未提供的 value 按空值匹配，不使用前缀或模糊匹配。修改前会读取三个属性，保存后回读核对目标值及未指定属性。成功输出具体条目和 Action、Upgrade、Done 的最终状态。所有 Project 定义类型共享此路径，CopyProp 受上述类型限制。

```bash
# 准备复制完整 Record：Copy 包含 Record Fields，取消 Done 以允许处理
python scripts/peoplesoft_api.py project update-item C_AI_EXPORT_20261010 --object-type 0 --value1 C_AI_KF1010 --action Copy --upgrade on --done off
# 仅复制 Record 属性：保留目标 Record Fields
python scripts/peoplesoft_api.py project update-item C_AI_EXPORT_20261010 --object-type 0 --value1 C_AI_KF1010 --action CopyProp --upgrade on --done off
# 仅取消 Done，Action 和 Upgrade 保持原值；Upgrade 原来未勾选时仍会跳过
python scripts/peoplesoft_api.py project update-item C_AI_EXPORT_20261010 --object-type 0 --value1 C_AI_KF1010 --done off
# 普通 SQL 的子类型必须明确指定
python scripts/peoplesoft_api.py project update-item C_AI_EXPORT_20261010 --object-type 30 --value1 C_AI_SF1010 --value2 0 --action Copy --upgrade off
python scripts/peoplesoft_api.py project struct C_AI_EXPORT_20261010 --json
```

也可显式提供全部四个 ID；只提供一部分会拒绝。以下是普通 SQL 的完整键示例。实际四个 ID 应复制 struct 返回值，不能照抄其他定义的键。delete-item 继续要求全部 ID。

```bash
python scripts/peoplesoft_api.py project update-item MY_PROJECT --object-type 30 --id1 65 --id2 0 --id3 0 --id4 0 --value1 MY_SQL --value2 0 --take-action 1 --upgrade-action 0 --copy-done 0
python scripts/peoplesoft_api.py project delete-item MY_PROJECT --object-type 30 --id1 65 --id2 0 --id3 0 --id4 0 --value1 MY_SQL --value2 0
```

CLI 的 update-item/delete-item 对省略的 value 参数发送显式空字符串。删除历史坏条目时，空的 value2 应保持空，不能改成 0；否则会定位到正常条目。

`--done`/`copyDone` 和自动回读验证要求部署 2.3.0 服务端工程。仅升级 Python 脚本不足以增加服务端能力；旧服务端缺少 copyDone 回读时，CLI 会在写入前报错。

CopyProp 的服务端类型限制要求部署 2.3.1 工程；仅更新客户端不能防止直接调用旧 API 写入非法 Action。

## 响应及状态

接口统一返回 code/message/data；code=0 为成功。insertItem 的 data 包含 projectName 和 inserted；updateItem/deleteItem 分别返回 updated/deleted。错误返回非零 code 和原因，失败事务会回滚。

当前 Project 仅是 CLI 保存在 config.json 当前环境 active_project 中的上次选择，不是服务端的权威业务归属。create/insert-item/modify 成功后更新当前选择，struct/update-item/delete-item 不切换；use 仅写本地状态，因此切换前先确认服务端项目存在。项目有条目并不代表会迁移，还要核对正确的 Action、Upgrade、Done，以及本次复制是否重置 Done、是否选择该定义类型、使用哪份 Project 定义。

App Package 根包的首次创建仍需 AD；Project API 只登记项目条目，不负责创建根包或修复缺失定义。

2.4 新五组写命令会自动登记已确认工程，已有 Upgrade 保持，Done 取消；精确删除登记 Action=Delete/Upgrade=on/Done=off，重建改回 Copy。此行为表示需要再次迁移，不代表复制已经完成。删除菜单项也登记其已存在的所属程序删除。消息集/权限等数据的实际迁移还须检查原生导出能力与目标安全配置。
