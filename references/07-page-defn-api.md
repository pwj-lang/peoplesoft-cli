# Page、Component 与页面结构

读写分离部署：查询使用 `C_META_DATA_READ` 的对应 `AI_READ_*` URI，写入使用 `C_META_DATA_WRITE` 的原 `AI_OPER_*` URI；处理类分别位于 `C_META_DATA_PKG:MetaData:Read`、`:Write`。CLI 在 split 环境自动选择，完整映射及许可权配置见 [安装与读写分离](01-auth-api.md#读写分离2026-10-30)。下文参数/版本契约继续适用；旧混合 URI 的读取示例须改用对应 Read URI。

## 2.0.0-dev.6：Page 原始快照与第7批属性（2026-10-27）

所有 Page 写入都必须使用读取时的 `expectedVersion`，包括新建、页面属性、控件新增/修改/删除及 Activate 修改/删除。`struct` 返回 `exists`、`version`、`pageVersion`；`pageVersionControl=1` 表示并发保护。不存在名称也先读结构再创建。令牌覆盖16个Page表和Activate存在性/正文；写入在PCM/PDM和已有页面行锁内比较，缺版本返回应用码428、冲突409。原生PDM缓存与Page VERSION同步维护。版本保护针对数据库已保存状态，不读取或保存AD内存草稿，也不提供历史回滚。

CLI `page struct` 自动保存绑定环境、服务器、节点、账号及页面名的原始快照，也可 `--output` 另存并在写入时指定 `--snapshot`。写前读取当前状态只核对，不自动替换原始令牌；冲突下载到新文件，保留原稿与原快照。写后独立回读，成功登记工程；回读/登记失败明确报告已提交状态。

本批新增12个属性，要求 `controlPropertyVersion>=7`；其余已验证能力保留。仅支持已研究的Edit/DDL属性，未知请求拒绝，未指定的未知位保留。其他控件可读取原始元数据，未验证的开关语义不输出；新增/修改/删除控件只开放Edit/DDL，新增只支持level0，`editSize`写入及层级调整暂不开放。

| API属性 / CLI参数 | 已验证范围与存储 |
|---|---|
| showLabel / --show-label | Edit/DDL，最终Invisible=1；FIELDUSE1024 |
| enableWhenPageDisplayOnly / --enable-when-page-display-only | Edit；FIELDUSE262144 |
| wrapLongWords / --wrap-long-words | DDL，启用须Text Only；FIELDUSETMP64；Disabled自动清除 |
| modifiableByJavaScript / --modifiable-by-javascript | DDL，最终Invisible=1；SECUREINVISIBLE反向 |
| generateHtml / --generate-html | DDL，最终Invisible=1；EXT.FIELDUSETEMP2位32 |
| popupMenu / --popup-menu | DDL；POPUPMENU，空字符串清除，非空须已有Popup菜单 |
| autoDecimal / --auto-decimal | 数字Edit（PSDBFIELD.FIELDTYPE=2）；DSPLFORMAT1024 |
| currencySymbol / --currency-symbol | 同上；DSPLFORMAT16 |
| thousandsSeparator / --thousands-separator | 同上；DSPLFORMAT32 |
| displayZero / --display-zero | 字符/数字Edit（类型0/2）；DSPLFORMAT128 |
| showCentury / --show-century | 日期Edit（类型4）；DSPLFORMAT65536 |
| showTimeZone / --show-time-zone | 日期Edit（类型4）；DSPLFORMAT536870912，仅验证持久化属性 |

除popupMenu外均为数字0/1。其他控件、数值字段类型及条件未取得证据，暂不扩展。Page Field Name依AD输入样例收紧为18字符；这不是数据库列上限结论。DDL清除Invisible同时清SECUREINVISIBLE；未主动清其他未指定位。数值解码避免PeopleCode Mod的2^32整数转换，并保留高位。

```powershell
python scripts/peoplesoft_api.py page struct MY_PAGE --full --json --output ./page-before.json
python scripts/peoplesoft_api.py page mod-control MY_PAGE --snapshot ./page-before.json --pnl-fld-id 1 --auto-decimal 1 --currency-symbol 1 --project MY_PROJECT
# 成功后显式重读，或使用CLI更新的默认缓存；原始page-before.json保持不变。
python scripts/peoplesoft_api.py page view-code MY_PAGE
# 编辑输出的Cached文件；旁边.snapshot.json保存原始版本。
python scripts/peoplesoft_api.py page modify-code MY_PAGE --file <Cached文件> --project MY_PROJECT
python scripts/peoplesoft_api.py page delete-code MY_PAGE --snapshot <view-code输出的Snapshot文件> --project MY_PROJECT --dry-run
```

直接API同样必须带 `"expectedVersion":"<原struct/viewPeopleCode返回的version>"`；下文早期请求示例需补该字段才能写入。旧客户端无法绕过服务端保护。PANWX25/8.60.10已通过65项接口/并发检查、14项原始AD差异的16表对照、CLI结构/代码流程及Postman17请求19断言。本批没有新增GUI/PIA验收，不把数据库对照当成完整设计器或运行验收。以后每批10–20属性，先证据、再实现和独立验证，未确认属性不纳入支持范围。

公共认证与响应见 [安装说明](01-auth-api.md#公共调用规则)。

通过 Integration Broker REST 接口查询、创建和修改 Page 定义及其控件。

## 接口地址

```
POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/PSFT_HR/AI_OPER_PAGE_DEFN.v1/
```

## Service Operation

`AI_OPER_PAGE_DEFN_POST` — 需要在 PIA 中给用户授予 Execute 权限。

## operationType 一览

| operationType | 功能 | 关键参数 |
|---|---|---|
| `struct` | 查询 Page 结构；`full=1` 时返回全量列 | `pageName`；`full` |
| `createPage` | 新建 Page | `descr` / `comment` / `pnlType` |
| `modifyPageProps` | 修改页面属性 | `descr` / `comment` / `pnlType` / `deferProc` / `panelRight` / `panelBottom` |
| `addControl` | 新增控件 | `controlType`、记录字段、标签、坐标和位标志 |
| `deleteControl` | 删除控件 | `pnlFldId` |
| `findControls` | 检索控件 | `recName` / `fieldName` / `labelContains` / `fieldType` |
| `modifyControl` | 修改控件属性 | `pnlFldId` 和白名单属性 |
| `viewPeopleCode` / `modifyPeopleCode` | 读取/修改 Activate；修改拒绝空白正文 | `pageName`；修改加 `peoplecode` |
| `deletePeopleCode` | 真正删除 Activate 程序，保留 Page | `pageName`、`expectedCode`；可选 `dryRun` |

## 请求体参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `pageName` | string | **是** | Page 名称 |
| `operationType` | string | 否 | 默认 `"struct"` |

## 响应结构 (operationType=struct)

```json
{
  "pnlName": "JOB_DATA1",
  "controlPropertyVersion": 7,
  "pageVersionControl": 1,
  "version": "p1:...",
  "descr": "Job Data",
  "descrLong": "...",
  "pnlType": "standard",
  "pnlUse": 12345,
  "fieldCount": 89,
  "lastUpdate": "Last updated by: ...",
  "fields": [
    {
      "pnlFldId": 1,
      "recName": "DERIVED_HR",
      "fieldName": "",
      "fieldType": "scrollArea",
      "invisible": 0,
      "displayOnly": 0,
      "displayControl": 0,
      "multiCurrency": 0,
      "relatedField": 0,
      "relatedDisplay": 0,
      "occursLevel": 0,
      "labelText": "",
      "labelType": 0,
      "labelLoc": 0,
      "fieldLeft": 0,
      "fieldTop": 0,
      "fieldRight": 0,
      "fieldBottom": 0,
      "editSize": 0
    }
  ]
}
```

## 涉及的 PeopleTools 表

### PSPNLDEFN — Page 定义
- PNLNAME (KEY), DESCR, DESCRLONG, PNLTYPE, PNLUSE, FIELDCOUNT
- PNLSTYLE, STYLESHEETNAME, FFSTYLESHEETNAME, FFSTYLE* 系列

### PSPNLFIELD — Page 控件 (98 字段)
核心字段用于 GetPageStruct:
- PNLFLDID, RECNAME, FIELDNAME — 绑定
- FIELDTYPE — 控件类型码
- FIELDUSE — 用途位掩码
- OCCURSLEVEL — Scroll 层级
- LBLTEXT, LBLTYPE, LBLLOC — 标签
- FIELDLEFT/TOP/RIGHT/BOTTOM — 坐标
- EDITSIZE — 编辑尺寸

### PSPNLFIELDEXT — 控件扩展 (31 字段)
`full=1` 时按 PNLNAME/PNLFLDID 使用单个 Record 的 SelectByKey 读取扩展属性到 `fields[].ext`，不存在时为 {}。普通 struct 也读取扩展以解码属性，但不返回原始 ext；避免批量 Rowset 访问的网关错误。

### PSPNLGROUP — Component-Page 映射 (8 字段)
PNLGRPNAME 在此表中，不在 PSPNLDEFN。

### PSPNLGRPDEFN — Component 定义 (43 字段)

## FIELDUSE 位掩码（已验证常用位）

| 位 | 值 | 属性 |
|----|-----|------|
| 0 | 1 | displayOnly（AD Display Only） |
| 1 | 2 | invisible |
| 3 | 8 | displayControl（AD Display Control Field） |
| 4 | 16 | relatedField；relatedDisplay 为兼容同义字段 |
| 5 | 32 | multiCurrency |

以上按 PANWX25 / PeopleTools 8.60.10 的 AD 单变量保存差异核验。旧版把值1误作 Required、值4误作 Display Only、值8误作 Key；现已纠正。`struct` 省略原 `required` / `key` 两键，保留 `fieldUse` 原始位掩码。调用方使用 `controlPropertyVersion >= 1` 判断本批能力；不得把 Page 标志解释为 Record 字段的 Required/Key 约束。`addControl` / `modifyControl` 传 `required`（包括0）返回应用 code=400。

## 注意事项

- 调用前需授予 `AI_OPER_PAGE_DEFN_POST` 的 Execute 权限
- PNLGRPNAME 在 PSPNLGROUP 表，不在 PSPNLDEFN（Component 层概念）
- PNLUSE 是 number(5) 大位掩码，PNLTYPE 是 number(1) 只存类型码
- PNLLBLTEXTSRC / PNLCLASS 不是 PSPNLDEFN 的字段

## 写操作

`createPage`、`modifyPageProps`、`addControl`、`deleteControl`、`findControls`、`modifyControl` 与 `struct` 共用同一个 Service Operation 和 Handler，无需另行发布接口。

### addControl 参数

```json
{
  "pageName": "C_AI_PJT_P1",
  "operationType": "addControl",
  "controlType": "editBox",
  "recName": "ABBR_TYPE_TBL",
  "fieldName": "DESCR",
  "labelId": "",
  "labelText": "",
  "left": 140,
  "top": 50,
  "right": 0,
  "bottom": 0,
  "occursLevel": 0,
  "invisible": 0,
  "displayOnly": 0,
  "onValue": "Y",
  "offValue": "N"
}
```

| controlType | FIELDTYPE | 说明 |
|---|---:|---|
| `editBox` | 4 | 需已有recName + fieldName，level0 |
| `dropDown` | 5 | 需已有recName + fieldName，level0；默认Xlat Short |

旧的其他类型新增分支现由白名单拒绝；类型码仍用于只读结构识别。

> `11=subPage`、`27=scrollArea`、`25=htmlArea`、`13=hyperlink`、`19=grid`。`findControls.fieldType` 传 PeopleTools 数值码，不要传解码后的字符串。

新增控件的 FIELDNUM 按页面现有控件次序追加，包含 scroll 等容器；它不是 Record 内字段序号。绑定字段仍先核实 Record/Field 存在，再设置页面顺序，避免 L0/L1 控件被错误分组。

grid 列定义和 tab 子页关联不应盲写；执行这类写入前先用 AD 手工操作前后的结构快照做 golden diff。

新增 Edit/DDL 已补原生 EXT 基础行（含父级/Page `$0` 引用和 FFSTYLELONG）、字符型0标志及自动标签边界0；DDL 不沿用 Edit 的 DSPLFORMAT=2097160。能力3在省略或同时传空labelId/labelText时按PSDBFLDLABL.DEFAULT_LABEL=1解析基准默认LABEL_ID和LONGNAME；默认ID可能与字段名不同。PANWX25当前基准语言和用户语言均ZHS，已对照DESCR、EFF_STATUS、ADDRESS_TYPE三例；显式新增标签、多语言/Context及完整布局仍待补齐。类型分支清单不表示全部属性和子Item已支持。

### modifyControl

能力5补充DDL的`displayedText`（CLI `--displayed-text xlatShort|xlatLong|prompt`）和`promptField`（`--prompt-field FIELDNAME`），当前用于修改已有DDL；新增后可立即调用modify设置。struct增加displayedText、promptField和按Record字段派生的promptTable。

模式只调整DSPLFORMAT的131072/262144两位，保留标签对齐、First occurs only及其他格式位。切换到任一Xlat模式会清空PROMPTFIELD；切换Prompt时，有实际提示表而原字段为空须显式给promptField，避免猜测AD自动选择规则。promptField须属于派生提示表的List Box Item；当前候选筛选与ADDRESS_TYP_TBL的AD两项选择一致，其他绑定、字段类型和动态提示表条件继续补测。没有提示表的EFF_STATUS可保留空字段Prompt状态，已见AD24；这不代表该状态提供有效运行时列表。

有提示表的ADDRESS_TYPE被CLI按旧默认Xlat Short新增、缺PROMPTFIELD时，AD保存会报15,84；在CLI设置有效Prompt模式/字段后再进行原生验收。显示模式与提示字段只限DDL，未知枚举、非DDL、Xlat+显式PromptField、空必需字段或表外字段原子拒绝；完整新增默认选择、自动初始化及绑定变更仍待补齐。

允许修改的属性：

既有属性：`left` / `top` / `right` / `bottom` / `labelText` / `labelId` / `labelType` / `labelLoc` / `fieldStyle` / `labelStyle` / `deferProc` / `invisible` / `displayOnly`。

本批新增属性仅限 Edit Box / Drop-Down List Box（类型4/5），省略保持原值：

| API 属性 | CLI 参数 | 值及存储规则 |
|---|---|---|
| `displayControl` | `--display-control` | 数字0/1；FIELDUSE值8 |
| `multiCurrency` | `--multi-currency` | 数字0/1；FIELDUSE值32 |
| `setComponentChanged` | `--set-component-changed` | 数字0/1；FIELDUSETMP值8反向设置 |
| `displayOnlyAppearance` | `--display-only-appearance` | `textOnly` / `disabled`；FIELDUSETMP值4 |
| `readOnlyScreenReader` | `--read-only-screen-reader` | 数字0/1；EXT.FIELDUSETEMP2值65536 |
| `pageFieldName` | `--page-field-name` | 最长18字符；非空须全页唯一，空字符串清除 |
| `enableAsAnchor` | `--enable-as-anchor` | 数字0/1；ENABLEASANCHOR，启用须最终名称非空 |

名称唯一性及 Anchor 非空规则是本接口的输入保护，尚未完成 AD 所有边界组合实验。`displayOnly` 现在写 FIELDUSE值1；`invisible` 从可见启用时另设 SECUREINVISIBLE=1，关闭只清值2。更复杂的 JavaScript、Generate in HTML 组合继续验证。

`struct.fields[]` 返回上述属性及 `fieldUse`。控件新增/修改拒绝未知参数、非法二值参数、空修改及不适用属性；失败回滚，不默默忽略参数。新增七项在 `addControl` 中不适用，须新增后修改。修改不支持重新绑定 Record/Field，也不把坐标单列赋值视为已完成 AD 的标签/Custom 边界联动移动。

### Edit Box 的 Record 属性（能力2）

以下七项仅限 `modifyControl` 的 Edit Box（类型4）；DDL、Long Edit等类型未扩展。省略保持，二值使用数字0/1。`struct` 对Edit返回同名属性。

| API属性 | CLI参数 | 值及原生存储 |
|---|---|---|
| `alignment` | `--alignment` | `auto` / `left` / `right`；DSPLFORMAT值8/1/4互斥，保留其他位；未知组合读取为unknown |
| `fillCharacter` | `--fill-character` | 空或一个字符；DSPLFILL，显式空字符串清除 |
| `password` | `--password` | 0/1；DSPLFORMAT值32768 |
| `inputOnly` | `--input-only` | 0/1；EXT.FIELDUSETEMP2值512；显式开启须最终password=1 |
| `showPromptButton` | `--show-prompt-button` | 0/1；Spell Check关闭时DSPLFORMAT值8388608反向设置 |
| `autoFill` | `--auto-fill` | 0/1；DSPLFORMAT值512 |
| `spellCheck` | `--spell-check` | 0/1；FIELDUSETMP值2，和Prompt存在下述联动 |

Spell Check开启后，AD清除并禁用Prompt选项，保存时清DSPLFORMAT8388608；读取showPromptButton=0。关闭原来开启的Spell Check时，Prompt恢复可用但未勾，设置8388608；同次显式showPromptButton按最终有效请求处理。spellCheck=1和showPromptButton=1冲突拒绝。Password关闭时保留之前的Input Only扩展位（AD仍显示勾选但禁用），省略inputOnly不会自动清除；显式inputOnly=1要求最终Password开启。

本批按AD快照11/12、48–60验证，14项CLI列差异重放通过，另覆盖Basic/Record属性组合时共享FIELDUSETMP与EXT位保留；8项API及2项CLI拒绝通过。客户端发送本批键前要求controlPropertyVersion>=2，旧键仍仅需>=1；不能把二者条件语义简化为独立的位开关。日期/数字专属显示、尺寸和完整标签/布局仍待后续。

验收标准：修改 1 个控件后，`struct` 快照 diff 应只有目标控件的预期列变化。

### Edit Box / Drop-Down List Box 的 Label 联动（能力3/4）

新增Edit/DDL的基准默认标签解析要求能力3。以下修改语义已分别在Edit Box（类型4）和Drop-Down List Box（类型5）进行单变量AD实验；Edit修改要求能力3，DDL修改要求能力4。DDL的标签位置、样式、换行和条件属性仍需继续验证，不能据此宣称某个Item已完整支持。

| API属性 | CLI参数 | 值及行为 |
|---|---|---|
| `noColon` | `--no-colon` | 0/1，LBLLOC值1；保留其他位，不能与raw labelLoc同传 |
| `firstOccursOnly` | `--first-occurs-only` | 0/1，DSPLFORMAT值4194304 |
| `labelAlignment` | `--label-alignment` | left/center/right，DSPLFORMAT值524288/1048576/2097152互斥；与Record alignment分开 |
| `useDefaultLabel` | `--use-default-label` | 0/1；RFT模式选择默认或已存显式ID，默认ID及文字重新解析 |
| 既有`labelType` | `--label-type` | 0=None、1=Text、2=RFT Short、3=RFT Long；RFT重取对应短/长文字，None/Text保留标签源和文字 |
| 既有`labelId` | `--label-id` | RFT模式选择已有显式ID，USEDEFAULTLABEL=0，并读取对应文字；不能与useDefaultLabel=1冲突 |
| 既有`labelText` | `--label-text` | None/Text模式修改文字，保留ID和默认标志；离开RFT须同传labelType=1 |

旧实现传labelId强制USEDEFAULTLABEL=1、传labelText强制置0，均不符合AD，能力3修正Edit路径，能力4根据DDL自身证据修正DDL路径。不存在的标签、未知类型/对齐、非法二值及冲突组合返回400，整次修改不写入。Record/Label组合更新后重新读取共享列，保留其他DSPLFORMAT位。

CLI按目标Item检查上述能力，拒绝在旧服务上沿用不等价标签语义。Edit已完成11项AD列差异重放、三个默认标签对照及Record/Label共享位组合。DDL新增12项独立AD单变量证据（75–86），覆盖No colon、First occurs only、三种对齐、None/Text/RFT切换、显式ID及恢复默认；长短文字从实际标签源读取，保留Xlat/Prompt显示模式位。新增Edit/DDL的98列除Page名与AD首次新增基线一致；完整Page头、尺寸、标签位置/独立移动、Style/换行/Context/Fluid及最终使用验收仍继续。

```powershell
python scripts/peoplesoft_api.py page mod-control MY_PAGE --pnl-fld-id 1 --label-type 1 --label-text "说明" --project MY_PROJECT
python scripts/peoplesoft_api.py page mod-control MY_PAGE --pnl-fld-id 1 --label-type 3 --label-id AAP --project MY_PROJECT
python scripts/peoplesoft_api.py page mod-control MY_PAGE --pnl-fld-id 1 --use-default-label 1 --no-colon 0 --label-alignment center --project MY_PROJECT
```

### 显式标签矩形、尺寸模式与 Custom 整体平移（能力6）

以下新增参数只适用于 `modifyControl` 的 Edit/DDL。`struct` 同时返回 `labelPosition`、`labelLeft/Top/Right/Bottom` 和 `sizeType`；未知模式读取为 `unknown`。

| API / CLI | 语义 |
|---|---|
| `labelPosition` / `--label-position` | left/custom/top，对应LABELSIZETYPE0/1/2。改变模式时必须同传完整标签矩形，明确保存AD产生的缓存边界 |
| `labelLeft/Top/Right/Bottom` / `--label-left/top/right/bottom` | 必须四项一起提供；独立修改要求Custom标签位置。自动位置的缓存可为零尺寸，Custom须正宽高；整数0至32767 |
| `sizeType` / `--size-type` | average/maximum/custom，对应FIELDSIZETYPE0/1/2，和旧EDITSIZE参数不同。改变模式须同传left/top/right/bottom，Custom须正宽高 |
| `moveX` / `--move-x`、`moveY` / `--move-y` | 坐标增量，要求现有主控件尺寸和标签位置均Custom；FIELD及EDITLBL四边界等量平移，保持宽高 |

`moveX/moveY` 不能和原始主控件坐标、尺寸模式、标签位置或标签矩形混合。两轴可一起提供，允许显式0；结果边界必须在0至32767。原 `left/top/right/bottom` 仍只修改对应列，不能把单独修改left理解成整个控件平移。

显式矩形用于精确重放AD结果；Left/Top的字体测量、切Custom时的缓存推导和箭头首次触发的网格吸附尚未自动实现。已观察到Edit标签Right时top50吸附48，后续Right不再改纵坐标，因此整体平移明确不模拟UI网格吸附。尺寸切换的自动宽高计算仍待补齐。

```powershell
python scripts/peoplesoft_api.py page mod-control MY_PAGE --pnl-fld-id 1 --size-type custom --left 132 --top 68 --right 472 --bottom 83 --project MY_PROJECT
python scripts/peoplesoft_api.py page mod-control MY_PAGE --pnl-fld-id 1 --label-position custom --label-left 140 --label-top 52 --label-right 170 --label-bottom 64 --project MY_PROJECT
python scripts/peoplesoft_api.py page mod-control MY_PAGE --pnl-fld-id 1 --move-x 8 --move-y 4 --project MY_PROJECT
```

### 控件维护约束

- `PNLFLDID` 使用 `MAXPNLFLDID + 1`，不复用删除后产生的空洞。
- 写入后维护 `PSPNLDEFN.FIELDCOUNT`、`MAXPNLFLDID`、`VERSION`，并更新 `PSVERSION` 中的 `PSPNLDEFN` 版本。
- `deleteControl` 同步清理 `PSPNLFIELDEXT`、`PSPNLHTMLAREA` 和 `PSPNLCNTRLDATA`。
- 嵌套 JSON 必须使用 `AddJsonObject`；PeopleCode 空值判断不能把值类型和对象类型混用。

## CLI

```bash
python scripts/peoplesoft_api.py page struct <page> [--full] [--json]
python scripts/peoplesoft_api.py page create <page> --descr "..." [--comment ...]
python scripts/peoplesoft_api.py page modify-props <page> --descr "..."
python scripts/peoplesoft_api.py page add-control <page> --control-type editBox --rec R --field F --left 140 --top 50
python scripts/peoplesoft_api.py page mod-control <page> --pnl-fld-id 4 --label-text "新标签" --left 160
python scripts/peoplesoft_api.py page mod-control <page> --pnl-fld-id 4 --display-only 1 --display-control 1 --project <project>
python scripts/peoplesoft_api.py page mod-control <page> --pnl-fld-id 4 --set-component-changed 0 --display-only-appearance disabled --read-only-screen-reader 1 --project <project>
python scripts/peoplesoft_api.py page mod-control <page> --pnl-fld-id 4 --alignment right --fill-character X --auto-fill 1 --project <project>
python scripts/peoplesoft_api.py page mod-control <page> --pnl-fld-id 4 --password 1 --input-only 1 --spell-check 1 --project <project>
python scripts/peoplesoft_api.py page find <page> --field EFF_STATUS
python scripts/peoplesoft_api.py page del-control <page> --pnl-fld-id 7
```

新建 Page 后执行 `project insert-item --object-type 5`。修改已有页面前，先用 `page struct --full --json` 保存基线。

`add-control` / `mod-control` 要求明确的 `--project` 或已确认的当前工程：先读服务器能力，写后独立回读目标值、保留的标志位和其他控件，再登记 Page 类型5的 Copy/on/off。回读或工程登记失败会明确报告写入已提交，先检查实际状态，不重发写请求。控件操作暂不支持 `--dry-run`，传入会在写入前拒绝。

本批通过12项 CLI 与 AD 原始快照列差异重放、9项直接接口拒绝和3项 CLI 拒绝验证；新增 DDL 的 EXT 31列归一化 Page 名后与原生基线一致。Page expectedVersion保护已在dev.6实现，规则以本页顶部为准。未验证的Item和属性暂不支持，后续按10–20属性分批研究；本批没有新增AD/PIA使用验收。

## PeopleCode 状态

struct 的 hasPeopleCode 只描述正文是否非空，不能证明原生程序不存在。viewPeopleCode 的 programExists 检查原生程序；modify-code 拒绝空白正文并自动独立回读，编译失败或回读不一致报错。空 Page 的字段列表和 fieldCount 都为 0。

page delete-code 真正删除 Activate，保留 Page/控件；删除后原生不存在，并按完整键登记 Project Delete 标记。C_AI_PF1010 关闭重开 AD 后 Activate 恢复普通字重。流程见 [真正删除](development-standards.md#peoplecode-真正删除)。

## Component 接口

### Component 属性与原始快照（PANWX25 / PeopleTools 8.60.10）

`component struct` 保存绑定环境、服务器、用户、Component 和 Market 的原始快照；`view-code` 保存带程序键的代码快照。修改属性、修改或删除程序必须使用相应原始 `expectedVersion`。缺少版本返回 428，过期返回 409；CLI 保留原稿与原快照，另存最新结构且不自动重试。服务端在 PCM、PGM 锁内检查快照，版本包括 Component 表、页面关联、翻译及脚本行与该 Market 的 Component PeopleCode 原生版本。它不读取 AD 内存草稿，也不提供历史回滚。旧客户端写入会被新版处理类拒绝；须同时部署新版 CLI 和服务端工程。

`modify-props` 是局部修改，未指定的属性保留。支持 Description (`--descr`)、Comments (`--comment`)、Search record (`--search-record`)、Add search record (`--add-search-record`)，以及 `--allow-add`、`--allow-update`、`--allow-update-all`、`--allow-correction`（各 0/1）。`--page-name` 精确定位既有 Page，可同时设置 `--hidden`、`--item-label` 和 `--folder-tab-label`。Description 和 Item Label 最长 30 字符，Folder Tab Label 最长 18 字符；非空搜索记录必须存在。

Add search record 传空字符串表示使用 Search record；如果原先两者相同，单独修改 Search record 会同步 Add search record。动作开关同步对应工具栏位；关闭 Add 后若当前主操作为 New，则切为 Search；全部搜索动作关闭后切为 New。仍有 Update/Display All 或 Correction 时，不因关闭 Update/Display 而切走 Search。四种动作不得全部关闭。写入成功后独立回读，并将 Component/Market 以类型 7 重新登记工程；代码写入和删除分别使用服务端返回的完整程序键登记 Copy 或 Delete。旧的直接接口 `modifyComponent` 仍保留原有原始字段语义；本次动作联动和校验属于 `modifyComponentProps`。

#### Internet 属性 1～4（2026-10-28）

本批支持下表七个语义属性。须同时部署新版 CLI 与服务端；`struct` 返回 `componentInternetPropertyVersion>=1` 才可使用新参数。所有写入继续使用原始 `expectedVersion`，缺失 428、过期 409；未知属性、非法枚举和矛盾组合返回 400 且不修改定义。

| AD 属性 | CLI 参数 | API 字段与数值 |
|---|---|---|
| Primary Action | `--primary-action new/search/keyword-search` | `primaryAction` = 0/1/2 |
| Default Search Action | `--default-search-action update-display/update-display-all/correction` | `dfltAction` = 1/2/3 |
| Default Search/Lookup Type | `--default-search-type basic/advanced/keyword-only` | `dfltSrchType` = 0/1/2 |
| Display Folder Tabs (top) | `--display-folder-tabs 0/1` | `displayFolderTabs`；PNLNAVFLAGS 位 1 |
| Display Hyperlinks (bottom) | `--display-hyperlinks 0/1` | `displayHyperlinks`；PNLNAVFLAGS 位 2 |
| Page Navigation in History | `--page-navigation-in-history 0/1` | `pageNavigationInHistory`；TBARBTNS 位 67108864 |
| Return to Last Page in History | `--return-to-last-page-in-history 0/1` | `returnToLastPageInHistory`；TBARBTNS 位 536870912 |

主操作 New 需要 Add；Search/Keyword Search 需要至少一种已启用的搜索动作。Default Search Action 只允许选择已启用的 Update/Display、Update/Display All 或 Correction，Add 不属于默认搜索动作。关闭当前默认动作且仍有搜索动作时，按 Update/Display、Update/Display All、Correction 顺序选择首个可用项；动作修改导致仅剩 Add 时，按进入 Internet 页后的 AD 行为将 `dfltAction` 设为 **10（禁用空白）**。10 仅作为回读状态，不能显式选择。历史只在 Use 页直接保存的样本可能保留旧默认值；本批统一采用 Internet 页完成编辑后的状态。

一次请求先合并四种 Actions，再应用显式主操作和默认动作。显式选择 Keyword Search 且省略搜索类型时，自动设置 Keyword Only；切换至 New/Search 时若原类型为 Keyword Only，则回退 Basic。显式搜索类型在主操作之后应用，所以 Keyword Search 可以搭配 Basic/Advanced；Keyword Only 必须搭配 Keyword Search。未请求主操作时，仅修改 Basic/Advanced 不会切换主操作。

开启 Page Navigation in History 会联动 Return=1；关闭 History 保留 Return 原值。History 最终开启时显式指定 Return=0 将原子拒绝；需要同时关闭时传两个 0。仅修改所需位，保留 TBARBTNS、PNLNAVFLAGS 的其他位。`struct` 增加 `dfltSrchType`、`pnlNavFlags`、`tbarBtns` 以及四个数字 0/1 导航开关，原有数字字段保持兼容。Toolbar 与 Pagebar 在下面的能力版本 2 中补齐。

```powershell
python scripts/peoplesoft_api.py component struct MY_COMPONENT --market GBL --json --output ./component-before.json
python scripts/peoplesoft_api.py component modify-props MY_COMPONENT --market GBL --snapshot ./component-before.json --primary-action keyword-search --default-search-type advanced --default-search-action update-display --display-folder-tabs 1 --display-hyperlinks 0 --page-navigation-in-history 1 --project MY_PROJECT
```

#### Toolbar 与 Pagebar（2026-10-29，属性 5～6）

须服务端 `componentInternetPropertyVersion>=2`；版本 1 仍支持前述 1～4 项。新增参数均为数字 `0/1`，1 表示界面勾选。沿用 `modify-props`、原始结构快照和工程登记；未知字段、非法范围及动作按钮矛盾请求原子拒绝。

| AD Toolbar 属性 | CLI 参数 | API 字段 | TBARBTNS 位 |
|---|---|---|---|
| Save | `--toolbar-save 0/1` | `toolbarSave` | 1 |
| Cancel | `--toolbar-cancel 0/1` | `toolbarCancel` | 65536 |
| Spell Check | `--toolbar-spell-check 0/1` | `toolbarSpellCheck` | 131072 |
| Return to List | `--toolbar-return-to-list 0/1` | `toolbarReturnToList` | 2 |
| Next in List | `--toolbar-next-in-list 0/1` | `toolbarNextInList` | 256 |
| Previous in List | `--toolbar-previous-in-list 0/1` | `toolbarPreviousInList` | 512 |
| Next Page in Component | `--toolbar-next-page 0/1` | `toolbarNextPage` | 4 |
| Previous Page in Component | `--toolbar-previous-page 0/1` | `toolbarPreviousPage` | 8 |
| Hide Back Button | `--toolbar-hide-back-button 0/1` | `toolbarHideBackButton` | 268435456 |
| Refresh | `--toolbar-refresh 0/1` | `toolbarRefresh` | 2048 |
| Notify | `--toolbar-notify 0/1` | `toolbarNotify` | 32768 |
| View WorkList | `--toolbar-view-worklist 0/1` | `toolbarViewWorklist` | 4096 |
| Next in WorkList | `--toolbar-next-in-worklist 0/1` | `toolbarNextInWorklist` | 8192 |
| Previous in WorkList | `--toolbar-previous-in-worklist 0/1` | `toolbarPreviousInWorklist` | 16384 |
| Add | `--toolbar-add 0/1` | `toolbarAdd` | 16 |
| Update/Display | `--toolbar-update-display 0/1` | `toolbarUpdateDisplay` | 32 |
| Update/Display All | `--toolbar-update-display-all 0/1` | `toolbarUpdateDisplayAll` | 64 |
| Correction | `--toolbar-correction 0/1` | `toolbarCorrection` | 128 |

| AD 属性 | CLI 参数 | API 字段 | SHOWTBAR 存储 |
|---|---|---|---|
| Disable Toolbar | `--disable-toolbar 0/1` | `disableToolbar` | 位 1 反向：勾选清零 |
| Disable Pagebar | `--disable-pagebar 0/1` | `disablePagebar` | 位 2：勾选置位 |
| Help Link | `--pagebar-help-link 0/1` | `pagebarHelpLink` | 位 4 反向 |
| Copy URL Link | `--pagebar-copy-url-link 0/1` | `pagebarCopyUrlLink` | 位 8 反向 |
| New Window Link | `--pagebar-new-window-link 0/1` | `pagebarNewWindowLink` | 位 16 反向 |
| Customize Page Link | `--pagebar-customize-page-link 0/1` | `pagebarCustomizePageLink` | 位 32 反向 |

部分更新保留未指定的按钮、History、PNLNAVFLAGS 和 SHOWTBAR 其他位。关闭 Toolbar/Pagebar 总开关只改变显示状态，保留子选项，可在同一请求预设禁用组的子选项。`struct` 同时回读原始数字及所有语义开关。

四个 Toolbar 动作按钮与 Use 页四种 Actions 不等价。Actions 从关闭变为启用时按 AD 默认勾选对应按钮；关闭 Actions 清除按钮位。一次请求先应用 Actions 联动，再应用显式 Toolbar 设置，所以 `--allow-correction 1 --toolbar-correction 0` 合法；`--allow-correction 0 --toolbar-correction 1` 原子拒绝。单独隐藏按钮不会关闭 Component 动作；禁用动作的按钮不能显式显示。

```powershell
python scripts/peoplesoft_api.py component struct MY_COMPONENT --json --output ./before.json
python scripts/peoplesoft_api.py component modify-props MY_COMPONENT --snapshot ./before.json --disable-toolbar 0 --toolbar-save 1 --toolbar-cancel 0 --toolbar-hide-back-button 1 --disable-pagebar 0 --pagebar-help-link 1 --pagebar-copy-url-link 0 --project MY_PROJECT
```

PANWX25 / PeopleTools 8.60.10 已完成全部选项的 AD 单变量采集、六张表精确回放、CLI/API 真实保存和 AD 关闭重开。其他 Tools/数据库、PIA 实际按钮点击及运行行为未验收。以上支持定义属性持久化和 AD 展示。

本批证据覆盖 PANWX25 / PeopleTools 8.60.10 的 AD 单变量保存差异、动作与搜索类型/导航联动、独立原始表回读和 AD 关闭重开。其他 Tools/数据库、Keyword 搜索部署和 PIA 实际搜索/浏览器历史行为未验收；属性保存不代表搜索基础设施已部署。

```powershell
python scripts/peoplesoft_api.py component struct MY_COMPONENT --market GBL --json --output ./component-before.json
python scripts/peoplesoft_api.py component modify-props MY_COMPONENT --market GBL --snapshot ./component-before.json --descr 'Example' --search-record INSTALLATION --allow-add 1 --page-name MY_PAGE --hidden 0 --item-label 'Home' --folder-tab-label 'Home' --project MY_PROJECT
python scripts/peoplesoft_api.py component view-code MY_COMPONENT --market GBL --event PreBuild
# 修改下载的文件；写入使用该文件旁的 .snapshot.json，或用 --snapshot 指定。
python scripts/peoplesoft_api.py component modify-code MY_COMPONENT --market GBL --event PreBuild --file <Cached文件> --project MY_PROJECT
```

PANWX25 已验证 AD 单变量差异、CLI 组合修改与 AD 重开回读、原始版本缺失/过期、双请求竞争，以及 Component 级 PreBuild 的创建、读取、删除预演和删除。其他 PeopleTools 版本、其他数据库和 PIA 运行行为尚未验收。

通过 Integration Broker REST 接口查看 Component 定义结构（包含其下 Page 列表）。

### 接口地址

```
POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/PSFT_HR/AI_OPER_COMPONENT_DEFN.v1/
```

### Service Operation

`AI_OPER_COMPONENT_DEFN_POST` — 需要在 PIA 中给用户授予 Execute 权限。

处理类： `C_META_DATA_PKG:MetaData:Read:OperComponentDefn` / `C_META_DATA_PKG:MetaData:Write:OperComponentDefn`

### 请求体参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `pnlGrpName` | string | **是** | Component 名称 |
| `market` | string | 否 | 市场，默认 `"GBL"` |
| `operationType` | string | 否 | 默认 `"struct"`，可选 `"structDeep"`、`"modifyComponentProps"`、`"createComponent"`、`"modifyComponent"`、`"viewPeopleCode"`、`"modifyPeopleCode"`、`"deletePeopleCode"` |
| `expectedVersion` | string | 所有写入必填 | 读取时保存的原始 `c1:` 版本；不能取写入前最新版本替换旧快照 |
| `recordName` | string | 否 | view/modify/delete 时指定 Record 名（Component Record 级或 Component Record Field 级） |
| `fieldName` | string | 否 | view/modify/delete 时指定 Field 名（Component Record Field 级） |
| `event` | string | 否 | view/modify/delete 时指定事件名（如 `PreBuild`、`RowInit`、`FieldChange`） |
| `peoplecode` | string | 否 | modifyPeopleCode 时传入的 PeopleCode 源码 |

### 响应结构 (operationType=struct)

```json
{
  "pnlGrpName": "JOB_DATA",
  "market": "GBL",
  "descr": "职务数据",
  "descrLong": "Maintain Job History for people...",
  "searchRecName": "EMPLMT_SRCH_ALL",
  "addSrchRecName": "EMPLMT_SRCH_ALL",
  "searchPnlName": "PERSONAL_DATA1",

  "fluidMode": 0,
  "layoutMode": 0,
  "disableSave": 0,
  "forceSearch": 0,
  "deferProc": 1,
  "allowActModeSel": 1,
  "inclNavigation": 1,
  "incHeader": 0,
  "incFooter": 0,
  "incSide": 0,
  "incSearch": 0,
  "compType": 0,
  "showTbar": 1,
  "primaryAction": 1,
  "dfltAction": 1,
  "actions": 14,
  "pnlGrpUse": 1,
  "lastUpdate": "Last updated by: PPLSOFT, 2021/03/05 09:27:17",

  "pageCount": 12,
  "pages": [
    {
      "pnlName": "JOB_DATA1",
      "market": "GBL",
      "subItemNum": 1,
      "itemName": "JOB_DATA1",
      "itemLabel": "工作地点(&W)",
      "folderTabLabel": "",
      "hidden": 0
    }
  ]
}
```

### 响应结构 (operationType=structDeep)

直接返回 Component 下所有 Page 的字段聚合结果，按 **Level → Record → Field** 层级组织，**不含 Page 层**。

同时注入 **PeopleCode 事件信息**：
- Component 级事件挂在 Component 对象的 `events` 数组下
- Record 级事件（如 RowInit、SaveEdit 等）挂在 Level 内 Record 对象的 `events` 数组下
- Field 级事件（如 FieldChange、FieldDefault 等）挂在 Field 对象的 `events` 数组下

```json
{
  "pnlGrpName": "JOB_DATA",
  "market": "GBL",
  "descr": "职务数据",
  "events": ["PostBuild", "PreBuild", "SavePostChange", "SavePreChange"],
  "levels": [
    {
      "level": 0,
      "records": [
        {
          "recName": "DERIVED",
          "events": [],
          "fields": [
            {"fieldName": "EDITTABLE2", "fieldType": "editBox"}
          ]
        },
        {
          "recName": "JOB",
          "events": ["RowDelete", "RowInit", "RowInsert", "SaveEdit", "SavePostChange", "SavePreChange"],
          "fields": [
            {"fieldName": "EMPLID", "fieldType": "editBox"},
            {"fieldName": "EFFDT", "fieldType": "editBox", "events": ["FieldChange"]}
          ]
        }
      ]
    }
  ]
}
```

**事件级别说明：**
| 级别 | 事件示例 | 定位方式 |
|------|---------|---------|
| Component 级 | PreBuild, PostBuild, SavePreChange, SavePostChange | 无 recordName/fieldName |
| Component Record 级 | RowInit, RowInsert, RowDelete, SaveEdit | 需 recordName |
| Component Record Field 级 | FieldChange, FieldDefault, FieldEdit | 需 recordName + fieldName |

**事件查询源：** PSPCMPROG (OBJECTID1=10, OBJECTVALUE1=Component名)

### 响应结构 (operationType=viewPeopleCode)

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "pnlGrpName": "JOB_DATA",
    "recordName": "JOB",
    "fieldName": "EFFDT",
    "event": "FieldChange",
    "peoplecode": "If %Component = \"JOB_DATA\" Then...",
    "lastUpdate": "Last updated by: PPLSOFT, 2024/01/08 08:27:49"
  }
}
```

### 响应结构 (operationType=modifyPeopleCode)

```json
{
  "code": 0,
  "message": "success"
}
```

修改后系统会自动调用 PeopleCode Program Manager 进行编译校验。
- 跨所有 Page 自动合并同一 Level + Record + Field 的重复项（去重）
- 过滤掉纯容器控件（subPage、horizontalRule、scrollArea 等 fieldName 为空的条目）
- 字段类型通过 `MappingUtil.DecodePnlFieldType` 解析
- 不返回字段属性（key、req、ro、hidden 等），仅返回 `fieldName` + `fieldType`

### 涉及的 PeopleTools 表

#### PSPNLGRPDEFN — Component 定义 (43 字段)

Key: PNLGRPNAME + MARKET

| 字段 | 类型 | 说明 |
|------|------|------|
| PNLGRPNAME | char(18) | Component 名（主键） |
| MARKET | char(3) | 市场（主键） |
| DESCR | char(30) | 短描述 |
| DESCRLONG | CLOB | 长描述 |
| SEARCHRECNAME | char(15) | 搜索记录 |
| ADDSRCHRECNAME | char(15) | 添加搜索记录 |
| SEARCHPNLNAME | char(18) | 搜索页面 |
| FLUIDMODE | number(1) | Fluid 模式 |
| LAYOUTMODE | number(1) | 布局模式 |
| DISABLESAVE | number(1) | 禁用保存 |
| FORCESEARCH | number(1) | 强制搜索 |
| DEFERPROC | number(1) | 延迟处理 |
| ALLOWACTMODESEL | number(1) | 允许操作模式选择 |
| INCLNAVIGATION | number(1) | 包含导航 |
| INCHEADER | number(1) | 包含页头 |
| INCFOOTER | number(1) | 包含页脚 |
| INCSIDE | number(1) | 包含侧栏 |
| INCSEARCH | number(3) | 包含搜索 |
| COMP_TYPE | number(3) | 组件类型 |
| SHOWTBAR | number(2) | 显示工具栏 |
| PRIMARYACTION | number(3) | 主操作 |
| DFLTACTION | number(5) | 默认操作 |
| ACTIONS | number(4) | 操作位掩码 |
| PNLGRPUSE | number(10) | 组件用途位掩码 |
| LASTUPDDTTM | datetime | 最后更新 |
| LASTUPDOPRID | char(30) | 更新人 |

#### PSPNLGROUP — Component → Page 映射 (8 字段)

Key: PNLGRPNAME + MARKET + PNLNAME

| 字段 | 类型 | 说明 |
|------|------|------|
| PNLGRPNAME | char(18) | Component 名 |
| MARKET | char(3) | 市场 |
| PNLNAME | char(30) | Page 名 |
| SUBITEMNUM | number(4) | 子项序号 |
| ITEMNAME | char(30) | 项名 |
| ITEMLABEL | char(30) | 项标签 |
| FOLDERTABLABEL | char(18) | 文件夹/标签 |
| HIDDEN | number(2) | 隐藏标志 |

### PeopleCode 类

`C_META_DATA_PKG:MetaData:Read:OperComponentDefn` / `C_META_DATA_PKG:MetaData:Write:OperComponentDefn` — 实现 IRequestHandler 接口。

#### 方法
- `OnRequest(&message)` — IB 入口
- `GetComponentStruct()` — 查询 PSPNLGRPDEFN + PSPNLGROUP，返回结构化 JSON

### CLI 用法

```bash
# 查看 Component 结构（默认 market=GBL）
python scripts/peoplesoft_api.py component struct JOB_DATA

# 指定 market
python scripts/peoplesoft_api.py component struct JOB_DATA --market GBL

# 查看 Component 深度结构（含 PeopleCode 事件信息）
python scripts/peoplesoft_api.py component structDeep JOB_DATA
python scripts/peoplesoft_api.py component structDeep JOB_DATA --market GBL

# 也可以通过 struct --deep 调用
python scripts/peoplesoft_api.py component struct JOB_DATA --deep

# 查看 Component 级 PeopleCode
python scripts/peoplesoft_api.py component view-code JOB_DATA --event PreBuild

# 查看 Component Record 级 PeopleCode
python scripts/peoplesoft_api.py component view-code JOB_DATA --record JOB --event RowInit

# 查看 Component Record Field 级 PeopleCode
python scripts/peoplesoft_api.py component view-code JOB_DATA --record JOB --field EFFDT --event FieldChange

# 修改 Component Record Field 级 PeopleCode
python scripts/peoplesoft_api.py component modify-code JOB_DATA --record JOB --field EFFDT --event FieldChange --file ./new_code.txt
```

### 注意事项

- 调用前需在 PIA 中授予 `AI_OPER_COMPONENT_DEFN_POST` 的 Execute 权限
- market 默认 GBL，可通过参数覆盖
- pages 按 SUBITEMNUM 升序排列
- descrLong 经 EscapeJSON 编码返回
- viewPeopleCode / modifyPeopleCode 支持三种级别：
  - **Component 级**：只需 `event`
  - **Component Record 级**：需 `recordName` + `event`
  - **Component Record Field 级**：需 `recordName` + `fieldName` + `event`
- PeopleCode Key 结构使用 `10` (对应 OBJECTID1=Component) + Market(39) + Record(1) + Field(2) + Method(12)
- modifyPeopleCode 会调用 PeopleCode Program Manager 自动编译，失败时返回 code=-1 和错误信息
- 支持 struct、structDeep、viewPeopleCode、modifyPeopleCode、deletePeopleCode；代码读取增加 programExists，空白修改被拒绝

## 元数据结构参考

已在 PANWX25 核实的主要定位：PSPNLDEFN 的键为 PNLNAME；PSPNLFIELD、PSPNLFIELDEXT 为 PNLNAME+PNLFLDID；PSPNLGRPDEFN 为 PNLGRPNAME+MARKET；PSPNLGROUP 为 PNLGRPNAME+MARKET+PNLNAME。组件与页面是多对多映射，PNLGRPNAME 不属于 PSPNLDEFN。

PNLUSE 是页面位掩码，PNLTYPE 是类型码；PNLLBLTEXTSRC、PNLCLASS 不是 PSPNLDEFN 字段。样式相关字段为 PNLSTYLE、STYLESHEETNAME、FFSTYLESHEETNAME、FFSTYLE*，未核实的取值不写入。

PSPNLFIELDEXT 含 PTMODALHEIGHT/WIDTH、PTPOPUPPNL、GRPBOXTYPE、PLACEHOLDER、SCROLLBARS、MINNUMBER/MAXNUMBER/STEPNUMBER、PARENTPNLFLDID、PAGEPNLFLDID、FIELDUSETEMP2、FFSTYLELONG 等扩展。struct --full 按单个 Record 读取 fields[].ext，不用批量 Rowset 路径替代。

已验证的控件码见 addControl；19 为 grid（GRDCOLUMNCOUNT>0），11 在 SUBPNLNAME 非空时表示 subPage，27 为 scrollArea，25 为 htmlArea，13 为 hyperlink。历史统计曾对 6/8/10 等罕见码作推测，不作为新增控件的支持承诺。

FIELDUSE 与 Record 的 USEEDIT 不同；既有分支还有按钮/链接、grid/scroll、groupBox 的基值，完整语义待原生逐项验证。Edit/DDL 的 LBLTYPE 实测1=Text、2=RFT Short、3=RFT Long；标签位置单独研究，不把复选框的右置推作 LBLTYPE。默认 Label ID 应按字段原生默认标签解析，可能与字段名不同；PSDBFIELD 没有 LABEL_ID 列。PNLUSE 和样式位含义未完整解码，不猜高位组合。

## 删除 Page / Component 程序

```powershell
python scripts/peoplesoft_api.py page delete-code MY_PAGE --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py component delete-code MY_COMPONENT --market GBL --event PreBuild --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py component delete-code MY_COMPONENT --market GBL --record MY_RECORD --event RowInit --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py component delete-code MY_COMPONENT --market GBL --record MY_RECORD --field COUNTRY --event FieldChange --project MY_PROJECT --dry-run
```

Component 的 view/modify/delete 均使用同一个 market；指定 field 必须指定 record。省略 `--dry-run` 执行删除；支持 `--output`。快照、原生检查与迁移完整键见 [删除流程](development-standards.md#peoplecode-真正删除)。
