"""Page writes use the original downloaded snapshot, including Activate code."""
import json
import time
from pathlib import Path

from definition_operations import _context, _path, _save, _save_text

ENDPOINT = 'AI_OPER_PAGE_DEFN.v1/'


def read(api, name):
    return api._api_call(ENDPOINT, dict(pageName=name, operationType='struct', full=1))


def snapshot(api, args):
    code = args.op in ('modify-code', 'delete-code')
    supplied = getattr(args, 'snapshot', None)
    path = (Path(supplied).resolve() if supplied else
            Path(str(Path(args.file).resolve()) + '.snapshot.json') if code and args.file else
            _path(api, 'page', args.pagename))
    if not path.is_file():
        raise api.PSAPIError('缺少 Page 版本快照：先 page struct/view-code，或提供 --snapshot。')
    try:
        data = json.loads(path.read_text('utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise api.PSAPIError(f'无法读取 Page 快照：{path}') from exc
    if not isinstance(data, dict) or any(data.get(k) != v for k, v in _context(api, 'page', args.pagename).items()):
        raise api.PSAPIError('Page 快照的环境、服务器、账号或页面名称不符。')
    if not isinstance(data.get('version'), str) or not data['version'].startswith('p1:'):
        raise api.PSAPIError('Page 快照缺少版本令牌；先部署新版处理类并重新读取。')
    if data.get('artifactKind') != ('code' if code else 'structure'):
        raise api.PSAPIError('Page 操作需要对应的结构/代码原始快照。')
    return data


def conflict(api, args, error):
    paths = []
    try:
        prefix = f'conflict_{time.time_ns()}_'
        latest = read(api, args.pagename)
        paths.append(str(_save(api, 'page', args.pagename, latest,
            api._artifact_dir() / f'{prefix}{args.pagename}.structure.json')))
        if args.op in ('modify-code', 'delete-code') and latest.get('exists'):
            code = api._api_call(ENDPOINT, dict(pageName=args.pagename, operationType='viewPeopleCode'))
            paths.extend(map(str, _save_text(api, 'page', args.pagename, code, 'code',
                code.get('peoplecode') or '', prefix, event='Activate')))
    except Exception as exc:
        paths.append('最新状态读取失败：' + str(exc))
    raise api.PSAPIError(str(error), code=409, hint='Page 版本冲突，原稿和原快照保留，未重试写入。\n' + '\n'.join(paths)) from error


def fresh_baseline(api, args):
    original = snapshot(api, args)
    current = read(api, args.pagename)
    if current.get('version') != original['version']:
        conflict(api, args, api.PSAPIError('Page 已在原始快照之后被修改。', code=409))
    return original, current


def guarded_call(api, args, payload, version):
    try:
        return api._api_call(ENDPOINT, dict(payload, expectedVersion=version))
    except api.PSAPIError as exc:
        if exc.code == 409:
            conflict(api, args, exc)
        raise


def handle_page(api, args):
    name = args.pagename
    if args.op == 'struct':
        data = read(api, name)
        path = _save(api, 'page', name, data)
        if args.output:
            _save(api, 'page', name, data, Path(args.output).resolve())
        if args.json:
            print(json.dumps(dict(data, snapshotPath=str(path)), ensure_ascii=False, indent=2))
        else:
            api._print_page_struct(data, full=args.full)
            print(f'Snapshot: {path}')
        return data
    if args.op == 'view-code':
        data = api._api_call(ENDPOINT, dict(pageName=name, operationType='viewPeopleCode'))
        file, sidecar = _save_text(api, 'page', name, data, 'code', data.get('peoplecode') or '', event='Activate')
        print(data.get('peoplecode') or '(no Activate PeopleCode)')
        print(f'Cached: {file}\nSnapshot: {sidecar}')
        return data
    if args.op in ('add-control', 'mod-control'):
        from page_controls import write_control
        return write_control(api, args, adding=args.op == 'add-control')
    if args.op == 'find':
        payload = dict(pageName=name, operationType='findControls')
        for attr, key in [('rec', 'recName'), ('field', 'fieldName'), ('label_text', 'labelContains'), ('field_type', 'fieldType')]:
            if getattr(args, attr, None) is not None:
                payload[key] = getattr(args, attr)
        data = api._api_call(ENDPOINT, payload)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return data
    if args.dry_run and args.op != 'delete-code':
        raise api.PSAPIError('--dry-run 仅适用于 delete-code；尚未写入。')
    project = args.project or api._active_project()
    if not project:
        raise api.PSAPIError('Page 写入需要 --project 或已确认的当前工程。')
    api._require_project(project)
    original, before = fresh_baseline(api, args)
    payload = dict(pageName=name)
    if args.op == 'create':
        if before.get('exists'):
            raise api.PSAPIError('Page 已存在；尚未创建。')
        payload['operationType'] = 'createPage'
    elif args.op == 'modify-props':
        payload['operationType'] = 'modifyPageProps'
    elif args.op == 'del-control':
        if args.pnl_fld_id is None:
            raise api.PSAPIError('del-control requires --pnl-fld-id')
        payload.update(operationType='deleteControl', pnlFldId=args.pnl_fld_id)
    elif args.op in ('modify-code', 'delete-code'):
        if args.op == 'modify-code':
            if not args.file or not Path(args.file).is_file():
                raise api.PSAPIError('modify-code requires a saved --file')
            text = Path(args.file).read_text('utf-8-sig')
            if not text.strip():
                raise api.PSAPIError('Empty PeopleCode is not deletion; use delete-code.')
            payload.update(operationType='modifyPeopleCode', peoplecode=api.json_escape(text))
        else:
            payload.update(operationType='deletePeopleCode', expectedCode=api.json_escape(original.get('peoplecode') or ''), dryRun=args.dry_run)
    else:
        raise api.PSAPIError('Unsupported Page operation')
    if args.op in ('create', 'modify-props'):
        for attr, key in [('descr', 'descr'), ('comment', 'comment'), ('pnl_type', 'pnlType'),
                          ('defer_proc', 'deferProc'), ('panel_right', 'panelRight'), ('panel_bottom', 'panelBottom')]:
            value = getattr(args, attr, None)
            if value is not None:
                payload[key] = api.json_escape(value) if key == 'comment' else value
        if args.op == 'modify-props' and len(payload) == 2:
            raise api.PSAPIError('modify-props 至少指定一个属性。')
    result = guarded_call(api, args, payload, original['version'])
    try:
        after = read(api, name)
        if result.get('version') != after.get('version'):
            raise ValueError('写后页面版本不符，可能存在后续并发修改')
        if args.op == 'del-control' and any(f['pnlFldId'] == args.pnl_fld_id for f in after['fields']):
            raise ValueError('目标控件仍存在')
        if args.op in ('modify-code', 'delete-code'):
            code = api._api_call(ENDPOINT, dict(pageName=name, operationType='viewPeopleCode'))
            if args.op == 'modify-code' and api._peoplecode_signature(code.get('peoplecode')) != api._peoplecode_signature(text):
                raise ValueError('Activate 正文回读不一致')
            if args.op == 'delete-code' and code.get('programExists') is not bool(args.dry_run):
                raise ValueError('Activate 存在状态不符')
        if args.op == 'modify-props':
            columns = dict(descr='DESCR', comment='DESCRLONG', pnlType='PNLTYPE', deferProc='DEFERPROC', panelRight='PANELRIGHT', panelBottom='PANELBOTTOM')
            for key, column in columns.items():
                if key in payload:
                    expected = args.comment if key == 'comment' else payload[key]
                    if after['raw'][column] != expected:
                        raise ValueError(f'{key} 回读不一致')
    except Exception as exc:
        raise api.PSAPIError(f'Page 写入请求已提交，回读未通过：{exc}；先检查现状，不重发写入。') from exc
    if not args.dry_run:
        try:
            if args.op == 'delete-code':
                item = result['projectItem']
                api._insert_project_item(project, item['objectType'], [item[f'objectValue{i}'] for i in range(1, 5)], action=1, take_action=1)
            else:
                api._insert_project_item(project, 5, [name], action=0, take_action=1)
        except Exception as exc:
            raise api.PSAPIError(f'Page 写入和回读已通过，工程登记失败：{exc}；仅补登记。') from exc
        _save(api, 'page', name, after)
    result.update(pageName=name, project=project, readbackVerified=True)
    if args.output:
        api._write_json_atomic(Path(args.output).resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else f'OK — Page {args.op}: {name}; readback verified')
    return result
