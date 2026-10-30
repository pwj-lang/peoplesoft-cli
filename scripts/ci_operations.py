"""CI definition and Methods writes use the original, context-bound version."""
import hashlib
import json
import time
from pathlib import Path

from definition_operations import _context, _path, _save, _save_text

ENDPOINT = 'AI_OPER_CI_DEFN.v1/'
WRITES = {'create': 'create', 'modify': 'modify', 'delete-item': 'deleteChild',
          'modify-code': 'modifyCode', 'delete-code': 'deleteCode'}


def _code_index(api, name):
    digest = hashlib.sha256(json.dumps(_context(api, 'ci', name), sort_keys=True).encode()).hexdigest()[:16]
    return api._artifact_dir() / f'ci_{digest}_{name}.code.snapshot.json'


def _read(api, name, code=False):
    return api._api_call(ENDPOINT, dict(kind='ci', name=name,
        operationType='viewCode' if code else 'struct'))


def _require_version(api, data):
    if (data.get('ciVersionControl') != 1 or not isinstance(data.get('version'), str)
            or not data['version'].startswith('ci1:')):
        raise api.PSAPIError('服务端缺少 CI 版本保护；部署配套处理类并重新读取，未写入。')


def _snapshot(api, args, code):
    path = (Path(args.snapshot).resolve() if args.snapshot else
            Path(str(Path(args.file).resolve()) + '.snapshot.json') if code and args.file else
            _code_index(api, args.name) if code else _path(api, 'ci', args.name))
    if not path.is_file():
        raise api.PSAPIError('缺少 CI 原始快照：先 ci struct/view-code，或使用 --snapshot。')
    try:
        data = json.loads(path.read_text('utf-8-sig'))
    except (ValueError, OSError) as exc:
        raise api.PSAPIError(f'无法读取 CI 快照：{path}') from exc
    if not isinstance(data, dict) or any(data.get(k) != v for k, v in _context(api, 'ci', args.name).items()):
        raise api.PSAPIError('CI 快照的环境、服务器、节点、账号或名称不符。')
    _require_version(api, data)
    if data.get('artifactKind') != ('code' if code else 'structure'):
        raise api.PSAPIError('CI 写入需要对应的结构或 Methods 代码快照。')
    if code and (data.get('event') != 'Methods' or not isinstance(data.get('peoplecode'), str)
                 or type(data.get('programExists')) is not bool):
        raise api.PSAPIError('Methods 快照缺少精确事件、正文或原生程序状态。')
    return data


def _conflict(api, args, error, code):
    paths = []
    prefix = f'conflict_{time.time_ns()}_'
    try:
        latest = _read(api, args.name)
        paths.append(str(_save(api, 'ci', args.name, latest,
            api._artifact_dir() / f'{prefix}{args.name}.structure.json')))
        if code and latest.get('exists'):
            data = _read(api, args.name, True)
            paths.extend(map(str, _save_text(api, 'ci', args.name, data, 'code',
                data.get('peoplecode') or '', prefix, event='Methods')))
    except Exception as exc:
        paths.append('最新状态读取失败：' + str(exc))
    raise api.PSAPIError(str(error), code=409,
        hint='CI 版本冲突，原稿和原快照保留，未重试写入。\n' + '\n'.join(paths)) from error


def handle(api, args):
    import object_operations as ops
    code = args.op in ('view-code', 'modify-code', 'delete-code')
    if args.op in ('struct', 'exists', 'view-code'):
        data = (_read(api, args.name, code) if args.op != 'exists' else
                api._api_call(ENDPOINT, dict(kind='ci', name=args.name, operationType='exists')))
        _require_version(api, data)
        if args.op == 'struct':
            path = _save(api, 'ci', args.name, data)
            result = dict(data, **_context(api, 'ci', args.name), artifactKind='structure', snapshotPath=str(path))
        elif code:
            file, sidecar = _save_text(api, 'ci', args.name, data, 'code', data.get('peoplecode') or '', event='Methods')
            _save(api, 'ci', args.name, data, _code_index(api, args.name), 'code', event='Methods')
            result = dict(data, **_context(api, 'ci', args.name), artifactKind='code', event='Methods',
                          cachePath=str(file), snapshotPath=str(sidecar))
        else:
            result = data
        ops._output(api, args, result)
        return result
    if args.op not in WRITES:
        raise api.PSAPIError('Unsupported CI command.')
    original = _snapshot(api, args, code)
    project, _ = ops._project(api, args)
    before = _read(api, args.name, code)
    _require_version(api, before)
    if before['version'] != original['version']:
        _conflict(api, args, api.PSAPIError('CI 已在原始快照之后被修改。', code=409), code)
    if args.op == 'create' and before.get('exists'):
        raise api.PSAPIError('CI 已存在；尚未创建。')
    patch = ops._patch(api, args) if not code else {}
    if not code and args.op != 'create' and not patch:
        raise api.PSAPIError('未提供 properties/collections 补丁。')
    payload = dict(kind='ci', name=args.name, operationType=WRITES[args.op],
                   expectedVersion=original['version'], dryRun=args.dry_run, **patch)
    if code:
        payload['expectedCode'] = original['peoplecode']
        if args.op == 'modify-code':
            if not args.file:
                raise api.PSAPIError('modify-code 需要 --file。')
            payload['peoplecode'] = ops._read_file(api, args.file)
            if not payload['peoplecode'].strip():
                raise api.PSAPIError('空白 Methods 正文不能用于删除；使用 delete-code。')
        elif not original['programExists']:
            raise api.PSAPIError('原始快照中 Methods 程序不存在。')
    backup = None
    if args.op == 'delete-code' and not args.dry_run:
        backup = api._cache_artifact(f'delete_{time.time_ns()}_{args.name}_Methods', '.pcode', before['peoplecode'])
        if isinstance(api, ops._WriteJournal):
            api.snapshots.append(str(backup))
    try:
        result = api._api_call(ENDPOINT, payload)
    except api.PSAPIError as exc:
        if exc.code == 409:
            _conflict(api, args, exc, code)
        raise
    if backup:
        result['snapshotPath'] = str(backup)
    if not args.dry_run:
        after = _read(api, args.name, code)
        _require_version(api, after)
        if after['version'] != result.get('version'):
            _conflict(api, args, api.PSAPIError('CI 在保存后再次被修改；需核实当前状态。', code=409), code)
        if code:
            if args.op == 'delete-code':
                if after.get('programExists'):
                    raise api.PSAPIError('删除后 Methods 程序仍存在。')
            elif (not after.get('programExists') or
                  api._peoplecode_signature(after['peoplecode']) != api._peoplecode_signature(payload['peoplecode'])):
                raise api.PSAPIError('Methods 正文独立回读不符。')
        else:
            ops._verify(api, after, patch, args.op == 'delete-item')
        ops._register(api, project, 42 if code else 32,
                      [args.name, 'Methods'] if code else [args.name], args.op == 'delete-code')
        result.update(verified=True, project=project)
    result['environment'] = api.ENVIRONMENT
    ops._output(api, args, result)
    return result
