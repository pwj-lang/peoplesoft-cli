# 菜单与 ItemSelected 代码

读写分离部署：查询使用 `C_META_DATA_READ` 的对应 `AI_READ_*` URI，写入使用 `C_META_DATA_WRITE` 的原 `AI_OPER_*` URI；处理类分别位于 `C_META_DATA_PKG:MetaData:Read`、`:Write`。CLI 在 split 环境自动选择，完整映射及许可权配置见 [安装与读写分离](01-auth-api.md#读写分离2026-10-30)。下文参数/版本契约继续适用；旧混合 URI 的读取示例须改用对应 Read URI。

REST：`AI_OPER_MENU_DEFN.v1/`；Operation：`AI_OPER_MENU_DEFN_POST`；kind=`menu`。通用规则见 [通用规则](12-service-defn-api.md#通用规则)。

支持标准菜单（Menutype=0）和弹出菜单（1）的创建、属性修改、栏/项目增改和排序、精确删除项目。整份菜单删除、改名不开放。菜单不等于 Portal 导航；菜单中的 Component 项也不自动创建 CREF。

弹出菜单是关联到页面或页面字段的局部操作菜单，用户点击弹出按钮后选择项目，触发该项目的 ItemSelected PeopleCode，例如查看说明或执行字段相关动作。它不是创建后自动出现在门户导航中的菜单。PrePopup 可调整项目的显示、勾选或可用状态。AD 能打开菜单、CLI 能回读并编译 ItemSelected 证明定义可维护；要验收实际弹出和点击效果，还需在明确的测试页面/字段中关联菜单并打开该页面。不能把“未关联业务页面”当作菜单创建失败，也不能把结构验收等同于浏览器实际触发。

参见 [Oracle 弹出菜单显示](https://docs.oracle.com/en/applications/peoplesoft/peopletools/8.63/peoplecode-developer-s-guide/pop-menu-display.html)。

属性：`MenuLabel`、`MenuGroup`、`MenuOrder`、`GroupOrder`、`Installed`、`GroupSep`、`MenuSep`、`Descr`、`Descrlong`、`LanguageCd`、`ObjectOwnerId`；`Menuname` 不可改。

菜单栏和项目存于 `Mit`，键为 **BarName + ItemName**；不能只按同名 ItemName 或数组下标修改。行字段：BarName、BarLabel、ItemName、ItemLabel、ItemType、PnlGrpName、Market、ItemNum、AllowedActions、DisplayOnly、SearchRecName、AddSearchRecName、SearchPnlName。**AllowedActions、AddSearchRecName 仅供读取**：PANWX25 / 8.60.10 原生 API 对它们赋值后没有持久保存，CLI 与服务端均拒绝在补丁中写入；需要改变时使用 AD 并独立回读。实测 Component 项为 ItemType=5，Pop-up PeopleCode 项为 9；不应猜其他类型编码。Component/Market 需存在。同一栏改标签应在该栏项目中一致提供 BarLabel，ItemNum 决定排序。现有原生项目必须标记修改状态才能保存，适配器已处理并回读。

```json
{"properties":{"Menutype":1,"MenuLabel":"示例弹出菜单","Installed":true},"collections":{"Mit":[{"BarName":"MAIN","BarLabel":"主菜单","ItemName":"FIRST","ItemLabel":"第一项","ItemType":9,"ItemNum":1}]}}
```

```powershell
python scripts/peoplesoft_api.py menu struct C_MY_POPUP
python scripts/peoplesoft_api.py menu create C_MY_POPUP --file D:\work\menu.json --project MY_PROJECT
python scripts/peoplesoft_api.py menu struct C_MY_POPUP
python scripts/peoplesoft_api.py menu modify C_MY_POPUP --file D:\work\items.json --project MY_PROJECT
python scripts/peoplesoft_api.py menu struct C_MY_POPUP
python scripts/peoplesoft_api.py menu delete-item C_MY_POPUP --bar MAIN --item SECOND --project MY_PROJECT
python scripts/peoplesoft_api.py menu view-code C_MY_POPUP --bar MAIN --item FIRST
python scripts/peoplesoft_api.py menu modify-code C_MY_POPUP --bar MAIN --item FIRST --file <view-code返回的cachePath> --project MY_PROJECT
python scripts/peoplesoft_api.py menu view-code C_MY_POPUP --bar MAIN --item FIRST
python scripts/peoplesoft_api.py menu delete-code C_MY_POPUP --bar MAIN --item FIRST --project MY_PROJECT
```

代码限定 **Pop-up + 已存在的栏/项目 + ItemSelected**；标准菜单不开放该代码事件。修改会编译，保留错误文本和位置；编译失败保留旧程序。成功后独立回读正文比较，忽略编译器格式和注释、保留字符串。view-code 同时缓存 UTF-8 `.pcode`。

空文本不是删除：modify-code 拒绝空代码及仅含空白字符的代码；delete-code 调用原生 DeleteDefn 并检查程序不存在。CLI 删除前保存唯一 UTF-8 备份，输出 snapshotPath；分步失败记录保留备份路径。删除项目也清理所属 ItemSelected 程序；菜单保存和程序清理是分步操作，后一步错误会明确报错，不声称共同回滚。

API operationType 为 exists/view/struct/create/modify/deleteChild/viewCode/modifyCode/deleteCode；代码请求提供 BarName、ItemName、peoplecode（普通 JSON 字符串），写入还必须提供原始 expectedVersion 和 expectedCode。Project：Menu=6，Menu PeopleCode=9，四个值依次菜单/栏/项目/ItemSelected。

## 原始版本与冲突处理（2026-10-29）

Menu 的 `create`、`modify`、`deleteChild`、`modifyCode`、`deleteCode` 全部要求读取时的 `expectedVersion`，包括 dry-run。缺少或空版本返回应用码 **428**；版本过期返回 **409**。`expectedState` 不能代替原始版本。版本控制检测并发覆盖，不提供历史版本库。

`struct` / `view` / `exists` / `viewCode` 返回 `menuVersionControl=1`、`beforeVersion` 和 `version`（`menu1:` 前缀）。不存在的名称也能读取 `exists=false` 的结构快照，创建前必须先读。令牌覆盖菜单定义、栏/项目及排序、多语言、原生删除/来源记录和该菜单的所有 PeopleCode 程序版本；任意项目的代码或结构变化都会使整个菜单的旧快照失效。不存在名称的令牌还包含原生菜单全局版本，其他菜单保存后可能需要重新读取不存在名称。

CLI 的 `menu struct` 自动缓存绑定环境、服务器、节点、账号、对象类型与名称的结构快照，输出 `snapshotPath`。结构写入默认使用这份原始快照，也可传 `--snapshot <原始JSON>`；不会在写入前自动换成最新版本。补丁只接受 `properties` / `collections`，不能注入操作、版本或 dryRun。

代码编辑先 `menu view-code --bar ... --item ...`，编辑返回的 `cachePath`，`modify-code --file` 默认读取文件旁 `.snapshot.json`；另存正文时显式传原始 `--snapshot`。快照另绑定 BarName、ItemName、固定事件 ItemSelected、原始正文和 `programExists`，不能混用其他栏的同名项目、结构快照或其他环境。`delete-code` 默认读取该精确项目最后一次 `view-code` 的原始快照。

成功后独立回读并登记工程；保存后需再次读取，才能开始下一次编辑。dry-run 不保存、不登记。409 时保留改稿与原快照，将最新结构/可读取的目标程序另存为 `conflict_*`；不自动重试。若目标项目已删除，仍保留最新结构并报告目标代码读取失败。保存已成功而后续回读或工程登记失败时，CLI 输出分步恢复记录，不能盲目重写。

菜单和代码使用同一事务中的 PCM、MDM 原生锁完成比较与保存；CLI 的写前回读不能代替服务端检查。`delete-item` 会备份已有目标程序，再精确清理 ItemSelected 并登记父 Menu Copy、原程序 Delete；相邻栏/项目保留。原生菜单保存和代码清理仍须按实际响应核对，工程登记属于后续独立步骤。

需配套部署新版编译后的 `MetaData:OperMenuDefn`、`Utility:MenuCodeAdapter` 和含 `scripts/menu_operations.py` 的 CLI，继续依赖 `Utility:DefinitionVersion`、`NativeAdapter`、`ObjectKeyResolver`。旧客户端无版本写入会被新版服务端拒绝；仅升级客户端或替换 XML 正文不能启用。REST URI、服务操作和权限不变。

[Oracle 的菜单项 PeopleCode 说明](https://docs.oracle.com/cd/E92519_02/pt856pbr3/eng/pt/tpcd/task_AccessingMenuItemPeopleCode-074a15.html)。

2026-10-11 已在测试 Page C_AI_DP1011 的 COUNTRY 字段绑定 C_AI_EXT_POPUP 并实际触发 MAIN/FIRST，NAME 和消息框均显示 POPUP_OK_1011。此验收没有保存业务数据；其他页面仍须按自己的布局和权限核验。
