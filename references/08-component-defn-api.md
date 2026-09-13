# AI_OPER_COMPONENT_DEFN API

通过 Integration Broker REST 接口查看 Component 定义结构（包含其下 Page 列表）。

## 接口地址

```
POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/{node}/AI_OPER_COMPONENT_DEFN.v1/
```

## Service Operation

`AI_OPER_COMPONENT_DEFN_POST` — 需要在 PIA 中给用户授予 Execute 权限。

Handler: `C_META_DATA_PKG:MetaData:OperComponentDefn`

## 请求体参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `pnlGrpName` | string | **是** | Component 名称 |
| `market` | string | 否 | 市场，默认 `"GBL"` |
| `operationType` | string | 否 | 默认 `"struct"`，可选 `"structDeep"`、`"viewPeopleCode"`、`"modifyPeopleCode"` |
| `recordName` | string | 否 | view/modify 时指定 Record 名（Component Record 级或 Component Record Field 级） |
| `fieldName` | string | 否 | view/modify 时指定 Field 名（Component Record Field 级） |
| `event` | string | 否 | view/modify 时指定事件名（如 `PreBuild`、`RowInit`、`FieldChange`） |
| `peoplecode` | string | 否 | modifyPeopleCode 时传入的 PeopleCode 源码 |

## 响应结构 (operationType=struct)

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

## 响应结构 (operationType=structDeep)

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

## 响应结构 (operationType=viewPeopleCode)

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

## 响应结构 (operationType=modifyPeopleCode)

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

## 涉及的 PeopleTools 表

### PSPNLGRPDEFN — Component 定义 (43 字段)

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

### PSPNLGROUP — Component → Page 映射 (8 字段)

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

## PeopleCode 类

`C_META_DATA_PKG:MetaData:OperComponentDefn` — 实现 IRequestHandler 接口。

### 方法
- `OnRequest(&message)` — IB 入口
- `GetComponentStruct()` — 查询 PSPNLGRPDEFN + PSPNLGROUP，返回结构化 JSON

## CLI 用法

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

## 注意事项

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
- 目前支持 struct、structDeep、viewPeopleCode、modifyPeopleCode 四种操作
