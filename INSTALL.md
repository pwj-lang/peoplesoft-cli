# Agent 安装与服务端部署入口

用户可以直接把下面这一句交给 Agent：

> 请安装并部署到我的 PeopleSoft 环境：https://github.com/pwj-lang/peoplesoft-cli

Agent 应读取本文件并执行安装，不要求用户复制整份流程。先发现已有配置，只询问缺失信息；环境尚未明确时先完成本地安装和部署准备。**明确要求“只安装本地 Skill”时，到本地验证为止。** 服务端部署须使用用户确认的目标环境，不能从历史环境名、上次 active_project 或偶然打开的浏览器推定目标。

This is the installation entry point for agents. Install the local skill, then deploy and verify the MetaData API in the user-confirmed PeopleSoft environment. Honor local-only requests. Discover existing configuration before asking for missing information; never infer the deployment target from this repository's examples.

## 用户只需要做什么

提供 GitHub 链接和安装意图；打开 Agent 给出的填写文件，填写需要的环境登录地址、用户名和密码，保存后说“填好了”。不用的环境块全部留空即可，Agent 自动跳过；填了一部分的环境会明确指出缺项。已在本轮提供的信息由 Agent 预填，不重复询问。填写且明确要求安装的环境就是本轮目标，不为每个普通步骤重复请求确认。

查工具、下载校验、配置合并、原生比较/备份/导入、编译、IB 配置及验收由 Agent 完成。进度用“下载中、准备环境、部署中、验证中”说明结果，不向用户抛命令、日志或技术选择题。需要角色授权时，只提醒用户或管理员分配预置角色；证据不足以唯一选择目标、存在业务定制冲突或确实缺少部署权限时，才集中说明具体需要用户处理的一件事。不要把尚未安装的接口当作自动安装自身的入口。

## 1. 确定目标与已有状态

先只读检查当前 Agent 的技能目录、Python、已有 ps-cli 版本、PeopleSoft 环境配置，以及可用的 Application Designer 客户端与登录会话。配置位置和环境命令见 [安装与认证参考](references/01-auth-api.md)。保留其他环境及本地独有修改。

这是面向开源使用者的通用安装流程，不为维护者或当前机器的某个示例环境创建配置。**项目根目录的 [install.example.json](install.example.json) 是多环境连接信息填写入口：Agent 复制为 `install.local.json`，用户在 environments 中按名称增加环境，分别填写登录地址、用户名和密码；active_environment 可选择当前环境，留空保留原选择。Agent 据此一次生成或合并正式环境配置。** 权限不在填写文件中选择或授予；导入后提醒用户或管理员自行分配角色。不先发一份技术调查表，也不把执行命令或查看比较报告交还给用户。

先确认一个可运行 CLI 的 Python 解释器，Windows 同时检查 `py`、`python`、`python3` 和已知安装路径；用实际解释器执行 `--help`，后续固定该路径。CLI 及安装助手只依赖标准库，不默认要求 pip、venv 或安装第三方模块。缺少 Python 时由 Agent 从官方来源按当前系统准备本地运行环境，遇到必须由用户处理的系统安装权限时只说明这项缺口，不让用户运行命令。

再用该解释器运行 `scripts/install_helper.py discover`，读取已有环境和本机 AD 路径、文件版本及来源。脚本只读，不输出密码或进程命令行。按 [发现与填写流程](references/install-discovery.md) 继续：

- 版本先查目标已有 PIA/AD 登录会话及目标可访问的版本信息；本机 AD 版本只是候选。将发现结果和推荐客户端并入一次环境确认，不要求用户查询补丁号；已有明确目标且证据一致时直接继续。多版本并存时不能取最高版本当服务器版本。
- 节点默认固定使用 `PSFT_HR`，不询问用户、不自动发现，也不为获取节点增加自举程序。已有环境明确配置的自定义节点继续保留；懂得修改节点的用户可自行使用高级覆盖，普通填写模板不增加节点项。
- 数据库类型/连接名从已有 AD 配置、已确认会话和本机连接别名发现；多个候选时只让用户确认能辨认的环境，不问命令行参数。
- 对外统一称“用户名、密码”。默认复用这一组用于网页登录、CLI 和 AD；只有实际发现凭据或权限不同，才说明哪一步缺什么。不要求另建所谓 API 账号；用户名为 PS 也继续安装，不把账号权限建议变成阻塞。
- 首次安装先用不带环境参数的 `prepare` 创建通用 `install.local.json` 并返回**实际文件的可点击链接**；不要要求用户先在聊天里提供目标参数才能取得填写文件。已知信息可预填，未知信息保留空白。保存后由 Agent 执行 `check`，按填写目标生成对应的正式环境配置并验证登录，节点直接使用默认值。不要要求用户输入命令或自己创建文件。

只把发现后仍缺少、且用户能回答的信息合并成一次简短询问。不要让用户把密码、Token 或填好的文件发到聊天里。凭据填写文件是本地明文，由操作系统文件权限保护，不宣称“加密”或“Agent 看不到”。交互登录确有工具限制时由用户完成该次登录，其余工作继续推进。

本仓库的流程不额外授予覆盖业务定义、删除共享类或扩大权限的许可。比较发现目标定制冲突或需要新增授权时，先完成具体比较/权限清单，再按用户已有授权处理；超出授权的部分才请求决定。

## 2. 选择发布包并安装本地 Skill

1. 从 [最新稳定版](https://github.com/pwj-lang/peoplesoft-cli/releases/latest) 选择正式 Release，记录 tag、版本、下载地址及校验和。用户指定版本时使用指定版本；不要把 main 分支当成已发行运行包。
2. 下载该 Release 的 `ps-cli-<版本>.zip` 和 `SHA256SUMS.txt`，核对 ZIP 的 SHA256；校验不符时停止使用该包。CLI、参考文档和原生服务端工程应来自同一发布包，整个安装过程固定使用这个版本。
3. 解压到当前 Agent 支持的 skills 目录，使最终入口为 `<skills目录>/ps-cli/SKILL.md`，避免多套一层 `ps-cli/ps-cli/`。Codex 通常使用 `~/.codex/skills`，其他 Agent 按其实际配置；不要为了安装一个 Agent 而写入所有客户端目录。
4. 更新已有安装前备份独有修改，不覆盖 `.peoplesoft` 中其他环境或凭据。核对 `SKILL.md` 中的版本、CLI 可执行性和原生 XML/INI 文件是否齐全。

先复用已经下载且哈希匹配的包。下载设置连接/总时限并观察进度，单次长时间无进展就停止，有限重试后尝试官方可用下载入口或本机既有代理；公共发布包可通过可用镜像取回，但最终必须与官方发布的校验值匹配。不要让用户先配置代理、下载 ZIP 或解压，也不要无限等待同一失败请求。原生 AD/Oracle 客户端不是本包交付物：先自动寻找可用安装和连接别名，确实没有时再说明“需要可用部署工具或部署机器”，不假称只凭 PIA 地址就能首次导入。

新包包含 `assets/security/manifest.json` 时，先运行 `python scripts/verify_install_security.py` 核对原生许可权、操作/CI 权限及角色数据哈希；它只检查交付物，不替代目标导入和用户名授权验收。角色使用 `assets/security/pscli-roles.dat` 与 `roles-import.dms` 配套交付，Agent 在私有工作副本填入路径、检查同名冲突后执行。模板内的路径占位符不能原样执行。

2.0.2 发布包包含本指南、安装助手和预置安全交付物。2.0.1 的历史 ZIP 不含这些新增内容。读取 main 的最新指南时留意所选包的实际能力；历史包缺少助手时由 Agent 执行相同发现/私有文件填写流程，不把缺少新工具变成用户需运行旧命令的理由。运行代码、接口参考及工程仍取所选 Release；不要混入 main 脚本、虚构历史包已包含许可权或改写历史 ZIP。

进入实际安装目录后执行：

```powershell
python scripts/peoplesoft_api.py --help
python scripts/peoplesoft_api.py env list
```

部分 Agent 需重开会话才能自动发现新 Skill。当前会话可以直接读取安装后的 `SKILL.md` 并继续部署，分别报告“文件已安装”和“自动发现已确认”。

部署前读取 [SKILL.md](SKILL.md)、[架构与交付边界](references/architecture.md)、[开发规范](references/development-standards.md)、[安装与认证参考](references/01-auth-api.md) 和 [已知问题](references/known-code-issues.md)。需要哪类写入验收，再读取对应对象参考。

## 3. 通过原生 AD 完成首次导入

**尚未安装的 MetaData API 不能用来安装自身。** 已有 API 时可先预检判断版本、路由及缺项；首次部署从随包的 `C_META_DATA_PKG/` 原生 XML/INI 工程开始，通过匹配目标版本的 Application Designer 导入。

2.0.2 工程清单为 303 条迁移成员（277 Copy、26 Delete）、297 个原生实例、100 个编译程序及 38 个 Service Operations；相比 2.0.1 增加两套工具许可权，程序及接口实现未变。这些数量是该版本的核对基线；其他版本以自身清单为准。工程包含实际使用的 `C_JSON_API`、`C_COMMONS_PKG` 依赖；只导入同名应用根包会漏掉运行依赖。

1. 核实目标数据库和 PeopleTools；使用该目标支持的 AD 客户端。主要验证基线是 Oracle / PeopleTools 8.60.10。8.54/8.55 等早期版本尚未实机验证，不等于完全不支持，也不以 8.57 划硬门槛；继续原生比较、导入和目标编译，以实际失败定位到具体功能。来源 INI 的 TOOLSREL / XML 编译版本记录导出来源，本身不能证明旧目标必然拒绝。不要预先要求用户升级。
2. 对目标已有相关定义作原生备份，再执行 Compare From File，保存比较报告。检查自定义差异、共享根包和全部 Delete 键。目标不存在的 Delete 对象可属于正常迁移状态；目标存在且仍被其他业务使用时，不能盲目删除或覆盖。
3. 对已确认范围执行 Copy From File，核对退出码、原生日志中的处理条目、成功标记和错误。命令无输出、进程退出或工程名出现，都不足以证明导入成功。

原生命令模板见 [安装参考](references/01-auth-api.md#安装)，按本机 `pside.exe` 参数核实：

| 操作 | 参数 | 要点 |
|---|---|---|
| Compare From File | `-PJFC C_META_DATA_PKG` | 先比较并检查冲突 |
| Copy From File | `-PJFF C_META_DATA_PKG` | 仅导入已确认范围 |
| Copy To File | `-PJTF C_META_DATA_PKG` | 备份和最终导出 |

这些命令供 Agent 执行，用户不需要理解或运行。`-FP` 指向**包含 `C_META_DATA_PKG/` 的父目录**，不能直接指向 XML 或工程子目录。`-RST 1 -OVW 1` 会重置迁移状态并覆盖目标 Project，仅用于已确认的导入范围。Compare 可能更新比较状态或写入报告，不笼统承诺“完全无副作用”；比较不等于已复制业务定义。凭据从本地来源读取到内存，不打印完整进程参数；AD 的 `-CP` 可能被本机有权限的进程观察到，不能宣称“读入变量就不在命令行”。优先复用可用会话/原生安全输入方式。

## 4. 编译、必要 DDL 与依赖核验

- 在目标版本原生编译整个工程，逐项检查错误及缺类；2.0.2 对应 100 个程序。不能手改 XML 的 TOOLSREL、替换源码后保留旧编译块，或把来源编译成功当作目标成功。
- 根据目标现状，只对缺失或确需调整的 Record 创建/调整表、视图或索引，先检查生成 SQL。不要对整个工程盲目执行 Drop/Create，也不要套用旧版 Build 设置。
- 如需 SQL DML，先检查 `C_AI_SQLAUD` 对应的 `PS_C_AI_SQLAUD` 表及 GUID 唯一索引；已有表保留数据。SQL DML 未获授权时保持关闭，不能为了安装冒烟而默认启用。
- JSON 默认使用 AUTO。`org.json` / JavaApi 是可选后端，不把安装 JAR 或重启 domain 当作默认步骤；目标确有需要时再按 [后端说明](references/01-auth-api.md#json-兼容层2026-10-30) 配置。
- 核验目标已有系统 `MESSAGE_CATALOG1` / `MESSAGE_CATALOG_CI`，并在使用消息维护时核对实际需要的方法权限。不要重新创建已退役的 `C_META_MSG_LANG` 页面、组件或 CI。

若原生编译/保存失败，保留完整错误及目标版本，按实际依赖继续排查。不要伪造导出或通过直接改元数据表绕过原生错误。

## 5. 配置 Integration Broker 与最小必要权限

节点按本工具约定默认使用 `PSFT_HR`，不将查询或确认节点作为安装前置步骤。Agent 配置目标 Gateway、Service、Operation/版本、URI、Handler、Routing 和 Active 状态；已有自定义节点或用户明确指定时才按覆盖值处理。公开包将 38 处环境专属 REST BaseURL 主机替换为 `https://ps.example.invalid`，必须改成目标实际主机，不能照搬占位地址。

- 元数据读服务：`C_META_DATA_READ`；定义写服务：`C_META_DATA_WRITE`。
- Token 入口：`PSTOKEN.v1` / `PSTOKEN_GET`，Handler 为 `C_COMMONS_PKG:Login:Login`。服务归属以工程和目标原生定义为准，不能假定 Token 操作就在 Read 服务内。
- 预置的只读/读写许可权及角色是安装交付物，不是当前用户名已有的权限。有部署权限时可导入这些定义；没有权限则提醒管理员处理。随后只提醒用户或管理员按需要自行分配 `C_PSCLI_READ` 或 `C_PSCLI_WRITE` 角色；Agent 不替自己授权，不按配置字段自动选择或分配角色。旧包缺少定义时如实说明并提醒管理员准备。见 [安全定义交付](references/install-discovery.md#预置许可权和角色)。
- 不默认使用 `PTPT1000`，不复制用户或成员授权，不对所有服务或所有 CI 开放 Full Access。用户已有更广权限时可继续安装；分配新角色不收缩既有权限，简述这一事实即可，不要求另建用户名。
- 完整基本读取健康检查含认证及 20 个读取操作，其中包括业务 Record 查询和任意 SQL 读取。若用户只授权较小的元数据范围，报告部分安装就绪及缺项，不为凑齐 20 项扩大权限。
- 定义写入按所需对象单独授权。`AI_EXEC_SQL_WRITE_POST` 默认不授权；权限矩阵及消息 CI 权限见 [授权参考](references/01-auth-api.md#授权)。

初始授权由用户或管理员自行完成，安装流程不调用 `service-op set-permission` 给自己授权。授权完成后再验证；缺权限时记录待授权及未验收范围，其他准备工作继续推进。

## 6. 配置 CLI 目标环境并验证读取

由 Agent 使用同一份发布包中的安装助手：

```powershell
python scripts/install_helper.py prepare
python scripts/install_helper.py check
python scripts/install_helper.py apply
python scripts/install_helper.py run --environment <环境名> current
python scripts/install_helper.py run --environment <环境名> preflight
python scripts/install_helper.py run --environment <环境名> healthcheck
```

以上同样供 Agent 执行。新安装优先用安装助手 `prepare → check → apply` 批量合并配置；用户只编辑通用填写副本。完全空白的环境自动跳过；其余环境全部校验通过、同名地址均无冲突后，才备份一次并一次写入，任一已填写环境有误则全部不写。重复 `prepare` 保留并返回原文件，重复 `apply` 对未改变的配置不重写、不增加备份、不清除其 Token 缓存。新环境节点均为默认 `PSFT_HR`，已有自定义节点和附加字段保留，未列出的已有环境不删除。填写文件中的非空 active_environment 明确选择当前环境；留空保留原选择，首次安装留空则选第一个填写完整的环境。配置默认在 `%USERPROFILE%/.peoplesoft/config.json`，支持 `PEOPLESOFT_CONFIG`。当前版本使用 split；401/403、部署或网络失败不能触发自动回退 legacy。

按环境分别验收，优先运行 `python scripts/install_helper.py run --environment <环境名> preflight`，之后同样运行 `healthcheck`；可用 `current` 先核对选中的目标。助手使用只含该目标的私有临时配置，完成或异常后删除，不改正式配置中的当前环境；默认请求上限 15 秒、整次检查上限 180 秒，Agent 可按实际情况调整。健康检查对象参数同样由 Agent 提供。历史包没有此助手时，在私有临时配置中选择目标并通过 `PEOPLESOFT_CONFIG` 仅传给该次子进程，不用反复 `env use` 改全局选择。

健康检查默认使用 `JOB.EMPLID` 等示例对象，新的应用环境可能不存在。先发现实际可用的 Page、Component、Record 和索引字段，再通过 `--page`、`--component`、`--record`、`--query-record`、`--query-field` 等实际支持参数替换；其余参数以该版本 `--help` 为准。

认证成功后检查 HTTP、JSON 业务 code 和实际返回内容。HTTP 200 不等于业务成功。区分路由缺失、180/74 缺类、401/403 权限失败和真实业务错误；保存脱敏原始输出。

中断后先读取本地安装记录并核对实际目标现状，从未完成的阶段继续；不要重建填写文件、重复导入已有角色或盲目重跑 Copy/DDL。某环境失败时继续其他环境独立的准备与验收，不混用结论。登录被明确拒绝时不反复重试同一密码；网络失败先排查连通性，缺权限只提醒授权，业务对象缺失先换成该目标真实存在的验收对象。详见 [常见卡点与续装](references/install-discovery.md#常见卡点与续装)。

完整范围的认证与 20 项读取 PASS 只证明基本读取安装就绪，不证明定义写入或 SQL DML 可用。若单独获准开启 SQL DML，完成审计表/唯一索引后，才额外运行 `healthcheck --refresh --include-sql-write`；其空 SQL 探测也不证明真实 DML 工作流已经验收。

## 7. 验证所需定义写入并清理

当安装目标包含开发能力时，在独立、带唯一名称的验收工程中验证所需代表性写入：读取原始快照 → dry-run 并验证未改变 → 实际保存 → 独立回读 → 原生核验 → 清理。原有对象与业务数据保持不变，夹具不进入 `C_META_DATA_PKG`。

优先选择可完整清理的 Field / XLAT、根包/类和 PeopleCode 编译等路径，按 [Field](references/06-record-defn-api.md)、[应用包](references/03-app-pkg-api.md) 的实际命令执行。创建前也读取不存在名称的版本；写入使用读取时的原始 `expectedVersion`，核对缺版本 428、旧版本 409 及 dry-run 回滚。冲突后不刷新版本自动重试。

不要默认全量重放历史测试：不同对象的删除能力不同，整页删除尚未开放，不应留下无法清理的 Page 夹具。只测试本次授权范围；不能为绕过 403 开放 SQL DML、直接修改元数据表或扩大权限。清理后独立确认对象与工程成员状态，并保存前后差异；无法清理时记录具体对象和恢复办法。

如当前 Agent 有 Postman，API 验证使用其 api-engineer / api-testing 流程，复用已有契约、请求和断言；凭据使用本地安全变量，不上传真实凭据或业务返回。没有该工具时可用 CLI 保存真实接口证据，明确工具与限制；本地模拟不算目标环境验收。

## 8. 交付安装结果

在用户私有数据目录的 `installations/<本次标识>/` 保存 `INSTALLATION.md` 和 `installation-result.json`，记录所选 tag/包 SHA256、确认过的环境标识、各环境当前阶段、下一步、脱敏日志位置、验证结果及清理情况，阶段完成或需要用户处理时更新，便于续装。记录不含密码/Token，不放到公开仓库或运行包中。不要提交环境地址、账号连接信息、认证头或配置文件到公开仓库。

逐项记录状态：

| 项目 | 需要的证据 |
|---|---|
| 本地 Skill | 正确目录、版本、包哈希、CLI help；自动发现是否确认 |
| 服务端导入 | Compare、备份、Copy 日志，冲突/Delete 键处理 |
| 编译与 DDL | 目标原生编译结果、实际执行的必要 SQL；不适用项注明原因 |
| IB 与认证 | 实际节点/路由/Handler 核验及认证结果 |
| 读取 | 20 项结果或有意授权的子集及未开放项 |
| 定义写入 | 授权范围内的实际保存、原生回读、版本保护与回滚证据 |
| 清理与导出 | 夹具清理、前后差异；目标最终工程原生导出及其哈希 |

状态使用 `passed`、`blocked`、`not_requested` 或 `not_run`，附理由，不把未运行标为通过。兼容性另记 `verified` / `unverified` / `failed`，附目标版本和通过/失败的功能；未测不写成 `not supported`。旧版目标完成安装验收可以报告“该环境部署成功、已验证这些功能”，仍保留其余功能未验收的边界。新目标编译/配置后的最终工程另存，不覆盖来源 Release 或历史备份。

仅下载 ZIP、仅导入工程或仅 healthcheck 通过，都不代表“本地与服务端完整安装验收完成”。最终向用户简述已可用的范围、剩余具体阻塞及需要支持的最小事项；无需再次要求用户阅读或复述整份安装指南。
