"""Effective-dated Field XLAT maintenance; retain the original Field snapshot."""
import datetime
import json
import time
from pathlib import Path
from definition_operations import _read, _save, _snapshot, _conflict, _register, ENDPOINTS


def _data(api, args):
    data = api._load_json_arg(args.file, 'XLAT JSON') if args.file else {}
    if not isinstance(data, dict) or set(data) - {'fieldValue','effdt','longName','shortName','effStatus'}:
        raise api.PSAPIError('XLAT 文件仅接受 fieldValue/effdt/longName/shortName/effStatus；不能覆盖身份、操作或版本。')
    data = dict(data)
    for attr, prop in [('value','fieldValue'),('effdt','effdt'),('long_name','longName'),('short_name','shortName'),('status','effStatus')]:
        value = getattr(args, attr, None)
        if value is not None:
            if prop in data: raise api.PSAPIError(prop+' 不能同时从文件和命令行提供。')
            data[prop] = value
    value = data.get('fieldValue')
    if not isinstance(value, str) or not value.strip() or value != value.rstrip(' ') or len(value)>4:
        raise api.PSAPIError('需要非空 --value，最多 4 字符且不能以空格结尾。')
    if args.op == 'add-xlat': data.setdefault('effdt', '1900-01-01')
    try:
        date = data['effdt']
        if not isinstance(date, str) or datetime.date.fromisoformat(date).isoformat()!=date: raise ValueError()
    except (KeyError, ValueError):
        raise api.PSAPIError('需要精确 --effdt YYYY-MM-DD；修改/删除不会猜测日期。') from None
    for key, limit in [('longName',30),('shortName',10)]:
        if key in data and (not isinstance(data[key],str) or not data[key].strip() or len(data[key])>limit or data[key]!=data[key].rstrip(' ')):
            raise api.PSAPIError(f'{key} 必须非空且最长 {limit} 字符。')
    if data.get('effStatus', 'A') not in ('A','I'): raise api.PSAPIError('effStatus 必须为 A 或 I。')
    props = set(data)-{'fieldValue','effdt'}
    if args.op == 'add-xlat' and 'longName' not in data: raise api.PSAPIError('add-xlat 需要 --long-name。')
    if args.op == 'modify-xlat' and not props: raise api.PSAPIError('modify-xlat 至少提供 longName/shortName/effStatus 中一项。')
    if args.op == 'delete-xlat' and props: raise api.PSAPIError('delete-xlat 只接受精确值和生效日期。')
    return data


def execute(api, args, name):
    if args.label_id is not None or args.replacement_label_id is not None:
        raise api.PSAPIError('XLAT 命令不接受 Label 参数。')
    if args.op == 'list-xlat':
        if args.file or args.dry_run or any(getattr(args,a,None) is not None for a in ('value','effdt','long_name','short_name','status')):
            raise api.PSAPIError('list-xlat 返回全部历史，不接受写入属性或 dry-run。')
        data = _read(api,'field',name)
        if data.get('xlatMaintenanceVersion',0)<1: raise api.PSAPIError('需先部署 XLAT 能力版本 1 的服务端。')
        snapshot = _save(api,'field',name,data)
        result = dict(fieldName=name,exists=data['exists'],version=data['version'],snapshotPath=str(snapshot),xlatValues=data['fields'][0]['xlatValues'] if data['exists'] else [])
        if args.output: api._write_json_atomic(Path(args.output).resolve(),result)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return result
    patch = _data(api,args)
    before = _snapshot(api,args,'field',name)
    if before.get('xlatMaintenanceVersion',0)<1 or before.get('exists') is not True:
        raise api.PSAPIError('需要已有 Field 的新版 struct/list-xlat 原始快照。')
    field = before['fields'][0]
    if field.get('fieldTypeCode')!=0 or not 1<=field.get('length',0)<=4 or len(patch['fieldValue'])>field['length']:
        raise api.PSAPIError('XLAT 仅用于长度 1–4 的 Character Field，值不能超过字段长度。')
    old = field['xlatValues']
    match = lambda row: all(row[k]==patch[k] for k in ('fieldValue','effdt'))
    target = [x for x in old if match(x)]
    if bool(target) == (args.op=='add-xlat'):
        raise api.PSAPIError('新增的 XLAT 行已存在，或修改/删除的精确行不存在。')
    project = args.project or api._active_project()
    if not project: raise api.PSAPIError('写入需要 --project 或已确认的当前工程。')
    api._require_project(project)
    operation = {'add-xlat':'addXlat','modify-xlat':'modifyXlat','delete-xlat':'deleteXlat'}[args.op]
    payload = dict(patch,fieldName=name,operationType=operation,expectedVersion=before['version'],dryRun=args.dry_run)
    backup = None
    if args.op=='delete-xlat':
        backup=api._artifact_dir()/f'delete_{time.time_ns()}_xlat_{name}.json'
        api._write_json_atomic(backup,dict(before,target=target))
    wrote=False
    try:
        result=api._api_call(ENDPOINTS['field'],payload)
        wrote=not args.dry_run
        fresh=_read(api,'field',name)
        if fresh.get('exists') is not True or fresh.get('version')!=result.get('version'):
            raise api.PSAPIError('XLAT 写后 Field 存在状态或版本不符。')
        if result.get('dryRun') is not bool(args.dry_run) or result.get('deleted') is not (args.op=='delete-xlat' and not args.dry_run):
            raise api.PSAPIError('XLAT 响应没有确认预期状态。')
        current=fresh['fields'][0]
        if args.dry_run:
            if fresh!=before_without_context(before): raise api.PSAPIError('dry-run 改变了 Field 或 XLAT。')
        else:
            expected=[dict(x) for x in old if not match(x)]
            if args.op!='delete-xlat':
                row=dict(target[0]) if target else dict(fieldValue=patch['fieldValue'],effdt=patch['effdt'],effStatus='A',shortName=patch['longName'][:10],translations=[])
                row.update(patch);expected.append(row)
            normalize=lambda rows: sorted([{k:v for k,v in x.items() if k!='lastUpdate'} for x in rows],key=lambda x:(x['fieldValue'],x['effdt']))
            if normalize(current['xlatValues'])!=normalize(expected): raise api.PSAPIError('XLAT 目标、其他生效日期或相关语言回读不符。')
            if {k:v for k,v in field.items() if k not in ('xlatValues','version')}!={k:v for k,v in current.items() if k not in ('xlatValues','version')}:
                raise api.PSAPIError('XLAT 写入改变了其他 Field 属性。')
            items=result.get('projectItems')
            required={'objectType','deleted'}|{f'objectId{i}' for i in range(1,5)}|{f'objectValue{i}' for i in range(1,5)}
            if not isinstance(items,list) or len(items)!=1 or not required<=items[0].keys() or items[0]['objectType']!=4 or [items[0][f'objectValue{i}'] for i in range(1,4)]!=[name,patch['fieldValue'],patch['effdt']] or items[0]['deleted'] is not (args.op=='delete-xlat'):
                raise api.PSAPIError('XLAT 响应缺少正确的完整迁移键。')
            try: _register(api,project,items)
            except Exception as exc:
                recovery=api._artifact_dir()/f'registration_pending_{time.time_ns()}.json'
                api._write_json_atomic(recovery,dict(result,project=project))
                raise api.PSAPIError(f'XLAT 已提交，工程登记失败；仅补登记。恢复记录：{recovery}') from exc
            _save(api,'field',name,fresh)
        result.update(project=project,readbackVerified=True)
        if backup: result['snapshotPath']=str(backup)
        if args.output: api._write_json_atomic(Path(args.output).resolve(),result)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return result
    except api.PSAPIError as exc:
        if exc.code==409 and not wrote: _conflict(api,args,'field',name,exc)
        if wrote: raise api.PSAPIError('XLAT 已提交；后续回读或登记失败，请核对现状，不重复写入。',hint=str(exc)) from exc
        raise


def before_without_context(data):
    metadata={'environment','baseUrl','node','username','definitionKind','definitionName','artifactKind'}
    return {k:v for k,v in data.items() if k not in metadata}
