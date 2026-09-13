# 当前已知限制

本文只保留会影响 Agent 判断或操作结果的未解决问题。已修复的历史问题、测试项目、修复日期和过程记录不再放在正式 skill 中。

## 1. SQL Definition 接口先检查 Handler 绑定

如果 `AI_OPER_SQL_DEFN_POST` 返回 HTTP 500，PeopleSoft 日志提示 180/74“找不到类”，先在 Service Operation 的 Handler 配置中确认类名是：

~~~text
C_META_DATA_PKG:MetaData:OperSqlDefn
~~~

不要使用拼写错误的 `OpenSqlDefn`。修复 Handler 后重新发布并验证 `sql view`、`sql create` 或 `sql modify`。

## 2. Page PeopleCode 清空后的状态

Page 的 `modifyPeopleCode` 传入空字符串后，PeopleCode 正文可能被清空，但定义记录仍存在，导致结构查询中的 `hasPeopleCode` 仍为 True，而 `viewPeopleCode` 返回空字符串。删除 Page PeopleCode 时，必须同时查看结构和代码响应，不能只依赖 `hasPeopleCode`。

## 3. Project 条目类型和删除能力

- Application Engine 插入 Project 使用 `objectType=33`；不要使用已验证不会显示在 AD 项目树中的 `objectType=31`。
- 当前 Project API 没有可靠的 `deleteItem` 操作。插入错误条目前先确认 object type 和四个 value 参数；如果已经插入错误定义，使用 AD 检查并清理。
- App Package PeopleCode 的 `objectType=58` 插入仍可能出现 SQL 错误，即使结构查询能看到部分条目；写入后必须用 Project 结构和 AD 双重验证。

## 4. Page 扩展表的网关错误

读取 `PSPNLFIELDEXT` 的 Rowset 并逐行访问，在部分包含扩展控件的 Page 上可能触发 IB 网关 500。Page 结构默认不要依赖该 Rowset 的批量迭代；需要扩展属性时优先采用单行查询，并在目标环境验证。

## 5. 安装验收必须覆盖所有接口

PSTOKEN、搜索或某一个定义接口成功，不能证明整个 Project 已完整导入。排查阶段先跑 `preflight`，验收阶段必须运行 `healthcheck`；两者都分别验证全部十个元数据 Service Operation。

如果某项返回“找不到类”、缺失 SQL Definition、无效 Record 属性或其他运行时错误，按部署/源码兼容性故障处理，不要误判成许可权问题。只有明确的 401、403、not authorized、permission denied 等响应才进入许可权列表排查。

## 6. PeopleTools 版本兼容性

导入前检查文件工程的 TOOLSREL 与目标 PeopleTools 版本。不同版本的系统 Record 字段、SQL Definition 和 Application Package 依赖可能不同；Compare 无冲突也不代表运行时兼容。目标版本低于文件工程版本时，必须以 healthcheck 结果作为是否可用的最终判断。

## 7. PeopleCode 修改必须回读

任何 `modifyPeopleCode` 返回成功后，都必须再执行对应的 `viewPeopleCode` 或结构查询确认实际内容。PeopleCode 编译失败时，服务器可能返回成功但没有保存预期代码。

## 8. 节点名错误报 (158,505)，别误判成接口未部署

IB REST 网关 URL 里的 `{node}` 段是目标库的**本地节点名**（`config.json` 的 `node` 字段）。客户实施时大多改过名，配错时返回：

~~~text
500 Internal Server Error
集成服务: 找不到与入站请求消息对应的发送处理。 (158,505)
~~~

它和「接口没部署」发生在同一阶段、都走不通，**极易混为一谈**，但修法完全相反：

| 报错 | 含义 | 修法 |
|---|---|---|
| `找不到与入站请求消息对应的发送处理。 (158,505)` | 节点名不对 | 改 `config.json` 的 `node` 或环境变量 `PEOPLESOFT_NODE`，**不要**导入 AD 工程 |
| `Unable to find a Routing corresponding to the incoming request message.` | 节点名对，接口没部署 | 导入 AD 工程 |

节点名在目标环境里的查法：`PeopleTools > 集成代理 > 集成设置 > 节点`，取标记为 **Local Node** 的那条。

按前者去导入 AD 工程不会解决任何问题，只会白跑一轮 Compare / Copy / Build（含 DDL）。`preflight` 已能自动区分这两种报错并给出对应 NEXT。
