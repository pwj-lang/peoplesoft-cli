"""Component operations guarded by the user's original server snapshot."""
import json
import time
from pathlib import Path
from definition_operations import _context, _path, _save, _save_text

ENDPOINT = 'AI_OPER_COMPONENT_DEFN.v1/'
INTERNET_ENUMS = {
    'primary_action': ('primaryAction', {'new': 0, 'search': 1, 'keyword-search': 2}),
    'default_search_action': ('dfltAction', {'update-display': 1, 'update-display-all': 2, 'correction': 3}),
    'default_search_type': ('dfltSrchType', {'basic': 0, 'advanced': 1, 'keyword-only': 2}),
}
INTERNET_FLAGS = {
    'display_folder_tabs': 'displayFolderTabs',
    'display_hyperlinks': 'displayHyperlinks',
    'page_navigation_in_history': 'pageNavigationInHistory',
    'return_to_last_page_in_history': 'returnToLastPageInHistory',
}

TOOLBAR_BITS = {'toolbarSave': 1, 'toolbarCancel': 65536, 'toolbarSpellCheck': 131072, 'toolbarReturnToList': 2, 'toolbarNextInList': 256, 'toolbarPreviousInList': 512, 'toolbarNextPage': 4, 'toolbarPreviousPage': 8, 'toolbarHideBackButton': 268435456, 'toolbarRefresh': 2048, 'toolbarNotify': 32768, 'toolbarViewWorklist': 4096, 'toolbarNextInWorklist': 8192, 'toolbarPreviousInWorklist': 16384, 'toolbarAdd': 16, 'toolbarUpdateDisplay': 32, 'toolbarUpdateDisplayAll': 64, 'toolbarCorrection': 128}
SHOW_BITS = {'disableToolbar': (1, True), 'disablePagebar': (2, False), 'pagebarHelpLink': (4, True), 'pagebarCopyUrlLink': (8, True), 'pagebarNewWindowLink': (16, True), 'pagebarCustomizePageLink': (32, True)}
TOOLBAR_FLAGS = {'toolbar_save': 'toolbarSave', 'toolbar_cancel': 'toolbarCancel', 'toolbar_spell_check': 'toolbarSpellCheck', 'toolbar_return_to_list': 'toolbarReturnToList', 'toolbar_next_in_list': 'toolbarNextInList', 'toolbar_previous_in_list': 'toolbarPreviousInList', 'toolbar_next_page': 'toolbarNextPage', 'toolbar_previous_page': 'toolbarPreviousPage', 'toolbar_hide_back_button': 'toolbarHideBackButton', 'toolbar_refresh': 'toolbarRefresh', 'toolbar_notify': 'toolbarNotify', 'toolbar_view_worklist': 'toolbarViewWorklist', 'toolbar_next_in_worklist': 'toolbarNextInWorklist', 'toolbar_previous_in_worklist': 'toolbarPreviousInWorklist', 'toolbar_add': 'toolbarAdd', 'toolbar_update_display': 'toolbarUpdateDisplay', 'toolbar_update_display_all': 'toolbarUpdateDisplayAll', 'toolbar_correction': 'toolbarCorrection', 'disable_toolbar': 'disableToolbar', 'disable_pagebar': 'disablePagebar', 'pagebar_help_link': 'pagebarHelpLink', 'pagebar_copy_url_link': 'pagebarCopyUrlLink', 'pagebar_new_window_link': 'pagebarNewWindowLink', 'pagebar_customize_page_link': 'pagebarCustomizePageLink'}

ACTION_BITS = [('allowAdd', 1), ('allowUpdateDisplay', 2), ('allowUpdateDisplayAll', 4), ('allowCorrection', 8)]

def expected_properties(before, payload):
    """Predict AD's documented linked values and preserve all unrelated bits."""
    actions, toolbar = int(before['actions']), int(before['tbarBtns'])
    nav = int(before['pnlNavFlags'])
    for name, bit in ACTION_BITS:
        if name in payload and bool(actions & bit) != bool(payload[name]):
            actions = (actions & ~bit) | (bit if payload[name] else 0)
            toolbar = (toolbar & ~(bit * 16)) | (bit * 16 if payload[name] else 0)
    if not actions & 15:
        raise ValueError('至少保留一种 Component 动作。')
    primary, default, search_type = (int(before[k]) for k in ('primaryAction', 'dfltAction', 'dfltSrchType'))
    if actions != int(before['actions']):
        if primary == 0 and not actions & 1:
            primary = 1
        elif primary in (1, 2) and not actions & 14:
            primary = 0
        available = [n for n in (1, 2, 3) if actions & (1 << n)]
        if available and default not in available:
            default = available[0]
        elif not available:
            default = 10  # AD Internet tab: disabled/blank default search action.
    if 'primaryAction' in payload:
        primary = payload['primaryAction']
        if primary == 2:
            search_type = 2
    if primary != 2 and ('primaryAction' in payload or primary != int(before['primaryAction'])) and search_type == 2:
        search_type = 0
    if 'primaryAction' in payload and ((primary == 0 and not actions & 1) or (primary in (1, 2) and not actions & 14)):
        raise ValueError('主操作需要对应的 Add 或至少一种搜索动作。')
    if 'dfltAction' in payload:
        default = payload['dfltAction']
        if not actions & (1 << default):
            raise ValueError('Default Search Action 必须是已启用的搜索动作。')
    if 'dfltSrchType' in payload:
        search_type = payload['dfltSrchType']
    if search_type == 2 and primary != 2 and ('dfltSrchType' in payload or 'primaryAction' in payload):
        raise ValueError('Keyword Only 需要 Keyword Search 主操作。')
    for name, bit in [('displayFolderTabs', 1), ('displayHyperlinks', 2)]:
        if name in payload:
            nav = (nav & ~bit) | (bit if payload[name] else 0)
    for name, bit in [('pageNavigationInHistory', 67108864), ('returnToLastPageInHistory', 536870912)]:
        if name in payload:
            toolbar = (toolbar & ~bit) | (bit if payload[name] else 0)
    if toolbar & 67108864:
        if payload.get('returnToLastPageInHistory') == 0:
            raise ValueError('历史页面导航开启时，不能关闭 Return to Last Page；请同时关闭前者。')
        if 'pageNavigationInHistory' in payload:
            toolbar |= 536870912
    for name, bit in TOOLBAR_BITS.items():
        if name in payload:
            if name in ('toolbarAdd', 'toolbarUpdateDisplay', 'toolbarUpdateDisplayAll', 'toolbarCorrection') and payload[name] and not actions & (bit // 16):
                raise ValueError('Toolbar 动作按钮需要先启用对应的 Component 动作：' + name)
            toolbar = (toolbar & ~bit) | (bit if payload[name] else 0)
    show = int(before['showTbar'])
    for name, (bit, inverted) in SHOW_BITS.items():
        if name in payload:
            value = 1 - payload[name] if inverted else payload[name]
            show = (show & ~bit) | (bit if value else 0)
    return dict(showTbar=show, actions=actions, primaryAction=primary, dfltAction=default,
                dfltSrchType=search_type, pnlNavFlags=nav, tbarBtns=toolbar)

def identity(args):
    return args.pnlgrpname + '.' + (args.market or 'GBL')

def key(args):
    return dict(pnlGrpName=args.pnlgrpname, market=args.market or 'GBL')

def program_key(args):
    result = dict(key(args), event=args.event)
    if args.record: result['recordName'] = args.record
    if args.field: result['fieldName'] = args.field
    return result

def read(api, args):
    return api._api_call(ENDPOINT, dict(key(args), operationType='struct'))

def snapshot(api, args):
    name = identity(args)
    code = args.op in ('modify-code', 'delete-code')
    if args.snapshot: path = Path(args.snapshot).resolve()
    elif code and args.file: path = Path(str(Path(args.file).resolve())+'.snapshot.json')
    else: path = _path(api, 'component', name)
    if not path.is_file(): raise api.PSAPIError('缺少 Component 原始快照：先 struct/view-code，或指定 --snapshot。')
    try: data=json.loads(path.read_text('utf-8-sig'))
    except (OSError, ValueError) as exc: raise api.PSAPIError(f'无法读取快照：{path}') from exc
    if not isinstance(data,dict) or any(data.get(k)!=v for k,v in _context(api,'component',name).items()):
        raise api.PSAPIError('快照的环境、服务器、账号、Component 或 Market 不符。')
    if not str(data.get('version','')).startswith('c1:'):
        raise api.PSAPIError('服务器缺少 Component 版本保护，请部署新版并重新读取。')
    if data.get('artifactKind') != ('code' if code else 'structure'):
        raise api.PSAPIError('需要对应的结构或代码快照。')
    if code and any(data.get(k)!=v for k,v in dict(event=args.event,recordName=args.record or '',fieldName=args.field or '').items()):
        raise api.PSAPIError('代码快照的 Record、Field 或 Event 不符。')
    return data

def conflict(api,args,error):
    try:
        latest=read(api,args)
        path=api._artifact_dir()/f'conflict_{time.time_ns()}_{identity(args)}.structure.json'
        _save(api,'component',identity(args),latest,path)
        hint=f'最新结构已保存：{path}；原稿和原快照保留，未重试。'
    except Exception as exc: hint=f'最新状态读取失败：{exc}；原稿和原快照保留。'
    raise api.PSAPIError(str(error),code=409,hint=hint) from error

def handle(api,args):
    name=identity(args)
    if args.field and not args.record: raise api.PSAPIError('--field 需要 --record。')
    if args.op=='structDeep' or (args.op=='struct' and args.deep):
        data=api._api_call(ENDPOINT,dict(key(args),operationType='structDeep'))
        api._print_component_struct_deep(data)
        return data
    if args.op=='struct':
        data=read(api,args)
        path=_save(api,'component',name,data)
        if args.output: _save(api,'component',name,data,Path(args.output).resolve())
        if args.json: print(json.dumps(dict(data,snapshotPath=str(path)),ensure_ascii=False,indent=2))
        else:
            if data.get('exists'): api._print_component_struct(data)
            else: print(f'Component 不存在：{name}')
            print(f'Snapshot: {path}')
        return data
    if args.op=='view-code':
        if not args.event: raise api.PSAPIError('view-code 需要 --event。')
        data=api._api_call(ENDPOINT,dict(program_key(args),operationType='viewPeopleCode'))
        f,sidecar=_save_text(api,'component',name,data,'code',data.get('peoplecode') or '',event=args.event,recordName=args.record or '',fieldName=args.field or '')
        print(data.get('peoplecode') or '(no peoplecode)')
        print(f'Cached: {f}\nSnapshot: {sidecar}')
        return data
    if args.dry_run and args.op!='delete-code': raise api.PSAPIError('--dry-run 仅用于 delete-code。')
    project=args.project or api._active_project()
    if not project: raise api.PSAPIError('写入需要 --project 或已确认的当前工程。')
    api._require_project(project)
    original=snapshot(api,args)
    before=read(api,args)
    if before.get('componentVersionControl')!=1: raise api.PSAPIError('服务端没有版本保护；未写入。')
    if before.get('version')!=original['version']: conflict(api,args,api.PSAPIError('Component 已在快照后修改。',code=409))
    if args.op == 'create':
        if before.get('exists'): raise api.PSAPIError('Component 已存在；create 不会覆盖它。')
    elif not before.get('exists'): raise api.PSAPIError('Component 不存在。')
    if args.op in ('create','add-page','remove-page'):
        from component_structure import write
        return write(api,args,project,original,before)
    if args.op=='modify-props':
        payload=dict(key(args),operationType='modifyComponentProps')
        for attr,k in [('descr','descr'),('comment','comment'),('search_record','searchRecName'),('add_search_record','addSrchRecName'),('allow_add','allowAdd'),('allow_update','allowUpdateDisplay'),('allow_update_all','allowUpdateDisplayAll'),('allow_correction','allowCorrection'),('page_name','pageName'),('hidden','hidden'),('item_label','itemLabel'),('folder_tab_label','folderTabLabel')]:
            value=getattr(args,attr,None)
            if value is not None: payload[k]=api.json_escape(value) if k=='comment' else value
        internet_requested = False
        for attr, (prop, choices) in INTERNET_ENUMS.items():
            value = getattr(args, attr, None)
            if value is not None:
                payload[prop] = choices[value]
                internet_requested = True
        for attr, prop in INTERNET_FLAGS.items():
            value = getattr(args, attr, None)
            if value is not None:
                payload[prop] = value
                internet_requested = True
        toolbar_requested = False
        for attr, prop in TOOLBAR_FLAGS.items():
            value = getattr(args, attr, None)
            if value is not None:
                payload[prop] = value
                toolbar_requested = True
        if toolbar_requested and before.get('componentInternetPropertyVersion', 0) < 2:
            raise api.PSAPIError('服务端尚未支持 Toolbar/Pagebar；请部署能力版本 2 的核心工程。未写入。')
        if internet_requested and before.get('componentInternetPropertyVersion', 0) < 1:
            raise api.PSAPIError('服务端尚未支持本批 Component Internet 属性；请部署新版工程。未写入。')
        expected = None
        if before.get('componentInternetPropertyVersion', 0) >= 1:
            try:
                expected = expected_properties(before, payload)
            except ValueError as exc:
                raise api.PSAPIError(str(exc)) from exc
        if len(payload)==3: raise api.PSAPIError('至少提供一个属性。')
        if 'pageName' in payload and not {'hidden','itemLabel','folderTabLabel'}.intersection(payload): raise api.PSAPIError('--page-name 需要页面属性。')
    else:
        if not args.event: raise api.PSAPIError('代码操作需要 --event。')
        payload=program_key(args)
        if args.op=='modify-code':
            if not args.file or not Path(args.file).is_file(): raise api.PSAPIError('modify-code 需要本地 --file。')
            code=Path(args.file).read_text('utf-8-sig')
            if not code.strip(): raise api.PSAPIError('空白代码不是删除；使用 delete-code。')
            payload.update(operationType='modifyPeopleCode',peoplecode=api.json_escape(code))
        elif args.op=='delete-code':
            if not original.get('programExists'): raise api.PSAPIError('快照中程序不存在。')
            payload.update(operationType='deletePeopleCode',expectedCode=api.json_escape(original.get('peoplecode') or ''),dryRun=bool(args.dry_run))
        else: raise api.PSAPIError('不支持的 Component 操作。')
    try: result=api._api_call(ENDPOINT,dict(payload,expectedVersion=original['version']))
    except api.PSAPIError as exc:
        if exc.code==409: conflict(api,args,exc)
        raise
    try:
        after=read(api,args)
        if after.get('version')!=result.get('version'): raise ValueError('写后版本不一致，可能发生并发修改。')
        if args.op=='modify-props':
            if expected is not None:
                for prop, value in expected.items():
                    if after.get(prop) != value:
                        raise ValueError(prop+' 回读不符')
            for k in ('descr','searchRecName'):
                if k in payload and after.get(k)!=payload[k]: raise ValueError(k+' 回读不符')
            if 'comment' in payload and after.get('descrLong')!=args.comment: raise ValueError('comment 回读不符')
            if 'addSrchRecName' in payload and after.get('addSrchRecName')!=(args.add_search_record or after.get('searchRecName')): raise ValueError('add search record 回读不符')
            for k,bit in ACTION_BITS:
                if k in payload and int(bool(int(after['actions']) & bit))!=payload[k]: raise ValueError(k+' 回读不符')
            if args.page_name:
                pages=[p for p in after['pages'] if p['pnlName']==args.page_name]
                if len(pages)!=1 or any(pages[0].get(k)!=payload[k] for k in ('hidden','itemLabel','folderTabLabel') if k in payload): raise ValueError('页面属性回读不符')
        else:
            actual=api._api_call(ENDPOINT,dict(program_key(args),operationType='viewPeopleCode'))
            if args.op=='modify-code' and api._peoplecode_signature(actual.get('peoplecode'))!=api._peoplecode_signature(code): raise ValueError('PeopleCode 回读不符')
            if args.op=='delete-code' and actual.get('programExists') is not bool(args.dry_run): raise ValueError('程序存在状态回读不符')
    except Exception as exc:
        raise api.PSAPIError(f'写入已提交，但独立回读未通过：{exc}；检查现状，不重试写入。') from exc
    if not args.dry_run:
        try:
            if args.op=='modify-props': api._insert_project_item(project,7,[args.pnlgrpname,args.market or 'GBL'])
            else:
                item=result['projectItem']
                _,actual=api._insert_project_item(project,item['objectType'],[item[f'objectValue{i}'] for i in range(1,5)],action=1 if args.op=='delete-code' else 0)
                if api._project_item_key(actual)!=api._project_item_key(item): raise ValueError('工程完整键不符')
        except Exception as exc: raise api.PSAPIError(f'写入与回读成功，但工程登记失败：{exc}；仅补登记。') from exc
        _save(api,'component',name,after)
    result.update(project=project,readbackVerified=True)
    if args.output: api._write_json_atomic(Path(args.output).resolve(),result)
    print(json.dumps(result,ensure_ascii=False,indent=2) if args.json else f'OK — Component {name}: readback verified')
    return result
