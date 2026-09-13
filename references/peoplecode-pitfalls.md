# PeopleCode 常见陷阱

本文件只收录会影响 PeopleSoft API 开发和 PeopleCode 修改结果的运行时/编译器行为。业务数据查询仍必须使用 `AI_QUERY_RECORD`，本文件不提供数据库连接或直接查询数据的方法。

## 类内私有方法调用

类内调用私有方法时使用 `%This.MethodName(...)`。直接写 `MethodName(...)` 可能被编译器当作未知函数。

```peoplecode
%This.BuildResponse();
```

## `Evaluate` 不支持任意嵌套

不要在 `When` 块内继续嵌套 `Evaluate`。需要更深层条件时使用 `If`：

```peoplecode
Evaluate &FieldType
When 2
   If &FieldLen <= 4 Then
      Return "SMALLINT";
   Else
      Return "INTEGER";
   End-If;
End-Evaluate;
```

## `Local` 声明位置

`Local` 变量声明放在方法体顶部，不要放在 `If`、`For` 或 `While` 块内部。

## `REM` 注释

`REM` 注释必须以分号结束，否则下一行代码可能被一起当作注释：

```peoplecode
REM 创建新代码;
&Value = "ok";
```

块注释 `/* ... */` 不需要额外分号。

## 修改 PeopleCode 后必须重新读取

`modifyPeopleCode` 返回成功不代表新代码已经编译并生效。上传后立即用 `viewPeopleCode` 重新读取，确认返回内容是预期版本；如果编译失败，保留服务器返回的错误位置和消息。

## `CreateRowset(Record.X)` 的初始行

`CreateRowset(Record.X)` 返回的独立 Rowset 初始包含一行空行。使用 `InsertRow` 构造多行数据时，第一次操作要明确是复用这行，还是在正确位置插入新行，避免留下未填充的首行。

## JsonObject 数字属性

某些 PeopleTools 环境中，`AddProperty(name, number)` 后使用 `GetNumber(name)` 读回可能得到 `0`。需要可靠传递的数字可以先作为字符串写入，再用 `Value(GetString(name))` 读回。

```peoplecode
&Obj.AddProperty("uniqueFlag", "1");
&Flag = Value(&Obj.GetString("uniqueFlag"));
```

客户端解析已有 JSON 字符串时，不要把这个现象误判为所有 JSON 数字都异常；以当前接口实测结果为准。

## JsonObject 跨方法传递

通过返回 JsonObject 在方法之间传递业务值时，属性可能在调用方读为空。需要稳定传值时优先使用明确的 `out` 参数或独立的基本类型返回值。

## 独立 Record 的字段赋值

在 Integration Broker handler 的独立上下文中，使用 `GetField` 比直接使用点号字段引用更稳定：

```peoplecode
&Rec.GetField(Field.FIELDNAME).Value = "x";
```

## `All()`/`Some()`/`None()` 的实参

这些函数不要直接接收带括号的方法调用结果。先保存到局部变量，再进行判断：

```peoplecode
Local string &Name = &Obj.GetString("name");
If &Name <> "" Then
   /* ... */
End-If;
```
