"""Page 控件属性：写前能力检查、写后独立回读和工程登记。

全部写入携带原始快照版本；冲突保留原稿，独立回读后登记工程。
"""
import json

ATTRS = {
    'rec': 'recName', 'field': 'fieldName', 'label_text': 'labelText',
    'label_id': 'labelId', 'left': 'left', 'top': 'top', 'right': 'right',
    'bottom': 'bottom', 'occurs_level': 'occursLevel', 'required': 'required',
    'invisible': 'invisible', 'display_only': 'displayOnly',
    'edit_size': 'editSize', 'label_type': 'labelType', 'label_loc': 'labelLoc',
    'field_style': 'fieldStyle', 'label_style': 'labelStyle', 'defer_proc': 'deferProc',
    'display_control': 'displayControl', 'multi_currency': 'multiCurrency',
    'set_component_changed': 'setComponentChanged',
    'display_only_appearance': 'displayOnlyAppearance',
    'read_only_screen_reader': 'readOnlyScreenReader',
    'page_field_name': 'pageFieldName', 'enable_as_anchor': 'enableAsAnchor',
    'on_value': 'onValue', 'off_value': 'offValue', 'sub_pnl_name': 'subPnlName',
    'html_text': 'htmlText', 'pb_display_type': 'pbDisplayType',
    'alignment': 'alignment', 'fill_character': 'fillCharacter',
    'password': 'password', 'input_only': 'inputOnly',
    'show_prompt_button': 'showPromptButton', 'auto_fill': 'autoFill',
    'spell_check': 'spellCheck', 'displayed_text': 'displayedText', 'prompt_field': 'promptField',
    'no_colon': 'noColon', 'first_occurs_only': 'firstOccursOnly',
    'label_alignment': 'labelAlignment', 'use_default_label': 'useDefaultLabel',
    'label_position': 'labelPosition', 'label_left': 'labelLeft', 'label_top': 'labelTop',
    'label_right': 'labelRight', 'label_bottom': 'labelBottom', 'move_x': 'moveX', 'move_y': 'moveY',
    'size_type': 'sizeType',
    'show_label': 'showLabel', 'enable_when_page_display_only': 'enableWhenPageDisplayOnly',
    'wrap_long_words': 'wrapLongWords', 'modifiable_by_javascript': 'modifiableByJavaScript',
    'generate_html': 'generateHtml', 'popup_menu': 'popupMenu', 'auto_decimal': 'autoDecimal',
    'currency_symbol': 'currencySymbol', 'thousands_separator': 'thousandsSeparator',
    'display_zero': 'displayZero', 'show_century': 'showCentury', 'show_time_zone': 'showTimeZone',
}
BATCH7 = {'showLabel', 'enableWhenPageDisplayOnly', 'wrapLongWords', 'modifiableByJavaScript',
          'generateHtml', 'popupMenu', 'autoDecimal', 'currencySymbol', 'thousandsSeparator',
          'displayZero', 'showCentury', 'showTimeZone'}
COMMON = {'labelText', 'labelId', 'left', 'top', 'right', 'bottom',
          'occursLevel', 'invisible', 'displayOnly'}
ADD = COMMON | {'recName', 'fieldName'}
EDIT_RECORD = {'alignment', 'fillCharacter', 'password', 'inputOnly',
               'showPromptButton', 'autoFill', 'spellCheck'}
EDIT_LABEL = {'noColon', 'firstOccursOnly', 'labelAlignment', 'useDefaultLabel'}
DROP_DOWN = {'displayedText', 'promptField'}
LABEL_BOUNDS = {'labelLeft', 'labelTop', 'labelRight', 'labelBottom'}
LAYOUT = LABEL_BOUNDS | {'labelPosition', 'moveX', 'moveY', 'sizeType'}
MODIFY = BATCH7 | COMMON | EDIT_RECORD | EDIT_LABEL | DROP_DOWN | LAYOUT | {'labelType', 'labelLoc', 'fieldStyle', 'labelStyle',
                   'deferProc', 'displayControl', 'multiCurrency',
                   'setComponentChanged', 'displayOnlyAppearance',
                   'readOnlyScreenReader', 'pageFieldName', 'enableAsAnchor'}
BINARY = {'invisible', 'displayOnly', 'deferProc', 'displayControl', 'multiCurrency',
          'setComponentChanged', 'readOnlyScreenReader', 'enableAsAnchor',
          'password', 'inputOnly', 'showPromptButton', 'autoFill', 'spellCheck',
          'noColon', 'firstOccursOnly', 'useDefaultLabel'} | (BATCH7 - {'popupMenu'})
COLUMNS = {'labelText': 'LBLTEXT', 'labelId': 'LABEL_ID', 'left': 'FIELDLEFT',
           'top': 'FIELDTOP', 'right': 'FIELDRIGHT', 'bottom': 'FIELDBOTTOM',
           'occursLevel': 'OCCURSLEVEL', 'editSize': 'EDITSIZE',
           'labelType': 'LBLTYPE', 'labelLoc': 'LBLLOC',
           'fieldStyle': 'FIELDSTYLE', 'labelStyle': 'LABELSTYLE', 'deferProc': 'DEFERPROC',
           'pageFieldName': 'PNLFIELDNAME', 'enableAsAnchor': 'ENABLEASANCHOR',
           'popupMenu': 'POPUPMENU', 'fillCharacter': 'DSPLFILL', 'promptField': 'PROMPTFIELD',
           'labelLeft': 'EDITLBLLEFT', 'labelTop': 'EDITLBLTOP',
           'labelRight': 'EDITLBLRIGHT', 'labelBottom': 'EDITLBLBOTTOM'}
NUMERIC = {'left', 'top', 'right', 'bottom', 'occursLevel', 'editSize',
           'labelType', 'labelLoc', 'deferProc', 'enableAsAnchor'} | LABEL_BOUNDS

def build_patch(args, adding=False):
    if getattr(args, 'dry_run', False):
        raise ValueError('控件写入暂不支持 --dry-run；尚未写入。该参数当前仅适用于 delete-code。')
    if not adding and getattr(args, 'control_type', None):
        raise ValueError('controlType 仅适用于 add-control。')
    allowed = ADD if adding else MODIFY
    patch = {}
    for attr, key in ATTRS.items():
        value = getattr(args, attr, None)
        if value is None:
            continue
        if key == 'required':
            raise ValueError('required 不是 Page 控件位属性；旧实现把只读位误作 Required，现拒绝该参数。')
        if key not in allowed:
            raise ValueError(f'{key} 不适用于当前控件操作。')
        if key in BINARY and (type(value) is not int or value not in (0, 1)):
            raise ValueError(f'{key} 必须是数字0或1。')
        if key == 'alignment' and value not in ('auto', 'left', 'right'):
            raise ValueError('alignment 必须是 auto/left/right。')
        if key == 'labelAlignment' and value not in ('left', 'center', 'right'):
            raise ValueError('labelAlignment 必须是 left/center/right。')
        if key == 'displayedText' and value not in ('xlatShort', 'xlatLong', 'prompt'):
            raise ValueError('displayedText 必须是 xlatShort/xlatLong/prompt。')
        if key == 'labelPosition' and value not in ('left', 'custom', 'top'):
            raise ValueError('labelPosition 必须是 left/custom/top。')
        if key == 'sizeType' and value not in ('average', 'maximum', 'custom'):
            raise ValueError('sizeType 必须是 average/maximum/custom。')
        if key in LABEL_BOUNDS | {'moveX', 'moveY'} and type(value) is not int:
            raise ValueError(f'{key} 必须是整数。')
        if key == 'fillCharacter' and (not isinstance(value, str) or len(value) > 1):
            raise ValueError('fillCharacter 必须为空或一个字符。')
        patch[key] = value
    bounds = LABEL_BOUNDS.intersection(patch)
    if bounds and bounds != LABEL_BOUNDS:
        raise ValueError('标签矩形必须同时指定 labelLeft/labelTop/labelRight/labelBottom。')
    if {'moveX', 'moveY'}.intersection(patch) and (LABEL_BOUNDS | {'labelPosition', 'left', 'top', 'right', 'bottom', 'editSize', 'sizeType'}).intersection(patch):
        raise ValueError('moveX/moveY 不能与标签矩形/位置或主控件原始坐标/尺寸组合。')
    if not adding and not patch:
        raise ValueError('mod-control 至少指定一个属性。')
    return patch

def _control(struct, ident):
    matches = [row for row in struct.get('fields', []) if row.get('pnlFldId') == ident]
    if len(matches) != 1:
        raise ValueError(f'控件不存在或不唯一：pnlFldId={ident}')
    return matches[0]

def _verify_patch(before, after, patch):
    """回读防护。预期行为的独立依据在维护项目的原始AD快照中。"""
    raw = after['raw']
    for key, value in patch.items():
        if key in COLUMNS:
            actual = raw[COLUMNS[key]]
            if key in NUMERIC:
                actual = int(actual)
            if actual != value:
                raise ValueError(f'{key} 回读不一致：提交={value!r}，实际={actual!r}')
        elif key in BINARY or key in ('displayOnlyAppearance', 'alignment', 'labelAlignment', 'displayedText', 'labelPosition', 'sizeType'):
            if after.get(key) != value:
                raise ValueError(f'{key} 回读不一致：提交={value!r}，实际={after.get(key)!r}')
    if LAYOUT.intersection(patch):
        expected = {column: int(before['raw'][column]) for column in (
            'FIELDLEFT', 'FIELDTOP', 'FIELDRIGHT', 'FIELDBOTTOM',
            'EDITLBLLEFT', 'EDITLBLTOP', 'EDITLBLRIGHT', 'EDITLBLBOTTOM', 'LABELSIZETYPE', 'FIELDSIZETYPE')}
        for key in {'left', 'top', 'right', 'bottom'} | LABEL_BOUNDS:
            if key in patch:
                expected[COLUMNS[key]] = patch[key]
        if 'labelPosition' in patch:
            expected['LABELSIZETYPE'] = {'left': 0, 'custom': 1, 'top': 2}[patch['labelPosition']]
        if 'sizeType' in patch:
            expected['FIELDSIZETYPE'] = {'average': 0, 'maximum': 1, 'custom': 2}[patch['sizeType']]
        for key, columns in [('moveX', ('FIELDLEFT', 'FIELDRIGHT', 'EDITLBLLEFT', 'EDITLBLRIGHT')),
                             ('moveY', ('FIELDTOP', 'FIELDBOTTOM', 'EDITLBLTOP', 'EDITLBLBOTTOM'))]:
            for column in columns:
                expected[column] += patch.get(key, 0)
        for column, value in expected.items():
            if int(raw[column]) != value:
                raise ValueError(f'{column} 布局回读不一致：预期={value}，实际={raw[column]}')
    # Also catch accidental replacement of unrelated flag bits.
    masks = (('FIELDUSE', {'displayOnly': 1, 'invisible': 2, 'displayControl': 8, 'multiCurrency': 32, 'showLabel': 1024, 'enableWhenPageDisplayOnly': 262144}),
             ('FIELDUSETMP', {'setComponentChanged': 8, 'displayOnlyAppearance': 4, 'spellCheck': 2, 'wrapLongWords': 64}))
    for column, flags in masks:
        allowed = sum(mask for key, mask in flags.items() if key in patch)
        if column == 'FIELDUSETMP' and patch.get('displayOnlyAppearance') == 'disabled' and after.get('fieldType') == 'dropDownList':
            allowed |= 64
            if int(raw[column]) & 64:
                raise ValueError('Disabled 外观必须清除 Wrap。')
        if (int(before['raw'][column]) ^ int(raw[column])) & ~allowed:
            raise ValueError(f'{column} 的未指定标志位发生变化。')
    # Spell Check deliberately changes the Prompt bit as observed in AD 54/55/57.
    display_masks = {'alignment': 13, 'password': 32768, 'autoFill': 512,
                     'showPromptButton': 8388608, 'spellCheck': 8388608,
                     'autoDecimal': 1024, 'currencySymbol': 16, 'thousandsSeparator': 32,
                     'displayZero': 128, 'showCentury': 65536, 'showTimeZone': 536870912,
                     'labelAlignment': 3670016, 'firstOccursOnly': 4194304, 'displayedText': 393216}
    display_allowed = 0
    for key, mask in display_masks.items():
        if key in patch:
            display_allowed |= mask
    if (int(before['raw']['DSPLFORMAT']) ^ int(raw['DSPLFORMAT'])) & ~display_allowed:
        raise ValueError('DSPLFORMAT 的未指定标志位发生变化。')
    if after.get('fieldType') in ('editBox', 'dropDownList'):
        if 'labelId' in patch and int(raw['USEDEFAULTLABEL']) != 0:
            raise ValueError('显式 Label ID 必须清除 Use Default Label。')
        if not {'labelId', 'useDefaultLabel'}.intersection(patch):
            if before['raw']['USEDEFAULTLABEL'] != raw['USEDEFAULTLABEL']:
                raise ValueError('未指定的默认标签选择被改变。')
        allowed_loc = 1 if 'noColon' in patch else 0
        if 'labelLoc' not in patch and (int(before['raw']['LBLLOC']) ^ int(raw['LBLLOC'])) & ~allowed_loc:
            raise ValueError('LBLLOC 的未指定标志位发生变化。')
    if patch.get('displayedText') in ('xlatShort', 'xlatLong') and raw['PROMPTFIELD'] != '':
        raise ValueError('Xlat模式必须清除Prompt Field。')
    if before.get('ext'):
        ext_allowed = (65536 if 'readOnlyScreenReader' in patch else 0) | (512 if 'inputOnly' in patch else 0) | (32 if 'generateHtml' in patch else 0)
        if (int(before['ext']['FIELDUSETEMP2']) ^ int(after['ext']['FIELDUSETEMP2'])) & ~ext_allowed:
            raise ValueError('EXT.FIELDUSETEMP2 的未指定标志位发生变化。')

def write_control(api, args, adding=False):
    try:
        patch = build_patch(args, adding)
        if not adding and args.pnl_fld_id is None:
            raise ValueError('mod-control requires --pnl-fld-id')
        if adding and not args.control_type:
            raise ValueError('add-control requires --control-type')
    except ValueError as exc:
        raise api.PSAPIError(str(exc)) from exc
    project = args.project or api._active_project()
    if not project:
        raise api.PSAPIError('控件写入需要 --project 或已确认的当前工程。')
    api._require_project(project)
    endpoint = 'AI_OPER_PAGE_DEFN.v1/'
    read = dict(pageName=args.pagename, operationType='struct', full=1)
    from page_operations import fresh_baseline, guarded_call
    from definition_operations import _save
    baseline, before = fresh_baseline(api, args)
    if before.get('pageVersionControl') != 1:
        raise api.PSAPIError('服务器缺少 Page 原始快照版本保护；尚未写入。')
    if BATCH7.intersection(patch) and before.get('controlPropertyVersion', 0) < 7:
        raise api.PSAPIError('服务器缺少第7批属性能力；尚未写入。')
    if before.get('controlPropertyVersion', 0) < 1:
        raise api.PSAPIError('服务器缺少 Page 属性纠错能力，请先部署首批 OperPageDefn；尚未写入。')
    if EDIT_RECORD.intersection(patch) and before.get('controlPropertyVersion', 0) < 2:
        raise api.PSAPIError('服务器缺少 Edit Record 属性能力2；尚未写入。')
    if (EDIT_LABEL.intersection(patch) or
            (adding and args.control_type in ('editBox', 'dropDown')) or
            (not adding and {'labelText', 'labelId', 'labelType'}.intersection(patch))) and before.get('controlPropertyVersion', 0) < 3:
        raise api.PSAPIError('服务器缺少标签联动能力3；尚未写入。')
    if DROP_DOWN.intersection(patch) and before.get('controlPropertyVersion', 0) < 5:
        raise api.PSAPIError('服务器缺少 Drop-Down 显示模式/Prompt字段能力5；尚未写入。')
    if LAYOUT.intersection(patch) and before.get('controlPropertyVersion', 0) < 6:
        raise api.PSAPIError('服务器缺少标签矩形/Custom整体平移能力6；尚未写入。')
    payload = dict(pageName=args.pagename, operationType='addControl' if adding else 'modifyControl', **patch)
    if adding:
        if args.control_type not in ('editBox', 'dropDown'):
            raise api.PSAPIError('当前仅支持已有实验覆盖的 Edit Box/Drop-Down 新增。')
        payload['controlType'] = args.control_type
        if 'htmlText' in payload:
            payload['htmlText'] = api.json_escape(payload['htmlText'])
    else:
        payload['pnlFldId'] = args.pnl_fld_id
        try:
            original = _control(before, args.pnl_fld_id)
        except ValueError as exc:
            raise api.PSAPIError(str(exc)) from exc
        if (original.get('fieldType') == 'dropDownList' and
                (EDIT_LABEL | {'labelText', 'labelId', 'labelType'}).intersection(patch) and
                before.get('controlPropertyVersion', 0) < 4):
            raise api.PSAPIError('服务器缺少 Drop-Down 标签联动能力4；尚未写入。')
    result = guarded_call(api, args, payload, baseline['version'])
    ident = result['pnlFldId']
    try:
        after = api._api_call(endpoint, read)
        if result.get('version') != after.get('version'):
            raise ValueError('写后页面版本不同，可能发生后续并发修改。')
        current = _control(after, ident)
        previous_others = [row for row in before['fields'] if adding or row['pnlFldId'] != ident]
        if [row for row in after['fields'] if row['pnlFldId'] != ident] != previous_others:
            raise ValueError('其他控件发生变化，请检查并发修改或服务器实现。')
        if adding:
            if len(after['fields']) != len(before['fields']) + 1:
                raise ValueError('新增控件数量回读不符。')
            if args.control_type in ('editBox', 'dropDown') and not current.get('ext'):
                raise ValueError('新增控件缺少EXT行。')
            if args.control_type == 'dropDown' and int(current['raw']['DSPLFORMAT']) != 2228224:
                raise ValueError('DDL默认显示格式回读不符。')
            if args.control_type in ('editBox', 'dropDown'):
                for key in ('recName', 'fieldName'):
                    if current.get(key) != patch.get(key):
                        raise ValueError(f'{key} 绑定回读不符。')
        else:
            _verify_patch(original, current, patch)
    except Exception as exc:
        raise api.PSAPIError(f'控件写入已提交，独立回读验证未通过：{exc}；先检查实际状态，不要重复写入。') from exc
    try:
        api._insert_project_item(project, 5, [args.pagename], action=0, take_action=1)
    except Exception as exc:
        raise api.PSAPIError(f'控件已写入且回读通过，但工程登记失败：{exc}；仅补登记，不要重发控件写入。') from exc
    _save(api, 'page', args.pagename, after)
    output = dict(version=after['version'], pageName=args.pagename, pnlFldId=ident, project=project,
                  readbackVerified=True, control=current)
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f'OK — control {"added" if adding else "modified"}: pnlFldId={ident} on {args.pagename}; readback verified; Project={project}')
    return output
