# 门户注册表

REST：`AI_OPER_PORTAL_REGISTRY.v1/`；Operation：`AI_OPER_PORTAL_REGISTRY_POST`；kind=`portal`。操作已有 Portal 内的 Folder、CREF、CREF Link。Portal 实例创建、整份门户删除、文件夹删除（含空文件夹）、递归删除、专用 Fluid/主页/Pagelet 向导不开放。

精确键：PortalName、RefType（F=文件夹，C=内容；Link 也用 C）、name=ObjName。`--type folder/cref/link` 必须匹配现有内容类型。标签不能作为键。写前/读取现有对象检查 Portal API 的 Authorized；创建和移动检查目标父文件夹权限及循环。

```powershell
python scripts/peoplesoft_api.py portal struct PORTAL_ROOT_OBJECT --portal EMPLOYEE --type folder
python scripts/peoplesoft_api.py portal tree C_MY_FOLDER --portal EMPLOYEE
python scripts/peoplesoft_api.py portal validate C_MY_FOLDER --portal EMPLOYEE --type folder
python scripts/peoplesoft_api.py portal create C_MY_FOLDER --parent PORTAL_ROOT_OBJECT --label '自定义目录' --sequence 1000 --project MY_PROJECT
python scripts/peoplesoft_api.py portal create C_MY_DOCS --type cref --parent C_MY_FOLDER --label '文档' --url https://docs.oracle.com/ --public off --project MY_PROJECT
python scripts/peoplesoft_api.py portal move C_MY_DOCS --type cref --parent C_OTHER_FOLDER --project MY_PROJECT
python scripts/peoplesoft_api.py portal modify C_MY_DOCS --type cref --label '新标签' --sequence 20 --project MY_PROJECT
python scripts/peoplesoft_api.py portal set-attribute C_MY_DOCS --type cref --attribute C_NOTE --values '["第一项;第二项"]' --project MY_PROJECT
python scripts/peoplesoft_api.py portal delete-attribute C_MY_DOCS --type cref --attribute C_NOTE --project MY_PROJECT
python scripts/peoplesoft_api.py portal set-permission C_MY_DOCS --type cref --permission-list MY_PERMISSION --project MY_PROJECT
python scripts/peoplesoft_api.py portal set-permission C_MY_FOLDER --role MY_ROLE --cascade off --project MY_PROJECT
python scripts/peoplesoft_api.py portal delete-permission C_MY_DOCS --type cref --permission-list MY_PERMISSION --project MY_PROJECT
python scripts/peoplesoft_api.py portal delete C_MY_DOCS --type cref --project MY_PROJECT
```

复杂结构用 --file；通用规则见 [通用规则](12-service-defn-api.md#通用规则)。主要可写属性：PrntObjName（父目录）、SeqNum（顺序）、LabelName、Descr、IsPublic（0/1）、IsVisible（boolean）、URLLogical、CntPrvName（节点）、CrefUsageType、CrefURLType、CrefTemplateType、CrefStorageType、TemplateName、StorageName、URISeg1~4、EffectiveDate/CreationDate/ExpirationDate（字符串）、Product、Fluid、SmallFFOpt。IsLink 为派生类型，不用它作为创建 Link 的开关；键和根目录只读。

外部 URL CREF 使用 CrefUsageType=TARG、CrefURLType=UEXT、CrefStorageType=RMTE、URLLogical；不套门户模板时 CrefTemplateType=NONE。创建 CREF 默认初始化 TARG/RMTE/HTML，按实际展示需要覆盖模板类型。完全限定的外部 URL 不必填 PeopleSoft 节点。PeopleSoft Component URL 等复杂 CREF 应先读取同类定义，按当前环境节点和 URI 段明确配置；不能把菜单项保存当作门户注册完成。

panwx25 原生保存会拒绝同一门户中重复 URL 的 CREF 创建；需要第二个导航入口时应创建指向原 CREF 的 Link。原生 SaveNewDefn 返回失败不能按成功登记。被 Link 引用的 CREF 也不能直接删除，须先精确处理引用链接；不会自动连带删除其他导航对象。

Link 创建示例：

```json
{"properties":{"PrntObjName":"C_MY_FOLDER","LabelName":"文档链接","CrefUsageType":"LINK","LinksPortalName":"EMPLOYEE","LinksObjectName":"C_MY_DOCS"},"collections":{"Permission":[{"PermType":"P","PermName":"MY_PERMISSION","IsCascade":false}]}}
```

使用 `portal create C_MY_LINK --type link --file ... --project ...`；目标必须为存在的 CREF，不能链接另一个 Link。保存同步目标的 URL 类型、模板类型、存储类型和节点；URL 在片段标记之前加入 pslnkid=链接名称，避免重复 URL 校验造成 Link 更新失败。显式权限需按需要设置，不把目标权限自动当作链接权限。

| 集合 | 键 | 内容/语义 |
|---|---|---|
| Attr | AttrName | AttrNameDsply、Values（最多一个字符串的数组）；只替换该属性值，省略其他属性保留；[] 清空为 [""]，保留一个原生值行 |
| Permission | PermType + PermName | P=Permission List、R=Role，IsCascade；主体需存在，仅 Folder 可 cascade |
| InheritPermission | PermType + PermName | 只读继承权限，不可通过 delete-permission 清除 |
| ChildFldr/ChildCref | ObjName | 只读导航列表及 SeqNum；通过对应对象创建/移动/排序维护 |

`delete-attribute` 和 `delete-permission` 只删除完整键匹配的一项，拒绝缺失项。默认保留其他属性、角色、许可权和继承权限。不要全量复制 Permission 数组来暗中清除权限；新增/删除用局部操作。

**属性在 PIA 中是一个字符串**，多个逻辑值按需要以分号分隔，例如 `["第一项;第二项"]`。不能写成 `["第一项","第二项"]`：2.4.0 曾写入两条原生 AttrValue 行，单独读取 CREF 正常，但 PIA 展开它的 CREF Link 会导致应用服务器崩溃。2.4.1 的 CLI 和 PeopleCode 都在保存前拒绝多行值；清空保留一个空值行，删除整个属性用 delete-attribute。不要自动拼接所有业务属性；分号含义由使用该属性的代码决定。

`validate` 只读检查：先检查原生属性行和链接目标，再调用 PIA 使用的 Portal Registry API 读取 QualifiedURL 和 Links。文件夹检查直接包含的 CREF/Link，不递归证明整个门户有效；子目录要分别检查。返回 valid=false 时 CLI 以失败退出，并展示错误，不登记工程，也不修改权限。它补充 struct 的元数据回读，不能替代浏览器点击和目标系统部署验收。

底层使用已在 panwx25 验证的 `%metadata:PortalRegStructDefn` 管理器维护定义和导航，并用 Portal Registry API 检查访问权限。**普通 Folder/CREF 的 Portal API ParentName 是只读的**；不能赋值后宣称移动成功，更不能用删文件夹再重建代替移动。当前实现原生保存后回读对象和父导航，循环移动拒绝。dry-run 不调用具有立即写入效果的 InsertItem/DeleteItem。

Project=55，value1=PortalName、value2=F/C、value3=ObjName。tree 按 SeqNum/名称排序，递归最多 1000 个文件夹；遇到无权读取或循环报错。迁移门户权限及引用依赖仍应检查原生导出和目标环境，不因 API 保存成功宣称完整运行已验证。

[Oracle 8.60 Folder Properties](https://docs.oracle.com/cd/F70249_01/pt860pbr1/eng/pt/tpcr/FolderClassProperties-c07ff7.html)、[Portal Registry 示例](https://docs.oracle.com/cd/F70249_01/pt860pbr1/eng/pt/tpcr/PortalRegistryClassesExample-c07e73.html)。

属性单值字符串与分号示例见 [Oracle Portal AttributeValue.Value](https://docs.oracle.com/cd/E24150_01/pt851h2/eng/psbooks/tpcr/htm/tpcr31.htm)。
