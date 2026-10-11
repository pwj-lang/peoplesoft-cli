# 开发规范

通过本 skill 开发或审查 PeopleSoft 定义前必读。约束适用于实际修改；维护 ps-cli 本身时另读 [发布规划](release-roadmap.md)。

## 环境、对象与工程

- 使用用户已指定的环境和 Project，沿用会话中的确认，不重复索取同一授权。`active_project` 仅提示上次选择；没有明确归属时先确认。
- 修改前搜索并读取当前定义、代码和属性；使用 API 取得结构，不猜字段、类型码、事件或完整键。业务字段映射未确定时，先列出候选名称、类型、长度供确认；已有明确映射直接核实复用。
- Record 引用的 Field 必须存在，创建 Record 不会自动创建 Field。
- 创建/修改定义后核对 Project 完整条目；缺失才插入，已有条目按需调整迁移标记。只读不登记；Project 成员删除不等于定义删除。详见 [Project](11-oper-project-defn-api.md)。

## 写入与失败处理

1. 保存写前结构或代码，提交任务所需的最小修改。全量替换字段（如 fieldProperty）必须先合并原值；局部补丁省略项保持原值。
2. 使用 CLI 和 UTF-8 文件传正文/复杂 JSON，编码按对应接口执行。旧代码接口与新对象接口不同，不能统一套 Base64 或双重转义。
3. 保存后独立回读目标及相关关联，核对未指定属性不受损。CLI 已验证正文的操作无需重复同一检查；直接 API、自定义写路径必须自行验证。
4. 编译错误、保存失败、回读不符或 Project 登记失败均如实报告。结果不明先读取实际状态，不盲目重试，不假设分步保存已经共同回滚。

dry-run 只验证计划，不能证明最终保存成功。modify-code 拒绝空白正文；真正删除使用下面的明确流程，支持范围见 [已知问题](known-code-issues.md)。跨定义的服务配置、菜单程序清理、门户及 DDL 各自检查部分成功状态。

## PeopleCode 真正删除

Page、Record、Component、AE、应用包的 `delete-code` 对应旧接口 `operationType=deletePeopleCode`。Menu 使用自己的 `deleteCode`，正文为普通 JSON 字符串；旧接口 expectedCode 按 CommonUtil 编码，CLI 自动处理，不混用。

删除一个精确程序，保留父定义。Page 为 Activate；Record 为 Record/Field/Event；Component 包含 Market，按 Component、Record、Field 三层定位，指定 Field 必须指定 Record；AE 为 Application/Section/Market/DBType/EffDt/Step/OnExecute；应用包为从根包到类的完整路径，保留类壳。

CLI 要求 `--project` 或当前确认的 Project：先读正文和 programExists，保存唯一 UTF-8 快照，再以 expectedCode 核对新鲜正文。服务端拒绝缺失快照、过期快照、不存在的程序，调用原生 PeopleCodeProgram_Manager.DeleteDefn 后检查原生不存在。CLI 再独立回读，按返回的完整 Project 键登记 Action=Delete、Upgrade=on、Done=off，并核对标记；程序删除成功但工程登记失败时明确报告部分成功，不盲目重删。

`--dry-run` 核对键和快照但不删除、不登记；`--output` 保存结果 JSON。重复删除返回不存在。`viewPeopleCode` 返回 programExists；不存在时正文可能为 null 或空字符串，不能仅检查正文或 hasPeopleCode。

| 程序 | Project objectType | 键要求 |
|---|---|---|
| Record Field | 8 | Record / Field / Event |
| AE | 43 | Section+Market+数据库原生名+生效日期按原生固定长度组成 value2；Step / OnExecute |
| Page | 44 | Page / Activate |
| Component / Record / Field | 46 / 47 / 48 | 保留 Market；48 的 value4 为固定长度 Field+Event |
| 应用类 | 58 | 根包到类按位置分段；未用值保持原生返回值 |

必须使用处理类返回的完整 objectId1～4/objectValue1～4；不要手工拼 AE/Component Field 复合键或将空字符串统一替换为空格。验收至少检查原生不存在、相邻程序/父定义保留、精确 Project 标记；外部修改后关闭重开 AD 检查事件显示。

## 验收与报告

报告具体环境、对象名、完整定位、修改的属性/值、回读结果及错误。API 成功只能证明对应阶段；界面行为使用 AD/PIA 核验：服务操作搜索/所属服务/Handler/Routing/权限，门户 validate 加实际导航，Record 外部修改后关闭并重开 AD。

BUG 只在复现条件消失且验收通过后关闭；未验证、暂不支持和明确延期分别记录。修改服务器源码后原生导出包含编译内容的完整工程，检查日志、依赖与 TOOLSREL；不能只替换 XML 正文或沿用旧编译块。流程见 [安装与导出](01-auth-api.md)。

## 工作副本与文档

view-code/view-sql 缓存为 UTF-8：优先 `PEOPLESOFT_TMP_DIR`，一般使用工作区 tmp；从 skill 运行时使用系统临时目录的 peoplesoft 子目录。命令输出实际路径，缓存不视为服务器当前状态。

临时导出、测试夹具、日志、字节码和验收报告不放进 skill 发布包。工具回归材料存于开发项目工作区。文档以中文维护，保留命令、参数、协议和许可证原文；先复用已有主题文档，避免为重复说明新增文件。密码、Token 不写入代码、日志、回复或工程。

## PeopleCode 实现约束

- 类内私有方法调用使用 `%This.MethodName(...)`；REM 注释以分号结束。
- CreateRowset(Record.X) 的独立 Rowset 初始有一行空行；构造数组前确认复用/插入位置。
- 独立 IB 上下文优先使用 `&rec.GetField(Field.X).Value` 赋值；方法返回值先存局部变量再判断，保留编译错误和位置。
- 工具历史实测遇到嵌套 Evaluate、块内 Local、JsonObject 数字/跨方法传值的编译或运行差异；先按当前 PeopleTools 验证，必要时改为 If、方法顶部声明或明确类型的参数。不能据单次异常推断所有版本的语言限制。

## 原生键解析

复用 `C_META_DATA_PKG:Utility:ObjectKeyResolver`，不为取编号加载固定 Project 或创建真实临时工程。ObjectID 是键类型，ObjectValue 是名称/事件等键值；解析成功不证明定义存在。

解析器通过 `%metadata:ProjectDefn:ProjectDefn_Manager.CreateDefn()` 创建未保存的空 ProjectDefn，调用原生 GetObjectIDs；每个实例复用自己的空对象，不使用跨请求全局缓存，不调用保存方法。

```peoplecode
import C_META_DATA_PKG:Utility:ObjectKeyResolver;
Local C_META_DATA_PKG:Utility:ObjectKeyResolver &keys = create C_META_DATA_PKG:Utility:ObjectKeyResolver();
Local array of integer &ids = &keys.GetObjectIDs(6, CreateArray(&menuName, " ", " ", " "));
Local %metadata:Key &key = create %metadata:Key(&ids[1], &menuName);
```

GetObjectIDs 接收非负 objectType 和四位置字符串数组，返回四个 ObjectID，主键类型必须为正，未使用位置可为 0。数组不能省位或改序：菜单程序按菜单/栏/项目/事件；门户按 PortalName/RefType/ObjName/空白。

NativeAdapter 和 MenuCodeAdapter 统一调用解析器，原生 Manager 验证目标定义及依赖。交付包须同时包含解析器与两个调用类。业务定义不必属于 C_META_DATA_PKG，实际登记使用已确认的工作 Project。
