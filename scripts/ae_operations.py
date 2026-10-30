"""AE writes use the original, context-bound snapshot; conflicts never retry writes."""
import copy
import hashlib
import json
import time
from pathlib import Path
from definition_operations import _context, _path, _save, _save_text

ENDPOINT = 'AI_OPER_APP_ENGINE.v1/'
OPERATIONS = {'create': 'createApplicationEngine', 'insert-section': 'insertSection',
    'insert-step': 'insertStep', 'insert-action': 'insertAction', 'modify-code': 'modifyPeopleCode',
    'modify-sql': 'modifySQL', 'delete-code': 'deletePeopleCode', 'delete-section': 'deleteSection',
    'delete-step': 'deleteStep', 'delete-action': 'deleteAction',
    'insert-state-record': 'insertStateRecord', 'insert-temp-table': 'insertTempTable'}
DELETES = {'delete-section', 'delete-step', 'delete-action', 'delete-code'}


def key(args, action=False):
    result = dict(sectionId=args.sectionid, market=args.market, dbType=args.dbtype.strip(), effdt=args.effdt)
    if args.stepid: result['stepId'] = args.stepid
    if action: result['actionType'] = args.actiontype
    return result


def read(api, args):
    return api._api_call(ENDPOINT, dict(aeId=args.aeid, operationType='struct'))


def artifact(args):
    if args.op in ('view-code', 'modify-code', 'delete-code'): return 'code'
    if args.op in ('view-sql', 'modify-sql'): return 'sql'
    return 'structure'


def artifact_key(args):
    return key(args, action=artifact(args) == 'sql')


def artifact_index(api, args):
    identity = dict(_context(api, 'ae', args.aeid), **artifact_key(args), artifactKind=artifact(args))
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:20]
    return api._artifact_dir() / f'ae_{digest}_{args.aeid}.{artifact(args)}.snapshot.json'


def snapshot(api, args, file):
    kind = artifact(args)
    path = Path(args.snapshot).resolve() if args.snapshot else (
        Path(str(file) + '.snapshot.json') if file and kind in ('code', 'sql') else
        _path(api, 'ae', args.aeid) if kind == 'structure' else artifact_index(api, args))
    if not path.is_file():
        raise api.PSAPIError('缺少 AE 原始快照：先 struct/view-code/view-sql，或指定 --snapshot。')
    try: data = json.loads(path.read_text('utf-8-sig'))
    except (OSError, ValueError) as exc: raise api.PSAPIError(f'无法读取快照：{path}') from exc
    if not isinstance(data, dict) or any(data.get(k) != v for k, v in _context(api, 'ae', args.aeid).items()):
        raise api.PSAPIError('快照的环境、服务器、账号或 AE 不符。')
    if not isinstance(data.get('version'), str) or not data['version'].startswith('ae1:'):
        raise api.PSAPIError('快照缺少 AE 版本令牌；部署新版服务端并重新读取。')
    if data.get('artifactKind') != kind:
        raise api.PSAPIError('需要与操作对应的结构、代码或 SQL 快照。')
    if kind != 'structure' and any(data.get(k) != v for k, v in artifact_key(args).items()):
        raise api.PSAPIError('快照的 Section/Market/DBType/EffDt/Step/Action 不符。')
    return data


def conflict(api, args, error):
    try:
        latest = read(api, args)
        path = api._artifact_dir() / f'conflict_{time.time_ns()}_{args.aeid}.structure.json'
        _save(api, 'ae', args.aeid, latest, path)
        hint = f'最新结构已保存：{path}；原稿和原快照保留，未重试。'
    except Exception as exc:
        hint = f'最新状态读取失败：{exc}；原稿和原快照保留，未重试。'
    raise api.PSAPIError(str(error), code=409, hint=hint) from error


def target(data, args):
    sections = [s for s in data.get('sections', []) if s['sectionId'] == args.sectionid]
    variants = [d for s in sections for d in s.get('detail', [])
        if (d['market'], d['dbType'].strip(), d['effdt']) == (args.market, args.dbtype.strip(), args.effdt)]
    if len(variants) != 1: raise ValueError('精确 Section 版本不存在或不唯一')
    if args.op in ('delete-section', 'insert-step'): return variants[0]
    steps = [s for s in variants[0].get('steps', []) if s['stepId'] == args.stepid]
    if len(steps) != 1: raise ValueError('精确 Step 不存在或不唯一')
    return steps[0]


def verify_delete(before, after, args):
    expected = copy.deepcopy(before)
    section = next(s for s in expected['sections'] if s['sectionId'] == args.sectionid)
    variant = next(d for d in section['detail'] if (d['market'], d['dbType'].strip(), d['effdt']) ==
        (args.market, args.dbtype.strip(), args.effdt))
    if args.op == 'delete-section':
        section['detail'].remove(variant)
        if not section['detail']: expected['sections'].remove(section)
    elif args.op == 'delete-step':
        variant['steps'] = [s for s in variant['steps'] if s['stepId'] != args.stepid]
    else:
        step = next(s for s in variant['steps'] if s['stepId'] == args.stepid)
        step['actions'] = [a for a in step['actions'] if a['actionType'] != args.actiontype]
    if after.get('sections') != expected['sections']:
        raise ValueError('删除目标或相邻 Section/Step/Action 回读不符')


def register(api, project, items):
    # Cascades can refer to the same SQL definition more than once. Last state wins.
    unique = {api._project_item_key(i): i for i in items}
    for item in unique.values():
        _, actual = api._insert_project_item(project, item['objectType'],
            [item[f'objectValue{i}'] for i in range(1, 5)], action=1 if item.get('deleted') else 0)
        if api._project_item_key(actual) != api._project_item_key(item): raise ValueError('工程完整键不符')


def handle(api, args):
    op = args.op
    file_arg = args.input_file or args.file
    if args.input_file and args.file: raise api.PSAPIError('正文文件只提供一次。')
    file = Path(file_arg).resolve() if file_arg else None
    if op not in ('struct', 'create', 'insert-section', 'insert-state-record', 'insert-temp-table') and not args.sectionid:
        raise api.PSAPIError('该操作需要 --sectionid。')
    if op in ('insert-action', 'view-code', 'modify-code', 'delete-code', 'view-sql', 'modify-sql', 'delete-step', 'delete-action') and not args.stepid:
        raise api.PSAPIError('该操作需要 --stepid。')
    if op in ('insert-action', 'view-sql', 'modify-sql', 'delete-action') and args.actiontype not in set('SPMWCHNXD'):
        raise api.PSAPIError('需要有效的 --actiontype S/P/M/W/C/H/N/X/D。')
    if args.dry_run and op not in DELETES: raise api.PSAPIError('--dry-run 仅支持删除。')
    if op == 'delete-section' and args.stepid: raise api.PSAPIError('delete-section 不接受 --stepid；删除一个 Step 使用 delete-step。')
    if op in ('delete-section', 'delete-step') and args.actiontype: raise api.PSAPIError('该删除层级不接受 --actiontype；删除一个 Action 使用 delete-action。')
    if op == 'struct':
        data = read(api, args)
        path = _save(api, 'ae', args.aeid, data)
        if args.output: _save(api, 'ae', args.aeid, data, Path(args.output).resolve())
        if args.json: print(json.dumps(dict(data, snapshotPath=str(path)), ensure_ascii=False, indent=2))
        else:
            print(f"AE: {args.aeid}\nexists: {data.get('exists')}\ndescr: {data.get('descr', '')}\nversion: {data.get('version', '')}")
            for section in data.get('sections', []):
                print(f"\nSection: {section['sectionId']}")
                for detail in section.get('detail', []):
                    print(f"  [{detail['market']}/{detail['dbType']}] effdt={detail['effdt']} {detail.get('descr', '')}")
                    for step in detail.get('steps', []):
                        print(f"    Step: {step['stepId']}")
                        for action in step.get('actions', []): print(f"      Action: {action['actionType']} {action.get('descr', '')}")
            print(f'Snapshot: {path}')
        return data
    if op in ('view-code', 'view-sql'):
        code = op == 'view-code'
        data = api._api_call(ENDPOINT, dict(aeId=args.aeid, operationType='viewPeopleCode' if code else 'viewSQL', **artifact_key(args)))
        text = data.get('peoplecode' if code else 'sqlText') or ''
        cached, sidecar = _save_text(api, 'ae', args.aeid, data, artifact(args), text, **artifact_key(args))
        _save(api, 'ae', args.aeid, data, artifact_index(api, args), artifact(args), **artifact_key(args))
        if args.output: _save(api, 'ae', args.aeid, data, Path(args.output).resolve(), artifact(args), **artifact_key(args))
        print(json.dumps(dict(data, cachedPath=str(cached), snapshotPath=str(sidecar)), ensure_ascii=False, indent=2)
              if args.json else f'{text}\nCached: {cached}\nSnapshot: {sidecar}')
        return data
    original = snapshot(api, args, file)
    project = args.project or api._active_project()
    if not project: raise api.PSAPIError('AE 写入需要 --project 或已确认的当前工程。')
    api._require_project(project)
    before = read(api, args)
    if before.get('aeVersionControl') != 1: raise api.PSAPIError('服务端缺少 AE 版本保护；未写入。')
    if before.get('version') != original['version']: conflict(api, args, api.PSAPIError('AE 已在原始快照后修改。', code=409))
    if op == 'create' and before.get('exists'): raise api.PSAPIError('AE 已存在。')
    if op != 'create' and not before.get('exists'): raise api.PSAPIError('AE 不存在。')
    payload = dict(aeId=args.aeid, operationType=OPERATIONS[op], expectedVersion=original['version'])
    if op in ('insert-section', 'insert-step', 'insert-action', 'modify-code', 'delete-code', 'modify-sql') or op in DELETES:
        payload.update(key(args, action=op in ('insert-action', 'delete-action', 'modify-sql')))
        if op == 'insert-section': payload.pop('stepId', None)
        if op == 'delete-section': payload.pop('stepId', None)
    if op in ('create', 'insert-section', 'insert-step', 'insert-action') and args.descr is not None: payload['descr'] = args.descr
    if op == 'create' and args.comment is not None: payload['comment'] = api.json_escape(args.comment)
    if op in ('modify-code', 'modify-sql'):
        if not file or not file.is_file(): raise api.PSAPIError('修改正文需要本地 UTF-8 文件。')
        text = file.read_text('utf-8-sig')
        if not text.strip(): raise api.PSAPIError('拒绝空白正文；删除请使用明确的 delete 命令。')
        payload['peopleCode' if op == 'modify-code' else 'sqlText'] = api.json_escape(text)
    if op == 'delete-code':
        if not original.get('programExists'): raise api.PSAPIError('原始快照中程序不存在。')
        payload['expectedCode'] = api.json_escape(original.get('peoplecode') or '')
    if op in DELETES: payload['dryRun'] = bool(args.dry_run)
    if op in ('insert-state-record', 'insert-temp-table'):
        if not args.recname: raise api.PSAPIError('需要 --recname。')
        payload['recName'] = args.recname
        if op == 'insert-state-record': payload['isDefault'] = args.is_default
    try: result = api._api_call(ENDPOINT, payload)
    except api.PSAPIError as exc:
        if exc.code == 409: conflict(api, args, exc)
        raise
    try:
        after = read(api, args)
        if after.get('version') != result.get('version'): raise ValueError('写后版本不同，可能有并发修改')
        if args.dry_run:
            if after != before or result.get('deleted') is not False or result.get('dryRun') is not True:
                raise ValueError('dry-run 修改了定义或缺少确认')
        elif op in ('delete-section', 'delete-step', 'delete-action'):
            if result.get('deleted') is not True: raise ValueError('服务端未确认删除')
            verify_delete(before, after, args)
        elif op in ('modify-code', 'delete-code', 'modify-sql'):
            actual = api._api_call(ENDPOINT, dict(aeId=args.aeid, operationType='viewSQL' if op == 'modify-sql' else 'viewPeopleCode', **artifact_key(args)))
            if actual.get('version') != after['version']: raise ValueError('正文回读时版本改变')
            if op == 'modify-code' and api._peoplecode_signature(actual.get('peoplecode')) != api._peoplecode_signature(text): raise ValueError('代码回读不符')
            if op == 'delete-code' and actual.get('programExists') is not False: raise ValueError('原生程序仍存在')
            if op == 'modify-sql' and (actual.get('sqlText') or '').replace('\r\n', '\n').strip() != text.replace('\r\n', '\n').strip(): raise ValueError('SQL 回读不符')
        elif op == 'create' and not after.get('exists'): raise ValueError('AE 创建回读不存在')
        elif op in ('insert-state-record', 'insert-temp-table'):
            values = [r['recordName'] for r in after['stateRecords']] if op == 'insert-state-record' else after['tempTables']
            if args.recname not in values: raise ValueError('Record 关联回读不符')
        elif op.startswith('insert-'):
            if not after.get('sections') or after['sections'] == before['sections']: raise ValueError('结构未改变')
    except Exception as exc:
        raise api.PSAPIError(f'写入已提交，但独立回读未通过：{exc}；先检查现状，不重试写入。') from exc
    if not args.dry_run:
        try:
            items = result.get('projectItems') or [dict(result['projectItem'], deleted=op == 'delete-code')]
            register(api, project, items)
        except Exception as exc: raise api.PSAPIError(f'写入与回读成功，但工程登记失败：{exc}；仅补登记。') from exc
        _save(api, 'ae', args.aeid, after)
    result.update(project=project, readbackVerified=True)
    if args.output: api._write_json_atomic(Path(args.output).resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else f'OK — AE {args.aeid}: {op}; readback verified')
    return result
