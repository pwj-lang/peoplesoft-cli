# Page、Component 与页面结构

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
      "required": false,
      "invisible": false,
      "displayOnly": false,
      "key": false,
      "relatedDisplay": false,
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
full=1 时按 PNLNAME/PNLFLDID 使用单个 Record 的 SelectByKey 读取 PT/Fluid 扩展属性，返回 rawExt；不存在时为 {}，避免批量 Rowset 访问的网关错误。

### PSPNLGROUP — Component-Page 映射 (8 字段)
PNLGRPNAME 在此表中，不在 PSPNLDEFN。

### PSPNLGRPDEFN — Component 定义 (43 字段)

## FIELDUSE 位掩码（已验证常用位）

| 位 | 值 | 属性 |
|----|-----|------|
| 0 | 1 | required |
| 1 | 2 | invisible |
| 2 | 4 | displayOnly |
| 3 | 8 | key |
| 4 | 16 | relatedDisplay |

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
  "required": 1,
  "invisible": 0,
  "displayOnly": 0,
  "onValue": "Y",
  "offValue": "N"
}
```

| controlType | FIELDTYPE | 说明 |
|---|---:|---|
| `editBox` | 4 | 需 `recName` + `fieldName`；label 左置 |
| `dropDown` | 5 | 需 `recName` + `fieldName` |
| `checkBox` | 7 | 标签在右；ON/OFF 值默认 Y/N |
| `staticText` | 0 | 无绑定，文本放 `labelText` |
| `groupBox` | 2 | 需记录字段作为标签源 |
| `hrule` | 23 | 无绑定；高 2px |
| `subPage` | 11 | `subPnlName` 必填 |
| `scrollArea` | 27 | 需 `recName`；写入滚动区域布局参数 |
| `htmlArea` | 25 | `htmlText` 必填 |
| `pushButton` | 12 | 通常绑定 DERIVED 工作字段 |
| `hyperlink` | 13 | 同 pushButton；可选 `pbDisplayType` |

> `11=subPage`、`27=scrollArea`、`25=htmlArea`、`13=hyperlink`、`19=grid`。`findControls.fieldType` 传 PeopleTools 数值码，不要传解码后的字符串。

grid 列定义和 tab 子页关联不应盲写；执行这类写入前先用 AD 手工操作前后的结构快照做 golden diff。

### modifyControl

允许修改的属性：

`left` / `top` / `right` / `bottom` / `editSize` / `occursLevel` / `labelText` / `labelId` / `labelType` / `labelLoc` / `fieldStyle` / `labelStyle` / `deferProc` / `required` / `invisible` / `displayOnly`

验收标准：修改 1 个控件后，`struct` 快照 diff 应只有目标控件的预期列变化。

### 已验证的实现约束

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
python scripts/peoplesoft_api.py page find <page> --field EFF_STATUS
python scripts/peoplesoft_api.py page del-control <page> --pnl-fld-id 7
```

新建 Page 后执行 `project insert-item --object-type 5`。修改已有页面前，先用 `page struct --full --json` 保存基线。

## PeopleCode 状态

struct 的 hasPeopleCode 只描述正文是否非空，不能证明原生程序不存在。viewPeopleCode 的 programExists 检查原生程序；modify-code 拒绝空白正文并自动独立回读，编译失败或回读不一致报错。空 Page 的字段列表和 fieldCount 都为 0。

page delete-code 真正删除 Activate，保留 Page/控件；删除后原生不存在，并按完整键登记 Project Delete 标记。C_AI_PF1010 关闭重开 AD 后 Activate 恢复普通字重。流程见 [真正删除](development-standards.md#peoplecode-真正删除)。

## Component 接口

通过 Integration Broker REST 接口查看 Component 定义结构（包含其下 Page 列表）。

### 接口地址

```
POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/PSFT_HR/AI_OPER_COMPONENT_DEFN.v1/
```

### Service Operation

`AI_OPER_COMPONENT_DEFN_POST` — 需要在 PIA 中给用户授予 Execute 权限。

处理类： `C_META_DATA_PKG:MetaData:OperComponentDefn`

### 请求体参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `pnlGrpName` | string | **是** | Component 名称 |
| `market` | string | 否 | 市场，默认 `"GBL"` |
| `operationType` | string | 否 | 默认 `"struct"`，可选 `"structDeep"`、`"viewPeopleCode"`、`"modifyPeopleCode"`、`"deletePeopleCode"` |
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

`C_META_DATA_PKG:MetaData:OperComponentDefn` — 实现 IRequestHandler 接口。

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

PSPNLFIELDEXT 含 PTMODALHEIGHT/WIDTH、PTPOPUPPNL、GRPBOXTYPE、PLACEHOLDER、SCROLLBARS、MINNUMBER/MAXNUMBER/STEPNUMBER、PARENTPNLFLDID、PAGEPNLFLDID、FIELDUSETEMP2、FFSTYLELONG 等扩展。struct --full 按单个 Record 读取 rawExt，不用批量 Rowset 路径替代。

已验证的控件码见 addControl；19 为 grid（GRDCOLUMNCOUNT>0），11 在 SUBPNLNAME 非空时表示 subPage，27 为 scrollArea，25 为 htmlArea，13 为 hyperlink。历史统计曾对 6/8/10 等罕见码作推测，不作为新增控件的支持承诺。

FIELDUSE 与 Record 的 USEEDIT 不同；额外实测位有 bit19=按钮/链接、bit12=grid/scroll、bit26=groupBox 基值。LBLTYPE 实测 1=字面量、2=复选框右侧、3=RFT 标签、7=消息目录；字段默认 RFT 标签 ID 为字段名，PSDBFIELD 没有 LABEL_ID 列。PNLUSE 和样式位含义未完整解码，不猜高位组合。

## 删除 Page / Component 程序

```powershell
python scripts/peoplesoft_api.py page delete-code MY_PAGE --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py component delete-code MY_COMPONENT --market GBL --event PreBuild --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py component delete-code MY_COMPONENT --market GBL --record MY_RECORD --event RowInit --project MY_PROJECT --dry-run
python scripts/peoplesoft_api.py component delete-code MY_COMPONENT --market GBL --record MY_RECORD --field COUNTRY --event FieldChange --project MY_PROJECT --dry-run
```

Component 的 view/modify/delete 均使用同一个 market；指定 field 必须指定 record。省略 `--dry-run` 执行删除；支持 `--output`。快照、原生检查与迁移完整键见 [删除流程](development-standards.md#peoplecode-真正删除)。
