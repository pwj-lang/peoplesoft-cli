"""Field/Record writes retain the version of the downloaded editing baseline."""
import hashlib
import json
import re
import time
from pathlib import Path

ENDPOINTS = {"field": "AI_OPER_FIELD_DEFN.v1/", "record": "AI_OPER_RECORD_DEFN.v1/"}
RECORD_OPS = {"create": "createRecord", "modify": "modifyRecord", "modify-code": "modifyPeopleCode",
              "modify-sql": "modifySQL", "delete-code": "deletePeopleCode", "delete": "deleteRecord",
              "delete-field": "deleteRecordField", "build": "buildRecord", "alter": "buildRecord", "create-view": "buildRecord"}


def _context(api, kind, name):
    return dict(environment=api.ENVIRONMENT, baseUrl=api.BASE_URL, node=api.NODE,
                username=api.USERNAME, definitionKind=kind, definitionName=name)


def _path(api, kind, name):
    key = hashlib.sha256(json.dumps(_context(api, kind, name), sort_keys=True).encode()).hexdigest()[:16]
    return (api._artifact_dir() / f"{kind}_{key}_{name}.structure.json").resolve()


def _save(api, kind, name, data, path=None, artifact="structure", **keys):
    path = path or _path(api, kind, name)
    api._write_json_atomic(path, dict(data, **_context(api, kind, name), artifactKind=artifact, **keys))
    return path


def _read(api, kind, name, **extra):
    return api._api_call(ENDPOINTS[kind], dict(operationType="struct",
        **{"fieldName" if kind == "field" else "recordName": name}, **extra))


def _snapshot(api, args, kind, name):
    supplied = getattr(args, "snapshot", None)
    if supplied:
        path = Path(supplied).resolve()
    elif args.op in ("modify-code", "modify-sql") and args.file:
        path = Path(str(Path(args.file).resolve()) + ".snapshot.json")
    else:
        path = _path(api, kind, name)
    if not path.is_file():
        raise api.PSAPIError(f"缺少版本快照：先读取 {kind} struct/view-code/view-sql，使用下载的文件或 --snapshot。")
    try:
        data = json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise api.PSAPIError(f"无法读取版本快照：{path}") from exc
    if not isinstance(data, dict) or any(data.get(k) != v for k, v in _context(api, kind, name).items()):
        raise api.PSAPIError("版本快照的环境、服务器、账号、对象类型或名称不符。")
    prefix = "f1:" if kind == "field" else "r1:"
    if not isinstance(data.get("version"), str) or not data["version"].startswith(prefix):
        raise api.PSAPIError("快照没有服务器版本令牌，请部署新版处理类和 DefinitionVersion 后重新读取。")
    if args.op == "modify-code":
        if data.get("artifactKind") != "code" or data.get("fieldName") != args.fieldname or data.get("event") != args.event:
            raise api.PSAPIError("代码修改必须使用该 Record/Field/Event 的 view-code 快照。")
    elif args.op == "modify-sql":
        if data.get("artifactKind") != "sql" or not isinstance(data.get("statement"), dict):
            raise api.PSAPIError("SQL 修改必须使用该 Record 的 view-sql 快照。")
    elif data.get("artifactKind") != "structure":
        raise api.PSAPIError("定义操作必须使用 struct 的结构快照。")
    return data


def _save_text(api, kind, name, data, artifact, text, prefix="", **keys):
    identity = dict(_context(api, kind, name), artifactKind=artifact, **keys)
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:16]
    file = api._cache_artifact(prefix + key + "_" + name + ("_" + keys.get("fieldName", "") if artifact == "code" else ""),
                               ".pcode" if artifact == "code" else ".sql", text)
    sidecar = _save(api, kind, name, data, Path(str(file) + ".snapshot.json"), artifact, **keys)
    return file, sidecar


def _conflict(api, args, kind, name, error):
    prefix = f"conflict_{time.time_ns()}_"
    paths = []
    try:
        latest = _read(api, kind, name)
        paths.append(str(_save(api, kind, name, latest, api._artifact_dir() / f"{prefix}{name}.structure.json")))
        if kind == "record" and args.op in ("modify-code", "delete-code") and latest.get("exists"):
            data = api._api_call(ENDPOINTS[kind], dict(recordName=name, fieldName=args.fieldname,
                event=args.event, operationType="viewPeopleCode"))
            paths.extend(map(str, _save_text(api, kind, name, data, "code", data.get("peoplecode") or "",
                prefix, fieldName=args.fieldname, event=args.event)))
        if kind == "record" and args.op == "modify-sql" and latest.get("exists"):
            data = api._api_call(ENDPOINTS[kind], dict(recordName=name, operationType="viewSQL"))
            for stmt in data.get("statements", []):
                paths.extend(map(str, _save_text(api, kind, name, data, "sql", stmt.get("sqlText") or "", prefix, statement=stmt)))
    except api.PSAPIError as exc:
        paths.append("最新状态读取失败：" + str(exc))
    raise api.PSAPIError(str(error), code=409, hint="版本冲突，写入已拒绝；原稿和原快照保留，未自动重试。\n" + "\n".join(paths)) from error


def _register(api, project, items):
    for item in items:
        _, actual = api._insert_project_item(project, item["objectType"], [item.get(f"objectValue{i}", "") for i in range(1, 5)],
                                             action=1 if item.get("deleted") else 0)
        if "objectId1" in item and api._project_item_key(actual) != api._project_item_key(item):
            raise api.PSAPIError("Project 完整键与服务端返回的键不同。")


def _item(typ, *values):
    return dict(objectType=typ, deleted=False, **{f"objectValue{i+1}": v for i, v in enumerate(list(values) + [" "]*(4-len(values)))})


def _check_patch(api, kind, before, after, patch):
    target = after.get("fields", [{}])[0] if kind == "field" else after
    if kind == "field":
        for key, value in patch.items():
            if key in target and key not in ("fieldName", "labels", "expectedVersion", "fieldType") and target[key] != value:
                raise api.PSAPIError(f"Field 回读不符：{key}")
        for label in patch.get("labels", []):
            found = [x for x in target.get("labels", []) if x.get("labelId") == label.get("labelId")]
            if len(found) != 1 or any(found[0].get(k) != v for k, v in label.items()):
                raise api.PSAPIError("Field 标签回读不符。")
    else:
        for key in ("descr", "comment", "optTrigFlag"):
            if key in patch and target.get(key) != patch[key]:
                raise api.PSAPIError(f"Record 回读不符：{key}")
        for field in patch.get("fields", []):
            found = [f for f in target.get("fields", []) if f.get("fieldName") == field.get("fieldName")]
            if len(found) != 1:
                raise api.PSAPIError("Record 字段回读缺少目标。")
            for key in ("fieldProperty", "editTable", "labelId", "defaultRecName", "defaultFieldName", "unmappedUseEdit"):
                if key in field and (set(found[0].get(key, [])) != set(field[key]) if key == "fieldProperty" else found[0].get(key) != field[key]):
                    raise api.PSAPIError(f"Record 字段属性回读不符：{field['fieldName']}.{key}")


def _check_label_delete(api, before, after, label_id, replacement, dry):
    if after.get("exists") is not True:
        raise api.PSAPIError("Label 删除后 Field 定义缺失。")
    old = before.get("fields", [])
    fresh = after.get("fields", [])
    if len(old) != 1 or len(fresh) != 1:
        raise api.PSAPIError("Label 删除回读缺少精确 Field。")
    expected = []
    for label in old[0].get("labels", []):
        if not dry and label.get("labelId") == label_id:
            continue
        label = dict(label)
        if not dry and replacement:
            label["defaultLabel"] = int(label.get("labelId") == replacement)
        expected.append(label)
    by_id = lambda rows: sorted(rows, key=lambda row: row["labelId"])
    if by_id(fresh[0].get("labels", [])) != by_id(expected):
        raise api.PSAPIError("Label 删除回读不符：目标、其余标签或默认替代不一致。")
    for key, value in old[0].items():
        if key not in ("labels", "version", "fieldVersion", "lastUpdate") and fresh[0].get(key) != value:
            raise api.PSAPIError(f"Label 删除改变了其他 Field 属性：{key}")


def execute(api, args):
    kind = args.cmd
    name = (args.name if kind == "field" else args.recname).upper()
    maximum = 18 if kind == "field" else 15
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0," + str(maximum-1) + "}", name):
        raise api.PSAPIError("无效的定义名称。")
    if kind == 'field' and args.op.endswith('-xlat'):
        from xlat_operations import execute as xlat_execute
        return xlat_execute(api, args, name)
    if kind == 'field' and any(getattr(args, a, None) is not None for a in ('value','effdt','long_name','short_name','status')):
        raise api.PSAPIError('XLAT 参数仅用于 list/add/modify/delete-xlat。')
    endpoint = ENDPOINTS[kind]
    identity = {"fieldName" if kind == "field" else "recordName": name}
    op = args.op
    label_id = replacement = None
    if op == "delete-label":
        label_id = getattr(args, "label_id", None)
        replacement = getattr(args, "replacement_label_id", None)
        if not isinstance(label_id, str) or not label_id.strip() or len(label_id) > 18:
            raise api.PSAPIError("delete-label 需要非空且不超过 18 字符的 --label-id。")
        label_id = label_id.upper()
        if replacement is not None:
            if not replacement.strip() or len(replacement) > 18 or replacement.upper() == label_id:
                raise api.PSAPIError("--replacement-label-id 必须是不同的非空 Label ID，最长 18 字符。")
            replacement = replacement.upper()
    elif getattr(args, "label_id", None) is not None or getattr(args, "replacement_label_id", None) is not None:
        raise api.PSAPIError("Label 参数只用于 field delete-label。")
    if op == "struct":
        data = _read(api, kind, name)
        path = _save(api, kind, name, data)
        if getattr(args, "json", False) or kind == "field" or not data.get("exists"):
            print(json.dumps(dict(data, snapshotPath=str(path)), ensure_ascii=False, indent=2))
        else:
            api._print_record_struct(data)
            print(f"version: {data.get('version')}\nSnapshot: {path}")
        return data
    if op in ("view-code", "modify-code", "delete-code", "delete-field"):
        if not args.fieldname or (op != "delete-field" and not args.event):
            raise api.PSAPIError("需要 --fieldname；程序操作还需要 --event。")
    if op == "view-code":
        data = api._api_call(endpoint, dict(identity, operationType="viewPeopleCode", fieldName=args.fieldname, event=args.event))
        file, sidecar = _save_text(api, kind, name, data, "code", data.get("peoplecode") or "", fieldName=args.fieldname, event=args.event)
        print((data.get("peoplecode") or "") + f"\nCached: {file}\nSnapshot: {sidecar}\nversion: {data.get('version')}")
        return data
    if op == "view-sql":
        data = api._api_call(endpoint, dict(identity, operationType="viewSQL"))
        for stmt in data.get("statements") or [dict(market="GBL", dbType=" ", effdt="1900-01-01", sqlText="")]:
            file, sidecar = _save_text(api, kind, name, data, "sql", stmt.get("sqlText") or "", statement=stmt)
            print((stmt.get("sqlText") or "") + f"\nCached: {file}\nSnapshot: {sidecar}\nversion: {data.get('version')}")
        return data
    dry = bool(getattr(args, "dry_run", False))
    if dry and op not in ("delete", "delete-code", "delete-field", "delete-label"):
        raise api.PSAPIError("--dry-run 仅用于删除。")
    before = _snapshot(api, args, kind, name)
    project = args.project or api._active_project()
    if not project:
        raise api.PSAPIError("写操作需要 --project 或已确认的当前 Project。")
    api._require_project(project)
    payload = dict(identity, expectedVersion=before["version"])
    payload["operationType"] = ({"create": "createField", "modify": "modifyField", "delete": "deleteField", "delete-label": "deleteLabel"}[op]
                                 if kind == "field" else RECORD_OPS[op])
    if op == "delete-label":
        payload["labelId"] = label_id
        if replacement is not None:
            payload["replacementLabelId"] = replacement
    patch = None
    text = None
    if op in ("create", "modify"):
        if not args.file:
            raise api.PSAPIError("需要 UTF-8 JSON 文件或 JSON 参数。")
        patch = api._load_json_arg(args.file, "定义 JSON")
        if not isinstance(patch, dict):
            raise api.PSAPIError("定义 JSON 必须是对象。")
        if kind == "field":
            if "fields" in patch:
                rows = patch["fields"]
                if not isinstance(rows, list) or len(rows) != 1:
                    raise api.PSAPIError("field 命令每次只写一个精确 Field。")
                patch = rows[0]
            if patch.get("fieldName", name) != name:
                raise api.PSAPIError("JSON fieldName 与命令参数不同。")
            patch = dict(patch, fieldName=name)
            wire = dict(patch, expectedVersion=before["version"])
            if "comment" in wire: wire["comment"] = api.json_escape(wire["comment"])
            payload["fields"] = [wire]
        else:
            if patch.get("recordName", name) != name or patch.get("recName", name) != name:
                raise api.PSAPIError("JSON Record 名称与命令参数不同。")
            if any(k in patch for k in ("operationType", "expectedVersion", "dryRun")):
                raise api.PSAPIError("JSON 不应覆盖操作、版本或 dryRun。")
            payload.update(patch)
            if "comment" in payload: payload["comment"] = api.json_escape(payload["comment"])
    if op in ("modify-code", "modify-sql"):
        if not args.file or not Path(args.file).is_file():
            raise api.PSAPIError("修改代码/SQL 需要本地 UTF-8 文件及下载时的版本快照。")
        text = Path(args.file).read_text("utf-8-sig")
        if not text.strip(): raise api.PSAPIError("空白正文不能作为删除。")
        payload["peoplecode" if op == "modify-code" else "sqlText"] = api.json_escape(text)
        if op == "modify-sql":
            for k in ("market", "dbType", "effdt"):
                if k in before["statement"]: payload[k] = before["statement"][k]
            if isinstance(payload.get("dbType"), int):
                payload["dbType"] = api._normalize_dbtype(str(payload["dbType"]))
    if op in ("modify-code", "delete-code", "delete-field"):
        payload["fieldName"] = args.fieldname
        if op != "delete-field": payload["event"] = args.event
    if op in ("build", "alter", "create-view"):
        payload[{"build": "createTable", "alter": "alterTable", "create-view": "createView"}[op]] = [name]
    wrote = False
    try:
        backup_path = None
        if op.startswith("delete"):
            payload["dryRun"] = dry
            backup = dict(before)
            if op == "delete-label":
                plan = api._api_call(endpoint, dict(payload, dryRun=True))
                if (plan.get("fieldName") != name or plan.get("labelId") != label_id or
                        plan.get("replacementLabelId") != (replacement or "") or
                        plan.get("deleted") is not False or plan.get("dryRun") is not True or
                        plan.get("version") != before["version"] or
                        not isinstance(plan.get("labelBackup"), dict) or plan["labelBackup"].get("labelId") != label_id or
                        not isinstance(plan.get("translations"), list) or not isinstance(plan.get("contexts"), list)):
                    raise api.PSAPIError("Label 删除预览缺少正确定位、版本或恢复数据，尚未执行删除。")
                backup["deletePlan"] = plan
            elif op == "delete-code":
                code = api._api_call(endpoint, dict(identity, operationType="viewPeopleCode", fieldName=args.fieldname, event=args.event))
                if code.get("version") != before["version"]:
                    raise api.PSAPIError("VERSION_CONFLICT: 程序读取版本与删除基线不同", code=409)
                if not code.get("programExists"): raise api.PSAPIError("目标原生程序不存在。")
                backup["programs"] = [code]
                payload["expectedCode"] = api.json_escape(code.get("peoplecode") or "")
            elif kind == "record":
                plan = api._api_call(endpoint, dict(payload, dryRun=True))
                backup["deletePlan"] = plan
                backup["programs"] = []
                for item in plan.get("projectItems", []):
                    if item.get("objectType") == 8:
                        backup["programs"].append(api._api_call(endpoint, dict(recordName=item["objectValue1"], fieldName=item["objectValue2"],
                            event=item["objectValue3"], operationType="viewPeopleCode")))
                backup["viewSQL"] = api._api_call(endpoint, dict(identity, operationType="viewSQL"))
            backup_path = (api._artifact_dir() / f"delete_{time.time_ns()}_{kind}_{name}.json").resolve()
            api._write_json_atomic(backup_path, backup)
        result = api._api_call(endpoint, payload)
        wrote = not dry
        fresh = _read(api, kind, name)
        items = []
        if op.startswith("delete"):
            if result.get("deleted") is not (not dry) or result.get("dryRun") is not dry:
                raise api.PSAPIError("服务端未确认删除状态，请检查当前对象。")
            if op == "delete-code":
                actual = api._api_call(endpoint, dict(identity, operationType="viewPeopleCode", fieldName=args.fieldname, event=args.event))
                if actual.get("programExists") is not dry:
                    raise api.PSAPIError("独立回读程序存在状态不符。")
                item = result.get("projectItem")
                items = [dict(item, deleted=True)] if isinstance(item, dict) else []
            else:
                items = result.get("projectItems", [])
                if op == "delete-label":
                    if result.get("labelId") != label_id or result.get("replacementLabelId") != (replacement or ""):
                        raise api.PSAPIError("Label 删除响应的定位或替代不符。")
                    _check_label_delete(api, before, fresh, label_id, replacement, dry)
                    present = any(label.get("labelId") == label_id for label in fresh["fields"][0].get("labels", []))
                    if len(items) != 1 or items[0].get("objectType") != 2 or items[0].get("objectValue1") != name or items[0].get("objectId1") != 6 or items[0].get("objectId2") != 0 or items[0].get("deleted") is not False:
                        raise api.PSAPIError("Label 删除必须登记父 Field 的完整 Copy 键。")
                elif op == "delete-field":
                    present = any(f.get("fieldName") == args.fieldname for f in fresh.get("fields", []))
                else:
                    present = fresh.get("exists")
                if present is not dry: raise api.PSAPIError("独立回读定义/字段存在状态不符。")
            required = {"objectType", "deleted"} | {f"objectId{i}" for i in range(1, 5)} | {f"objectValue{i}" for i in range(1, 5)}
            if not items or any(not isinstance(i, dict) or not required <= i.keys() for i in items):
                raise api.PSAPIError("删除响应缺少完整工程键。")
            if dry and fresh.get("version") != before["version"]:
                raise api.PSAPIError("dry-run 期间版本发生变化，请重新读取。")
        else:
            if fresh.get("exists") is not True: raise api.PSAPIError("写后回读缺少目标定义。")
            if patch is not None: _check_patch(api, kind, before, fresh, patch)
            items = result.get("projectItems") or [_item(2 if kind == "field" else 0, name)]
            if op == "modify-code":
                actual = api._api_call(endpoint, dict(identity, operationType="viewPeopleCode", fieldName=args.fieldname, event=args.event))
                if api._peoplecode_signature(actual.get("peoplecode")) != api._peoplecode_signature(text):
                    raise api.PSAPIError("程序写后独立回读不符。")
                if not any(i.get("objectType") == 8 and i.get("objectValue1") == name and i.get("objectValue2") == args.fieldname and i.get("objectValue3") == args.event for i in items):
                    items.append(_item(8, name, args.fieldname, args.event))
                _save(api, kind, name, actual, Path(str(Path(args.file).resolve()) + ".snapshot.json"), "code", fieldName=args.fieldname, event=args.event)
            if op == "modify-sql":
                actual = api._api_call(endpoint, dict(identity, operationType="viewSQL"))
                stmts = [s for s in actual.get("statements", []) if s.get("market") == payload.get("market") and
                         s.get("effdt") == payload.get("effdt") and
                         api._normalize_dbtype(str(s.get("dbType", ""))) == api._normalize_dbtype(str(payload.get("dbType", "")))]
                if len(stmts) != 1 or (stmts[0].get("sqlText") or "").replace("\r\n", "\n").strip() != text.replace("\r\n", "\n").strip():
                    raise api.PSAPIError("View SQL 写后独立回读不符。")
                if not any(i.get("objectType") == 65 for i in items): items.append(_item(65, name, "2"))
                _save(api, kind, name, actual, Path(str(Path(args.file).resolve()) + ".snapshot.json"), "sql", statement=stmts[0])
        if not dry:
            try:
                _register(api, project, items)
            except (api.PSAPIError, SystemExit) as exc:
                recovery = api._artifact_dir() / f"registration_pending_{time.time_ns()}.json"
                api._write_json_atomic(recovery, dict(result, project=project, projectItems=items, registrationPending=True))
                raise api.PSAPIError(f"定义操作已成功，Project 登记失败。恢复记录：{recovery}；按完整键补登记，勿重复删除/写入。") from exc
            _save(api, kind, name, fresh)
        result.update(environment=api.ENVIRONMENT, project=project, readbackVerified=True, projectItems=items)
        if backup_path: result["snapshotPath"] = str(backup_path)
        if args.output: api._write_json_atomic(Path(args.output).resolve(), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result
    except api.PSAPIError as exc:
        if exc.code == 409 and not wrote: _conflict(api, args, kind, name, exc)
        if wrote:
            raise api.PSAPIError("服务端已确认写入；后续验证或登记失败，请读取当前状态后处理，勿盲目重试。", hint=str(exc)) from exc
        raise
