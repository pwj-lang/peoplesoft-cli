"""服务、菜单、消息目录与门户命令；写入均使用已认证的 IB API。"""
import json
from pathlib import Path

ENDPOINTS = {
    "service": "AI_OPER_SERVICE_DEFN.v1/",
    "service-op": "AI_OPER_SERVICE_OP.v1/",
    "menu": "AI_OPER_MENU_DEFN.v1/",
    "message-catalog": "AI_OPER_MESSAGE_CATALOG.v1/",
    "portal": "AI_OPER_PORTAL_REGISTRY.v1/",
}
KINDS = {"service": "service", "service-op": "operation", "menu": "menu",
         "message-catalog": "catalog", "portal": "portal"}
TYPES = {"service": 79, "operation": 80, "version": 82, "handler": 81,
         "routing": 83, "menu": 6, "catalog": 25, "portal": 55}
READS = {"struct", "view", "exists", "view-code", "view-permission", "plan-delete", "validate", "tree"}


def add_parsers(sub):
    common = ["struct", "exists", "create", "modify"]
    for command, choices in {
        "service": common,
        "service-op": common + ["delete", "delete-child", "plan-delete", "view-permission", "set-permission", "configure-rest", "validate"],
        "menu": common + ["delete-item", "view-code", "modify-code", "delete-code"],
        "message-catalog": ["view", "struct", "exists", "create-set", "create", "modify", "delete"],
        "portal": common + ["validate", "tree", "move", "delete", "set-attribute", "delete-attribute", "set-permission", "delete-permission"],
    }.items():
        p = sub.add_parser(command, help=f"读取、新增和修改 {command} 定义")
        p.add_argument("op", choices=choices)
        p.add_argument("name", help="定义名；message-catalog 使用消息集号")
        p.add_argument("--file", help="UTF-8 JSON 补丁文件；modify-code 使用 PeopleCode 文本")
        p.add_argument("--project", help="已确认的工作 Project；默认使用当前环境的活动项目")
        p.add_argument("--dry-run", action="store_true", help="验证并返回计划，不保存")
        p.add_argument("--snapshot", help="先前读取的 JSON 快照；状态变化时拒绝保存")
        p.add_argument("--output", help="将完整 JSON 结果保存到文件")
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
    return name, api._api_call("AI_OPER_PROJECT_DEFN.v1/", {"projectName": name, "operationType": "struct"})


def _project_values(keys, result, code=False):
    kind = keys["kind"]
    values = [keys["name"]]
    if code:
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
    return TYPES[kind], values


def _register(api, project, typ, values, deleted=False):
    def read():
        return api._api_call("AI_OPER_PROJECT_DEFN.v1/", {"projectName": project, "operationType": "struct"})["items"]
    padded = values + [""] * (4 - len(values))
    def match(items):
        return [x for x in items if int(x["objectType"]) == typ and
                [(x.get(f"objectValue{i}") or "").rstrip() for i in range(1, 5)] == padded]
    matches = match(read())
    if len(matches) > 1:
        _error(api, "Ambiguous Project item; inspect native IDs before continuing.")
    if not matches:
        api._api_call("AI_OPER_PROJECT_DEFN.v1/", dict(projectName=project, operationType="insertItem",
            objectType=typ, takeAction=1, upgradeAction=1 if deleted else 0,
            **{f"objectValue{i + 1}": v for i, v in enumerate(padded)}))
        matches = match(read())
    if len(matches) != 1:
        _error(api, "Saved definition could not be registered in the work Project.")
    row = matches[0]
    flags = {"copyDone": 0}
    if deleted:
        flags.update(upgradeAction=1, takeAction=1)
    elif row.get("upgradeAction") == 1:
        # A recreated definition must no longer be marked for deletion.
        flags["upgradeAction"] = 0
    if any(row.get(k) != v for k, v in flags.items()):
        api._api_call("AI_OPER_PROJECT_DEFN.v1/", dict(projectName=project, operationType="updateItem",
            objectType=typ, **flags,
            **{f"objectId{i}": row[f"objectId{i}"] for i in range(1, 5)},
            **{f"objectValue{i}": row[f"objectValue{i}"] for i in range(1, 5)}))
        after = match(read())
        if len(after) != 1 or any(after[0].get(k) != v for k, v in flags.items()):
            _error(api, "Project migration flag readback failed.")


def _verify(api, actual, patch, deleted_child=False):
    for name, expected in patch.get("properties", {}).items():
        if actual.get(name) != expected:
            _error(api, f"Saved property differs: {name}; expected {expected!r}, received {actual.get(name)!r}.")
    child_keys = {"Mit": ("BarName", "ItemName"), "Serviceopr": ("Operationname",),
        "Operationuritemplate": ("URISeq",), "Operationhandler": ("Handlername",),
        "Operationversion": ("Versionname",), "Oprverdfnparm": ("Parametername",),
        "Oprvgenrtgparm": ("Parametername",), "Operationac": ("Classname",),
        "Ibrtngsubdefn": ("Seqnum",), "Rtngdfnparm": ("Parametername",),
        "Attr": ("AttrName",), "Permission": ("PermType", "PermName")}
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


def _catalog_verify(api, args, result, patch, actual):
    props = patch.get("properties", {})
    for field in ("descr", "descrShort"):
        if field in props and actual.get(field) != props[field]:
            _error(api, f"Message set {field} readback differs.")
    number = result["messageNumber"]
    if number:
        rows = [r for r in actual["messages"] if r["messageNumber"] == number]
        if args.op == "delete":
            if rows:
                _error(api, "Deleted message still exists.")
        else:
            expected = {k: v for k, v in props.items() if k in ("text", "explanation", "severity")}
            if "severity" in expected:
                expected["severity"] = {"Message": "M", "Warning": "W", "Error": "E", "Cancel": "C"}[expected["severity"]]
            if len(rows) != 1 or any(rows[0].get(k) != v for k, v in expected.items()):
                _error(api, "Message readback differs from the requested text/severity.")


def execute(api, args):
    if args.cmd == "service-op" and args.op == "configure-rest":
        return _configure_rest(api, args)
    keys = _identity(api, args)
    endpoint = ENDPOINTS[args.cmd]
    def call(action, **extra):
        return api._api_call(endpoint, dict(keys, operationType=action, **extra))
    if args.op == "validate":
        if args.cmd == "portal":
            result = call("validate")
            _output(api, args, result)
            if not result.get("valid"):
                _error(api, "Portal runtime validation failed; see the returned object errors.")
            return result
        return _validate_rest(api, args, keys, call)
    if args.op == "tree":
        if args.type != "folder":
            _error(api, "tree requires --type folder.")
        visited = set()
        def walk(name):
            if name in visited or len(visited) >= 1000:
                _error(api, "Portal tree contains a cycle or exceeds 1000 folders.")
            visited.add(name)
            view = api._api_call(endpoint, dict(keys, name=name, operationType="view"))
            return dict(name=name, label=view["LabelName"], sequence=view["SeqNum"],
                folders=[walk(r["ObjName"]) for r in sorted(view["ChildFldr"], key=lambda r: (r["SeqNum"], r["ObjName"]))],
                content=sorted(view["ChildCref"], key=lambda r: (r["SeqNum"], r["ObjName"])))
        return _output(api, args, dict(portal=args.portal, tree=walk(args.name)))
    if args.op == "plan-delete" or (args.cmd == "service-op" and args.op == "delete" and args.kind == "operation"):
        return _delete_operation(api, args, keys, call)
    code = args.op in ("view-code", "modify-code", "delete-code")
    if code:
        if not args.bar or not args.item:
            _error(api, "Menu PeopleCode requires exact --bar and --item; event is ItemSelected.")
        keys.update(BarName=args.bar, ItemName=args.item)
    if args.op in READS:
        result = call("viewCode" if code else "exists" if args.op == "exists" else "view")
        if args.cmd == "message-catalog" and args.number is not None and args.op != "exists":
            result["messages"] = [r for r in result["messages"] if r["messageNumber"] == args.number]
            if not result["messages"]:
                _error(api, "The requested message number does not exist.")
        if code:
            path = api._cache_artifact(f"{args.name}_{args.bar}_{args.item}_ItemSelected", ".pcode", result["peoplecode"])
            result["cachePath"] = str(path)
        return _output(api, args, result)
    project, _ = _project(api, args)
    creating = args.op == "create-set" or (args.op == "create" and keys["kind"] != "catalog")
    before = call("exists") if creating else call("viewCode" if code else "view")
    if creating and before["exists"]:
        _error(api, "Definition already exists; use modify.")
    snapshot = _document(api, args.snapshot) if args.snapshot else before
    if args.snapshot and snapshot.get("environment") not in (None, api.ENVIRONMENT):
        _error(api, "The snapshot belongs to another environment.")
    action = {"create-set": "createSet", "delete-item": "deleteChild", "delete-child": "deleteChild",
        "set-attribute": "modify", "delete-attribute": "deleteChild",
        "set-permission": "modify", "delete-permission": "deleteChild", "move": "modify",
        "modify-code": "modifyCode", "delete-code": "deleteCode"}.get(args.op, args.op)
    patch = _patch(api, args)
    if keys["kind"] == "catalog" and args.op == "modify" and args.number is None and set(patch.get("properties", {})) & {"text", "explanation", "severity"}:
        _error(api, "Message text/explanation/severity modification requires --number.")
    if keys["kind"] == "portal" and not creating and args.type != "folder" and before.get("IsLink") != (args.type == "link"):
        _error(api, "--type does not match the saved CREF/Link definition.")
    payload = dict(patch, dryRun=args.dry_run)
    item_code = None
    if args.cmd == "menu" and args.op == "delete-item" and before.get("Menutype") == 1:
        item_code = call("viewCode", BarName=args.bar, ItemName=args.item)
    if not creating:
        if code:
            payload["expectedCode"] = snapshot["peoplecode"]
        else:
            if not snapshot.get("stateToken"):
                _error(api, "Snapshot lacks stateToken; read it with the 2.4 endpoint first.")
            payload["expectedState"] = snapshot["stateToken"]
    if args.cmd == "message-catalog" and args.number is not None:
        payload["messageNumber"] = args.number
    if args.cmd == "service-op" and args.op == "set-permission":
        if not args.access:
            _error(api, "set-permission requires --access full|none.")
        payload["access"] = 4 if args.access == "full" else 0
    if code and args.op == "modify-code":
        if not args.file:
            _error(api, "modify-code requires --file.")
        payload["peoplecode"] = _read_file(api, args.file)
    if not patch and action in ("modify", "deleteChild") and keys["kind"] != "permission":
        _error(api, "No changes supplied; use --file or the named property options.")
    result = call(action, **payload)
    if not args.dry_run:
        if code:
            actual = call("viewCode")
            if args.op == "delete-code":
                if actual["exists"]:
                    _error(api, "Deleted Menu PeopleCode still exists.")
            elif api._peoplecode_signature(actual["peoplecode"]) != api._peoplecode_signature(payload["peoplecode"]):
                _error(api, "Menu PeopleCode readback differs.")
        elif action == "delete" and keys["kind"] != "catalog":
            if call("exists")["exists"]:
                _error(api, "Deleted definition still exists.")
        else:
            actual = call("view")
            if keys["kind"] == "catalog":
                _catalog_verify(api, args, result, patch, actual)
            elif keys["kind"] == "permission":
                if actual["access"] != payload["access"]:
                    _error(api, "Operation permission readback differs.")
            else:
                _verify(api, actual, patch, action == "deleteChild")
        if keys["kind"] == "catalog" and result["messageNumber"] == 0:
            for row in result["after"]["messages"]:
                _register(api, project, 25, [args.name, str(row["messageNumber"])])
        else:
            typ, values = _project_values(keys, result, code)
            _register(api, project, typ, values, action in ("delete", "deleteCode"))
        if keys["kind"] == "operation":
            _verify_service_membership(api, args.name, actual["Servicename"])
            for service in {before.get("Servicename"), actual["Servicename"]} - {None, ""}:
                if service != actual["Servicename"]:
                    _verify_service_membership(api, args.name, service, present=False)
                _register(api, project, TYPES["service"], [service])
        result.update(verified=True, project=project)
        if item_code and item_code["exists"]:
            _register(api, project, 9, [args.name, args.bar, args.item, "ItemSelected"], True)
    result["environment"] = api.ENVIRONMENT
    return _output(api, args, result)


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
    if operation["RestService"] != 2 or operation["Rtngtype"] != "S":
        issues.append("Operation must be synchronous REST Provider.")
    if not operation["Operationuritemplate"]:
        issues.append("No URI templates.")
    service = None
    service_keys = dict(kind="service", name=operation["Servicename"])
    if not service_keys["name"] or not api._api_call(ENDPOINTS["service"], dict(service_keys, operationType="exists"))["exists"]:
        issues.append("Parent service is missing.")
    else:
        service = api._api_call(ENDPOINTS["service"], dict(service_keys, operationType="view"))
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
        _error(api, "REST definition validation failed; inspect issues in the JSON result.")


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
    project, _ = _project(api, args)
    if args.dry_run:
        return _output(api, args, result)
    completed = []
    for target in plan:
        k = target["keys"]
        # Previous child deletion can update derived parent references. All other
        # properties must still match the reviewed plan before proceeding.
        current = api._api_call(endpoint, dict(k, operationType="view"))
        derived = {"stateToken", "Operationhandler", "Operationversion", "Oprvgenrtgparm"}
        old = {n: v for n, v in target["before"].items() if n not in derived}
        now = {n: v for n, v in current.items() if n not in derived}
        if old != now:
            _error(api, f"Definition changed during deletion: {k}; completed={completed}.")
        api._api_call(endpoint, dict(k, operationType="delete", expectedState=current["stateToken"]))
        if api._api_call(endpoint, dict(k, operationType="exists"))["exists"]:
            _error(api, f"Deletion readback failed: {k}; completed={completed}.")
        typ, values = _project_values(k, {})
        _register(api, project, typ, values, True)
        if k["kind"] == "operation":
            service = current["Servicename"]
            _verify_service_membership(api, args.name, service, present=False)
            _register(api, project, TYPES["service"], [service])
        completed.append(k)
    result.update(dryRun=False, verified=True, project=project, deleted=completed)
    return _output(api, args, result)


def _configure_rest(api, args):
    """Create/update a complete REST chain from an explicit, reviewable recipe."""
    recipe = _document(api, args.file)
    if set(recipe) - {"operation", "version", "handler", "routing", "permissionList"}:
        _error(api, "Unknown REST recipe sections.")
    if not all(isinstance(recipe.get(k), dict) for k in ("operation", "version", "handler", "routing")):
        _error(api, "REST recipe requires operation, version, handler and routing objects.")
    project, _ = _project(api, args)
    endpoint = ENDPOINTS["service-op"]
    if recipe.get("permissionList"):
        data = api._api_call("AI_QUERY_RECORD.v1/", dict(record="PSCLASSDEFN", fields=["CLASSID"],
            filter=[dict(field="CLASSID", op="=", value=recipe["permissionList"])], maxRows=2))
        if len(list(_query_rows(api, data))) != 1:
            _error(api, "REST recipe permissionList does not exist; no definitions were saved.")
    definitions = []
    for kind in ("operation", "version", "handler", "routing"):
        entry = dict(recipe[kind])
        if kind != "operation" and not entry.get("name"):
            _error(api, f"REST recipe {kind}.name is required.")
        name = entry.pop("name", args.name)
        if kind == "operation" and name != args.name:
            _error(api, "REST recipe operation.name must match the command's operation name.")
        keys = dict(kind=kind, name=name)
        if kind == "version":
            keys.update(name=args.name, Versionname=name)
        elif kind == "handler":
            keys.update(name=args.name, Handlername=name)
        elif kind == "routing":
            keys["Effdt"] = entry.pop("effdt", "1900-01-01")
        if set(entry) - {"properties", "collections"}:
            _error(api, f"Unknown {kind} recipe fields.")
        definitions.append((keys, entry))
    op_props = definitions[0][1].get("properties", {})
    route_props = definitions[3][1].get("properties", {})
    if op_props.get("Defaultversion") != definitions[1][0]["Versionname"]:
        _error(api, "REST recipe operation.Defaultversion must match version.name.")
    if route_props.get("Operationname") != args.name or route_props.get("Operationversion") != definitions[1][0]["Versionname"]:
        _error(api, "REST recipe routing must reference this operation and version.")
    snapshots = []
    for keys, entry in definitions:
        exists = api._api_call(endpoint, dict(keys, operationType="exists"))["exists"]
        before = api._api_call(endpoint, dict(keys, operationType="view")) if exists else None
        snapshots.append((keys, entry, before))
    if args.snapshot:
        snapshot = _document(api, args.snapshot)
        if not snapshots[0][2] or snapshot.get("stateToken") != snapshots[0][2]["stateToken"] or snapshot.get("environment") not in (None, api.ENVIRONMENT):
            _error(api, "REST operation differs from --snapshot; no definitions were saved.")
    # Validate every definition before saving the first one. Creation can refer to a
    # draft operation; the completed chain is re-read after all saves.
    results = []
    for keys, entry, before in snapshots:
        payload = dict(keys, operationType="modify" if before else "create", dryRun=True, **entry)
        if before:
            payload["expectedState"] = before["stateToken"]
        results.append(api._api_call(endpoint, payload))
    if args.dry_run:
        return _output(api, args, dict(environment=api.ENVIRONMENT, dryRun=True, plan=results))
    saved = []
    for keys, entry, before in snapshots:
        payload = dict(keys, operationType="modify" if before else "create", **entry)
        if before:
            # Native saves can update related definitions' reference collections.
            fresh = api._api_call(endpoint, dict(keys, operationType="view"))
            payload["expectedState"] = fresh["stateToken"]
        result = api._api_call(endpoint, payload)
        actual = api._api_call(endpoint, dict(keys, operationType="view"))
        _verify(api, actual, entry)
        typ, values = _project_values(keys, result)
        _register(api, project, typ, values)
        if keys["kind"] == "operation":
            _verify_service_membership(api, args.name, actual["Servicename"])
            for service in {(before or {}).get("Servicename"), actual["Servicename"]} - {None, ""}:
                if service != actual["Servicename"]:
                    _verify_service_membership(api, args.name, service, present=False)
                _register(api, project, TYPES["service"], [service])
        saved.append(dict(keys=keys, after=actual))
    # Native child saves populate the parent's derived version/handler/routing lists.
    for row in saved:
        row["after"] = api._api_call(endpoint, dict(row["keys"], operationType="view"))
    operation = saved[0]["after"]
    version_name = definitions[1][0]["Versionname"]
    handler_name = definitions[2][0]["Handlername"]
    route_name = definitions[3][0]["name"]
    if operation["Defaultversion"] != version_name or not any(v["Versionname"] == version_name for v in operation["Operationversion"]):
        _error(api, "REST default version is not linked to the saved operation.")
    if not any(h["Handlername"] == handler_name for h in operation["Operationhandler"]):
        _error(api, "REST handler is not linked to the saved operation.")
    if not any(r["Routingdefnname"] == route_name for r in saved[1]["after"]["Oprvgenrtgparm"]):
        _error(api, "REST routing is not linked to the saved version.")
    if recipe.get("permissionList"):
        keys = dict(kind="permission", name=args.name, permissionList=recipe["permissionList"])
        before = api._api_call(endpoint, dict(keys, operationType="view"))
        api._api_call(endpoint, dict(keys, operationType="modify", access=4, expectedState=before["stateToken"]))
        actual = api._api_call(endpoint, dict(keys, operationType="view"))
        if actual["access"] != 4:
            _error(api, "REST chain saved, but Permission List readback failed.")
        saved.append(dict(keys=keys, after=actual))
    return _output(api, args, dict(environment=api.ENVIRONMENT, verified=True, project=project, definitions=saved))
