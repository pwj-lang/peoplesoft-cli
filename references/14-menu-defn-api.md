# 菜单与 ItemSelected 代码

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
python scripts/peoplesoft_api.py menu create C_MY_POPUP --file D:\AI_Workspace\tmp\menu.json --project MY_PROJECT
python scripts/peoplesoft_api.py menu modify C_MY_POPUP --file D:\AI_Workspace\tmp\items.json --project MY_PROJECT
python scripts/peoplesoft_api.py menu delete-item C_MY_POPUP --bar MAIN --item SECOND --project MY_PROJECT
python scripts/peoplesoft_api.py menu view-code C_MY_POPUP --bar MAIN --item FIRST
python scripts/peoplesoft_api.py menu modify-code C_MY_POPUP --bar MAIN --item FIRST --file D:\AI_Workspace\tmp\item.pcode --project MY_PROJECT
python scripts/peoplesoft_api.py menu delete-code C_MY_POPUP --bar MAIN --item FIRST --project MY_PROJECT
```

代码限定 **Pop-up + 已存在的栏/项目 + ItemSelected**；标准菜单不开放该代码事件。修改会编译，保留错误文本和位置；编译失败保留旧程序。成功后独立回读正文比较，忽略编译器格式和注释、保留字符串。view-code 同时缓存 UTF-8 `.pcode`。

空文本不是删除：modify-code 拒绝空代码及仅含空白字符的代码；delete-code 调用原生 DeleteDefn 并检查程序不存在。删除项目也清理所属 ItemSelected 程序；菜单保存和程序清理是分步操作，后一步错误会明确报错，不声称共同回滚。

API operationType 为 exists/view/struct/create/modify/deleteChild/viewCode/modifyCode/deleteCode；代码请求提供 BarName、ItemName、peoplecode（普通 JSON 字符串），可提供 expectedCode。Project：Menu=6，Menu PeopleCode=9，四个值依次菜单/栏/项目/ItemSelected。

[Oracle 的菜单项 PeopleCode 说明](https://docs.oracle.com/cd/E92519_02/pt856pbr3/eng/pt/tpcd/task_AccessingMenuItemPeopleCode-074a15.html)。

2026-10-11 已在测试 Page C_AI_DP1011 的 COUNTRY 字段绑定 C_AI_EXT_POPUP 并实际触发 MAIN/FIRST，NAME 和消息框均显示 POPUP_OK_1011。此验收没有保存业务数据；其他页面仍须按自己的布局和权限核验。
