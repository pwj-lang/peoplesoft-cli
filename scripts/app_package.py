"""Application-package edits use the version of the user's downloaded snapshot."""
import hashlib
import json
import re
import time
from pathlib import Path

ENDPOINT = "AI_OPER_APP_PKG_POST.v1/"
OPERATIONS = {"modify-code": "modifyPeopleCode", "insert-class": "insertClass",
              "insert-package": "insertPackage", "delete-class": "deleteClass",
              "delete-package": "deletePackage", "delete-root": "deleteApplicationPackage"}


def _context(api, root):
    # Bind snapshots to the actual server and identity, not just an environment label.
    return dict(environment=api.ENVIRONMENT, baseUrl=api.BASE_URL, node=api.NODE,
                username=api.USERNAME, packageRoot=root)


def _structure_path(api, root):
    identity = json.dumps(_context(api, root), sort_keys=True).encode()
    name = api._safe_filename(root) + "_" + hashlib.sha256(identity).hexdigest()[:16]
    return (api._artifact_dir() / (name + ".structure.json")).resolve()


def _save_structure(api, root, data, path=None):
    path = path or _structure_path(api, root)
    api._write_json_atomic(path, dict(data, **_context(api, root)))
    return path


def _save_code(api, root, path, data, prefix=""):
    # A unique conflict download never overwrites the user's edited working copy.
    identity = json.dumps(dict(_context(api, root), classPath=path), sort_keys=True).encode()
    key = hashlib.sha256(identity).hexdigest()[:16]
    # Keep the identity before the human-readable part: long paths are truncated.
    file = api._cache_artifact(prefix + key + "_" + path, ".pcode", data.get("peoplecode") or "")
    sidecar = Path(str(file) + ".snapshot.json")
    api._write_json_atomic(sidecar, dict(data, **_context(api, root), classPath=path, sourcePath=str(file)))
    return file, sidecar


def _snapshot(api, args):
    supplied = getattr(args, "snapshot", None)
    if supplied:
        path = Path(supplied).resolve()
    elif args.op == "modify-code" and args.file:
        path = Path(str(Path(args.file).resolve()) + ".snapshot.json")
    else:
        path = _structure_path(api, args.pkg)
    if not path.is_file():
        raise api.PSAPIError("缺少版本快照：先运行 app-pkg struct/view-code，再使用下载的文件或 --snapshot。")
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        raise api.PSAPIError(f"版本快照无法读取：{path}") from exc
    if not isinstance(data, dict) or any(data.get(k) != v for k, v in _context(api, args.pkg).items()):
        raise api.PSAPIError("版本快照的环境、服务器、账号或包根与当前请求不同。")
    if not isinstance(data.get("version"), str) or not data["version"].startswith("ap1:"):
        raise api.PSAPIError("快照缺少服务器版本令牌；请先在 AD 部署新版 OperAppPackage，再重新读取。")
    if args.op == "modify-code" and (data.get("classPath") != args.classpath or "peoplecode" not in data):
        raise api.PSAPIError("修改代码必须使用该类 view-code 返回的代码快照；结构快照不能替代编辑基线。")
    if args.op not in ("modify-code", "delete-code") and not isinstance(data.get("packageTree"), dict):
        raise api.PSAPIError("类和包结构的新增、删除必须使用 struct 返回的结构快照。")
    return data


def _flatten(node):
    yield node
    for child in node.get("children", []):
        yield from _flatten(child)


def _conflict(api, args, error):
    prefix = f"conflict_{time.time_ns()}_"
    files = []
    try:
        data = api._api_call(ENDPOINT, dict(packageRoot=args.pkg, operationType="default"))
        path = api._artifact_dir() / (prefix + api._safe_filename(args.pkg) + ".structure.json")
        files.append(str(_save_structure(api, args.pkg, data, path.resolve())))
        # For subtree deletion, retrieve every latest class source in its scope too.
        nodes = list(_flatten(data.get("packageTree", {})))
        if args.op in ("modify-code", "delete-code", "delete-class", "insert-class"):
            paths = [args.classpath]
        else:
            target = args.classpath or args.pkg
            paths = [n["classPath"] for n in nodes if n.get("nodeType") == "class"
                     and n.get("classPath", "").startswith(target + ":")]
        for path in paths:
            if not any(n.get("classPath") == path and n.get("nodeType") == "class" for n in nodes):
                continue
            latest = api._api_call(ENDPOINT, dict(packageRoot=args.pkg, operationType="viewPeopleCode", classPath=path))
            files.extend(map(str, _save_code(api, args.pkg, path, latest, prefix)))
    except api.PSAPIError as fetch_error:
        # The target may have been deleted. Preserve the original conflict outcome.
        files.append(f"最新状态读取失败：{fetch_error}")
    raise api.PSAPIError(str(error), hint="版本冲突，写入已拒绝；本地文件与原快照保留，未自动重试。\n最新内容：\n" + "\n".join(files), code=409) from error


def _register(api, project, items):
    for item in items:
        values = [item.get(f"objectValue{i}", "") for i in range(1, 5)]
        _, actual = api._insert_project_item(project, item["objectType"], values,
                                             action=1 if item.get("deleted") else 0)
        if "objectId1" in item and api._project_item_key(actual) != api._project_item_key(item):
            raise api.PSAPIError("Project 完整键与删除计划返回值不同。")


def _copy_items(path, package=False, program=False):
    parts = path.split(":")
    depth = len(parts) if package else len(parts)-1
    rows = []
    for n in range(1, depth+1):
        q = "." if n == 1 else ":" if n == 2 else parts[1]
        values = [parts[n-1], parts[0], q, ""]
        rows.append(dict(objectType=57, deleted=False,
                         **{f"objectValue{i+1}": v for i, v in enumerate(values)}))
    if program:
        values = parts + [""]*(4-len(parts))
        rows.append(dict(objectType=58, deleted=False,
                         **{f"objectValue{i+1}": v for i, v in enumerate(values)}))
    return rows


def execute(api, args):
    op = args.op
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,29}", args.pkg):
        raise api.PSAPIError("packageRoot 必须以字母开头，最多 30 个字母、数字或下划线。")
    path = args.classpath
    if op == "delete-root":
        path = path or args.pkg
        args.classpath = path
        minimum, maximum = 1, 1
    else:
        minimum, maximum = (2, 3) if op in ("insert-package", "delete-package") else (2, 4)
    if op != "struct":
        parts = (path or "").split(":")
        if not minimum <= len(parts) <= maximum or parts[0] != args.pkg or any(
                not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,29}", p) for p in parts):
            raise api.PSAPIError("classPath 必须是给定根包下的完整有效路径。")
    payload = dict(packageRoot=args.pkg)
    if op == "struct":
        data = api._api_call(ENDPOINT, dict(payload, operationType="default"))
        snapshot = _save_structure(api, args.pkg, data)
        if getattr(args, "json", False):
            print(json.dumps(dict(data, snapshotPath=str(snapshot)), ensure_ascii=False, indent=2))
        else:
            api._print_pkg_tree(data.get("packageTree", {}), 0)
            print(f"version: {data.get('version', '服务端未部署版本校验')}\nSnapshot: {snapshot}")
        return data
    payload["classPath"] = path
    if op == "view-code":
        data = api._api_call(ENDPOINT, dict(payload, operationType="viewPeopleCode"))
        file, sidecar = _save_code(api, args.pkg, path, data)
        print(data.get("peoplecode") or "")
        print(f"Cached: {file}\nSnapshot: {sidecar}\nversion: {data.get('version', '服务端未部署版本校验')}")
        return data
    if getattr(args, "dry_run", False) and op not in ("delete-code", "delete-class", "delete-package", "delete-root"):
        raise api.PSAPIError("--dry-run 仅支持删除操作。")
    before = _snapshot(api, args)
    payload["expectedVersion"] = before["version"]
    project = args.project or api._active_project()
    if not project:
        raise api.PSAPIError("写操作需要 --project 或当前已确认的 Project。")
    api._require_project(project)
    write_succeeded = False
    try:
        if op == "delete-code":
            result = api._delete_verified_peoplecode(ENDPOINT, payload, args)
            write_succeeded = not args.dry_run
            if not args.dry_run:
                fresh = api._api_call(ENDPOINT, dict(packageRoot=args.pkg, operationType="default"))
                _save_structure(api, args.pkg, fresh)
            return result
        code = None
        if op == "modify-code":
            if not args.file or not Path(args.file).is_file():
                raise api.PSAPIError("modify-code 需要 UTF-8 PeopleCode 文件。")
            code = Path(args.file).read_text("utf-8-sig")
            if not code.strip():
                raise api.PSAPIError("空代码不能作为删除，请使用 delete-code。")
            payload["peoplecode"] = api.json_escape(code)
        dry = bool(args.dry_run)
        # Snapshot the entire affected subtree before any irreversible deletion.
        if op.startswith("delete-"):
            backup = dict(before)
            backup["programs"] = []
            for node in _flatten(before.get("packageTree", {})):
                cp = node.get("classPath", "")
                if node.get("nodeType") == "class" and (cp == path or cp.startswith(path+":")):
                    latest = api._api_call(ENDPOINT, dict(packageRoot=args.pkg, classPath=cp, operationType="viewPeopleCode"))
                    backup["programs"].append(latest)
            backup_path = (api._artifact_dir() / f"delete_{time.time_ns()}_{api._safe_filename(path)}.json").resolve()
            api._write_json_atomic(backup_path, backup)
            payload["dryRun"] = dry
        result = api._api_call(ENDPOINT, dict(payload, operationType=OPERATIONS[op]))
        write_succeeded = not dry
        items = []
        if op.startswith("delete-"):
            if result.get("deleted") is not (not dry) or result.get("dryRun") is not dry:
                raise api.PSAPIError("服务端没有确认删除状态，请先读取当前状态。")
            items = result.get("projectItems")
            required = {"objectType", "deleted"} | {f"objectId{i}" for i in range(1, 5)} | {f"objectValue{i}" for i in range(1, 5)}
            if not isinstance(items, list) or not items or any(not isinstance(i, dict) or not required <= i.keys() for i in items):
                raise api.PSAPIError("删除响应缺少完整 Project 键，请检查当前状态。")
            if op == "delete-root" and not dry:
                # A missing root is expected, but arbitrary API errors are not proof of absence.
                search = api._api_call("AI_SEARCH_DEFN.v1/", dict(definitionType=104, definitionName=args.pkg))
                if any(i.get("packageId") == args.pkg for i in search.get("list", [])):
                    raise api.PSAPIError("删除根包后的独立搜索仍找到该定义。")
                fresh = None
            else:
                fresh = api._api_call(ENDPOINT, dict(packageRoot=args.pkg, operationType="default"))
                present = {n.get("classPath") for n in _flatten(fresh.get("packageTree", {}))}
                if (path in present) is not dry:
                    raise api.PSAPIError("删除后的独立结构回读不符合预期。")
                if dry and fresh.get("version") != before["version"]:
                    raise api.PSAPIError("dry-run 期间版本变化，请重新读取。")
            result["snapshotPath"] = str(backup_path)
        else:
            fresh = api._api_call(ENDPOINT, dict(packageRoot=args.pkg, operationType="default"))
            if path not in {n.get("classPath") for n in _flatten(fresh.get("packageTree", {}))}:
                raise api.PSAPIError("写入后的独立结构回读缺少目标。")
            items = _copy_items(path, package=(op == "insert-package"), program=(op == "modify-code"))
            if code is not None:
                actual = api._api_call(ENDPOINT, dict(packageRoot=args.pkg, classPath=path, operationType="viewPeopleCode"))
                if api._peoplecode_signature(actual.get("peoplecode")) != api._peoplecode_signature(code):
                    raise api.PSAPIError("代码保存后独立回读不符，请检查当前程序。")
                api._write_json_atomic(Path(str(Path(args.file).resolve()) + ".snapshot.json"), dict(actual, **_context(api, args.pkg), classPath=path))
        if not dry:
            try:
                _register(api, project, items)
            except (api.PSAPIError, SystemExit) as exc:
                result.update(project=project, registrationPending=True, projectItems=items)
                recovery = api._artifact_dir() / f"registration_pending_{time.time_ns()}.json"
                api._write_json_atomic(recovery, result)
                raise api.PSAPIError(f"定义写入已成功，但 Project 登记失败。恢复记录：{recovery}；请按完整键补登记，勿重做删除/写入。") from exc
            if fresh is not None:
                _save_structure(api, args.pkg, fresh)
            elif op == "delete-root":
                # Keep the old snapshot as evidence; it will conflict if reused.
                pass
        result.update(environment=api.ENVIRONMENT, project=project, readbackVerified=True)
        if args.output:
            api._write_json_atomic(Path(args.output).resolve(), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result
    except api.PSAPIError as exc:
        if exc.code == 409:
            if write_succeeded:
                raise api.PSAPIError("服务端已确认写入，但后续回读遇到并发变化；请读取当前状态，勿自动重试。", hint=str(exc)) from exc
            _conflict(api, args, exc)
        raise
