# Agent 安装与服务端部署入口

用户可以直接把下面这一句交给 Agent：

> 请安装并部署到我的 PeopleSoft 环境：https://github.com/pwj-lang/peoplesoft-cli

Agent 应读取本文件并执行安装，不要求用户复制整份流程。先发现已有配置，只询问缺失信息；环境尚未明确时先完成本地安装和部署准备。**明确要求“只安装本地 Skill”时，到本地验证为止。** 服务端部署须使用用户确认的目标环境，不能从历史环境名、上次 active_project 或偶然打开的浏览器推定目标。

This is the installation entry point for agents. Install the local skill, then deploy and verify the MetaData API in the user-confirmed PeopleSoft environment. Honor local-only requests. Discover existing configuration before asking for missing information; never infer the deployment target from this repository's examples.

## 1. 确定目标与已有状态

先只读检查当前 Agent 的技能目录、Python、已有 ps-cli 版本、PeopleSoft 环境配置，以及可用的 Application Designer 客户端与登录会话。配置位置和环境命令见 [安装与认证参考](references/01-auth-api.md)。保留其他环境及本地独有修改。

将无法发现的信息合并成一次简短询问，只列实际缺项：

- 目标环境及 PIA 地址、Integration Broker 节点/入口。
- 数据库类型、连接名和匹配目标 PeopleTools 的 Windows AD 客户端。
- 部署账号、API 使用账号及安全的本地凭据来源，或需要用户完成的登录。
- API 的用途：元数据读取、定义写入，以及要使用的专用 Permission List。

不要让用户把密码或 Token 发到聊天里。优先使用已有安全配置；需要交互登录时按当前工具的认证规则交给用户。没有 Windows AD 或数据库连接时仍可完成本地安装和导入准备，但如实记录服务端阻塞。

本仓库的流程不额外授予覆盖业务定义、删除共享类或扩大权限的许可。比较发现目标定制冲突或需要新增授权时，先完成具体比较/权限清单，再按用户已有授权处理；超出授权的部分才请求决定。

## 2. 选择发布包并安装本地 Skill

1. 从 [最新稳定版](https://github.com/pwj-lang/peoplesoft-cli/releases/latest) 选择正式 Release，记录 tag、版本、下载地址及校验和。用户指定版本时使用指定版本；不要把 main 分支当成已发行运行包。
2. 下载该 Release 的 `ps-cli-<版本>.zip` 和 `SHA256SUMS.txt`，核对 ZIP 的 SHA256；校验不符时停止使用该包。CLI、参考文档和原生服务端工程应来自同一发布包，整个安装过程固定使用这个版本。
3. 解压到当前 Agent 支持的 skills 目录，使最终入口为 `<skills目录>/ps-cli/SKILL.md`，避免多套一层 `ps-cli/ps-cli/`。Codex 通常使用 `~/.codex/skills`，其他 Agent 按其实际配置；不要为了安装一个 Agent 而写入所有客户端目录。
4. 更新已有安装前备份独有修改，不覆盖 `.peoplesoft` 中其他环境或凭据。核对 `SKILL.md` 中的版本、CLI 可执行性和原生 XML/INI 文件是否齐全。

本安装指南可能比稳定版更新：例如 2.0.1 的历史 ZIP 尚不含本文件和 `AGENTS.md`。可以读取 main 的最新安装指南指导安装，但运行代码、接口参考及工程仍取所选 Release；不要混入 main 的脚本或改写历史 ZIP。

进入实际安装目录后执行：

```powershell
python scripts/peoplesoft_api.py --help
python scripts/peoplesoft_api.py env list
```

部分 Agent 需重开会话才能自动发现新 Skill。当前会话可以直接读取安装后的 `SKILL.md` 并继续部署，分别报告“文件已安装”和“自动发现已确认”。

部署前读取 [SKILL.md](SKILL.md)、[架构与交付边界](references/architecture.md)、[开发规范](references/development-standards.md)、[安装与认证参考](references/01-auth-api.md) 和 [已知问题](references/known-code-issues.md)。需要哪类写入验收，再读取对应对象参考。

## 3. 通过原生 AD 完成首次导入

**尚未安装的 MetaData API 不能用来安装自身。** 已有 API 时可先预检判断版本、路由及缺项；首次部署从随包的 `C_META_DATA_PKG/` 原生 XML/INI 工程开始，通过匹配目标版本的 Application Designer 导入。

以 2.0.1 为例，工程清单为 301 条迁移成员（275 Copy、26 Delete）、295 个原生实例、100 个编译程序及 38 个 Service Operations。这些数量是该版本的核对基线；其他版本以自身清单为准。工程包含实际使用的 `C_JSON_API`、`C_COMMONS_PKG` 依赖；只导入同名应用根包会漏掉运行依赖。

1. 核实目标数据库和 PeopleTools；使用该目标支持的 AD 客户端。主要验证基线是 Oracle / PeopleTools 8.60.10，其他组合需在目标编译和验证，不能沿用来源环境结论。
2. 对目标已有相关定义作原生备份，再执行 Compare From File，保存比较报告。检查自定义差异、共享根包和全部 Delete 键。目标不存在的 Delete 对象可属于正常迁移状态；目标存在且仍被其他业务使用时，不能盲目删除或覆盖。
3. 对已确认范围执行 Copy From File，核对退出码、原生日志中的处理条目、成功标记和错误。命令无输出、进程退出或工程名出现，都不足以证明导入成功。

原生命令模板见 [安装参考](references/01-auth-api.md#安装)，按本机 `pside.exe` 参数核实：

| 操作 | 参数 | 要点 |
|---|---|---|
| Compare From File | `-PJFC C_META_DATA_PKG` | 先比较并检查冲突 |
| Copy From File | `-PJFF C_META_DATA_PKG` | 仅导入已确认范围 |
| Copy To File | `-PJTF C_META_DATA_PKG` | 备份和最终导出 |

`-FP` 指向**包含 `C_META_DATA_PKG/` 的父目录**，不能直接指向 XML 或工程子目录。`-RST 1 -OVW 1` 会重置迁移状态并覆盖目标 Project，仅用于已确认的导入范围。凭据从本地安全来源读取到内存，不写入命令记录、脚本或报告。

## 4. 编译、必要 DDL 与依赖核验

- 在目标版本原生编译整个工程，逐项检查错误及缺类；2.0.1 对应 100 个程序。不能手改 XML 的 TOOLSREL、替换源码后保留旧编译块，或把来源编译成功当作目标成功。
- 根据目标现状，只对缺失或确需调整的 Record 创建/调整表、视图或索引，先检查生成 SQL。不要对整个工程盲目执行 Drop/Create，也不要套用旧版 Build 设置。
- 如需 SQL DML，先检查 `C_AI_SQLAUD` 对应的 `PS_C_AI_SQLAUD` 表及 GUID 唯一索引；已有表保留数据。SQL DML 未获授权时保持关闭，不能为了安装冒烟而默认启用。
- JSON 默认使用 AUTO。`org.json` / JavaApi 是可选后端，不把安装 JAR 或重启 domain 当作默认步骤；目标确有需要时再按 [后端说明](references/01-auth-api.md#json-兼容层2026-10-30) 配置。
- 核验目标已有系统 `MESSAGE_CATALOG1` / `MESSAGE_CATALOG_CI`，并在使用消息维护时核对实际需要的方法权限。不要重新创建已退役的 `C_META_MSG_LANG` 页面、组件或 CI。

若原生编译/保存失败，保留完整错误及目标版本，按实际依赖继续排查。不要伪造导出或通过直接改元数据表绕过原生错误。

## 5. 配置 Integration Broker 与最小必要权限

按目标环境核对 Gateway、Local Node、Service、Operation/版本、URI、Handler、Routing 和 Active 状态。公开包将 38 处环境专属 REST BaseURL 主机替换为 `https://ps.example.invalid`，必须改成目标实际地址，并核对节点和路径；不能照搬占位地址或默认 `PSFT_HR`。

- 元数据读服务：`C_META_DATA_READ`；定义写服务：`C_META_DATA_WRITE`。
- Token 入口：`PSTOKEN.v1` / `PSTOKEN_GET`，Handler 为 `C_COMMONS_PKG:Login:Login`。服务归属以工程和目标原生定义为准，不能假定 Token 操作就在 Read 服务内。
- 在已确认的专用 Permission List 上，仅授权所需操作，并验证 API 账号通过角色/许可权关联实际取得权限。不默认使用 `PTPT1000`，不对所有服务或所有 CI 开放 Full Access。
- 完整基本读取健康检查含认证及 20 个读取操作，其中包括业务 Record 查询和任意 SQL 读取。若用户只授权较小的元数据范围，报告部分安装就绪及缺项，不为凑齐 20 项扩大权限。
- 定义写入按所需对象单独授权。`AI_EXEC_SQL_WRITE_POST` 默认不授权；权限矩阵及消息 CI 权限见 [授权参考](references/01-auth-api.md#授权)。

初始授权不能依赖尚未可用的 `service-op set-permission` 自举。需要安全管理员操作时，给出具体账号、列表、操作及理由；其他安装工作继续推进。

## 6. 配置 CLI 目标环境并验证读取

先查看实际版本的 `env init --help`，避免覆盖同名环境；以下为当前命令形态：

```powershell
python scripts/peoplesoft_api.py env init <环境名> --url <PIA地址> --username <API用户> --node <实际节点> --password-stdin
python scripts/peoplesoft_api.py env use <环境名>
python scripts/peoplesoft_api.py env layout split
python scripts/peoplesoft_api.py env current
python scripts/peoplesoft_api.py auth --refresh
python scripts/peoplesoft_api.py preflight --refresh
python scripts/peoplesoft_api.py healthcheck --help
python scripts/peoplesoft_api.py healthcheck --refresh
```

通过安全输入传递密码，不在命令参数中填密码明文。配置默认在 `%USERPROFILE%/.peoplesoft/config.json`，支持 `PEOPLESOFT_CONFIG`；保留其他 profiles，确认选中的确是本次目标。当前版本使用 split；401/403、部署或网络失败不能触发自动回退 legacy。

健康检查默认使用 `JOB.EMPLID` 等示例对象，新的应用环境可能不存在。先发现实际可用的 Page、Component、Record 和索引字段，再通过 `--page`、`--component`、`--record`、`--query-record`、`--query-field` 等实际支持参数替换；其余参数以该版本 `--help` 为准。

认证成功后检查 HTTP、JSON 业务 code 和实际返回内容。HTTP 200 不等于业务成功。区分路由缺失、180/74 缺类、401/403 权限失败和真实业务错误；保存脱敏原始输出。

完整范围的认证与 20 项读取 PASS 只证明基本读取安装就绪，不证明定义写入或 SQL DML 可用。若单独获准开启 SQL DML，完成审计表/唯一索引后，才额外运行 `healthcheck --refresh --include-sql-write`；其空 SQL 探测也不证明真实 DML 工作流已经验收。

## 7. 验证所需定义写入并清理

当安装目标包含开发能力时，在独立、带唯一名称的验收工程中验证所需代表性写入：读取原始快照 → dry-run 并验证未改变 → 实际保存 → 独立回读 → 原生核验 → 清理。原有对象与业务数据保持不变，夹具不进入 `C_META_DATA_PKG`。

优先选择可完整清理的 Field / XLAT、根包/类和 PeopleCode 编译等路径，按 [Field](references/06-record-defn-api.md)、[应用包](references/03-app-pkg-api.md) 的实际命令执行。创建前也读取不存在名称的版本；写入使用读取时的原始 `expectedVersion`，核对缺版本 428、旧版本 409 及 dry-run 回滚。冲突后不刷新版本自动重试。

不要默认全量重放历史测试：不同对象的删除能力不同，整页删除尚未开放，不应留下无法清理的 Page 夹具。只测试本次授权范围；不能为绕过 403 开放 SQL DML、直接修改元数据表或扩大权限。清理后独立确认对象与工程成员状态，并保存前后差异；无法清理时记录具体对象和恢复办法。

如当前 Agent 有 Postman，API 验证使用其 api-engineer / api-testing 流程，复用已有契约、请求和断言；凭据使用本地安全变量，不上传真实凭据或业务返回。没有该工具时可用 CLI 保存真实接口证据，明确工具与限制；本地模拟不算目标环境验收。

## 8. 交付安装结果

在本次本地安装工作目录保存 `INSTALLATION.md` 和 `installation-result.json`，记录所选 tag/包 SHA256、确认过的环境标识、实际步骤、脱敏命令/日志位置、验证结果及清理情况。不要提交环境地址、账号连接信息、密码、Token、认证头或配置文件到公开仓库。

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

状态使用 `passed`、`blocked`、`not_requested` 或 `not_run`，附理由，不把未运行标为通过。新目标编译/配置后的最终工程另存，不覆盖来源 Release 或历史备份。

仅下载 ZIP、仅导入工程或仅 healthcheck 通过，都不代表“本地与服务端完整安装验收完成”。最终向用户简述已可用的范围、剩余具体阻塞及需要支持的最小事项；无需再次要求用户阅读或复述整份安装指南。
