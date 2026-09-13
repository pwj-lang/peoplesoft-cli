# 使用 AD 导入 Project

本Skill依赖Project[C_META_DATA_PKG]中实现的元数据Api，若发现使用PSToken接口时遇到Unable to find a Routing corresponding to the incoming request message.错误说明ps系统缺少元数据Api，可根据本文档将Api导入至系统中

## 前置条件

- 需要 AD/PSIDE 的实际路径、数据库类型、数据库名和 ps 用户凭据。
- AD工具的名称是“pside.exe”可根据名称查找系统文件
- 数据库信息查询用户的tnsnames.ora文件为准(仅适用Oracle数据库)
- ps 用户凭据一般和登录用户凭据一致，优先跟用户确认登录用户是否拥有peopleTools权限
- skill的根目录有个C_META_DATA_PKG文件夹，里面是元数据Api的代码，包含C_META_DATA_PKG.XML、C_META_DATA_PKG.ini两个文件

以下示例使用占位符；执行时替换为本机实际值：

~~~powershell
$AD = '<PeopleTools客户端目录>\client\winx86\pside.exe'
$DB_TYPE = 'ORACLE'
$DB_NAME = '<目标数据库>'
$DB_USER = '<PeopleSoft用户>'
$DB_PASSWORD = '<密码>'
$FILE_ROOT = '<本Skill所在目录>'
$PROJECT = 'C_META_DATA_PKG'
~~~

## 1. Compare From File

先比较工程和目标数据库，保存报告供用户审核：
- `-FP` 必须指向包含项目目录的父目录，不能直接指向 `C_META_DATA_PKG` 目录。
- 密码不要写入脚本、日志、Project 或回复内容。

~~~powershell
$REPORT = '<比较报告输出目录>'

& $AD `
  -CT $DB_TYPE -CD $DB_NAME -CO $DB_USER -CP $DB_PASSWORD `
  -FP $FILE_ROOT `
  -PJFC $PROJECT -PJFF $PROJECT `
  -CMXML 1 -ROD $REPORT `
  -HIDE -QUIET -SS -SN
~~~

重点检查 Compare 报告：
- 目标端缺少定义：通常是本次待导入内容，不单独视为冲突；
- 文件和目标端都存在自定义修改：属于定义冲突，需将冲突对象报告给用户；

## 2. Copy From File

在无定义冲突或用户确认可以导入后，执行 Copy From File
~~~powershell
& $AD `
  -CT $DB_TYPE -CD $DB_NAME -CO $DB_USER -CP $DB_PASSWORD `
  -FP $FILE_ROOT `
  -PJFF $PROJECT `
  -RST 1 -OVW 1 `
  -HIDE -QUIET -SS -SN
~~~

参数含义：

- `-RST 1`：重置文件工程中的处理标记，确保本次重新处理；
- `-OVW 1`：覆盖目标端已有 Project 定义。只能在用户明确授权后使用；
- `-FP`：仍然是文件工程根目录，不是 XML 文件路径。

导入日志应至少确认：

- `Total ... items processed.`；
- `Command line process successfully completed.`；

## 3. Build Record

导入后对 Project 执行 Build。Build 选项只选择以下三项：

| Build 选项 | 设置 |
|---|---:|
| Create Tables | 1 |
| Alter Tables | 1 |
| Create Views | 1 |
| Create Indexes | 0 |
| Create Triggers | 0 |
| 其它 Build 选项 | 0 |

如果当前 AD 版本通过注册表保存 RDM Build Settings，执行前先读取并确认对应值；在本次验证环境中使用了：

~~~text
HKCU\Software\PeopleSoft\PeopleTools\Release8.40\RDM Build Settings
CreateTables=1
AlterTables=1
CreateViews=1
CreateIndexes=0
CreateTrigger=0
ExecuteOption=3
~~~

`ExecuteOption=3` 用于在线执行 SQL，同时生成 Build 脚本。不要只生成脚本而不执行，否则数据库对象可能没有真正创建或修改。

执行 Build Project：

~~~powershell
& $AD `
  -CT $DB_TYPE -CD $DB_NAME -CO $DB_USER -CP $DB_PASSWORD `
  -PJB $PROJECT `
  -HIDE -QUIET -SS -SN
~~~

Build 完成后检查 Build 日志：

- 目标是 `0` 条错误、`0` 条警告；
- 日志明确显示 SQL 已在线执行；
- 只处理本次 Project 中需要的 Record/表和视图，不要顺手打开索引、触发器等其它选项。

## 4. 完成接口授权

参考文档 [rest-authorization.md](rest-authorization.md) 
