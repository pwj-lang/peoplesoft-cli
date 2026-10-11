# 应用包与类代码

REST：`AI_OPER_APP_PKG_POST.v1/`，此接口 URI 保留 `_POST`。公共认证与响应见 [安装说明](01-auth-api.md#公共调用规则)。根包首次创建仍需 AD；接口可读取目录、维护类代码、插入类和子包。

## 参数与操作

| 参数 | 说明 |
|---|---|
| packageRoot | 必填，精确根包名；搜索 definitionType=104 |
| operationType | 省略或 default=目录；viewPeopleCode、modifyPeopleCode、deletePeopleCode、insertClass、insertPackage |
| classPath | 除目录查询外必填；从根包开始，用 `:` 分隔，如 MY_ROOT:App:TestClass |
| peoplecode | 修改类的完整正文；旧接口需 EscapeJSON/UnEscapeJSON 编码，由 CLI 处理 |

```powershell
python scripts/peoplesoft_api.py app-pkg struct MY_ROOT
python scripts/peoplesoft_api.py app-pkg view-code MY_ROOT 'MY_ROOT:App:TestClass'
python scripts/peoplesoft_api.py app-pkg modify-code MY_ROOT 'MY_ROOT:App:TestClass' D:\AI_Workspace\tmp\class.pcode
```

直接 API 请求示例：

```json
{"packageRoot":"MY_ROOT","operationType":"insertClass","classPath":"MY_ROOT:App:TestClass"}
```

插入子包时 operationType 改为 insertPackage，classPath 为目标子包完整路径。名称区分大小写；仅 Class 有代码。

## 返回与验证

目录返回 descr、comment、lastUpdate、packageTree；树节点有 nodeName、nodeType（root/package/class）、children。comment 为编码的长描述。代码读取返回 classPath、programExists、peoplecode，CLI 解码并缓存 UTF-8 工作副本。

修改会编译并自动独立回读；失败保留错误位置和文本。空白正文被拒绝；delete-code 删除类程序，保留类定义。写后按 [Project 文档](11-oper-project-defn-api.md) 登记包节点和类的完整路径；编译约束见 [开发规范](development-standards.md#peoplecode-实现约束)。

## 删除类程序

```powershell
python scripts/peoplesoft_api.py app-pkg delete-code MY_ROOT 'MY_ROOT:App:TestClass' --project MY_PROJECT --dry-run
```

省略 `--dry-run` 执行删除；支持 `--output`。快照、独立回读与完整键迁移登记见 [删除流程](development-standards.md#peoplecode-真正删除)。
