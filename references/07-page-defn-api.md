# AI_OPER_PAGE_DEFN API

通过 Integration Broker REST 接口查询、创建和修改 Page 定义及其控件。

## 接口地址

```
POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/{node}/AI_OPER_PAGE_DEFN.v1/
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
PT/Fluid 扩展属性（v1 未使用，后续补充）

### PSPNLGROUP — Component-Page 映射 (8 字段)
PNLGRPNAME 在此表中，不在 PSPNLDEFN。

### PSPNLGRPDEFN — Component 定义 (43 字段)

## 常用 FIELDTYPE 解码

| 码 | 类型 | 备注 |
|----|------|------|
| 0 | staticText | |
| 2 | groupBox | |
| 4 | editBox | |
| 5 | dropDown | |
| 7 | checkBox | |
| 11 | subPage | `SUBPNLNAME` 非空时为子页面嵌入 |
| 12 | pushButton | |
| 13 | hyperlink | |
| 19 | grid | `GRDCOLUMNCOUNT > 0` 时为 Grid |
| 23 | hrule | |
| 25 | htmlArea | |
| 27 | scrollArea | |

## FIELDUSE 位掩码（已验证常用位）

| 位 | 值 | 属性 |
|----|-----|------|
| 0 | 1 | required |
| 1 | 2 | invisible |
| 2 | 4 | displayOnly |
| 3 | 8 | key |
| 4 | 16 | relatedDisplay |

## PeopleCode 类

`C_META_DATA_PKG:MetaData:OperPageDefn` — 实现 IRequestHandler 接口。

### 方法
- `OnRequest(&message)` — IB 入口
- `GetPageStruct()` — 查询 PSPNLDEFN + PSPNLFIELD，返回结构化 JSON
- `DecodePnlType(&p_pnlType)` — PNLTYPE → 字符串
- `DecodeFieldType(&p_fieldType)` — FIELDTYPE → 字符串

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
