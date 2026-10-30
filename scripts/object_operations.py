"""PeopleSoft 定义维护与列表命令；写入均使用已认证的 IB API。"""
import json
import time
from pathlib import Path

ENDPOINTS = {
    "service": "AI_OPER_SERVICE_DEFN.v1/",
    "service-op": "AI_OPER_SERVICE_OP.v1/",
    "menu": "AI_OPER_MENU_DEFN.v1/",
    "message-catalog": "AI_OPER_MESSAGE_CATALOG.v1/",
    "portal": "AI_OPER_PORTAL_REGISTRY.v1/",
    "html": "AI_OPER_HTML_DEFN.v1/",
    "stylesheet": "AI_OPER_STYLESHEET_DEFN.v1/",
    "ci": "AI_OPER_CI_DEFN.v1/",
}
KINDS = {"service": "service", "service-op": "operation", "menu": "menu",
         "message-catalog": "catalog", "portal": "portal", "html": "html",
         "stylesheet": "stylesheet", "ci": "ci"}
TYPES = {"service": 79, "operation": 80, "version": 82, "handler": 81,
         "routing": 83, "menu": 6, "catalog": 25, "portal": 55,
         "html": 51, "stylesheet": 50, "ci": 32}
READS = {"struct", "view", "exists", "view-code", "view-permission", "plan-delete", "plan-configure", "validate", "tree", "wsdl"}


def add_parsers(sub):
    common = ["list", "struct", "exists", "create", "modify"]
    for command, choices in {
        "service": common + ["wsdl", "plan-delete", "delete"],
        "service-op": common + ["delete", "delete-child", "plan-delete", "plan-configure", "view-permission", "set-permission", "configure-rest", "configure-soap", "validate"],
        "menu": common + ["delete-item", "view-code", "modify-code", "delete-code"],
        "message-catalog": ["list", "view", "struct", "exists", "create-set", "create", "modify", "delete"],
        "portal": common + ["validate", "tree", "move", "delete", "set-attribute", "delete-attribute", "set-permission", "delete-permission"],
        "html": common,
        "stylesheet": common,
        "ci": common + ["delete-item", "view-code", "modify-code", "delete-code"],
    }.items():
        p = sub.add_parser(command, help=f"读取、新增和修改 {command} 定义")
        p.add_argument("op", choices=choices)
        p.add_argument("name", nargs="?", default="", help="定义名；list 使用名称前缀，省略则列出全部；消息目录使用消息集号")
        p.add_argument("--limit", type=int, default=50, help="list 每页 1..200 条")
        p.add_argument("--after", default="", help="list 下一页：上次结果的 nextAfter")
        p.add_argument("--file", help="UTF-8 JSON 补丁文件；modify-code 使用 PeopleCode 文本")
        p.add_argument("--project", help="已确认的工作 Project；默认使用当前环境的活动项目")
        p.add_argument("--dry-run", action="store_true", help="验证并返回计划，不保存")
        p.add_argument("--snapshot", help="先前读取的 JSON 快照；状态变化时拒绝保存")
        p.add_argument("--output", help="将完整 JSON 结果保存到文件")
        if command in ("html", "stylesheet"):
            p.add_argument("--content-file", help="UTF-8 HTML/CSS 正文；允许显式空文件")
            p.add_argument("--descr", help="定义描述")
        if command == "service":
            p.add_argument("--operation", help="生成 WSDL 的所属 SOAP Operation")
            p.add_argument("--version", help="WSDL 使用的操作版本；默认使用该操作的默认版本")
            p.add_argument("--secure", action="store_true", help="WSDL 使用已配置的安全目标地址")
            p.add_argument("--wsdl-file", help="将生成的 WSDL XML 保存为 UTF-8 文件")
            p.add_argument("--endpoint", help="仅替换本次导出的 SOAP 地址，不修改服务器全局配置")
        if command == "service-op":
            p.add_argument("--kind", choices=["operation", "version", "handler", "routing"], default="operation")
            p.add_argument("--version")
            p.add_argument("--handler")
            p.add_argument("--effdt", default="1900-01-01")
            p.add_argument("--permission-list")
            p.add_argument("--access", choices=["full", "none"])
        elif command == "menu":
            p.add_argument("--bar")
            p.add_argument("--item")
        elif command == "message-catalog":
            p.add_argument("--number", type=int)
            p.add_argument("--language", help="独立翻译的 PeopleSoft 语言代码，例如 ENG；基准语言不传此选项")
            p.add_argument("--text")
            p.add_argument("--text-file")
            p.add_argument("--explanation-file")
            p.add_argument("--severity", choices=["Message", "Warning", "Error", "Cancel"])
            p.add_argument("--descr")
            p.add_argument("--descr-short")
        elif command == "portal":
            p.add_argument("--portal", default="EMPLOYEE")
            p.add_argument("--type", choices=["folder", "cref", "link"], default="folder")
            p.add_argument("--parent")
            p.add_argument("--label")
            p.add_argument("--sequence", type=int)
            p.add_argument("--url")
            p.add_argument("--public", choices=["on", "off"])
            p.add_argument("--attribute")
            p.add_argument("--values", help="仅一个字符串值的 JSON 数组；逻辑多值按属性语义用分号分隔")
            rights = p.add_mutually_exclusive_group()
            rights.add_argument("--permission-list")
            rights.add_argument("--role")
            p.add_argument("--cascade", choices=["on", "off"])


def _error(api, message):
    raise api.PSAPIError(message)


def _read_file(api, spec):
    try:
        return Path(spec).read_text(encoding="utf-8-sig")
    except (OSError, TypeError) as exc:
        _error(api, f"Cannot read UTF-8 file: {exc}")


def _document(api, spec):
    if not spec:
        return {}
    try:
        value = json.loads(_read_file(api, spec))
    except ValueError as exc:
        _error(api, f"Invalid JSON file: {exc}")
    if not isinstance(value, dict):
        _error(api, "The patch file must contain a JSON object.")
    return value


def _identity(api, args):
    kind = getattr(args, "kind", KINDS[args.cmd])
    keys = {"kind": kind, "name": args.name}
    if args.cmd == "message-catalog" and args.language:
        keys["language"] = args.language
        if args.number is not None:
            keys["messageNumber"] = args.number
        if args.op == "create-set":
            _error(api, "--language requires an existing base message; create-set maintains base messages only.")
        if args.op in ("create", "modify", "delete", "exists") and args.number is None:
            _error(api, "Translation operations require an exact --number.")
    if kind == "version":
        if not args.version:
            _error(api, "--version is required for version definitions.")
        keys["Versionname"] = args.version
    elif kind == "handler":
        if not args.handler:
            _error(api, "--handler is required for handler definitions.")
        keys["Handlername"] = args.handler
    elif kind == "routing":
        keys["Effdt"] = args.effdt
    elif kind == "portal":
        keys.update(PortalName=args.portal, RefType="F" if args.type == "folder" else "C")
    if args.cmd == "service-op" and args.op in ("set-permission", "view-permission"):
        if not args.permission_list:
            _error(api, "An existing --permission-list is required.")
        keys.update(kind="permission", permissionList=args.permission_list)
    return keys


def _patch(api, args):
    doc = _document(api, args.file) if args.op not in ("view-code", "modify-code", "delete-code") else {}
    unexpected = set(doc) - {"properties", "collections"}
    if unexpected:
        _error(api, f"Unknown patch sections: {sorted(unexpected)}; use properties and collections.")
    props = doc.setdefault("properties", {})
    colls = doc.setdefault("collections", {})
    if not isinstance(props, dict) or not isinstance(colls, dict):
        _error(api, "properties and collections must be JSON objects.")
    if any(v is None for v in props.values()):
        _error(api, "null is not a clearing operation; use an explicit supported value.")
    for name, rows in colls.items():
        if not isinstance(rows, list) or any(not isinstance(row, dict) or any(v is None for v in row.values()) for row in rows):
            _error(api, f"Collection {name} must be an array of non-null object patches.")
    if args.cmd in ("html", "stylesheet"):
        if args.content_file is not None:
            field = "ContStrData" if args.cmd == "html" else "ExtStyleSheetStr"
            if field in props:
                _error(api, f"{field} is supplied in both --file and --content-file.")
            props[field] = _read_file(api, args.content_file)
        if args.descr is not None:
            props["Descr"] = args.descr
    if args.cmd == "message-catalog":
        for attr, field in (("text", "text"), ("severity", "severity"), ("descr", "descr"), ("descr_short", "descrShort")):
            if getattr(args, attr) is not None:
                props[field] = getattr(args, attr)
        for attr, field in (("text_file", "text"), ("explanation_file", "explanation")):
            if getattr(args, attr):
                props[field] = _read_file(api, getattr(args, attr))
    if args.cmd == "portal":
        for attr, field in (("parent", "PrntObjName"), ("label", "LabelName"), ("sequence", "SeqNum"), ("url", "URLLogical")):
            if getattr(args, attr) is not None:
                props[field] = getattr(args, attr)
        if args.public is not None:
            props["IsPublic"] = int(args.public == "on")
        if args.op == "create" and args.type in ("cref", "link"):
            props.setdefault("CrefUsageType", "LINK" if args.type == "link" else "TARG")
            if args.url:
                props.setdefault("CrefURLType", "UEXT")
        if args.op == "move" and not args.parent:
            _error(api, "move requires --parent.")
        if args.op in ("set-attribute", "delete-attribute"):
            if not args.attribute:
                _error(api, "--attribute is required.")
            row = {"AttrName": args.attribute}
            if args.op == "set-attribute":
                try:
                    values = json.loads(args.values or "null")
                except ValueError:
                    _error(api, "--values must be a JSON array of strings.")
                if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
                    _error(api, "--values must be a JSON array of strings.")
                row["Values"] = values
            colls["Attr"] = [row]
        for attribute in colls.get("Attr", []):
            if "Values" in attribute:
                values = attribute["Values"]
                if not isinstance(values, list) or any(not isinstance(v, str) for v in values) or len(values) > 1:
                    _error(api, "Portal attributes require zero or one string in Values for PIA compatibility; use one semicolon-separated string for multiple logical values.")
                attribute["Values"] = values or [""]
        if args.op in ("set-permission", "delete-permission"):
            name = args.permission_list or args.role
            if not name:
                _error(api, "Provide --permission-list or --role.")
            row = {"PermType": "P" if args.permission_list else "R", "PermName": name}
            if args.cascade is not None:
                if args.type != "folder" and args.cascade == "on":
                    _error(api, "Permission cascade applies only to folders.")
                row["IsCascade"] = args.cascade == "on"
            colls["Permission"] = [row]
    if args.cmd == "menu" and args.op == "delete-item":
        if not args.bar or not args.item:
            _error(api, "delete-item requires exact --bar and --item.")
        colls["Mit"] = [{"BarName": args.bar, "ItemName": args.item}]
    if args.cmd == "menu":
        for row in colls.get("Mit", []):
            unsupported = set(row) & {"AllowedActions", "AddSearchRecName"}
            if unsupported:
                _error(api, f"Menu properties are read-only in the native API: {sorted(unsupported)}.")
    return {k: v for k, v in doc.items() if v}


def _project(api, args):
    name = args.project or api._active_project()
    if not name:
        _error(api, "Choose a confirmed --project or run project use before writing.")
    return name, api._require_project(name)


def _project_values(keys, result, code=False):
    kind = keys["kind"]
    values = [keys["name"]]
    if code:
        if kind == "ci":
            return 42, values + ["Methods"]
        return 9, values + [keys["BarName"], keys["ItemName"], "ItemSelected"]
    if kind == "permission":
        # Permission List security rows are data, not AD Project definitions.
        return 80, values
    if kind == "version":
        values.append(keys["Versionname"])
    elif kind == "handler":
        values.append(keys["Handlername"])
    elif kind == "routing":
        values.append(keys["Effdt"])
    elif kind == "catalog":
        values.append(str(result["messageNumber"]))
    elif kind == "portal":
        values = [keys["PortalName"], keys["RefType"], keys["name"]]
    elif kind == "html":
        values.append("4")
    return TYPES[kind], values


def _register(api, project, typ, values, deleted=False):
    api._insert_project_item(project, typ, values, action=1 if deleted else 0, take_action=1)


def _verify(api, actual, patch, deleted_child=False):
    for name, expected in patch.get("properties", {}).items():
        if actual.get(name) != expected:
            _error(api, f"Saved property differs: {name}; expected {expected!r}, received {actual.get(name)!r}.")
    child_keys = {"Mit": ("BarName", "ItemName"), "Serviceopr": ("Operationname",),
        "Operationuritemplate": ("URISeq",), "Operationhandler": ("Handlername",),
        "Operationversion": ("Versionname",), "Oprverdfnparm": ("Parametername",),
        "Oprvgenrtgparm": ("Parametername",), "Operationac": ("Classname",),
        "Ibrtngsubdefn": ("Seqnum",), "Rtngdfnparm": ("Parametername",),
        "Attr": ("AttrName",), "Permission": ("PermType", "PermName"), "Pit": ("Seq",)}
    for collection, rows in patch.get("collections", {}).items():
        if collection not in child_keys:
            _error(api, f"No verification schema for {collection}.")
        for row in rows:
            names = child_keys[collection]
            found = [r for r in actual.get(collection, []) if all(r.get(k) == row.get(k) for k in names)]
            if deleted_child:
                if found:
                    _error(api, f"Deleted child still exists: {collection} {row}.")
            elif len(found) != 1 or any(found[0].get(k) != v for k, v in row.items()):
                _error(api, f"Saved child differs: {collection} {row}.")


def _output(api, args, result):
    result.setdefault("environment", api.ENVIRONMENT)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        path = Path(args.output).resolve()
        api._write_json_atomic(path, result)
    print(text)
    return result


def _write_wsdl(api, args, result):
    """Export native WSDL and its message schemas without changing IB settings."""
    import re
    from urllib.parse import urlsplit
    from xml.dom import minidom
    doc = minidom.parseString(result["wsdl"])
    if args.endpoint:
        url = urlsplit(args.endpoint)
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
            _error(api, "--endpoint requires an HTTP(S) URL without embedded credentials.")
        for node in doc.getElementsByTagNameNS("http://schemas.xmlsoap.org/wsdl/soap/", "address"):
            node.setAttribute("location", args.endpoint)
    if args.wsdl_file:
        path = Path(args.wsdl_file).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        schemas = {}
        for schema in result.get("schemas", []):
            key = schema["namespace"]
            if key in schemas and schemas[key] != schema["xml"]:
                _error(api, "Different message schemas share one namespace; export requires distinct namespaces.")
            schemas[key] = schema["xml"]
        exported = {}
        for index, (namespace, xml) in enumerate(schemas.items(), 1):
            minidom.parseString(xml)
            filename = re.sub(r"[^A-Za-z0-9_.-]", "_", path.stem) + f".schema-{index}.xsd"
            (path.parent / filename).write_text(xml, encoding="utf-8")
            exported[namespace] = filename
        for node in doc.getElementsByTagNameNS("http://www.w3.org/2001/XMLSchema", "import"):
            if node.getAttribute("namespace") in exported:
                node.setAttribute("schemaLocation", exported[node.getAttribute("namespace")])
        result["schemaFiles"] = list(exported.values())
        result["wsdlPath"] = str(path)
        result["wsdl"] = doc.toxml()
        path.write_text(result["wsdl"], encoding="utf-8")
    elif args.endpoint:
        result["wsdl"] = doc.toxml()


def _catalog_verify(api, args, result, patch, actual):
    props = patch.get("properties", {})
    for field in ("descr", "descrShort"):
        if field in props and actual.get(field) != props[field]:
            _error(api, f"Message set {field} readback differs.")
    number = result["messageNumber"]
    if number:
        rows = [r for r in actual["messages"] if r["messageNumber"] == number]
        if args.language:
            before = result["before"]
            def base_state(snapshot):
                return {"descr": snapshot["descr"], "descrShort": snapshot["descrShort"],
                    "messages": [{k:r[k] for k in ("messageNumber", "baseText", "baseExplanation", "severity")}
                                 for r in snapshot["messages"]]}
            def other_translations(snapshot):
                return [r for r in snapshot["allTranslations"]
                        if (r["messageNumber"], r["language"]) != (number, args.language)]
            if base_state(before) != base_state(actual) or other_translations(before) != other_translations(actual):
                _error(api, "Base messages or other translations changed during translation save; inspect current state.")
            if len(rows) != 1 or rows[0]["translationExists"] != (args.op != "delete"):
                _error(api, "Translation existence readback differs; the base message must remain present.")
            if args.op != "delete" and any(rows[0].get(k) != v for k, v in props.items()):
                _error(api, "Translation text/explanation readback differs.")
            return
        if args.op == "delete":
            if rows:
                _error(api, "Deleted message still exists.")
        else:
            expected = {k: v for k, v in props.items() if k in ("text", "explanation", "severity")}
            if "severity" in expected:
                expected["severity"] = {"Message": "M", "Warning": "W", "Error": "E", "Cancel": "C"}[expected["severity"]]
            if len(rows) != 1 or any(rows[0].get(k) != v for k, v in expected.items()):
                _error(api, "Message readback differs from the requested text/severity.")


def _require_translation_snapshot(api, language, snapshot):
    if (snapshot.get("language") != language or not snapshot.get("baseLanguage")
            or snapshot["baseLanguage"] == language
            or not isinstance(snapshot.get("allTranslations"), list)
            or not isinstance(snapshot.get("messages"), list)
            or any(not all(k in row for k in ("baseText", "baseExplanation", "severity"))
                   or type(row.get("translationExists")) is not bool for row in snapshot["messages"])):
        _error(api, "Server/snapshot lacks independent translation support; deploy the complete dev.4 server project before using --language.")


class _WriteJournal:
    """记录已收到响应的写请求；失败时不猜测回滚、不自动重试。"""
    def __init__(self, api):
        self._api = api
        self.completed = []
        self.current = None
        self.attempted = False
        self.project = None
        self.snapshots = []

    def __getattr__(self, name):
        return getattr(self._api, name)

    def _api_call(self, endpoint, payload):
        action = payload.get("operationType", "view")
        if payload.get("projectName"):
            self.project = payload["projectName"]
        reads = {"view", "struct", "exists", "viewCode", "validate", "wsdl"}
        writing = action not in reads and not payload.get("dryRun")
        identity = {k:payload[k] for k in ("kind", "name", "Versionname", "Handlername", "Effdt",
            "PortalName", "RefType", "permissionList", "messageNumber", "language", "BarName", "ItemName", "projectName",
            "objectType", *[f"objectId{i}" for i in range(1,5)], *[f"objectValue{i}" for i in range(1,5)]) if k in payload}
        if writing:
            self.attempted = True
        self.current = dict(endpoint=endpoint, operationType=action, keys=identity,
            phase="projectRegistration" if endpoint == "AI_OPER_PROJECT_DEFN.v1/" else "save" if writing else "readback",
            outcome="unknown")
        result = self._api._api_call(endpoint, payload)
        if writing:
            self.current["outcome"] = "acknowledged"
            self.completed.append(dict(self.current))
        else:
            self.current["outcome"] = "returned"
        return result


def execute(api, args):
    if args.op in READS or args.op == "list" or args.dry_run:
        return _execute(api, args)
    journal = _WriteJournal(api)
    errors = (api.PSAPIError, getattr(api, "PSAuthError", api.PSAPIError))
    try:
        return _execute(journal, args)
    except errors as exc:
        if args.cmd in ("ci", "menu", "html", "stylesheet", "service", "service-op", "message-catalog", "portal") and getattr(exc, "code", None) == 409 and not journal.completed:
            raise
        if journal.attempted:
            report = dict(environment=api.ENVIRONMENT, verified=False, status="incomplete",
                workflow=f"{args.cmd} {args.op}", name=args.name, project=journal.project or args.project,
                completedWrites=journal.completed, lastRequest=journal.current,
                recoverySnapshots=journal.snapshots,
                error=str(exc), recovery="先独立回读目标定义、关联和 Project；确认已保存状态后，只补做未完成步骤。未自动回滚或重试；acknowledged 仅表示收到写入响应，不表示全部验收通过。")
            try:
                _output(api, args, report)
            except (OSError, api.PSAPIError) as output_error:
                _error(api, f"{exc}; recovery report could not be written: {output_error}")
            if args.cmd in ("ci", "menu", "html", "stylesheet", "service", "service-op", "message-catalog", "portal") and getattr(exc, "code", None) == 409:
                raise api.PSAPIError(f"{exc}; workflow incomplete; inspect completedWrites and lastRequest before continuing.",
                                     code=409, hint=getattr(exc, "hint", None)) from exc
            _error(api, f"{exc}; workflow incomplete; inspect completedWrites and lastRequest before continuing.")
        raise


def _execute(api, args):
    if args.op == "list":
        if args.cmd == "service-op" and args.kind != "operation":
            _error(api, "service-op list 只列出操作；版本、Handler 和 Routing 请读取所属操作的 struct。")
        if not 1 <= args.limit <= 200 or len(args.name) > 30 or len(args.after) > 30:
            _error(api, "list 的 limit 须为 1..200；前缀和 after 最多 30 字符。")
        payload = dict(kind=KINDS[args.cmd], prefix=args.name, limit=args.limit, after=args.after)
        if args.cmd == "portal":
            payload.update(PortalName=args.portal, RefType="F" if args.type=="folder" else "C")
            if args.type != "folder":
                payload["IsLink"] = args.type == "link"
        return _output(api, args, api._api_call("AI_LIST_DEFN.v1/", payload))
    if not args.name:
        _error(api, "此操作需要明确的定义名称。")
    if args.cmd in ("service", "service-op", "message-catalog", "portal"):
        from managed_operations import handle
        return handle(api, args)
    if args.cmd == "ci":
        from ci_operations import handle
        return handle(api, args)
    if args.cmd == "menu":
        from menu_operations import handle
        return handle(api, args)
    if args.cmd in ("html", "stylesheet"):
        from content_operations import handle
        return handle(api, args)
    raise api.PSAPIError('Unsupported definition command; a versioned handler is required.')


def _query_rows(api, data):
    fields = [r["name"] for r in data.get("fields", [])]
    for row in data.get("rows", []):
        values = row.get("v", [])
        if len(values) != len(fields):
            _error(api, "Query-record returned an incomplete routing row.")
        yield dict(zip(fields, values))


def _verify_service_membership(api, name, service, present=True):
    state = api._api_call(ENDPOINTS["service"], dict(kind="service", name=service, operationType="view"))
    found = any(row["Operationname"] == name for row in state["Serviceopr"])
    if found != present:
        _error(api, f"Service {service} membership readback failed for {name}; PIA visibility is not verified.")
    return state


def _validate_rest(api, args, keys, call):
    if keys["kind"] != "operation":
        _error(api, "validate requires --kind operation.")
    operation = call("view")
    issues = []
    endpoint = ENDPOINTS["service-op"]
    protocol = operation["RestService"]
    if protocol not in (0, 2) or operation["Rtngtype"] != "S":
        issues.append("Operation must be synchronous SOAP or REST Provider.")
    if protocol == 2 and not operation["Operationuritemplate"]:
        issues.append("No URI templates.")
    if protocol == 0 and (operation["Operationuritemplate"] or operation["Restmethod"]):
        issues.append("SOAP operation contains REST method/URI settings.")
    service = None
    service_keys = dict(kind="service", name=operation["Servicename"])
    if not service_keys["name"] or not api._api_call(ENDPOINTS["service"], dict(service_keys, operationType="exists"))["exists"]:
        issues.append("Parent service is missing.")
    else:
        service = api._api_call(ENDPOINTS["service"], dict(service_keys, operationType="view"))
        if service["RestService"] != protocol:
            issues.append("Parent service protocol differs.")
        if not any(row["Operationname"] == args.name for row in service["Serviceopr"]):
            issues.append("Operation is absent from its parent service; PIA search and permission grouping cannot find it.")
    version_name = args.version or operation["Defaultversion"]
    version_keys = dict(kind="version", name=args.name, Versionname=version_name)
    version = None
    if not version_name or not api._api_call(endpoint, dict(version_keys, operationType="exists"))["exists"]:
        issues.append("Default/selected version is missing.")
    else:
        version = api._api_call(endpoint, dict(version_keys, operationType="view"))
        if version["Active_flag"] != "A":
            issues.append("Version is inactive.")
        if not version["Oprverdfnparm"]:
            issues.append("No version message bindings.")
        if protocol == 0 and not {"REQUEST", "RESPONSE"} <= {r["Parametername"] for r in version["Oprverdfnparm"]}:
            issues.append("Synchronous SOAP requires REQUEST and RESPONSE messages.")
        if not version["Oprvgenrtgparm"]:
            issues.append("No version routing bindings.")
    handlers = []
    for row in operation["Operationhandler"]:
        k = dict(kind="handler", name=args.name, Handlername=row["Handlername"])
        if api._api_call(endpoint, dict(k, operationType="exists"))["exists"]:
            handlers.append(api._api_call(endpoint, dict(k, operationType="view")))
    if not any(h["Active_flag"] == "A" and h["Handlerid"] == "RQST" and h["Operationac"] for h in handlers):
        issues.append("No active Application Class request handler.")
    routes = []
    data = api._api_call("AI_QUERY_RECORD.v1/", dict(record="PSIBRTNGDEFN", fields=["ROUTINGDEFNNAME", "EFFDT"],
        filter=[dict(field="IB_OPERATIONNAME", op="=", value=args.name)], maxRows=1000))
    for item in _query_rows(api, data):
        k = dict(kind="routing", name=item["ROUTINGDEFNNAME"], Effdt=str(item["EFFDT"])[:10])
        routes.append(api._api_call(endpoint, dict(k, operationType="view")))
    if not any(r["Eff_status"] == "A" and r["Operationversion"] == version_name for r in routes):
        issues.append("No active route for the selected version.")
    permissions = None
    if args.permission_list:
        permissions = api._api_call(endpoint, dict(kind="permission", name=args.name,
            permissionList=args.permission_list, operationType="view"))
        if permissions["access"] != 4:
            issues.append("Selected Permission List lacks full operation access.")
    result = dict(valid=not issues, issues=issues, service=service, operation=operation, version=version,
                  handlers=handlers, routes=routes, permission=permissions,
                  validation="Definition checks only; this command does not invoke the business endpoint.")
    _output(api, args, result)
    if issues:
        _error(api, "Service operation validation failed; inspect issues in the JSON result.")


def _delete_operation(api, args, keys, call):
    if keys["kind"] != "operation":
        _error(api, "plan-delete requires --kind operation.")
    endpoint = ENDPOINTS["service-op"]
    operation = call("view")
    if args.snapshot:
        snapshot = _document(api, args.snapshot)
        if snapshot.get("environment") not in (None, api.ENVIRONMENT) or snapshot.get("stateToken") != operation["stateToken"]:
            _error(api, "Operation differs from --snapshot; read and review the deletion plan again.")
    plan = []
    routes = {}
    for row in operation["Operationversion"]:
        k = dict(kind="version", name=args.name, Versionname=row["Versionname"])
        if api._api_call(endpoint, dict(k, operationType="exists"))["exists"]:
            view = api._api_call(endpoint, dict(k, operationType="view"))
            for route in view["Oprvgenrtgparm"]:
                name = route["Routingdefnname"]
                if name:
                    # Routing keys require every effective date, retrieved read-only.
                    data = api._api_call("AI_QUERY_RECORD.v1/", dict(record="PSIBRTNGDEFN", fields=["ROUTINGDEFNNAME", "EFFDT"],
                        filter=[dict(field="ROUTINGDEFNNAME", op="=", value=name)], maxRows=100))
                    for item in _query_rows(api, data):
                        rk = dict(kind="routing", name=name, Effdt=str(item["EFFDT"])[:10])
                        rv = api._api_call(endpoint, dict(rk, operationType="view"))
                        if rv["Operationname"] != args.name:
                            _error(api, f"Routing {name} belongs to a different operation; deletion stopped.")
                        routes[(name, rk["Effdt"])] = dict(keys=rk, before=rv)
            plan.append(dict(keys=k, before=view))
    for row in operation["Operationhandler"]:
        k = dict(kind="handler", name=args.name, Handlername=row["Handlername"])
        if api._api_call(endpoint, dict(k, operationType="exists"))["exists"]:
            plan.append(dict(keys=k, before=api._api_call(endpoint, dict(k, operationType="view"))))
    # Read all routes owned by this operation, including non-generated routes.
    data = api._api_call("AI_QUERY_RECORD.v1/", dict(record="PSIBRTNGDEFN", fields=["ROUTINGDEFNNAME", "EFFDT"],
        filter=[dict(field="IB_OPERATIONNAME", op="=", value=args.name)], maxRows=1000))
    for item in _query_rows(api, data):
        rk = dict(kind="routing", name=item["ROUTINGDEFNNAME"], Effdt=str(item["EFFDT"])[:10])
        routes[(rk["name"], rk["Effdt"])] = dict(keys=rk, before=api._api_call(endpoint, dict(rk, operationType="view")))
    if data.get("rowCount", 0) >= 1000:
        _error(api, "Routing scan reached its limit; no deletion was performed.")
    plan = list(routes.values()) + plan + [dict(keys=keys, before=operation)]
    result = dict(environment=api.ENVIRONMENT, dryRun=True, deletePlan=plan,
                  preserved="Shared Message definitions and Application Classes are preserved.")
    if args.op == "plan-delete":
        return _output(api, args, result)
    from managed_operations import workflow
    return workflow(api, args, endpoint, keys)


def _configure_rest(api, args):
    from managed_operations import workflow
    return workflow(api, args, ENDPOINTS['service-op'], dict(kind='operation', name=args.name))
