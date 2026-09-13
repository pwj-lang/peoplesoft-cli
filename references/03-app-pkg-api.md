# AI_OPER_APP_PKG_POST API

通过 Integration Broker REST 接口操作 Application Package（应用程序包）。

支持：查看目录结构、查看代码、修改代码、插入 Class、插入 Subpackage。

## 接口地址

```
POST {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/{node}/AI_OPER_APP_PKG_POST.v1/
```

## 请求头

| Header | 值 | 必填 |
|--------|-----|------|
| `Content-Type` | `application/json` | 是 |
| `PS_TOKEN` | 登录获取的 token | 是 |

## 请求体参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `packageRoot` | string | **是** | 应用程序包完整名称，必须精确匹配（不模糊）。可通过查询定义接口的 `definitionType=104` 获取包名 |
| `operationType` | string | 否 | 操作类型，不填或填 `"default"` 返回目录结构。可选值见下表 |
| `classPath` | string | 否 | viewPeopleCode/modifyPeopleCode/insertClass/insertPackage 时需要指定路径。定义之间用 `:` 隔开，如 `MY_ROOT:App3:Test3` |
| `peoplecode` | string | 否 | modifyPeopleCode 时传入修改后的完整代码。**代码经过 JSON 转义后传输**。viewPeopleCode 返回的代码也是 JSON 转义格式 |

## operationType 取值一览

| operationType | 说明 | classPath | peoplecode |
|---------------|------|-----------|------------|
| 不填 / `"default"` | 返回 App Package 的目录结构 | 不需要 | 不需要 |
| `"viewPeopleCode"` | 查看代码（仅 Class 有代码） | **需要** | 不需要 |
| `"modifyPeopleCode"` | 修改代码 | **需要** | **需要**（JSON 转义后传） |
| `"insertClass"` | 插入新 Class | **需要** | 不需要 |
| `"insertPackage"` | 插入新 Subpackage | **需要** | 不需要 |

## 响应格式

与查询定义接口一致，统一 `code/message/data` 格式：

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | int | 0=成功，非0=失败 |
| `message` | string | 成功固定 `"success"`，失败返回原因 |
| `data` | object | 成功时包含返回数据，失败时为 `{}` |

## 请求示例

### 1. 查看目录结构（默认）

```json
{
  "packageRoot": "MY_ROOT"
}
```

### 2. 查看目录结构（显式指定 default）

```json
{
  "packageRoot": "MY_ROOT",
  "operationType": "default"
}
```

### 3. 查看 Class 代码

```json
{
  "packageRoot": "MY_ROOT",
  "operationType": "viewPeopleCode",
  "classPath": "MY_ROOT:App:TestClass1"
}
```

### 4. 修改 Class 代码

```json
{
  "packageRoot": "MY_ROOT",
  "operationType": "modifyPeopleCode",
  "classPath": "MY_ROOT:App:TestClass1",
  "peoplecode": "class TestClass1\\n  method SayHello();\\nend-class;"
}
```

> `peoplecode` 字段的值必须是 JSON 转义后的 PeopleCode 源码。JSON 解析后即为原始代码。

### 5. 插入新 Class

```json
{
  "packageRoot": "MY_ROOT",
  "operationType": "insertClass",
  "classPath": "MY_ROOT:App:MyNewClass"
}
```

### 6. 插入新 Subpackage

```json
{
  "packageRoot": "MY_ROOT",
  "operationType": "insertPackage",
  "classPath": "MY_ROOT:App:MySubPkg"
}
```

## 响应示例

### 查看目录结构成功

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "packageRoot": "MY_ROOT",
    "descr": "My Root Package",
    "comment": "Long description text",
    "lastUpdate": "Last updated by: panwx, 2026/07/03 10:00:00",
    "packageTree": {
      "nodeName": "MY_ROOT",
      "nodeType": "root",
      "children": [
        { "nodeName": "AppClass1", "nodeType": "class" },
        {
          "nodeName": "App",
          "nodeType": "package",
          "children": [
            { "nodeName": "TestClass1", "nodeType": "class" }
          ]
        }
      ]
    }
  }
}
```

- `descr` 为明文描述
- `comment` 为 **JSON 转义** 的长注释（来自 PSPACKAGEDEFN.DESCRLONG），JSON 解析后即为原文
- `packageTree` 为递归树结构，`nodeType` 取值：`"root"` / `"package"` / `"class"`

### 查看代码成功

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "peoplecode": "class TestClass1\\nend-class;",
    "classPath": "MY_ROOT:App:TestClass1"
  }
}
```

peoplecode 字段为 JSON 转义，JSON 解析后得到 PeopleCode 源码。

### 修改代码成功

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

### 失败

```json
{
  "code": -1,
  "message": "Application package MY_ROOT not found",
  "data": {}
}
```

## 注意事项

1. **packageRoot 必须精确匹配**，不模糊搜索，大小写敏感
2. **peoplecode 需 JSON 转义** — viewPeopleCode 返回的是 JSON 转义，modifyPeopleCode 传入时也需 JSON 转义。使用 `C_PORTAL_PKG:Util:CommonUtil.EscapeJSON` / `UnEscapeJSON`
3. **classPath 用 `:` 分隔** — 格式为 `包根:子包:类名`，从根包开始写
4. 仅 **Class** 有代码可查看/修改，Subpackage 无代码
5. PS_TOKEN 过期后需重新登录
