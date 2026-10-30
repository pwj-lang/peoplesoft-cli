"""Original snapshots for services, operation graphs, catalogs and portal entries."""
import contextlib
import hashlib
import io
import json
import time
from pathlib import Path
from definition_operations import _context
import object_operations as ops

COMMANDS=('service','service-op','message-catalog','portal')
PREFIXES={'service':'svc1:','operation':'ib1:','version':'ib1:','handler':'ib1:','routing':'ib1:','permission':'ib1:','catalog':'cat1:','portal':'por1:'}


def context(api, keys):
    return dict(_context(api,keys['kind'],keys['name']),definitionKeys=keys)


def path(api,keys,workflow=None):
    identity=dict(context(api,keys),workflow=workflow)
    key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:20]
    return api._artifact_dir()/f'managed_{key}.snapshot.json'


def require(api,keys,data):
    if not isinstance(keys,dict) or keys.get('kind') not in PREFIXES or not isinstance(data,dict):
        raise api.PSAPIError('原始版本快照的定义键或数据结构不完整。')
    reported=data.get('versionKeys')
    if keys['kind']=='catalog' and 'language' not in keys and isinstance(reported,dict):
        reported={k:v for k,v in reported.items() if k!='messageNumber'}
    if (data.get('managedVersionControl')!=1 or not isinstance(data.get('version'),str)
            or not data['version'].startswith(PREFIXES[keys['kind']]) or reported!=keys):
        raise api.PSAPIError('服务端缺少匹配完整键的原始版本保护；请部署配套 ManagedVersion 和处理类后重新读取。')


def read(api,endpoint,keys):
    data=api._api_call(endpoint,dict(keys,operationType='struct'))
    require(api,keys,data)
    return data


def save(api,keys,data,workflow=None,destination=None):
    destination=destination or path(api,keys,workflow)
    result=dict(data,**context(api,keys),artifactKind='managed-workflow' if workflow else 'structure')
    if workflow:result['workflowKind']=workflow
    api._write_json_atomic(destination,result)
    result['snapshotPath']=str(destination)
    return result


def snapshot(api,args,keys,workflow=None):
    file=Path(args.snapshot).resolve() if args.snapshot else path(api,keys,workflow)
    try:data=json.loads(file.read_text('utf-8-sig'))
    except (OSError,ValueError) as exc:
        raise api.PSAPIError('缺少可用的原始快照；先 struct/view、plan-configure 或 plan-delete，或使用 --snapshot。') from exc
    if not isinstance(data,dict) or any(data.get(k)!=v for k,v in context(api,keys).items()):
        raise api.PSAPIError('快照的环境、服务器、节点、账号、类型、名称或完整键不符。')
    if workflow:
        if data.get('artifactKind')!='managed-workflow' or data.get('workflowKind')!=workflow or not isinstance(data.get('targets'),list):
            raise api.PSAPIError('需要对应流程的完整原始计划快照。')
        if (not isinstance(data.get('root'),dict) or not 1<=len(data['targets'])<=200
                or any(not isinstance(t,dict) or not isinstance(t.get('keys'),dict) or not isinstance(t.get('before'),dict) for t in data['targets'])):
            raise api.PSAPIError('流程快照缺少原始根定义或完整目标集合（1–200项）。')
        require(api,keys,data['root'])
        for target in data['targets']:require(api,target['keys'],target['before'])
    else:
        require(api,keys,data)
        if data.get('artifactKind')!='structure' or type(data.get('exists')) is not bool:
            raise api.PSAPIError('需要对应定义的原始结构及存在状态快照。')
    return data


def conflict(api,endpoint,keys,error):
    latest_file=None
    try:
        latest=read(api,endpoint,keys)
        latest_file=api._artifact_dir()/f'conflict_{time.time_ns()}_managed.snapshot.json'
        save(api,keys,latest,destination=latest_file)
    except Exception:pass
    raise api.PSAPIError(str(error),code=409,hint='版本冲突；原稿与原始快照保留，未自动换基线或重试。'+('\n最新状态：'+str(latest_file) if latest_file else '')) from error


def write(api,endpoint,keys,payload,original):
    try:return api._api_call(endpoint,dict(keys,**payload,expectedVersion=original['version']))
    except api.PSAPIError as exc:
        if exc.code==409:conflict(api,endpoint,keys,exc)
        raise


def after(api,endpoint,keys,result):
    actual=read(api,endpoint,keys)
    if actual['version']!=result['version']:
        conflict(api,endpoint,keys,api.PSAPIError('保存后定义再次变化，请核对当前状态。',code=409))
    return actual


def definitions(api,args):
    recipe=ops._document(api,args.file)
    if set(recipe)-{'operation','version','handler','routing','permissionList'} or not all(isinstance(recipe.get(k),dict) for k in ('operation','version','handler','routing')):
        raise api.PSAPIError('配置文件需要 operation/version/handler/routing，可选 permissionList。')
    result=[]
    for kind in ('operation','version','handler','routing'):
        entry=dict(recipe[kind]);name=entry.pop('name',args.name if kind=='operation' else None)
        if not name:raise api.PSAPIError('配置缺少完整定义键：'+kind)
        keys=dict(kind=kind,name=name)
        if kind=='operation' and name!=args.name:raise api.PSAPIError('配置操作名称不符。')
        if kind=='version':keys=dict(kind=kind,name=args.name,Versionname=name)
        if kind=='handler':keys=dict(kind=kind,name=args.name,Handlername=name)
        if kind=='routing':keys['Effdt']=entry.pop('effdt','1900-01-01')
        if set(entry)-{'properties','collections'}:raise api.PSAPIError('配置含未知字段。')
        result.append((keys,entry))
    op=result[0][1].get('properties',{})
    protocol=op.get('RestService',2)
    if protocol not in (0,2) or op.get('Rtngtype','S')!='S':raise api.PSAPIError('只支持同步SOAP/REST Provider。')
    if args.op=='configure-rest' and protocol!=2 or args.op=='configure-soap' and protocol!=0:
        raise api.PSAPIError('配置协议与命令不符。')
    if op.get('Defaultversion')!=result[1][0]['Versionname']:raise api.PSAPIError('默认版本与配置版本不符。')
    route=result[3][1].get('properties',{})
    if route.get('Operationname')!=args.name or route.get('Operationversion')!=result[1][0]['Versionname']:
        raise api.PSAPIError('路由须关联相同操作和版本。')
    if protocol==0:
        bindings=result[1][1].get('collections',{}).get('Oprverdfnparm',[])
        if not {'REQUEST','RESPONSE'}<={r.get('Parametername') for r in bindings}:
            raise api.PSAPIError('SOAP需要REQUEST/RESPONSE绑定。')
        if op.get('Restmethod') or result[0][1].get('collections',{}).get('Operationuritemplate'):
            raise api.PSAPIError('SOAP配置不能含REST方法或URI模板。')
    if recipe.get('permissionList'):
        result.append((dict(kind='permission',name=args.name,permissionList=recipe['permissionList']),dict(access=4)))
    return result


def plan_configure(api,args,endpoint,keys):
    items=definitions(api,args)
    root=read(api,endpoint,keys)
    targets=[dict(keys=k,before=read(api,endpoint,k)) for k,entry in items]
    if read(api,endpoint,keys)['version']!=root['version']:
        conflict(api,endpoint,keys,api.PSAPIError('配置计划读取期间操作图已改变。',code=409))
    return save(api,keys,dict(root=root,targets=targets),'configure')


def plan_delete(api,args,endpoint,keys):
    root=read(api,endpoint,keys)
    if not root['exists']:raise api.PSAPIError('操作不存在，不能生成删除计划。')
    from types import SimpleNamespace
    planning=SimpleNamespace(**vars(args));planning.op='plan-delete';planning.snapshot=None;planning.output=None
    with contextlib.redirect_stdout(io.StringIO()):
        result=ops._delete_operation(api,planning,keys,lambda action:api._api_call(endpoint,dict(keys,operationType=action)))
    if read(api,endpoint,keys)['version']!=root['version']:
        conflict(api,endpoint,keys,api.PSAPIError('删除计划读取期间操作图已改变。',code=409))
    for target in result['deletePlan']:require(api,target['keys'],target['before'])
    return save(api,keys,dict(root=root,targets=result['deletePlan']),'delete')


def workflow(api,args,endpoint,keys):
    kind='delete' if args.op=='delete' else 'configure'
    if args.op=='plan-configure':return ops._output(api,args,plan_configure(api,args,endpoint,keys))
    if args.op=='plan-delete':return ops._output(api,args,plan_delete(api,args,endpoint,keys))
    if args.dry_run and not args.snapshot and not path(api,keys,kind).is_file():
        if kind=='configure':plan_configure(api,args,endpoint,keys)
        else:plan_delete(api,args,endpoint,keys)
    original=snapshot(api,args,keys,kind)
    targets=original['targets']
    steps=[]
    if kind=='configure':
        entries=definitions(api,args)
        if [k for k,p in entries]!=[t['keys'] for t in targets]:
            raise api.PSAPIError('配置键或权限列表已改变，必须重新生成原始计划。')
        for (k,entry),target in zip(entries,targets):
            action='modify' if k['kind']=='permission' or target['before']['exists'] else 'create'
            steps.append(dict(k,**entry,operationType=action,expectedVersion=target['before']['version']))
    else:
        steps=[dict(t['keys'],operationType='delete',expectedVersion=t['before']['version']) for t in targets]
    project,_=ops._project(api,args)
    result=write(api,endpoint,keys,dict(operationType='workflow',steps=steps,dryRun=args.dry_run),original['root'])
    if not args.dry_run:
        states=[]
        for index,target in enumerate(targets):
            current=after(api,endpoint,target['keys'],result['states'][index])
            if kind=='delete':
                if current['exists']:raise api.PSAPIError('服务操作删除回读仍存在。')
            elif target['keys']['kind']=='permission':
                if current.get('access')!=4:raise api.PSAPIError('操作授权回读不符。')
            else:ops._verify(api,current,entries[index][1])
            typ,values=ops._project_values(target['keys'],result['results'][index])
            if target['keys']['kind']!='permission':ops._register(api,project,typ,values,kind=='delete')
            states.append(dict(keys=target['keys'],after=current))
        old_service=original['root'].get('Servicename')
        new_service=states[0]['after'].get('Servicename') if kind=='configure' else None
        for service in {old_service,new_service}-{None,''}:
            ops._verify_service_membership(api,args.name,service,kind=='configure' and service==new_service)
            ops._register(api,project,ops.TYPES['service'],[service])
        result.update(verified=True,project=project,definitions=states)
    result['environment']=api.ENVIRONMENT
    return ops._output(api,args,result)


def service_delete(api, args, endpoint, keys):
    """Delete one empty Service using an original read-only deletion plan."""
    if args.file:
        raise api.PSAPIError('Service 删除不接受补丁文件或级联选项。')
    workflow_kind = 'delete-service'
    if args.op == 'plan-delete' or (args.dry_run and not args.snapshot and not path(api, keys, workflow_kind).is_file()):
        original = read(api, endpoint, keys)
        if original.get('serviceDeleteVersion') != 1:
            raise api.PSAPIError('服务端尚未安装空 Service 删除能力；请更新配套编译工程。')
        if not original['exists']:
            raise api.PSAPIError('Service 不存在，不能生成删除计划。')
        linked = [row['Operationname'] for row in original.get('Serviceopr', [])]
        owned = original.get('ownedOperations')
        if not isinstance(owned, list) or any(not isinstance(name, str) for name in owned):
            raise api.PSAPIError('服务端缺少实际所属 Service Operation 清单。')
        blockers = sorted(set(linked + owned))
        planned = save(api, keys, dict(root=original, targets=[dict(keys=keys, before=original)],
                       deletable=not blockers, blockingOperations=blockers,
                       preserved='Service Operations, shared Messages and Application Classes are not deleted.'), workflow_kind)
        if args.op == 'plan-delete':
            return ops._output(api, args, planned)
    original = snapshot(api, args, keys, workflow_kind)
    root = original['root']
    if (root.get('serviceDeleteVersion') != 1 or not root.get('exists')
            or len(original['targets']) != 1 or original['targets'][0]['keys'] != keys
            or original['targets'][0]['before']['version'] != root['version']):
        raise api.PSAPIError('Service 删除需要匹配的原始单定义计划；先运行 service plan-delete。')
    blockers = sorted(set([row['Operationname'] for row in root.get('Serviceopr', [])]
                         + root.get('ownedOperations', [])))
    if blockers:
        raise api.PSAPIError('Service 非空，先删除或迁移所属操作并重新生成计划：' + ', '.join(blockers))
    project, _ = ops._project(api, args)
    result = write(api, endpoint, keys, dict(operationType='delete', dryRun=args.dry_run), root)
    require(api, keys, result)
    if result.get('dryRun') is not args.dry_run or result.get('deleted') is not (not args.dry_run):
        raise api.PSAPIError('Service 删除响应的 deleted/dryRun 与请求不符；先回读确认状态。')
    actual = after(api, endpoint, keys, result)
    if actual['exists'] is not args.dry_run:
        raise api.PSAPIError('Service 删除/预演后的原生存在状态不符。')
    if args.dry_run:
        if actual['version'] != root['version']:
            conflict(api, endpoint, keys, api.PSAPIError('Service dry-run 后版本变化。', code=409))
    else:
        ops._register(api, project, ops.TYPES['service'], [args.name], True)
    result.update(verified=True, project=project, environment=api.ENVIRONMENT)
    return ops._output(api, args, result)


def handle(api,args):
    keys=ops._identity(api,args);endpoint=ops.ENDPOINTS[args.cmd]
    if args.cmd == 'service' and args.op in ('plan-delete', 'delete'):
        return service_delete(api, args, endpoint, keys)
    if args.cmd=='service-op' and (args.op in ('plan-configure','plan-delete','configure-rest','configure-soap') or args.op=='delete' and keys['kind']=='operation'):
        return workflow(api,args,endpoint,keys)
    if args.op=='wsdl':
        if not args.operation:raise api.PSAPIError('wsdl需要 --operation。')
        payload=dict(keys,operationType='wsdl',operationName=args.operation,secure=args.secure)
        if args.version:payload['version']=args.version
        result=api._api_call(endpoint,payload);ops._write_wsdl(api,args,result)
        return ops._output(api,args,result)
    if args.op=='validate':
        if args.cmd=='portal':
            result=api._api_call(endpoint,dict(keys,operationType='validate'))
            if not result.get('valid'):raise api.PSAPIError('Portal运行时校验失败。')
            return ops._output(api,args,result)
        return ops._validate_rest(api,args,keys,lambda action,**extra:api._api_call(endpoint,dict(keys,operationType=action,**extra)))
    if args.op=='tree':
        if args.type!='folder':raise api.PSAPIError('tree 需要 --type folder。')
        visited=set()
        def walk(name):
            if name in visited or len(visited)>=1000:raise api.PSAPIError('门户树出现循环或超过1000个文件夹。')
            visited.add(name);data=read(api,endpoint,dict(keys,name=name))
            return dict(name=name,label=data['LabelName'],sequence=data['SeqNum'],folders=[walk(r['ObjName']) for r in sorted(data['ChildFldr'],key=lambda r:(r['SeqNum'],r['ObjName']))],content=sorted(data['ChildCref'],key=lambda r:(r['SeqNum'],r['ObjName'])))
        return ops._output(api,args,dict(portal=args.portal,tree=walk(args.name)))
    if args.op in ops.READS:
        if args.op=='exists':
            data=api._api_call(endpoint,dict(keys,operationType='exists'))
            require(api,keys,data)
            return ops._output(api,args,data)
        data=read(api,endpoint,keys)
        if args.cmd=='message-catalog' and args.language and data.get('exists'):
            ops._require_translation_snapshot(api,args.language,data)
        result=save(api,keys,data)
        if args.cmd=='message-catalog' and args.number is not None and result.get('exists'):
            result['messages']=[r for r in result['messages'] if r['messageNumber']==args.number]
            if not result['messages']:raise api.PSAPIError('指定的消息号不存在。')
        return ops._output(api,args,result)
    original=snapshot(api,args,keys)
    before=read(api,endpoint,keys)
    if before['version']!=original['version']:
        conflict(api,endpoint,keys,api.PSAPIError('定义在原始快照之后已被修改。',code=409))
    project,_=ops._project(api,args)
    action={'create-set':'createSet','delete-child':'deleteChild','set-attribute':'modify','delete-attribute':'deleteChild','set-permission':'modify','delete-permission':'deleteChild','move':'modify'}.get(args.op,args.op)
    patch=ops._patch(api,args)
    if keys['kind']=='catalog' and args.op=='modify' and args.number is None and set(patch.get('properties',{}))&{'text','explanation','severity'}:
        raise api.PSAPIError('消息正文修改需要 --number。')
    if keys['kind']=='portal' and original['exists'] and args.type!='folder' and original.get('IsLink')!=(args.type=='link'):
        raise api.PSAPIError('--type 与原始CREF/Link类型不符。')
    payload=dict(patch,operationType=action,dryRun=args.dry_run)
    if keys['kind']=='catalog' and args.number is not None:payload['messageNumber']=args.number
    if keys['kind']=='permission':
        if not args.access:raise api.PSAPIError('操作授权需要 --access full|none。')
        payload['access']=4 if args.access=='full' else 0
    elif action in ('modify','deleteChild') and not patch:
        raise api.PSAPIError('未提供修改内容。')
    result=write(api,endpoint,keys,payload,original)
    require(api,keys,result)
    if not args.dry_run:
        actual=after(api,endpoint,keys,result)
        if keys['kind']=='catalog':ops._catalog_verify(api,args,result,patch,actual)
        elif action=='delete':
            if actual['exists']:raise api.PSAPIError('删除后定义仍存在。')
        elif keys['kind']=='permission':
            if actual.get('access')!=payload['access']:raise api.PSAPIError('操作权限回读不符。')
        else:ops._verify(api,actual,patch,action=='deleteChild')
        if keys['kind']=='catalog' and result['messageNumber']==0:
            for row in result['after']['messages']:ops._register(api,project,25,[args.name,str(row['messageNumber'])])
        elif keys['kind']!='permission':
            typ,values=ops._project_values(keys,result)
            ops._register(api,project,typ,values,action=='delete' and not(keys['kind']=='catalog' and args.language))
        if keys['kind']=='operation':
            for service in {original.get('Servicename'),actual.get('Servicename')}-{None,''}:
                ops._verify_service_membership(api,args.name,service,service==actual.get('Servicename'))
                ops._register(api,project,ops.TYPES['service'],[service])
        result.update(verified=True,project=project)
        if keys['kind']=='catalog' and args.language and action=='delete':
            result['translationMigration']=dict(projectAction='Copy',nativeCopyDeletesMissingTranslations=False,replayInTargetEnvironment=True,replayArguments=['message-catalog','delete',args.name,'--number',str(args.number),'--language',args.language,'--project',project])
    result['environment']=api.ENVIRONMENT
    return ops._output(api,args,result)
