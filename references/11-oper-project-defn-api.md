# AI_OPER_PROJECT_DEFN API

通过 Integration Broker REST 接口操作 Project（应用数据集 / ADS）定义，底层复用 Oracle 交付的 `PROJECT` 应用包（`PROJECT:ProjectDefn`、`PROJECT:ProjectItemDefn2`）。

支持：创建 Project、插入定义条目到 Project、修改 Project 描述/详细描述、查看 Project 条目结构。

## 接口地址

```
POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/{node}/AI_OPER_PROJECT_DEFN.v1/
```

> Service Operation `AI_OPER_PROJECT_DEFN` 已发布，4 个操作（createProject / insertItem / modifyProject / struct）均可用。

## 请求头

| Header | 值 | 必填 |
|--------|-----|------|
| `Content-Type` | `application/json` | 是 |
| `PS_TOKEN` | 登录获取的 token | 是 |

## 请求体参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `projectName` | string | **是** | Project 名称（PSPROJECTDEFN.PROJECTNAME，≤30 字符） |
| `operationType` | string | 否 | 操作类型，默认 `"createProject"`。可选值见下表 |
| `descr` | string | 否 | 项目描述（PROJECTDESCR，≤30 字符），用于 createProject / modifyProject |
| `comment` | string | 否 | 详细描述（DESCRLONG，长文本），**JSON 转义后传输**，用于 createProject / modifyProject |
| `objectType` | int | insertItem 必填 | 条目对象类型（PeopleTools 对象类型编码，见下表） |
| `objectValue1` | string | 否 | 条目对象值 1（如 Record 名 / Field 名） |
| `objectValue2` | string | 否 | 条目对象值 2 |
| `objectValue3` | string | 否 | 条目对象值 3 |
| `objectValue4` | string | 否 | 条目对象值 4 |
| `upgradeAction` | int | 否 | 升级动作：0=Copy, 1=Delete, 2=None, 3=Copy Property（服务器默认 0） |
| `takeAction` | int | 否 | 是否执行升级动作（0/1）。⚠️ **服务器默认 0（等价于 AD Upgrade 视图不勾选 Upgrade，迁移时会漏掉该定义）**。skill CLI `project insert-item` 已改为默认传 1（勾选 Upgrade），仅用户明确说不迁移时才传 0（2026-09-06 起，源码 review 确认） |

> **takeAction 与 AD 界面的对应关系**（2026-09-06 实测）：AD 中打开 Project → Project Workspace 底部 **Upgrade** 标签页 → 双击定义类型文件夹（如 Application Engine Programs）→ 右侧弹出表格，其中 **Upgrade 复选框 = takeAction**，**Action 列 = upgradeAction**（Copy）。勾选后需 **File → Save Project** 保存（Ctrl+S 在升级表格为活动窗口时不会落库）。

## operationType 取值一览

| operationType | 说明 | 必填参数 |
|---------------|------|----------|
| `createProject`（默认） | 创建 Project | projectName；可选 descr / comment |
| `insertItem` | 插入一条定义到 Project（**每次插入后自动落库**） | projectName、objectType；可选 objectValue1~4 / upgradeAction / takeAction |
| `modifyProject` | 修改 Project 描述、详细描述 | projectName；可选 descr / comment（未传的字段保留原值） |
| `struct` | 查看 Project 内的定义条目列表（PSPROJECTITEM） | projectName |

## 对象类型编码（objectType）

`objectType` 使用 PeopleTools 标准对象类型编码，常用值：

| 编码 | 对象类型 |
|------|----------|
| 0 | Record |
| 2 | Field |
| 5 | Page |
| 6 | Menu |
| 7 | Component |
| 10 | Query |
| 65 | SQL 定义 |
| 104 | Application Package |

> **注意区分**：这里的 `objectType` 是 PeopleTools 对象类型编码（写入 `PSPROJECTITEM.OBJECTTYPE`），与 `AI_SEARCH_DEFN` 接口的 `definitionType`（Record=1/Field=2/SQL=65/AppPkg=104/Project=105 的 API 自有枚举）**不是同一套**，两者互不相干。

### ⚠️ App Package **类**的正确插入方式（易踩坑）

**插入 App Package 类时，`objectType` 不要用 104（整串 classPath 塞进 `objectValue1`）**，PeopleSoft 不会识别，会留下"看起来插成功、实际无效"的脏条目。正确做法：

| 层级 | `objectType` | `objectValue1~4` 怎么填 |
|---|---|---|
| **包级**（整个包，如 `C_GP_LINK_PAY`）| `57` | value1=包名, value2=包名, value3="." |
| **类级**（包内的具体类）| `58` | value1=包根, value2=子包..., valueN=类名（**类名放最后一个 value**） |

**类级示例**（`C_JT_PT:globalPay:outBound:GetCalRunListByWF`）：

```
objectValue1 = C_JT_PT
objectValue2 = globalPay
objectValue3 = outBound
objectValue4 = GetCalRunListByWF
```

**验证是否真正收录（不要只看 `OK — item inserted`）**：用 `query-record PSPROJECTITEM` 查真实落库，并确认 `OBJECTTYPE=58` 且 `OBJECTVALUE*` 是分段存的；`OBJECTTYPE=104` + 整串冒号 classPath 是错误插法，需清理（DELETE 从 `PSPROJECTITEM`，注意表名**无下划线**，是 `PSPROJECTITEM` 不是 `PS_PROJECTITEM`）。

## 响应格式

统一 `code / message / data` 格式：

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | int | 0=成功，非0=失败 |
| `message` | string | 成功固定 `"success"`，失败返回原因 |
| `data` | object | 成功时包含结果，失败时为 `{}` |

## 请求示例

### 1. 创建 Project

```json
{
  "projectName": "MY_PROJECT",
  "operationType": "createProject",
  "descr": "Compare Project",
  "comment": "详细描述文本"
}
```

### 2. 插入一个 Record 定义到 Project

```json
{
  "projectName": "MY_PROJECT",
  "operationType": "insertItem",
  "objectType": 0,
  "objectValue1": "ABSV_ACCRUAL"
}
```

### 3. 插入一个 Field 定义到 Project

```json
{
  "projectName": "MY_PROJECT",
  "operationType": "insertItem",
  "objectType": 2,
  "objectValue1": "EMPLID"
}
```

### 4. 修改 Project 描述和详细描述

```json
{
  "projectName": "MY_PROJECT",
  "operationType": "modifyProject",
  "descr": "New Descr",
  "comment": "新的详细描述"
}
```

### 5. 查看 Project 条目结构

```json
{
  "projectName": "MY_PROJECT",
  "operationType": "struct"
}
```

## 响应示例

### 创建成功

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "projectName": "MY_PROJECT",
    "created": true
  }
}
```

### 插入成功

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "projectName": "MY_PROJECT",
    "inserted": true
  }
}
```

### 修改成功

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "projectName": "MY_PROJECT",
    "modified": true
  }
}
```

### 查看结构成功

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "projectName": "MY_PROJECT",
    "items": [
      {
        "objectType": 0,
        "objectId1": 1,
        "objectValue1": "ABSV_ACCRUAL",
        "objectId2": 0,
        "objectValue2": "",
        "objectId3": 0,
        "objectValue3": "",
        "objectId4": 0,
        "objectValue4": "",
        "upgradeAction": 0,
        "takeAction": 0
      }
    ]
  }
}
```

每个条目包含 `objectType`（PeopleTools 对象类型编码）、`objectId1~4`（解析后的对象 ID）、`objectValue1~4`（对象键值）、`upgradeAction`、`takeAction`。

### 失败（项目已存在）

```json
{
  "code": 400,
  "message": "project already exists: MY_PROJECT",
  "data": {}
}
```

## 实现说明

- **底层类**：`C_META_DATA_PKG:MetaData:OperProjectDefn`，实现 `PS_PT:Integration:IRequestHandler`。
- **创建**：`PROJECT:ProjectDefn` 构造 → 设置 `m_sDescription` / `m_sComments` → `save()`（内部走 `SaveNewDefn`，会自动 `CreateSession`）。
- **插入**：`PROJECT:ProjectItemDefn2` 构造（构造器内部用 `ProjectDefn.GetObjectIDs` 把 objectValue1~4 解析成 OBJECTID1~4）→ `save()`（直接 `INSERT INTO PSPROJECTITEM`）→ `CommitWork()`。**每次插入即落库，无需额外 save**。
- **修改**：`PROJECT:ProjectDefn` → 读取当前 `ProjectDescr`/`DescrLong` 作为兜底 → 用传入值覆盖 → `save()`（内部走 `UpdateDefn`）。未传 `descr` 或 `comment` 的字段保留原值。
- **结构查看**：`struct` 直接查 `PSPROJECTITEM WHERE PROJECTNAME = :1`（按 OBJECTTYPE 排序），返回条目列表，不依赖 metadata API。

## CLI 侧：当前 Project 状态

以上 4 个 `operationType` 都要求显式传 `projectName`，服务端没有「当前 Project」概念。CLI 在本地维护这个状态，文件位置见 SKILL.md「配置与认证」：

```bash
python scripts/peoplesoft_api.py project current          # 查看当前环境上次使用的 Project
python scripts/peoplesoft_api.py project use MY_PROJECT   # 设为当前 Project
```

- 状态按**环境**分节存放在同一个文件里，`env use` 切换环境后自动跟随，不会串台
- `project create` / `insert-item` / `modify` 成功后**自动**把该 Project 记为当前；`struct` 是只读，不改变状态
- `project current` 在没有记录时提示尚未选择，并给出 `project use` 的下一步命令
- `use` 只写本地状态，**不校验** Project 在服务端是否存在。按 SKILL.md 第4步要求，更换 Project 前应先用 `project struct <name>` 确认它在当前环境存在
- 状态文件缺失或损坏时按「无记录」处理，不会中断命令

> 不要与 `healthcheck` / `bundle-check` 的 `--project` 参数混淆：那个默认值 `C_META_DATA_PKG` 指的是实现 ps-metadata 接口的 AD 工程，不是开发交付用的 Project。

## 注意事项

1. `projectName` 必须精确匹配，插入条目时项目必须已存在（否则返回「project does not exist」）。
2. `comment`（DESCRLONG）为长文本，传输时需 JSON 转义（客户端 `json.dumps(text)[1:-1]`，服务端 `UnEscapeJSON` 解码）。
3. `insertItem` 依赖 `PSPROJECTITEM.OBJECTTYPE` 的合法对象类型编码，非法编码会导致 `GetObjectIDs` 解析不到 ID，条目照插但 ID 可能为 0。
4. `objectType` 与 search 接口的 `definitionType` 是两套编码，勿混用。
5. ⚠️ `descr` 超过 30 字符时 `createProject` 报 500：(2,535) `Failed to set value ... ProjectDescr`（PROJECT.ProjectDefn.save Statement:77，2026-09-06 实测）。描述控制在 30 字符内，长说明放 `comment`。
6. `insertItem` 对已存在的条目重复插入会失败（PSPROJECTITEM 主键冲突），且无 updateItem/deleteItem 操作——修改已有条目的 takeAction/upgradeAction 目前只能在 AD 中改后 Save Project，或先手工删行再重插。

## OBJECTTYPE 对照与已知限制（2026-09-05 AD 实证）

| OBJECTTYPE | 定义类型 | 备注 |
|---|---|---|
| 0 | Record | value1=RECNAME |
| 2 | Field | value1=FIELDNAME |
| 4 | Translate Value | value1=FIELDNAME, value2=字段值, value3=EFFDT |
| 5 | Page | value1=PNLNAME |
| 7 | Component | value1=PNLGRPNAME, **value2=MARKET（必填）** |
| 30 | SQL | value1=SQLID |
| 33 | Application Engine | value1=AE_APPLID。**⚠️ 31 是错误代码**：插入后 AD 项目树不显示（静默隐藏），且 AE 文件夹不会出现 |
| 57 | Application Package（根） | AD 自身按路径节点拆行存储（value2/value3 为路径片段、take=1）；insertItem 只写 value1 的行 AD 能显示 |
| 58 | Application Package PeopleCode | value1=根包, value2=子包, value3=类名。⚠️ 部分场景 ProjectItemDefn2.save() 会抛 SQL 错误（待查），行可能已插入也可能未插入，需 struct+AD 双重确认 |
| 79 / 80 | Service / Service Operation | 已实测可用 |

已知限制：
1. **无 deleteItem 操作**——插错 OBJECTTYPE 的行无法通过 API 删除（AD 会隐藏无效行，但不影响脏数据存在），需手工 SQL 清理
2. **App Package 根包无法通过 insertPackage 创建**（服务器要求父包已存在），需在 AD 中创建
3. **struct ≠ AD 真相**：struct 反映 PSPROJECTITEM 原始行；AD 对无法识别的行静默隐藏。交付核对以 **AD 项目树** 为准

