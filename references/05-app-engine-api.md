# AI_OPER_APP_ENGINE API

通过 Integration Broker REST 接口查看和操作 PeopleSoft Application Engine 定义。

## 接口地址

```
POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/{node}/AI_OPER_APP_ENGINE.v1/
```

## 请求头

| Header | 值 | 必填 |
|--------|-----|------|
| `Content-Type` | `application/json` | 是 |
| `PS_TOKEN` | 登录获取的 token | 是 |

## 请求体公共参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| aeId | string | **是** | Application Engine 的唯一标识 |
| operationType | string | **否** | 操作类型，默认为 `struct` |

## operationType 参数说明

| operationType | 说明 |
|---------------|------|
| struct | **默认**，返回 AE 的完整结构（基本信息 + Main Section + 所有 Step 和 Action） |
| createApplicationEngine | 创建一个新的 AE |
| insertSection | 添加一个 Section |
| insertStep | 添加一个 Step，可附带插入 Actions |
| insertAction | 添加一个 Action |
| viewSQL | 查看 Step 中 Action 绑定的 SQL 语句 |
| modifySQL | 修改 Step 中 Action 绑定的 SQL 语句 |
| viewPeopleCode | 查看 Step 中 PeopleCode Action 的代码 |
| modifyPeopleCode | 修改 Step 中 PeopleCode Action 的代码 |
| insertStateRecord | 插入 State Record（记录名需含有 PROCESS_INSTANCE 字段且为 Key） |
| insertTempTable | 插入 Temp Table（记录名需含有 PROCESS_INSTANCE 字段且为 Key） |

---

## 各操作请求体详解

### 1. struct — 查看 AE 结构

无需额外参数。返回 AE 的基本信息、所有 Section 的 Step 和 Action 详情。

### 2. createApplicationEngine — 创建 AE

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| descr | string | 否 | AE 描述，不传则默认与 aeId 相同 |
| programType | string | 否 | 程序类型 |
| tempTblInstance | number | 否 | 临时表实例数 |
| recordUse | number | 否 | 记录使用 |
| comment | string | 否 | 注释（需 JSON 转义后传） |
| disableRestart | string | 否 | 是否禁用重启（Y/N） |
| AppLibrary | string | 否 | Application Library |
| Sections | array | 否 | Section 数组，用于批量创建 Section |

### 3. insertSection — 插入 Section

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| sectionId | string | 否 | 自动生成（Section1 / Section2 ...） | Section 名称 |
| market | string | 否 | GBL | 市场 |
| dbType | string | 否 | — | 数据库类型 |
| effdt | date | 否 | 1901-01-01 | 生效日期 |
| descr | string | 否 | "{sectionId} description" | 描述 |
| autoCommit | string | 否 | N | 是否自动提交（Y/N） |
| sectionType | string | 否 | P | Section 类型 |
| publicAccess | string | 否 | N | 是否公共访问（Y/N） |
| steps | array | 否 | — | 要同时创建的 Step 数组 |

### 4. insertStep — 插入 Step

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| sectionId | string | **是** | — | 所属 Section |
| market | string | **是** | — | 市场 |
| dbType | string | **是** | — | 数据库类型 |
| effdt | date | **是** | — | 生效日期 |
| stepId | string | 否 | 自动生成（Step01 / Step02 ...） | Step 名称 |
| descr | string | 否 | "{stepId} description" | 描述 |
| afterStepId | string | 否 | Section 最后一个 Step | 在哪个 Step 之后插入 |
| commitAfter | string | 否 | D | 提交策略 |
| abendAction | string | 否 | A | 异常处理：A=Abort, I=Ignore, S=Suppress |
| actions | array | 否 | 插入一个默认 SQL Action | 要同时插入的 Action 列表 |

### 5. insertAction — 插入 Action

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| sectionId | string | **是** | — | 所属 Section |
| market | string | **是** | — | 市场 |
| dbType | string | **是** | — | 数据库类型 |
| effdt | date | **是** | — | 生效日期 |
| stepId | string | **是** | — | 所属 Step |
| actionType | string | **是** | — | Action 类型（见下方 actionType 取值） |
| descr | string | 否 | 根据 actionType 自动生成 | 描述 |
| reuseStatement | string | 否 | N | 是否复用 SQL Statement（Y/N/S），仅 SQL 相关类型有效 |
| doSelectType | string | 否 | 空 | Do Select 类型：空=Select/Fetch, F=Re-Select, R=Restartable |
| callSectionAeId | string | 否 | — | Call Section 的目标 AE ID（actionType=C 时） |
| callSectionId | string | 否 | — | Call Section 的目标 Section（actionType=C 时） |
| messageSetNbr | int | 否 | — | Log Message 的消息集编号（actionType=M 时） |
| messageNbr | int | 否 | — | Log Message 的消息编号（actionType=M 时） |
| messageParameter | string | 否 | — | Log Message 的参数（actionType=M 时） |
| peoplecodeOnReturn | string | 否 | S | PeopleCode 返回行为（actionType=P 时）：S=Skip, E=Error, B=Break |

### actionType 取值

| 值 | 说明 | 默认描述 |
|----|------|----------|
| S | SQL | SQL |
| P | PeopleCode | PeopleCode |
| M | Log Message | Log Message |
| W | Do While | Do While |
| C | Call Section | Call Section |
| H | Do When | Do When |
| N | Do Util | Do Util |
| X | XSLT | XSLT |
| D | Do Select | Do Select |

### 6. viewSQL — 查看 SQL

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| sectionId | string | **是** | — |
| market | string | **是** | — |
| dbType | string | **是** | — |
| effdt | date | **是** | — |
| stepId | string | **是** | — |
| actionType | string | **是** | 哪个 Action 的 SQL |

返回 `sqlText`（JSON 转义）、`sqlId`、`sqlType`、`stmtCount`、`lastUpdate`。

### 7. modifySQL — 修改 SQL

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| sectionId | string | **是** | — |
| market | string | **是** | — |
| dbType | string | **是** | — |
| effdt | date | **是** | — |
| stepId | string | **是** | — |
| actionType | string | **是** | 哪个 Action 的 SQL |
| sqlText | string | **是** | SQL 文本（需 JSON 转义后传） |

### 8. viewPeopleCode — 查看 PeopleCode

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| sectionId | string | **是** | — |
| market | string | **是** | — |
| dbType | string | **是** | — |
| effdt | date | **是** | — |
| stepId | string | **是** | — |

返回 `peoplecode`（JSON 转义）、`lastUpdate`。

### 9. modifyPeopleCode — 修改 PeopleCode

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| sectionId | string | **是** | — |
| market | string | **是** | — |
| dbType | string | **是** | — |
| effdt | date | **是** | — |
| stepId | string | **是** | — |
| peopleCode | string | **是** | PeopleCode 代码（需 JSON 转义后传） |

修改时会自动编译，编译失败则返回错误信息及位置。

### 10. insertStateRecord — 插入 State Record

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| recName | string | **是** | — | 记录名，需在 PSRECDEFN 中存在 |
| isDefault | string | 否 | N | 是否为默认 State Record（Y/N） |

插入前校验：

- 记录在 PSRECDEFN 中存在（RECTYPE=0）
- 记录有 PROCESS_INSTANCE 字段且该字段是 Key（PSRECFIELD.KEYCOUNT > 0）
- 该 State Record 未在 PSAEAPPLSTATE 中已存在

### 11. insertTempTable — 插入 Temp Table

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| recName | string | **是** | — | 记录名，需在 PSRECDEFN 中存在 |

插入前校验：

- 记录在 PSRECDEFN 中存在（RECTYPE=0）
- 记录有 PROCESS_INSTANCE 字段且该字段是 Key（PSRECFIELD.KEYCOUNT > 0）
- 该 Temp Table 未在 PSAEAPPLTEMPTBL 中已存在

> Temp Table 的实例数（TEMPTBLINSTANCES）属于 AE 级属性，新增 Temp Table 时不需传此参数。

---

## 响应格式

所有操作返回统一格式：

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | int | 0=成功，非0=失败 |
| `message` | string | 成功为 `"success"`，失败返回原因 |
| `data` | object | 成功时包含返回数据，失败时为 `{}` |

### struct 操作返回的 data 结构

| 字段 | 说明 |
|------|------|
| descr | AE 的简短描述 |
| comment | AE 的详细描述（JSON 转义） |
| lastUpdate | 最后修改人及时间 |
| mainSection | AE 执行的入口 Section |

### mainSection 结构

| 字段 | 说明 |
|------|------|
| sectionType | Section 类型 |
| publicAccess | 是否公共访问 |
| detail | Section 明细数组 |

### detail 中的每个元素

| 字段 | 说明 |
|------|------|
| market | 市场 |
| dbType | 数据库类型 |
| descr | 描述 |
| effdt | 生效日期 |
| effStatus | 生效状态（A/I） |
| autoCommit | 是否自动提交（Y/N） |
| steps | Step 数组（已按 SEQ_NUM 排序） |

### Step 结构

| 字段 | 说明 |
|------|------|
| stepId | Step 标识 |
| activeStatus | 有效状态（A=有效, I=无效） |
| abendAction | 异常处理：A=Abort, I=Ignore, S=Suppress |
| commitAfter | 提交策略 |
| descr | 描述 |
| actions | Action 数组 |

### Action 结构

| 字段 | 说明 | 适用类型 |
|------|------|----------|
| actionType | Action 类型（S/P/M/W/C/H/N/X/D） | 全部 |
| reuseStatement | 是否复用 SQL Statement（Y/N/S） | 仅 H/W/N/D/S |
| sqlId | SQL ID | 仅 H/W/N/D/S |
| doSelectType | Do Select 类型（空/F/R） | 仅 D |
| descr | 描述 | 全部 |
| callSectionAeId | Call Section 的目标 AE ID | 仅 C |
| callSectionId | Call Section 的目标 Section | 仅 C |
| section | Call Section 的目标 Section 结构（递归） | 仅 C |
| messageSetNumber | 消息集编号 | 仅 M |
| messageNumber | 消息编号 | 仅 M |
| messageParameters | 消息参数 | 仅 M |

### viewSQL 返回的 data 结构

| 字段 | 说明 |
|------|------|
| sqlId | SQL 标识 |
| sqlType | SQL 类型 |
| sqlText | SQL 文本（JSON 转义） |
| stmtCount | 语句数 |
| lastUpdate | 最后修改人及时间 |

### viewPeopleCode 返回的 data 结构

| 字段 | 说明 |
|------|------|
| peoplecode | PeopleCode 代码（JSON 转义）；无代码时返回空字符串 |
| lastUpdate | 最后修改人及时间 |

---

## 请求示例

```json
{
  "aeId": "HPS_AE_SAL_CAL",
  "operationType": "struct"
}
```

```json
{
  "aeId": "HPS_AE_SAL_CAL",
  "operationType": "insertStep",
  "sectionId": "MAIN",
  "market": "GBL",
  "dbType": " ",
  "effdt": "1901-01-01",
  "stepId": "Step03",
  "descr": "Step03 description",
  "afterStepId": "Step02",
  "commitAfter": "D",
  "abendAction": "A"
}
```

```json
{
  "aeId": "HPS_AE_SAL_CAL",
  "operationType": "insertStateRecord",
  "recName": "PS_HPS_AE_AUDIT"
}
```

```json
{
  "aeId": "HPS_AE_SAL_CAL",
  "operationType": "insertTempTable",
  "recName": "PS_HPS_TMP_SALARY"
}
```

> 所有代码类参数（SQL 文本、PeopleCode、comment）在传输时需经过 JSON 转义。PS_TOKEN 过期后需重新登录获取。
