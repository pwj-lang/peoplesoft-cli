"""HTML/StyleSheet writes retain the original, context-bound editing baseline."""
import hashlib
import json
import time
from pathlib import Path

from definition_operations import _context, _path, _save

ENDPOINTS = {'html': 'AI_OPER_HTML_DEFN.v1/', 'image': 'AI_OPER_HTML_DEFN.v1/', 'stylesheet': 'AI_OPER_STYLESHEET_DEFN.v1/'}
FIELDS = {'html': 'ContStrData', 'image': 'ContStrData', 'stylesheet': 'ExtStyleSheetStr'}
PREFIXES = {'html': 'html1:', 'image': 'image1:', 'stylesheet': 'css1:'}


def _read(api, kind, name, operation='struct'):
    return api._api_call(ENDPOINTS[kind], dict(kind=kind, name=name, operationType=operation))


def _require_version(api, kind, data):
    if (data.get(kind + 'VersionControl') != 1 or not isinstance(data.get('version'), str)
            or not data['version'].startswith(PREFIXES[kind])):
        raise api.PSAPIError(f'服务端缺少 {kind} 版本保护；部署配套处理类并重新读取，未写入。')
    if kind == 'image' and data.get('exists') and any(not isinstance(data.get(k), str) for k in ('blobFingerprint','translationBlobFingerprint')):
        raise api.PSAPIError('Image 读取缺少完整 BLOB 指纹；先更新服务端并读取新的原始快照。')


def _save_content(api, kind, name, data, prefix=''):
    identity = json.dumps(_context(api, kind, name), sort_keys=True).encode()
    key = hashlib.sha256(identity).hexdigest()[:16]
    text = data.get(FIELDS[kind])
    if not isinstance(text, str):
        raise api.PSAPIError(f'{kind} 结构缺少正文，未建立内容快照。')
    file = api._cache_artifact(f'{prefix}{kind}_{key}_{name}', '.svg' if kind == 'image' else '.html' if kind == 'html' else '.css', text)
    sidecar = _save(api, kind, name, data, Path(str(file) + '.snapshot.json'))
    return file, sidecar


def _snapshot(api, args):
    sidecar = Path(str(Path(args.content_file).resolve()) + '.snapshot.json') if args.content_file else None
    path = (Path(args.snapshot).resolve() if args.snapshot else
            sidecar if sidecar and sidecar.is_file() else _path(api, args.cmd, args.name))
    if not path.is_file():
        raise api.PSAPIError(f'缺少 {args.cmd} 原始快照：先 {args.cmd} struct，或使用 --snapshot。')
    try:
        data = json.loads(path.read_text('utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise api.PSAPIError(f'无法读取 {args.cmd} 快照：{path}') from exc
    if not isinstance(data, dict) or any(data.get(k) != v for k, v in _context(api, args.cmd, args.name).items()):
        raise api.PSAPIError('HTML/StyleSheet 快照的环境、服务器、节点、账号、对象类型或名称不符。')
    _require_version(api, args.cmd, data)
    if data.get('artifactKind') != 'structure' or type(data.get('exists')) is not bool:
        raise api.PSAPIError('HTML/StyleSheet 写入需要 struct 的原始结构快照及存在状态。')
    return data


def _conflict(api, args, error):
    paths = []
    prefix = f'conflict_{time.time_ns()}_'
    try:
        latest = _read(api, args.cmd, args.name)
        paths.append(str(_save(api, args.cmd, args.name, latest,
            api._artifact_dir() / f'{prefix}{args.cmd}_{args.name}.structure.json')))
        if latest.get('exists'):
            paths.extend(map(str, _save_content(api, args.cmd, args.name, latest, prefix)))
    except Exception as exc:
        paths.append('最新状态读取失败：' + str(exc))
    raise api.PSAPIError(str(error), code=409,
        hint='HTML/StyleSheet 版本冲突，原稿和原快照保留，未重试写入。\n' + '\n'.join(paths)) from error


def handle(api, args):
    import object_operations as ops
    kind, name = args.cmd, args.name
    if args.op in ('struct', 'exists'):
        data = _read(api, kind, name, args.op)
        _require_version(api, kind, data)
        if args.op == 'struct':
            path = _save(api, kind, name, data)
            result = dict(data, **_context(api, kind, name), artifactKind='structure', snapshotPath=str(path))
            if data.get('exists') and kind != 'image':
                file, sidecar = _save_content(api, kind, name, data)
                result.update(cachePath=str(file), contentSnapshotPath=str(sidecar))
        else:
            result = data
        ops._output(api, args, result)
        return result
    if kind == 'image' and args.op == 'clone':
        return clone_image(api, args)
    if args.op not in ('create', 'modify'):
        raise api.PSAPIError('Unsupported HTML/StyleSheet command.')
    original = _snapshot(api, args)
    patch = ops._patch(api, args)
    if args.op == 'modify' and not patch:
        raise api.PSAPIError('未提供 properties 补丁或 --content-file/--descr。')
    project, _ = ops._project(api, args)
    before = _read(api, kind, name)
    _require_version(api, kind, before)
    if before['version'] != original['version']:
        _conflict(api, args, api.PSAPIError('定义已在原始快照之后被修改。', code=409))
    if args.op == 'create' and before.get('exists'):
        raise api.PSAPIError('定义已存在；尚未创建。')
    payload = dict(kind=kind, name=name, operationType=args.op, expectedVersion=original['version'],
                   dryRun=args.dry_run, **patch)
    try:
        result = api._api_call(ENDPOINTS[kind], payload)
    except api.PSAPIError as exc:
        if exc.code == 409:
            _conflict(api, args, exc)
        raise
    _require_version(api, kind, result)
    if not args.dry_run:
        after = _read(api, kind, name)
        _require_version(api, kind, after)
        if after['version'] != result['version']:
            _conflict(api, args, api.PSAPIError('定义在保存后再次被修改；需核实当前状态。', code=409))
        ops._verify(api, after, patch)
        typ, values = (49, [name, '1']) if kind == 'image' else (51, [name, '4']) if kind == 'html' else (50, [name])
        ops._register(api, project, typ, values)
        result.update(verified=True, project=project)
    result['environment'] = api.ENVIRONMENT
    ops._output(api, args, result)
    return result


def clone_image(api, args):
    import object_operations as ops
    if not args.source or args.source == args.name or args.file or args.content_file or args.descr:
        raise api.PSAPIError('image clone 需要不同的 --source；不接受正文或属性补丁。')
    original = _snapshot(api, args)
    if original.get('exists'):
        raise api.PSAPIError('目标 Image 已存在；不覆盖。')
    source_path = Path(args.source_snapshot).resolve() if args.source_snapshot else _path(api, 'image', args.source)
    try: source = json.loads(source_path.read_text('utf-8-sig'))
    except (OSError, ValueError): raise api.PSAPIError('缺少源 image struct 原始快照。') from None
    if any(source.get(k) != v for k, v in _context(api, 'image', args.source).items()) or source.get('exists') is not True:
        raise api.PSAPIError('源 Image 快照环境、对象或存在状态不符。')
    _require_version(api, 'image', source)
    project, _ = ops._project(api, args)
    payload = dict(kind='image', name=args.name, operationType='create', sourceName=args.source,
                   expectedSourceVersion=source['version'], expectedVersion=original['version'], dryRun=args.dry_run)
    result = api._api_call(ENDPOINTS['image'], payload)
    _require_version(api, 'image', result)
    target = _read(api, 'image', args.name)
    source_after = _read(api, 'image', args.source)
    if source_after.get('version') != source['version']:
        raise api.PSAPIError('源 Image 在克隆后发生变化；检查实际状态，不重试。')
    if args.dry_run:
        if target.get('exists') or target.get('version') != original['version']:
            raise api.PSAPIError('Image dry-run 未保持目标缺席状态。')
    else:
        if (not target.get('exists') or target.get('version') != result['version'] or
                target.get('blobFingerprint') != source.get('blobFingerprint') or
                target.get('translationBlobFingerprint') != source.get('translationBlobFingerprint')):
            raise api.PSAPIError('Image 已写入，但原生 BLOB 独立回读不符；检查实际状态。')
        ops._register(api, project, 49, [args.name, '1'])
    result.update(verified=True, project=project, dryRun=args.dry_run)
    ops._output(api, args, result)
    return result
