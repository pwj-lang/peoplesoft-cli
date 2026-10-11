# 安装、认证与授权

## 公共调用规则

CLI 负责环境、PS_TOKEN 和文本编码。直接调用 REST 时使用 `Content-Type: application/json`、`PS_TOKEN`；接口地址中的 `PSFT_HR` 换成目标环境节点。通常返回 `code/message/data`，`code=0` 表示请求成功，实际写入还须独立回读。各接口的正文编码及特殊返回结构见对应文档。所有子命令支持 `--timeout <秒>` 限制单个 API 请求的超时（默认不限；网关无响应时使用）。

## 安装

先运行 `preflight --refresh`。路由缺失时核对接口部署；180/74“找不到类”核对 Handler 与完整包，不按授权失败处理。

导入使用根目录下 `C_META_DATA_PKG/` 的 XML/INI。核实 pside.exe 路径、数据库类型/名称、PeopleSoft 用户及 TOOLSREL；Oracle 数据库连接名可参考本机 tnsnames.ora。凭据只从配置读入内存，不写入脚本、日志或回复。

下面变量使用实际配置；`$psFileRoot` 是包含项目目录的父目录，不能直接指向 XML 或 `C_META_DATA_PKG` 目录。日志目录需先创建。

```powershell
$psAd = '<pside.exe 绝对路径>'
$psDbType = 'ORACLE'
$psDbName = '<目标数据库>'
$psUser = '<PeopleSoft 用户>'
$psPassword = '<从本地配置读取的密码>'
$psFileRoot = '<skill 根目录>'
$psProject = 'C_META_DATA_PKG'
$psReport = '<比较报告目录>'
$psLog = '<本次操作的独立日志路径>'

# Compare From File：先比较，检查目标自定义修改及冲突
& $psAd -CT $psDbType -CD $psDbName -CO $psUser -CP $psPassword `
  -FP $psFileRoot -PJFC $psProject -PJFF $psProject `
  -CMXML 1 -ROD $psReport -LF $psLog -HIDE -QUIET -SS -SN

# Copy From File：在已授权范围内导入；冲突先明确处理方式
& $psAd -CT $psDbType -CD $psDbName -CO $psUser -CP $psPassword `
  -FP $psFileRoot -PJFF $psProject -RST 1 -OVW 1 `
  -LF $psLog -HIDE -QUIET -SS -SN
```

目标缺少定义通常是待新增内容；两端均有自定义修改则需处理冲突。`-RST 1` 重置 Done；`-OVW 1` 覆盖目标 Project，必须符合已确认的导入范围。日志需出现已处理条目及成功完成标记。

导入后按需 Build Project。本工具已验证的设置为 Create Tables、Alter Tables、Create Views 打开，Create Indexes、Create Triggers 及其他选项关闭。核对本机 RDM Build Settings；验证环境的注册表位置为 `HKCU\Software\PeopleSoft\PeopleTools\Release8.40\RDM Build Settings`，`ExecuteOption=3` 表示执行 SQL 并生成脚本，不推定所有版本都相同。

```powershell
& $psAd -CT $psDbType -CD $psDbName -CO $psUser -CP $psPassword `
  -PJB $psProject -LF $psLog -HIDE -QUIET -SS -SN
```

检查 Build 日志的错误、警告和 SQL 是否实际执行。工程导入不等于接口已授权。

## 认证

CLI 通过 PSTOKEN.v1 获取 PS_TOKEN，并复用本地缓存：

```powershell
python scripts/peoplesoft_api.py auth --refresh
python scripts/peoplesoft_api.py env init <环境名> --url <PIA地址> --username <用户> --password-stdin
```

默认配置为 `%USERPROFILE%\.peoplesoft\config.json`；PEOPLESOFT_CONFIG 可指定其他路径。认证失败先核对当前环境、PIA 地址、用户和密码，再刷新 Token，不绕过认证直连数据库。

直接接口为 `GET {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/<节点>/PSTOKEN.v1/`。请求头 Authorization 使用 Basic 编码的 username:password，可选 LanguageCd（ZHS/ENG）；编码后的凭据同样不得展示。成功 data 包含 psToken、userid、description、language。服务端有效期以单点登录配置为准；本工具缓存 11 小时，授权变化后使用 --refresh。

## 授权

使用用户已确认的专用 Permission List，不默认选 PTPT1000。已有授权沿用；缺少目标权限列表时才确认。初始安装授权可在已获准的浏览器会话中完成：

1. 打开 **PeopleTools → 安全性 → 许可权与角色 → 许可权列表**，搜索并打开指定列表。
2. 切换 **Web 服务** 页签。没有 `C_META_DATA_SERVICE` 时用新增行及查询按钮选入该服务；已有时点击该行 **编辑**。
3. 在操作权限窗口找到 `PSTOKEN_GET`；若显示接口别名，则对应 `PSTOKEN.v1`。设置为 **完全访问**。
4. 按任务给所需元数据操作设置 **完全访问**，核对全部分页/滚动区域；保存权限窗口，再保存许可权列表。不要对无关服务使用“完全访问（全部）”。
5. 完整安装验收需覆盖下列 15 个操作；账号必须通过自身角色/许可权关联实际取得该列表。

```text
AI_OPER_APP_ENGINE_POST
AI_OPER_APP_PKG_POST
AI_OPER_COMPONENT_DEFN_POST
AI_OPER_FIELD_DEFN_POST
AI_OPER_PAGE_DEFN_POST
AI_OPER_PROJECT_DEFN_POST
AI_OPER_RECORD_DEFN_POST
AI_OPER_SQL_DEFN_POST
AI_OPER_SERVICE_DEFN_POST
AI_OPER_SERVICE_OP_POST
AI_OPER_MENU_DEFN_POST
AI_OPER_MESSAGE_CATALOG_POST
AI_OPER_PORTAL_REGISTRY_POST
AI_QUERY_RECORD_POST
AI_SEARCH_DEFN_POST
```

```powershell
python scripts/peoplesoft_api.py healthcheck --refresh
```

PSTOKEN_GET 与全部 15 个操作均为 PASS 才报告完整安装成功；有意采用部分授权时如实说明可用范围，不宣称完整健康检查通过。Token 成功但接口未授权时核对对应操作，重新导入工程不能代替授权。

已部署且已授权的 `service-op set-permission` 可为指定现有列表设置某个 REST 操作的 Full/None，见 [服务操作](12-service-defn-api.md#服务操作)；它不能创建列表或代替初始授权。

## 原生导出

CLI 当前没有 `project export` 子命令，使用 AD 的 Copy To File：

```powershell
& $psAd -CT $psDbType -CD $psDbName -CO $psUser -CP $psPassword `
  -PJTF $psProject -FP $psFileRoot -LF $psLog -HIDE -QUIET -SS -SN
```

先导出到新的目录，检查退出码、日志、XML/INI、完整键清单和 TOOLSREL，再替换发布工程。源码变更须先在服务器编译并回读，不能仅修改 XML 的 peoplecode_text 而沿用旧编译块。

PANWX25 / PeopleTools 8.60.10 的 `-HIDE -QUIET` 成功/失败均可能没有标准输出；成功退出码为 0，不存在项目为 8，具体错误写入 `-LF` 日志。日志按 BOM 或 UTF-16LE 读取，不能仅凭没有输出判断成功。报告退出码、导出目录和具体错误。导出会更新 Done，标记语义见 [Project 管理](11-oper-project-defn-api.md)。

命令依据见 [Oracle 原生复制说明](https://docs.oracle.com/cd/F44947_01/pt858pbr3/eng/pt/tlcm/task_CopyingDefinitionsUsingTheCommandLine.html)。
