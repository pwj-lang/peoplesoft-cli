"""Create Components and edit page associations using original snapshots."""
import json
import re
import time
from pathlib import Path


def definition_name(value, label, length=18):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,'+str(length-1)+'}', value):
        raise ValueError(f'{label} 必须以大写字母开头，最多 {length} 位大写字母、数字或下划线。')
    return value


def page_item(item):
    if not isinstance(item, dict) or set(item) - {'pnlName', 'itemLabel'}:
        raise ValueError('pages 每项只接受 pnlName 和可选 itemLabel；其他页面属性用 modify-props 设置。')
    page = definition_name(item.get('pnlName'), 'Page')
    label = item.get('itemLabel', page)
    if not isinstance(label, str) or len(label) > 18:
        raise ValueError('初始 itemLabel 同时作为 Folder Tab Label，最长 18 字符。')
    return dict(pnlName=page, itemLabel=label)


def build_payload(args, before):
    from component_operations import key, INTERNET_ENUMS, INTERNET_FLAGS, TOOLBAR_FLAGS
    if any(getattr(args, attr, None) is not None for attr in (
            'record', 'field', 'event', 'hidden', 'folder_tab_label',
            'allow_add', 'allow_update', 'allow_update_all', 'allow_correction',
            *INTERNET_ENUMS, *INTERNET_FLAGS, *TOOLBAR_FLAGS)):
        raise ValueError('结构命令只处理创建/页面关联；其他属性请用 modify-props，代码请用代码命令。')
    definition_name(args.pnlgrpname, 'Component')
    if args.op != 'create':
        if any(getattr(args, attr, None) is not None for attr in ('file','descr','comment','search_record','add_search_record','template_component')):
            raise ValueError('add-page/remove-page 只接受 --page-name、可选 --item-label 和通用参数。')
        page = definition_name(args.page_name, 'Page')
        present = any(p['pnlName'] == page for p in before.get('pages', []))
        if args.op == 'remove-page':
            if args.item_label is not None:
                raise ValueError('remove-page 不接受 --item-label。')
            if not present:
                raise ValueError('该 Page 不属于当前 Component。')
            return dict(key(args), operationType='modifyComponent', removePages=[page])
        if present:
            raise ValueError('Page 已在当前 Component 中，不能重复添加。')
        item = dict(pnlName=page)
        if args.item_label is not None:
            item['itemLabel'] = args.item_label
        return dict(key(args), operationType='modifyComponent', addPages=[page_item(item)])
    data = {}
    if args.file:
        try:
            data = json.loads(Path(args.file).read_text('utf-8-sig'))
        except (OSError, ValueError) as exc:
            raise ValueError(f'无法读取 Component 创建文件：{exc}') from exc
        allowed = {'templatePnlGrp','descr','descrLong','searchRecName','addSrchRecName','pages'}
        if not isinstance(data, dict) or set(data) - allowed:
            raise ValueError('创建文件只接受 templatePnlGrp/descr/descrLong/searchRecName/addSrchRecName/pages；不能提供操作、身份或版本字段。')
    data = dict(data)
    for attr, prop in [('template_component','templatePnlGrp'),('descr','descr'),('comment','descrLong'),('search_record','searchRecName'),('add_search_record','addSrchRecName')]:
        value = getattr(args, attr, None)
        if value is not None:
            if prop in data:
                raise ValueError(prop+' 不能同时由文件和命令参数提供。')
            data[prop] = value
    if args.page_name:
        if 'pages' in data:
            raise ValueError('--page-name 和文件中的 pages 不能同时提供。')
        item = dict(pnlName=args.page_name)
        if args.item_label is not None:
            item['itemLabel'] = args.item_label
        data['pages'] = [item]
    elif args.item_label is not None:
        raise ValueError('--item-label 需要 --page-name。')
    if not isinstance(data.get('pages'), list) or not data['pages']:
        raise ValueError('create 需要至少一张已有页面：使用 --page-name 或文件中的 pages。')
    data['pages'] = [page_item(p) for p in data['pages']]
    if len({p['pnlName'] for p in data['pages']}) != len(data['pages']):
        raise ValueError('创建文件中的 Page 不能重复。')
    data.setdefault('templatePnlGrp', 'DFLT_FREQUENCY')
    definition_name(data['templatePnlGrp'], '模板 Component')
    data.setdefault('descr', args.pnlgrpname)
    if not isinstance(data['descr'], str) or len(data['descr']) > 30:
        raise ValueError('descr 必须是最长 30 字符的字符串。')
    if 'descrLong' in data and not isinstance(data['descrLong'], str):
        raise ValueError('descrLong 必须是字符串。')
    for prop in ('searchRecName', 'addSrchRecName'):
        if prop in data and data[prop] != '':
            definition_name(data[prop], prop, 15)
    return dict(data, **key(args), operationType='createComponent')


def write(api, args, project, original, before):
    from component_operations import ENDPOINT, key, identity, read, conflict
    from definition_operations import _save
    try:
        payload = build_payload(args, before)
    except ValueError as exc:
        raise api.PSAPIError(str(exc)) from exc
    if args.op == 'create':
        template = api._api_call(ENDPOINT, dict(pnlGrpName=payload['templatePnlGrp'], market='GBL', operationType='struct'))
        if not template.get('exists'):
            raise api.PSAPIError('GBL 模板组件不存在，尚未写入。')
        for prop in ('searchRecName', 'addSrchRecName'):
            if payload.get(prop):
                rec = api._api_call('AI_OPER_RECORD_DEFN.v1/', dict(recordName=payload[prop], operationType='struct'))
                if not rec.get('exists'):
                    raise api.PSAPIError(prop+' 引用的 Record 不存在，尚未写入。')
    for page in payload.get('pages', payload.get('addPages', [])):
        definition = api._api_call('AI_OPER_PAGE_DEFN.v1/', dict(pageName=page['pnlName'], operationType='struct'))
        if not definition.get('exists'):
            raise api.PSAPIError('Page 不存在：'+page['pnlName']+'；尚未写入。')
    wire = dict(payload, expectedVersion=original['version'])
    if 'descrLong' in wire:
        wire['descrLong'] = api.json_escape(wire['descrLong'])
    try:
        result = api._api_call(ENDPOINT, wire)
    except api.PSAPIError as exc:
        if exc.code == 409:
            conflict(api, args, exc)
        raise
    try:
        after = read(api, args)
        if not after.get('exists') or after.get('version') != result.get('version'):
            raise ValueError('写后存在状态或版本不符。')
        expected_pages = [] if args.op == 'create' else list(before['pages'])
        if 'removePages' in payload:
            expected_pages = [p for p in expected_pages if p['pnlName'] not in payload['removePages']]
        next_item = max((p['subItemNum'] for p in expected_pages), default=0)
        for page in payload.get('pages', payload.get('addPages', [])):
            next_item += 1
            expected_pages.append(dict(pnlName=page['pnlName'], market=key(args)['market'], subItemNum=next_item,
                itemName=page['pnlName'], itemLabel=page['itemLabel'], folderTabLabel=page['itemLabel'], hidden=0))
        if after.get('pages') != expected_pages:
            raise ValueError('页面关联、顺序或未修改页面属性回读不符。')
        if args.op == 'create':
            for prop in ('descr','descrLong','searchRecName','addSrchRecName'):
                if prop in payload and after.get(prop) != payload[prop]:
                    raise ValueError(prop+' 回读不符。')
        else:
            excluded = {'pages','pageCount','version','lastUpdate'}
            if {k:v for k,v in before.items() if k not in excluded} != {k:v for k,v in after.items() if k not in excluded}:
                raise ValueError('页面关联操作改变了其他组件属性。')
    except Exception as exc:
        raise api.PSAPIError(f'写入已提交，但独立回读未通过：{exc}；检查现状，不重试写入。') from exc
    try:
        api._insert_project_item(project, 7, [args.pnlgrpname, key(args)['market']])
    except Exception as exc:
        recovery = api._artifact_dir()/f'registration_pending_{time.time_ns()}.json'
        api._write_json_atomic(recovery, dict(result, project=project, pnlGrpName=args.pnlgrpname, market=key(args)['market']))
        raise api.PSAPIError(f'写入与回读成功，但工程登记失败：{exc}；仅补登记。恢复记录：{recovery}') from exc
    _save(api, 'component', identity(args), after)
    result.update(project=project, readbackVerified=True)
    if args.output:
        api._write_json_atomic(Path(args.output).resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else f'OK — Component {identity(args)}: readback verified')
    return result
