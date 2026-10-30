"""Standalone SQL and Project writes use the original, context-bound baseline."""
import hashlib
import json
import re
import time
from pathlib import Path
from definition_operations import _context, _path, _save

ENDPOINTS = {'sql': 'AI_OPER_SQL_DEFN.v1/', 'project': 'AI_OPER_PROJECT_DEFN.v1/'}
PREFIXES = {'sql': 'sql1:', 'project': 'prj1:'}


def require(api, kind, data):
    if (data.get(kind + 'VersionControl') != 1 or not isinstance(data.get('version'), str)
            or not data['version'].startswith(PREFIXES[kind])):
        raise api.PSAPIError(f'服务端缺少 {kind} 原始版本保护；部署配套处理类后重新读取。')


def read(api, kind, name):
    key = 'sqlId' if kind == 'sql' else 'projectName'
    result = api._api_call(ENDPOINTS[kind], {key: name, 'operationType': 'view' if kind == 'sql' else 'struct'})
    require(api, kind, result)
    return result


def _snapshot(api, args, kind, name):
    supplied = getattr(args, 'snapshot', None)
    text_file = getattr(args, 'sqltext_file', None) or getattr(args, 'comment_file', None)
    if supplied:
        path = Path(supplied).resolve()
    elif kind == 'sql' and args.op == 'modify' and text_file:
        # Never fall back to a newer structure snapshot when an editing file is supplied.
        path = Path(str(Path(text_file).resolve()) + '.snapshot.json')
    else:
        path = _path(api, kind, name)
    if not path.is_file():
        raise api.PSAPIError(f'缺少 {kind} 原始快照：先读取 sql view / project struct，或使用 --snapshot。')
    try:
        result = json.loads(path.read_text('utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise api.PSAPIError(f'无法读取原始快照：{path}') from exc
    if not isinstance(result, dict) or any(result.get(k) != v for k, v in _context(api, kind, name).items()):
        raise api.PSAPIError('快照的环境、服务器、节点、账号、定义类型或名称不符。')
    require(api, kind, result)
    if result.get('artifactKind') not in ('structure', 'sql') or type(result.get('exists')) is not bool:
        raise api.PSAPIError('快照缺少原始结构或存在状态。')
    collection = 'statements' if kind == 'sql' else 'items'
    if (not isinstance(result.get(collection), list)
            or any(not isinstance(row, dict) for row in result[collection])
            or (kind == 'project' and result['exists'] and not isinstance(result.get('header'), dict))):
        raise api.PSAPIError('快照缺少完整的 SQL Statement 或 Project 结构。')
    if result['artifactKind'] == 'sql':
        if kind != 'sql' or args.op != 'modify':
            raise api.PSAPIError('该操作需要原始结构快照。')
        target = dict(market=args.market, dbType=_db(api, args.dbtype), effdt=args.effdt)
        if result.get('statementKey') != target:
            raise api.PSAPIError('SQL 工作副本快照与 Market/DBType/EffDt 不符。')
    return result


def _db(api, value):
    native = api._normalize_dbtype(value)
    return '32' if native == '' else str(48 + int(native))


def _text_files(api, name, data, prefix=''):
    files = []
    identity = hashlib.sha256(json.dumps(_context(api, 'sql', name), sort_keys=True).encode()).hexdigest()[:16]
    for stmt in data.get('statements', []):
        key = dict(market=stmt['market'], dbType=_db(api, stmt['dbType']), effdt=str(stmt['effdt'])[:10])
        stem = f"{prefix}sql_{identity}_{name}_{key['market']}_{key['dbType']}_{key['effdt']}"
        path = api._cache_artifact(stem, '.sql', stmt.get('sqlText') or '')
        snapshot = _save(api, 'sql', name, data, Path(str(path) + '.snapshot.json'), artifact='sql', statementKey=key)
        files.append(dict(**key, cachePath=str(path), snapshotPath=str(snapshot)))
    return files


def conflict(api, kind, name, error):
    paths = []
    prefix = f'conflict_{time.time_ns()}_'
    try:
        latest = read(api, kind, name)
        paths.append(str(_save(api, kind, name, latest, api._artifact_dir() / f'{prefix}{kind}_{name}.structure.json')))
        if kind == 'sql' and latest.get('exists'):
            paths.extend(f['cachePath'] for f in _text_files(api, name, latest, prefix))
    except Exception as exc:
        paths.append('最新状态读取失败：' + str(exc))
    raise api.PSAPIError(str(error), code=409, hint='版本冲突；原稿与原快照保留，未自动重试。\n' + '\n'.join(paths)) from error


def write(api, kind, name, payload, original):
    require(api, kind, original)
    try:
        result = api._api_call(ENDPOINTS[kind], dict(payload, expectedVersion=original['version']))
    except api.PSAPIError as exc:
        if exc.code == 409:
            conflict(api, kind, name, exc)
        raise
    require(api, kind, result)
    return result


def _after(api, kind, name, result):
    actual = read(api, kind, name)
    if actual['version'] != result['version']:
        conflict(api, kind, name, api.PSAPIError('保存后定义再次变化，请核对当前状态。', code=409))
    return actual


def _output(api, args, result):
    if getattr(args, 'output', None):
        api._write_json_atomic(Path(args.output).resolve(), result)
    if args.op in ('view', 'struct') and not getattr(args, 'json', False):
        if args.cmd == 'sql':
            print(f"sqlId: {result.get('sqlId')}\nsqlType: {result.get('sqlType')}\nexists: {result['exists']}")
            print(f"lastUpdate: {result.get('lastUpdate', '')}")
            for statement, file in zip(result.get('statements', []), result['files']):
                print(f"\n--- [{statement['market']}/{statement['dbType']}] {statement['effdt']} ---")
                print(statement.get('sqlText') or '')
                print(f"Cached: {file['cachePath']}\nSnapshot: {file['snapshotPath']}")
                if statement.get('descr'): print('descr: ' + statement['descr'])
                if statement.get('comment'): print('comment: ' + statement['comment'])
        else:
            print(f"Project: {result.get('projectName')}\nexists: {result['exists']}")
            header = result.get('header', {})
            if header:
                print('Options: ' + ' '.join(f'{k}={header.get(k)}' for k in ('KEEPTGT','REPORTFILTER','COMPARETYPE','COMMITLIMIT','TGTORIENTATION')))
            items = result.get('items', [])
            print(f'Items ({len(items)}):')
            for item in items:
                keys = '  '.join(f"id{i}={item.get(f'objectId{i}')} value{i}={item.get(f'objectValue{i}')}" for i in range(1,5))
                print(f"  objectType={item['objectType']}  {keys}  {api._format_project_flags(item)}")
        print(f"Version: {result['version']}\nSnapshot: {result['snapshotPath']}")
        return result
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def handle_sql(api, args):
    if args.op in ('exec', 'run', 'write'):
        if args.dry_run:
            raise api.PSAPIError('--dry-run 仅适用于 SQL 定义创建/修改，不支持数据执行。')
        from sql_execution import execute
        return execute(api, args)
    name = args.sqlid
    if not name:
        raise api.PSAPIError('SQL 定义命令需要 SQL ID。')
    if args.op == 'view':
        data = read(api, 'sql', name)
        snapshot = _save(api, 'sql', name, data)
        result = dict(data, **_context(api, 'sql', name), artifactKind='structure', snapshotPath=str(snapshot))
        result['files'] = _text_files(api, name, data)
        return _output(api, args, result)
    original = _snapshot(api, args, 'sql', name)
    payload = dict(sqlId=name, operationType=args.op, dryRun=args.dry_run)
    expected = []
    if args.op == 'create':
        if not args.file:
            raise api.PSAPIError('sql create 需要 statements JSON 文件或内联 JSON。')
        patch = api._load_json_arg(args.file, 'create 的 JSON')
        if not isinstance(patch, dict) or not isinstance(patch.get('statements'), list) or not patch['statements']:
            raise api.PSAPIError('create 需要至少一条 Statement。')
        for stmt in patch['statements']:
            if not isinstance(stmt, dict) or not isinstance(stmt.get('sqlText'), str):
                raise api.PSAPIError('每条 Statement 需要 sqlText 字符串。')
            expected.append(dict(market=stmt.get('market', 'GBL'), dbType=_db(api, stmt.get('dbType', '')),
                                 effdt=stmt.get('effdt', '1900-01-01'), **{k:v for k,v in stmt.items() if k not in ('market','dbType','effdt')}))
        payload['statements'] = [dict(s, dbType=api._normalize_dbtype(s['dbType']),
            sqlText=api.json_escape(s['sqlText']), **({'comment':api.json_escape(s['comment'])} if 'comment' in s else {})) for s in expected]
    else:
        key = dict(market=args.market, dbType=_db(api, args.dbtype), effdt=args.effdt)
        payload.update(key, dbType=api._normalize_dbtype(args.dbtype))
        patch = {}
        for field, file in (('sqlText', args.sqltext_file), ('comment', args.comment_file)):
            if file:
                patch[field] = Path(file).read_text('utf-8-sig')
                payload[field] = api.json_escape(patch[field])
        if args.descr is not None:
            patch['descr'] = payload['descr'] = args.descr
        if not patch:
            raise api.PSAPIError('sql modify 需要 --sqltext-file、--comment-file 或 --descr。')
        expected = [dict(s, **patch) if all(str(s[k])[:10] == v for k,v in key.items()) else s for s in original['statements']]
    result = write(api, 'sql', name, payload, original)
    if not args.dry_run:
        actual = _after(api, 'sql', name, result)
        def keyed(statements):
            return {(s['market'],_db(api,s['dbType']),str(s['effdt'])[:10]):s for s in statements}
        wanted, found = keyed(expected), keyed(actual['statements'])
        if wanted.keys() != found.keys():
            raise api.PSAPIError('SQL 保存后 Statement 集合不符。')
        for key, stmt in wanted.items():
            for field in ('sqlText','descr','comment'):
                if field in stmt:
                    value = re.sub(r'\s+', ' ', stmt[field]) if field == 'sqlText' else stmt[field]
                    if found[key].get(field) != value:
                        raise api.PSAPIError(f'SQL 保存后 Statement {key} 的 {field} 不符；请核对当前状态，勿盲目重试。')
        result['verified'] = True
    return _output(api, args, result)


def handle_project(api, args):
    if args.op == 'current':
        print(f'Current project for environment {api.ENVIRONMENT}: {api._active_project() or "(none)"}')
        return
    name = args.projectname
    if not name:
        raise api.PSAPIError('Project 命令需要工程名称。')
    if args.op == 'use':
        if not read(api, 'project', name).get('exists'):
            raise api.PSAPIError('Project 不存在。')
        api._set_active_project(name)
        print(f'Current project for environment {api.ENVIRONMENT}: {name}')
        return
    if args.op == 'struct':
        data = read(api, 'project', name)
        path = _save(api, 'project', name, data)
        return _output(api, args, dict(data, **_context(api, 'project', name), artifactKind='structure', snapshotPath=str(path)))
    original = _snapshot(api, args, 'project', name)
    payload = dict(projectName=name, dryRun=args.dry_run)
    if args.ad_defaults and args.op != 'modify':
        raise api.PSAPIError('--ad-defaults 仅适用于 project modify。')
    if args.op in ('create', 'modify'):
        payload['operationType'] = 'createProject' if args.op == 'create' else 'modifyProject'
        if args.descr is not None: payload['descr'] = args.descr
        if args.comment is not None: payload['comment'] = api.json_escape(args.comment)
        if args.ad_defaults: payload['adDefaults'] = True
        if args.op == 'modify' and len(payload) == 3:
            raise api.PSAPIError('project modify 需要 --descr、--comment 或 --ad-defaults。')
    else:
        if args.object_type is None or not args.value1:
            raise api.PSAPIError('成员操作需要 --object-type 和 --value1 及所有非空键。')
        values = [(getattr(args, f'value{i}') or '').rstrip(' ') for i in range(1,5)]
        ids = [getattr(args,f'id{i}') for i in range(1,5)]
        if any(i is not None for i in ids) and any(i is None for i in ids):
            raise api.PSAPIError('ObjectID 须全部提供或全部省略。')
        payload.update(objectType=args.object_type, **{f'objectValue{i+1}':v for i,v in enumerate(values)})
        if args.op == 'insert-item':
            if args.copy_done is not None:
                raise api.PSAPIError('insert-item 的 Done 固定为 off；调整时使用 update-item。')
            if args.object_type == 30 and not values[1]:
                payload['objectValue2'] = '0'
            payload.update(operationType='insertItem',upgradeAction=args.upgrade_action if args.upgrade_action is not None else 0,
                           takeAction=args.take_action if args.take_action is not None else 1)
        else:
            rows = [r for r in original.get('items',[]) if r['objectType']==args.object_type and
                    [(r.get(f'objectValue{i}') or '').rstrip(' ') for i in range(1,5)]==values and
                    (ids[0] is None or [r[f'objectId{i}'] for i in range(1,5)]==ids)]
            if len(rows)!=1:
                raise api.PSAPIError(f'原始快照需匹配唯一完整成员，实际 {len(rows)} 项。')
            target = rows[0]
            payload.update({k:v for k,v in target.items() if k.startswith('objectId') or k.startswith('objectValue')})
            payload['operationType'] = 'deleteItem' if args.op=='delete-item' else 'updateItem'
            if args.op=='update-item':
                changes = {k:getattr(args,a) for k,a in (('upgradeAction','upgrade_action'),('takeAction','take_action'),('copyDone','copy_done')) if getattr(args,a) is not None}
                if not changes: raise api.PSAPIError('update-item 需要 --action、--upgrade 或 --done。')
                payload.update(changes)
    result = write(api, 'project', name, payload, original)
    if not args.dry_run:
        actual = _after(api, 'project', name, result)
        expected_header = dict(original.get('header',{}))
        if args.op in ('create','modify'):
            if args.descr is not None: expected_header['PROJECTDESCR']=args.descr
            if args.comment is not None: expected_header['DESCRLONG']=args.comment
            if args.op=='create' or args.ad_defaults:
                expected_header.update(KEEPTGT='31',REPORTFILTER='16232832',COMMITLIMIT='50',COMPARETYPE='1',TGTORIENTATION='0')
        if any(actual.get('header',{}).get(k)!=v for k,v in expected_header.items() if k not in ('VERSION','LASTUPDDTTM','LASTUPDOPRID')):
            raise api.PSAPIError('Project 保存后工程头或未指定选项不符。')
        before = {api._project_item_key(r):r for r in original.get('items',[])}
        after = {api._project_item_key(r):r for r in actual['items']}
        if args.op in ('create','modify'):
            if before != after: raise api.PSAPIError('Project 保存后成员意外变化。')
        else:
            values=[(payload.get(f'objectValue{i}') or '').rstrip(' ') for i in range(1,5)]
            found=[r for r in actual['items'] if r['objectType']==args.object_type and [(r.get(f'objectValue{i}') or '').rstrip(' ') for i in range(1,5)]==values]
            if args.op=='delete-item':
                expected=dict(before);expected.pop(api._project_item_key(target))
                if after!=expected: raise api.PSAPIError('Project 删除回读不符。')
            else:
                flags = dict(upgradeAction=payload['upgradeAction'],takeAction=payload['takeAction'],copyDone=0,sourceStatus=0,targetStatus=0) if args.op=='insert-item' else dict(target,**changes)
                if len(found)!=1 or any(found[0].get(k)!=v for k,v in flags.items()):
                    raise api.PSAPIError('Project 成员标记回读不符。')
                key=api._project_item_key(found[0])
                if {k:v for k,v in before.items() if k!=key}!={k:v for k,v in after.items() if k!=key}:
                    raise api.PSAPIError('Project 未指定成员变化。')
        result['verified']=True
        if args.op in ('create','modify','insert-item'): api._set_active_project(name)
    return _output(api, args, result)
