"""Menu writes use the original structure or exact ItemSelected snapshot."""
import hashlib
import json
import time
from pathlib import Path

from definition_operations import _context, _path, _save, _save_text, _register

ENDPOINT = 'AI_OPER_MENU_DEFN.v1/'
WRITES = {'create': 'create', 'modify': 'modify', 'delete-item': 'deleteChild',
          'modify-code': 'modifyCode', 'delete-code': 'deleteCode'}


def _keys(args):
    return dict(BarName=args.bar, ItemName=args.item, event='ItemSelected')


def _code_index(api, args):
    identity = dict(_context(api, 'menu', args.name), **_keys(args))
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:16]
    return api._artifact_dir() / f'menu_{digest}_{args.name}.code.snapshot.json'


def _read(api, args, code=False):
    keys = dict(BarName=args.bar, ItemName=args.item) if code else {}
    return api._api_call(ENDPOINT, dict(kind='menu', name=args.name,
        operationType='viewCode' if code else 'struct', **keys))


def _require_version(api, data):
    if (data.get('menuVersionControl') != 1 or not isinstance(data.get('version'), str)
            or not data['version'].startswith('menu1:')):
        raise api.PSAPIError('服务端缺少 Menu 版本保护；部署配套处理类并重新读取，未写入。')


def _snapshot(api, args, code):
    path = (Path(args.snapshot).resolve() if args.snapshot else
            Path(str(Path(args.file).resolve()) + '.snapshot.json') if code and args.file else
            _code_index(api, args) if code else _path(api, 'menu', args.name))
    if not path.is_file():
        raise api.PSAPIError('缺少 Menu 原始快照：先 menu struct/view-code，或使用 --snapshot。')
    try:
        data = json.loads(path.read_text('utf-8-sig'))
    except (ValueError, OSError) as exc:
        raise api.PSAPIError(f'无法读取 Menu 快照：{path}') from exc
    if not isinstance(data, dict) or any(data.get(k) != v for k, v in _context(api, 'menu', args.name).items()):
        raise api.PSAPIError('Menu 快照的环境、服务器、节点、账号或名称不符。')
    _require_version(api, data)
    if data.get('artifactKind') != ('code' if code else 'structure'):
        raise api.PSAPIError('Menu 写入需要对应的结构或 ItemSelected 代码快照。')
    if code and (any(data.get(k) != v for k, v in _keys(args).items())
                 or not isinstance(data.get('peoplecode'), str)
                 or type(data.get('programExists')) is not bool):
        raise api.PSAPIError('代码快照的 Menu/Bar/Item/ItemSelected、正文或原生程序状态不符。')
    return data


def _conflict(api, args, error, code):
    paths = []
    prefix = f'conflict_{time.time_ns()}_'
    try:
        latest = _read(api, args)
        paths.append(str(_save(api, 'menu', args.name, latest,
            api._artifact_dir() / f'{prefix}{args.name}.structure.json')))
        if code and latest.get('exists'):
            data = _read(api, args, True)
            paths.extend(map(str, _save_text(api, 'menu', args.name, data, 'code',
                data.get('peoplecode') or '', prefix, **_keys(args))))
    except Exception as exc:
        paths.append('最新状态读取失败：' + str(exc))
    raise api.PSAPIError(str(error), code=409,
        hint='Menu 版本冲突，原稿和原快照保留，未重试写入。\n' + '\n'.join(paths)) from error


def _backup(api, args, data):
    import object_operations as ops
    path = api._cache_artifact(f'delete_{time.time_ns()}_{args.name}_{args.bar}_{args.item}_ItemSelected',
                               '.pcode', data['peoplecode'])
    if isinstance(api, ops._WriteJournal):
        api.snapshots.append(str(path))
    return path


def _preflight(api, args, original, code):
    # Compare the parent before resolving a program whose item may have been deleted.
    before = _read(api, args)
    _require_version(api, before)
    if before['version'] != original['version']:
        _conflict(api, args, api.PSAPIError('Menu 已在原始快照之后被修改。', code=409), code)
    if code:
        try:
            before = _read(api, args, True)
        except api.PSAPIError as exc:
            try:
                latest = _read(api, args)
            except api.PSAPIError:
                raise exc
            if exc.code == 409 or latest.get('version') != original['version']:
                _conflict(api, args, api.PSAPIError('Menu 在代码读取期间被修改。', code=409), True)
            raise
        _require_version(api, before)
        if before['version'] != original['version']:
            _conflict(api, args, api.PSAPIError('Menu 在代码读取期间被修改。', code=409), True)
    return before


def handle(api, args):
    import object_operations as ops
    code = args.op in ('view-code', 'modify-code', 'delete-code')
    if code and (not args.bar or not args.item):
        raise api.PSAPIError('Menu PeopleCode 需要精确 --bar 和 --item；事件固定为 ItemSelected。')
    if args.op in ('struct', 'exists', 'view-code'):
        data = (_read(api, args, code) if args.op != 'exists' else
                api._api_call(ENDPOINT, dict(kind='menu', name=args.name, operationType='exists')))
        _require_version(api, data)
        if args.op == 'struct':
            path = _save(api, 'menu', args.name, data)
            result = dict(data, **_context(api, 'menu', args.name), artifactKind='structure', snapshotPath=str(path))
        elif code:
            file, sidecar = _save_text(api, 'menu', args.name, data, 'code', data.get('peoplecode') or '', **_keys(args))
            _save(api, 'menu', args.name, data, _code_index(api, args), 'code', **_keys(args))
            result = dict(data, **_context(api, 'menu', args.name), artifactKind='code',
                          cachePath=str(file), snapshotPath=str(sidecar))
        else:
            result = data
        ops._output(api, args, result)
        return result
    if args.op not in WRITES:
        raise api.PSAPIError('Unsupported Menu command.')
    original = _snapshot(api, args, code)
    project, _ = ops._project(api, args)
    before = _preflight(api, args, original, code)
    if args.op == 'create' and before.get('exists'):
        raise api.PSAPIError('Menu 已存在；尚未创建。')
    patch = ops._patch(api, args) if not code else {}
    if not code and args.op != 'create' and not patch:
        raise api.PSAPIError('未提供 properties/collections 补丁。')
    payload = dict(kind='menu', name=args.name, operationType=WRITES[args.op],
                   expectedVersion=original['version'], dryRun=args.dry_run, **patch)
    if code:
        payload.update(BarName=args.bar, ItemName=args.item, expectedCode=original['peoplecode'])
        if args.op == 'modify-code':
            if not args.file:
                raise api.PSAPIError('modify-code 需要 --file。')
            payload['peoplecode'] = ops._read_file(api, args.file)
            if not payload['peoplecode'].strip():
                raise api.PSAPIError('空白 ItemSelected 正文不能用于删除；使用 delete-code。')
        elif not original['programExists']:
            raise api.PSAPIError('原始快照中 ItemSelected 程序不存在。')
    item_code = None
    if args.op == 'delete-item' and before.get('Menutype') == 1:
        item_code = _read(api, args, True)
        if item_code['version'] != original['version']:
            _conflict(api, args, api.PSAPIError('Menu 在删除计划读取期间被修改。', code=409), False)
    backup = None
    if not args.dry_run and (args.op == 'delete-code' or item_code and item_code.get('programExists')):
        backup = _backup(api, args, before if code else item_code)
    try:
        result = api._api_call(ENDPOINT, payload)
    except api.PSAPIError as exc:
        if exc.code == 409:
            _conflict(api, args, exc, code)
        raise
    if backup:
        result['snapshotPath'] = str(backup)
    if not args.dry_run:
        after = _preflight(api, args, result, code)
        if code:
            if args.op == 'delete-code':
                if after.get('programExists'):
                    raise api.PSAPIError('删除后 ItemSelected 程序仍存在。')
            elif (not after.get('programExists') or
                  api._peoplecode_signature(after['peoplecode']) != api._peoplecode_signature(payload['peoplecode'])):
                raise api.PSAPIError('ItemSelected 正文独立回读不符。')
            item = dict(result['projectItem'], deleted=args.op == 'delete-code')
            _register(api, project, [item])
        else:
            ops._verify(api, after, patch, args.op == 'delete-item')
            ops._register(api, project, 6, [args.name])
            if item_code and item_code.get('programExists'):
                item = dict(item_code['projectItem'], deleted=True)
                _register(api, project, [item])
        result.update(verified=True, project=project)
    result['environment'] = api.ENVIRONMENT
    ops._output(api, args, result)
    return result
