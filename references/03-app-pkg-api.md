# 应用包与类代码

读写分离部署：查询使用 `C_META_DATA_READ` 的对应 `AI_READ_*` URI，写入使用 `C_META_DATA_WRITE` 的原 `AI_OPER_*` URI；处理类分别位于 `C_META_DATA_PKG:MetaData:Read`、`:Write`。CLI 在 split 环境自动选择，完整映射及许可权配置见 [安装与读写分离](01-auth-api.md#读写分离2026-10-30)。下文参数/版本契约继续适用；旧混合 URI 的读取示例须改用对应 Read URI。

REST：`AI_OPER_APP_PKG_POST.v1/`。根包首次创建仍使用 AD；接口支持读取目录、维护类代码、新增类/子包，以及删除类、子包和整个应用包。认证和响应见 [安装说明](01-auth-api.md#公共调用规则)。

## 版本快照与写入契约

`default` 和 `viewPeopleCode` 返回不透明字符串 `version`；所有写操作必须把读取时的原值放入 `expectedVersion`。不能在提交旧编辑稿前临时读取最新版本来绕过冲突检查。

结构树每个节点有 `classPath` 和相同根包作用域的 `version`。包节点另有原生 `packageVersion`；类节点另有原生 `programVersion` 和 `programExists`，空类壳的程序版本为 0。代码读取返回 `classPath/programExists/peoplecode/programVersion/version/lastUpdate`。数值版本用于显示，提交校验使用完整 `version` 字符串。

令牌基于排序后的包键及 PSPACKAGEDEFN.VERSION、类定义键、程序完整键及 PSPCMPROG.VERSION 计算 SHA-256。包结构和程序版本分别维护，不能只校验包版本或 MAX(程序版本)。同一根包任一类程序或结构变化都会让旧令牌失效，包括 AD 保存；这是根包级的保守并发控制，不是 Git 历史。

服务端先锁定 PSLOCK 的 APM、PCM 行，再重新读取并核对版本，校验与写入间不提前提交。编译失败回滚新增类壳和结构修改。读取前后令牌变化时也返回冲突，避免将不一致的结构/正文绑定到版本。版本批量读取后在本请求内复用，不对每个节点单独查询版本。

| 响应 JSON code | 客户端处理 |
|---|---|
| 428 | 缺少/空 expectedVersion，先获取快照 |
| 409 | 版本冲突，拒绝本次写入；重新读取结构和目标代码，保留本地改稿，合并后显式提交 |
| 403 | 正在执行的 OperAppPackage 不能通过自身接口修改、删除，包含它的祖先包也不能删除；使用 AD |
| 404 | 根包不存在 |
| 400 | 路径、操作、编译或其他请求校验失败，检查 message |

这些是响应体的 code，不保证对应 HTTP 状态。冲突不自动重试写入。元数据保存与 Project 登记分步执行，登记失败须补登记，不能重复删除。

## 请求参数与操作

| 参数 | 说明 |
|---|---|
| packageRoot | 必填精确根包名，搜索 definitionType=104 |
| operationType | 省略/空/default=结构；其他操作见下表 |
| classPath | 除结构查询外必填，从根包开始、用冒号分隔；删除整个根包时等于 packageRoot |
| expectedVersion | 所有写操作必填，原样使用同根包先前读取的 version |
| peoplecode | modifyPeopleCode 必填；insertClass 可选，完整正文按 CommonUtil EscapeJSON 编码，CLI 自动处理 |
| expectedCode | deletePeopleCode 还须提供新鲜代码快照，编码同 peoplecode |
| dryRun | 四种删除操作可选；只返回计划，不删除、不登记、不改变版本 |

| operationType | 行为 |
|---|---|
| default | 返回 descr/comment/lastUpdate/packageTree/version |
| viewPeopleCode | 获取精确类程序及版本，空类壳仍可读取 |
| modifyPeopleCode | 原生编译保存；类必须存在，允许在空类壳上创建程序；拒绝空白正文 |
| insertClass | 新增一个类，可附代码；代码编译失败时不保留新类壳 |
| insertPackage | 新增一级或二级子包，父包须已存在 |
| deletePeopleCode | 删除程序，保留类壳；沿用 expectedCode 和完整 Project 键校验 |
| deleteClass | 删除一个精确类的程序及类定义，也支持空类壳 |
| deletePackage | 删除一个子包及其全部后代，保留父包和其他分支；Foo 不匹配 Foo2 |
| deleteApplicationPackage | 删除整个 packageRoot 的类、程序、子包、语言数据及根包 |

名称以字母开头，后续只含字母、数字和下划线，每段最多 30 个字符；根包下最多两级子包。结构删除返回 `targets` 和 `projectItems`；每个工程条目含 objectType、objectId1～4、objectValue1～4、deleted。被删除程序登记 58/Delete，被删除包登记 57/Delete；保留的直接父包登记 57/Copy，以迁移类清单变化。删除调用不修改外部引用它的业务定义。

**PeopleTools 8.60.10 实测限制**：AppPackageDefn_Manager.DeleteDefn 收到子包键也会按 PACKAGEROOT 删除整包，不能用于子包删除。处理类仅在整包删除中调用此入口；子包精确清理 PSPACKAGEDEFN/PSPACKAGELANG、写入 PSPACKAGEDEL，并同步 APM/SYS 缓存版本。程序删除仍走 PeopleCodeProgram_Manager.DeleteDefn。其他 PeopleTools/数据库尚未验证。

请求示例，token 使用先前读取的原值：

```json
{"packageRoot":"MY_ROOT","operationType":"deletePackage","classPath":"MY_ROOT:App","expectedVersion":"<先前返回的version>","dryRun":true}
```

## CLI 工作流

```powershell
python scripts/peoplesoft_api.py app-pkg struct MY_ROOT --json
python scripts/peoplesoft_api.py app-pkg insert-package MY_ROOT 'MY_ROOT:App' --project MY_PROJECT
python scripts/peoplesoft_api.py app-pkg insert-class MY_ROOT 'MY_ROOT:App:TestClass' --project MY_PROJECT
python scripts/peoplesoft_api.py app-pkg view-code MY_ROOT 'MY_ROOT:App:TestClass'
# 编辑上一步 Cached 所指文件；其 .snapshot.json 保留下载时的版本和环境。
python scripts/peoplesoft_api.py app-pkg modify-code MY_ROOT 'MY_ROOT:App:TestClass' D:\work\class.pcode --snapshot D:\work\original.pcode.snapshot.json --project MY_PROJECT
python scripts/peoplesoft_api.py app-pkg delete-code MY_ROOT 'MY_ROOT:App:TestClass' --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py app-pkg delete-class MY_ROOT 'MY_ROOT:App:TestClass' --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py app-pkg delete-package MY_ROOT 'MY_ROOT:App' --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py app-pkg delete-root MY_ROOT --project MY_PROJECT --dry-run
```

省略 --dry-run 才执行删除。所有写命令要求 --project 或当前工程，独立回读后按完整键登记并校验迁移标记。支持 --output 保存结果。结构写默认使用最近一次 struct 的本地结构快照，--snapshot 可显式指定；成功写入后更新结构缓存。modify-code 必须使用该类的代码快照，默认读取输入文件旁的 .snapshot.json，不能借用更新过的结构版本上传旧代码。快照绑定环境、服务器、节点、账号和包根。

CLI 遇到 409 会另存 `conflict_*` 最新结构、受影响类的代码及版本快照，保留原改稿和原快照。人工合并后使用新下载文件或显式 --snapshot 再提交。目标被其他人删除时报告读取失败，不当成成功写入。若写入已确认而后续回读发生并发变化，报告已确认写入，不能误称为“写入被拒绝”。

结构删除前保存受影响子树及代码 JSON；delete-code 另存唯一 UTF-8 正文。删除后的完整 Project 键见 [Project 管理](11-oper-project-defn-api.md)。包处理类、CLI 和快照协议须一起更新；旧客户端写入被拒绝，旧服务端返回值不能作为新版校验已部署的证据。
