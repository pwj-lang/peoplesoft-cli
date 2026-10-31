"""Export/apply a page structure with a validated context baseline and id mapping."""
import json
import os
from datetime import datetime
from pathlib import Path

ENDPOINT = 'AI_OPER_PAGE_DEFN.v1/'

PAGE_MANAGED = {'VERSION', 'FIELDCOUNT', 'MAXPNLFLDID', 'LASTUPDDTTM', 'LASTUPDOPRID',
                'LICENSE_CODE', 'PNLNAME'}
FIELD_MANAGED = {'PNLNAME', 'PNLFLDID', 'FIELDNUM'}
EXT_MANAGED = {'PNLNAME', 'PNLFLDID', 'PARENTPNLFLDID', 'PAGEPNLFLDID'}
BTN_MANAGED = {'PNLNAME', 'PNLFLDID'}
DERIVED = {'PARENTPNLFLDID', 'PAGEPNLFLDID'}

# filled in by label resolution when the file left them empty
LABEL_EXCEPTIONS = {'LABEL_ID', 'LBLTEXT'}

CONTEXT_KEYS = ('environment', 'baseUrl', 'node', 'username', 'definitionKind', 'definitionName')


def _strip(row, managed):
    return {k: v for k, v in row.items() if k not in managed}


def _strip_refs(key, value):
    if key == 'ext':
        return _strip(value, DERIVED)
    if key == 'btndata':
        return [_strip(row, DERIVED) for row in value]
    return value


def _read(api, page):
    return api._api_call(ENDPOINT, dict(pageName=page, operationType='struct', full=1))


def _context(api, name):
    return {'environment': api.ENVIRONMENT, 'baseUrl': api.BASE_URL, 'node': api.NODE,
            'username': api.USERNAME, 'definitionKind': 'page', 'definitionName': name}


def _write_json(path, payload):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding='utf-8')
    os.replace(tmp, path)
    return path


def export_structure(api, page, name=None):
    data = _read(api, page)
    if not data.get('exists'):
        raise api.PSAPIError(f'Page 不存在，无法导出结构：{page}')
    target = name or page
    ordered = sorted(data.get('fields', []), key=lambda f: f['raw'].get('FIELDNUM') or 0)
    fields = []
    for f in ordered:
        item = {'id': str(f['pnlFldId']), 'pnlFldId': int(f['pnlFldId']),
                'raw': _strip(f['raw'], FIELD_MANAGED)}
        if f.get('ext'):
            item['ext'] = _strip(f['ext'], EXT_MANAGED)
        if f.get('cntrldata'):
            item['cntrldata'] = _strip(f['cntrldata'], EXT_MANAGED)
        if f.get('btndata'):
            item['btndata'] = [_strip(b, BTN_MANAGED) for b in f['btndata']]
        fields.append(item)
    structure = {
        'pageName': target,
        'sourcePage': page,
        'page': _strip(data['raw'], PAGE_MANAGED),
        'fields': fields,
    }
    # target == page: the token comes from the same read as the data
    target_state = data if target == page else _read(api, target)
    snapshot = dict(_context(api, target), version=target_state['version'],
                    existed=bool(target_state.get('exists')), sourcePage=page,
                    capturedAt=datetime.now().isoformat(timespec='seconds'),
                    fieldCount=len(fields))
    return structure, snapshot


def snapshot_path_for(path):
    return Path(str(path) + '.snapshot.json')


def write_snapshot(path, snapshot):
    _write_json(path, snapshot)


def load_structure(api, path):
    try:
        data = json.loads(Path(path).read_text('utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise api.PSAPIError(f'无法读取结构文件：{path}') from exc
    if not isinstance(data, dict) or not isinstance(data.get('fields'), list):
        raise api.PSAPIError('结构文件缺少 fields 数组。')
    return data


def load_snapshot(api, structure_path, explicit, target):
    path = Path(explicit) if explicit else snapshot_path_for(structure_path)
    if not path.is_file():
        raise api.PSAPIError(
            f'缺少版本基线快照：{path}。请先用 `page structure` 重新导出（不要用手工文件直接写库）。')
    try:
        snap = json.loads(path.read_text('utf-8-sig'))
    except ValueError as exc:
        raise api.PSAPIError(f'快照不可读：{path}') from exc
    if not snap.get('version'):
        raise api.PSAPIError(f'快照缺少 version：{path}')
    context = _context(api, target)
    if snap.get('definitionName') != target:
        raise api.PSAPIError(
            f'快照对应的页面是 {snap.get("definitionName")}，与目标 {target} 不一致；'
            f'请用 `page structure <源页> --name {target}` 重新导出。')
    missing = [k for k in CONTEXT_KEYS if not snap.get(k)]
    if missing:
        raise api.PSAPIError(f'快照缺少上下文 {missing}，请重新导出。')
    wrong = [k for k in CONTEXT_KEYS if str(snap[k]) != str(context[k])]
    if wrong:
        detail = ', '.join(f'{k}: 快照={snap[k]!r} 当前={context[k]!r}' for k in wrong)
        raise api.PSAPIError(f'快照上下文与当前不一致（{detail}），请重新导出。')
    return snap, path


def mapping_path_for(path):
    return Path(str(path) + '.map.json')


def receipt_path_for(path):
    return Path(str(path) + '.receipt.json')


def load_mapping(api, path, target):
    candidate = mapping_path_for(path)
    if not candidate.is_file():
        return {}
    try:
        blob = json.loads(candidate.read_text('utf-8'))
    except ValueError:
        raise api.PSAPIError(f'映射文件不可读：{candidate}')
    if not isinstance(blob, dict) or 'mapping' not in blob:
        raise api.PSAPIError(f'映射文件缺少上下文，请重新导出或删除 {candidate.name}')
    context = _context(api, target)
    missing = [k for k in CONTEXT_KEYS if not blob.get(k)]
    if missing:
        raise api.PSAPIError(f'映射文件缺少上下文 {missing}，请重新导出或删除 {candidate.name}')
    wrong = [k for k in CONTEXT_KEYS if str(blob[k]) != str(context[k])]
    if wrong:
        detail = ', '.join(f'{k}: 映射={blob[k]!r} 当前={context[k]!r}' for k in wrong)
        raise api.PSAPIError(f'映射文件上下文与当前不一致（{detail}），不能套用')
    try:
        return {str(k): int(v) for k, v in blob['mapping'].items()}
    except (ValueError, TypeError, AttributeError) as exc:
        raise api.PSAPIError(f'映射文件内容无效：{candidate}') from exc


def _validate_file(api, data):
    allowed_top = {'pageName', 'sourcePage', 'page', 'fields'}
    unknown = set(data) - allowed_top
    if unknown:
        raise api.PSAPIError(f'结构文件包含未知字段：{sorted(unknown)}')
    ids = set()
    for i, item in enumerate(data['fields'], 1):
        if not isinstance(item, dict) or 'id' not in item or 'raw' not in item:
            raise api.PSAPIError(f'fields[{i}] 缺少 id 或 raw。')
        if item['id'] in ids:
            raise api.PSAPIError(f'控件 id 重复：{item["id"]}')
        ids.add(item['id'])
        extra = set(item) - {'id', 'pnlFldId', 'raw', 'ext', 'cntrldata', 'btndata', 'new'}
        if extra:
            raise api.PSAPIError(f'控件 {item["id"]} 含未知字段：{sorted(extra)}')
        if 'pnlFldId' in item and not isinstance(item['pnlFldId'], int):
            raise api.PSAPIError(f'控件 {item["id"]} 的 pnlFldId 必须是整数')
        if 'new' in item and not isinstance(item['new'], bool):
            raise api.PSAPIError(f'控件 {item["id"]} 的 new 必须是布尔值，收到 {item["new"]!r}')
        if item.get('new') and 'pnlFldId' in item:
            raise api.PSAPIError(
                f'控件 {item["id"]} 同时声明 new=true 和 pnlFldId，意图冲突；新增项不要写 pnlFldId')
    return len(data['fields'])


def _same(a, b):
    if a is None:
        a = ''
    if b is None:
        b = ''
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    return str(a).strip() == str(b).strip()


def _verify_readback(api, data, create, result, out, target):
    raw_ids = result.get('pnlFldIds', '').strip(',')
    ids = [int(x) for x in raw_ids.split(',') if x] if raw_ids else []
    if len(ids) != len(data['fields']):
        raise api.PSAPIError(f'返回的 pnlFldIds 数量不符：{len(ids)} != {len(data["fields"])}')
    if len(set(ids)) != len(ids):
        raise api.PSAPIError('返回的 pnlFldIds 有重复')
    by_id = {int(f['pnlFldId']): f for f in out.get('fields', [])}
    if len(by_id) != len(data['fields']):
        raise api.PSAPIError(f'回读控件数不符：期望 {len(data["fields"])}，实际 {len(by_id)}')
    for pos, (item, fid) in enumerate(zip(data['fields'], ids), 1):
        f = by_id.get(fid)
        if f is None:
            raise api.PSAPIError(f'回读缺少控件 pnlFldId={fid}')
        if f['raw']['FIELDNUM'] != pos:
            raise api.PSAPIError(f'FIELDNUM 不符：pnlFldId={fid} 期望 {pos}，实际 {f["raw"]["FIELDNUM"]}')
        default_label = str(item['raw'].get('USEDEFAULTLABEL') or '') in ('1', 'True', 'true')
        for col, want in item['raw'].items():
            if col in LABEL_EXCEPTIONS and default_label and not str(want).strip():
                continue  # resolved from the data dictionary
            if not _same(want, f['raw'].get(col)):
                raise api.PSAPIError(
                    f'列值不符：pnlFldId={fid} {col} 文件={want!r} 回读={f["raw"].get(col)!r}')
        # every control written by this call must have an EXT row whose derived refs
        # point at the target page, whether or not the file carried an ext block
        got_ext = f.get('ext') or {}
        if not got_ext:
            raise api.PSAPIError(f'回读缺少 EXT 行：pnlFldId={fid}')
        expect_ref = f'{target}$0'
        for ref in ('PARENTPNLFLDID', 'PAGEPNLFLDID'):
            if ref not in got_ext:
                raise api.PSAPIError(f'EXT 缺少派生引用 {ref}：pnlFldId={fid}')
            if not _same(got_ext[ref], expect_ref):
                raise api.PSAPIError(
                    f'EXT 引用未指向目标页：pnlFldId={fid} {ref} 回读={got_ext[ref]!r} 期望={expect_ref!r}')
        if 'ext' in item:
            for col, want in item['ext'].items():
                if col in DERIVED:
                    continue  # normalised away: the server rebuilds them from the target page
                if not _same(want, got_ext.get(col)):
                    raise api.PSAPIError(
                        f'EXT 列值不符：pnlFldId={fid} {col} 文件={want!r} 回读={got_ext.get(col)!r}')
        if 'cntrldata' in item:
            got_ctl = f.get('cntrldata') or {}
            for col, want in item['cntrldata'].items():
                if not _same(want, got_ctl.get(col)):
                    raise api.PSAPIError(
                        f'CNTRLDATA 列值不符：pnlFldId={fid} {col} 文件={want!r} 回读={got_ctl.get(col)!r}')
        if 'btndata' in item:
            got_btn = f.get('btndata') or []
            if len(got_btn) != len(item['btndata']):
                raise api.PSAPIError(
                    f'BTNDATA 行数不符：pnlFldId={fid} 文件={len(item["btndata"])} 回读={len(got_btn)}')
            for want_row, got_row in zip(item['btndata'], got_btn):
                for col, want in want_row.items():
                    if not _same(want, got_row.get(col)):
                        raise api.PSAPIError(
                            f'BTNDATA 列值不符：pnlFldId={fid} {col} 文件={want!r} 回读={got_row.get(col)!r}')
    if result.get('version') != out.get('version'):
        raise api.PSAPIError(
            f'响应版本与回读版本不一致：{result.get("version")} != {out.get("version")}')
    if 'page' in data:
        got_page = out.get('raw', {})
        for col, want in data['page'].items():
            if not _same(want, got_page.get(col)):
                raise api.PSAPIError(f'页面属性不符：{col} 文件={want!r} 回读={got_page.get(col)!r}')
    return ids


def _rewrite_file(path, data, mapping):
    """Absorb the one-shot `new` marks and record the assigned native ids."""
    changed = False
    for item in data['fields']:
        fid = mapping.get(str(item['id']))
        if fid is None:
            continue
        if item.get('pnlFldId') != fid:
            item['pnlFldId'] = fid
            changed = True
        if 'new' in item:
            item.pop('new')
            changed = True
    if changed:
        _write_json(path, data)


def apply_structure(api, args, data, target):
    _validate_file(api, data)
    create = bool(getattr(args, 'create', False))
    dry = bool(getattr(args, 'dry_run', False))
    snap, snap_path = load_snapshot(api, Path(args.file), getattr(args, 'snapshot', None), target)
    before = _read(api, target)
    if create and before.get('exists'):
        raise api.PSAPIError(f'Page 已存在，不能按 create 应用：{target}')
    if not create and not before.get('exists'):
        raise api.PSAPIError(f'Page 不存在，请使用 --create：{target}')

    mapping = load_mapping(api, Path(args.file), target)
    fields = []
    for item in data['fields']:
        entry = {'id': item['id'], 'raw': item['raw']}
        for key in ('ext', 'cntrldata', 'btndata'):
            if key in item:
                entry[key] = _strip_refs(key, item[key])
        if not create:
            fid = mapping.get(str(item['id']))
            if fid is None:
                fid = item.get('pnlFldId')
            if fid is not None:
                entry['pnlFldId'] = int(fid)   # a known id always wins over a stale `new` flag
            elif not item.get('new'):
                raise api.PSAPIError(
                    f'控件 {item["id"]} 缺少 pnlFldId；新增控件请显式写 "new": true，'
                    f'或先执行一次 create 以生成 {mapping_path_for(args.file)}')
        fields.append(entry)

    payload = dict(pageName=target, operationType='applyStructure',
                   mode='create' if create else 'sync',
                   expectedVersion=snap['version'],
                   fields=fields)
    if 'page' in data:
        payload['page'] = data['page']
    if getattr(args, 'delete_unlisted', False):
        payload['deleteUnlisted'] = True
    if dry:
        payload['dryRun'] = True
    try:
        result = api._api_call(ENDPOINT, payload)
    except api.PSAPIError as exc:
        if getattr(exc, 'code', None) in (409, 428):
            raise api.PSAPIError(
                f'版本基线已过期（{exc}）。页面在 {snap.get("capturedAt")} 导出后被修改，请重新导出。') from exc
        raise

    if dry:
        out = _read(api, target)
        if create and out.get('exists'):
            raise api.PSAPIError('dryRun 后页面仍然存在，回滚未生效')
        if not create and out.get('version') != before.get('version'):
            raise api.PSAPIError('dryRun 后页面版本发生变化，回滚未生效')
        result['dryRun'] = True
        result['rolledBack'] = True
        result['readback'] = 'skipped (dry run rolled back)'
        return result

    # the page is committed from here on: keep a server receipt and the id mapping
    # before anything else can fail
    ids = [int(x) for x in result.get('pnlFldIds', '').strip(',').split(',') if x]
    context = _context(api, target)
    receipt = dict(context, pageName=target, fieldCount=result.get('fieldCount'),
                   version=result.get('version'), pnlFldIds=result.get('pnlFldIds'),
                   submittedAt=datetime.now().isoformat(timespec='seconds'))
    receipt_path = _write_json(receipt_path_for(args.file), receipt)
    mapping_now = {item['id']: fid for item, fid in zip(data['fields'], ids)}
    mapping_path = _write_json(mapping_path_for(args.file),
                               dict(context, pageName=target, mapping=mapping_now))
    snap['version'] = result.get('version')
    snap['existed'] = True
    snap['capturedAt'] = datetime.now().isoformat(timespec='seconds')
    write_snapshot(snap_path, snap)

    try:
        out = _read(api, target)
        ids = _verify_readback(api, data, create, result, out, target)
    except api.PSAPIError as exc:
        raise api.PSAPIError(
            f'页面已提交，但回读校验失败：{exc}；回执 {receipt_path}，映射 {mapping_path}') from exc

    _rewrite_file(Path(args.file), data, mapping_now)
    result['pnlFldIds'] = ',' + ','.join(str(i) for i in ids) + ','
    result['readbackFieldCount'] = len(ids)
    result['readbackVersion'] = out.get('version')
    result['mapping'] = mapping_now
    result['receiptPath'] = str(receipt_path)
    result['mappingPath'] = str(mapping_path)
    return result
