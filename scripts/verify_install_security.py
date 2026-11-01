#!/usr/bin/env python3
"""Read-only bundle checks for the tool's native permission and role delivery.

This verifies native Project roles and fallback DAT integrity, not user authorization.
"""
import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def verify(root):
    root = Path(root)
    directory = root / 'assets' / 'security'
    manifest = json.loads((directory / 'manifest.json').read_text('utf-8'))
    text = (root / 'C_META_DATA_PKG' / 'C_META_DATA_PKG.XML').read_text('utf-8-sig')
    tree = ET.fromstring('<export>' + re.sub(r'^\s*<\?xml[^?]*\?>', '', text, count=1) + '</export>')
    member_rows = [row for rs in tree.iter('rowset') if rs.get('name') == 'PjmPit' for row in rs.findall('row')]
    members = {row.findtext('szObjectValue_0'): row for row in member_rows if row.findtext('eObjectType') == '53'}
    definitions = {rs.find('row').findtext('szClassId'): rs.find('row')
                   for rs in tree.iter('rowset') if rs.get('name') == 'ClmDefn'}
    role_members = {row.findtext('szObjectValue_0'): row for row in member_rows if row.findtext('eObjectType') == '19'}
    role_definitions = {rs.find('row').findtext('szRolename'): rs.find('row')
                        for rs in tree.iter('rowset') if rs.get('name') == 'Roledefn'}
    expected_names = {'C_PSCLI_READ', 'C_PSCLI_WRITE'}
    if any(set(rows) != expected_names for rows in (members, definitions, role_members, role_definitions)):
        raise ValueError('Native core must contain exactly the two tool Permission Lists and Roles')
    for mode in ('read', 'write'):
        entry = manifest[mode]
        name = entry['permissionList']
        if entry['role'] != name or name != ('C_PSCLI_READ' if mode == 'read' else 'C_PSCLI_WRITE'):
            raise ValueError('Unexpected installation role or Permission List name')
        if members[name].findtext('eUpgradeAction') != '0':
            raise ValueError('Permission List must use the native Copy migration action')
        definition = definitions[name]
        label = '读取' if mode == 'read' else '写入'
        if definition.findtext('szClassDefnDescr') != 'PsCli' + label + '许可权' or entry['permissionDescription'] != definition.findtext('szClassDefnDescr'):
            raise ValueError('Permission List description differs from the installation contract')
        role = role_definitions[name]
        if role_members[name].findtext('eUpgradeAction') != '0' or role.findtext('szDescr') != 'PsCli' + label + '角色' or entry['roleDescription'] != role.findtext('szDescr'):
            raise ValueError('Native Role action or description differs from the installation contract')
        if [r.findtext('szClassid') for rs in role.iter('rowset') if rs.get('name') == 'Roleclass' for r in rs.findall('row')] != [name]:
            raise ValueError('Native Role must contain exactly its matching tool Permission List')
        if any(role.findtext(k) != 'N' for k in ('cRole_pcode_rule_on', 'cRole_query_rule_on', 'cLdap_rule_on')):
            raise ValueError('Tool Roles must not contain dynamic membership rules')
        if any('roleuser' in r.tag.lower() or (r.get('name') or '').lower() == 'roleuser' for r in role.iter()):
            raise ValueError('Native Role must not migrate user assignments')
        operations = {r.findtext('szWSOperationName'): r.findtext('nAuthActions')
                      for r in definition.iter('row') if r.find('szWSOperationName') is not None}
        if operations != {op: '4' for op in entry['operations']}:
            raise ValueError('Native operation grants differ from the installation contract')
        if 'AI_EXEC_SQL_WRITE_POST' in operations or 'PSTOKEN_GET' not in operations:
            raise ValueError('SQL DML must remain excluded and login permission must exist')
        if mode == 'read' and any(op.startswith('AI_OPER_') for op in operations):
            raise ValueError('Read-only list includes a definition-write operation')
        ci = {(r.findtext('szBusCompName'), r.findtext('szBusCompMethod')): r.findtext('nAuthActions')
              for r in definition.iter('row') if r.find('szBusCompName') is not None}
        if ci != {('MESSAGE_CATALOG_CI', method): '4' for method in entry['messageCatalogMethods']}:
            raise ValueError('Native CI method grants differ from the installation contract')
        for field in ('nAuthItemCount', 'nAuthSignonCount', 'nAuthPrcsCount', 'nAuthQueueCount', 'nAuthCubeCount'):
            if definition.findtext(field) != '0':
                raise ValueError('Unrelated permissions in installation Permission List')
        if definition.findtext('bStartAppServer') != '0':
            raise ValueError('Installation list must not grant App Server startup')
    if not set(manifest['read']['operations']) < set(manifest['write']['operations']):
        raise ValueError('Write role must include read permissions')
    roles = manifest['roleDelivery']
    if roles['projectObjectType'] != 19 or roles['nativeXmlRoles'] != 2:
        raise ValueError('Role delivery must include the two native Project Role members')
    if roles['records'] != {'PSROLEDEFN': 2, 'PSROLECLASS': 2}:
        raise ValueError('Role delivery must contain only two definitions and their associations')
    data = (directory / 'pscli-roles.dat').read_bytes()
    if b'REM Database:' not in data or any(name in data for name in (b'PSROLEUSER', b'PSOPRDEFN')):
        raise ValueError('Native Role DAT must exclude users and their role assignments')
    if hashlib.sha256(data).hexdigest() != roles['sha256'] or roles['sourceSha256'] != roles['sha256'] or not roles['nativeBytesPreserved']:
        raise ValueError('Native role DAT hash does not match verified export')
    dms = (directory / 'roles-import.dms').read_text('utf-8')
    imports = re.findall(r'^IMPORT\s+(\w+)\s*;', dms, re.M | re.I)
    if imports != ['PSROLEDEFN', 'PSROLECLASS'] or len(re.findall(r'^SET\s+UPDATE_DUPS\s*;', dms, re.M | re.I)) != 1 or re.search(r'REPLACE_ALL|DELETE|IGNORE_DUPS|PSROLEUSER|PSOPRDEFN', dms, re.I):
        raise ValueError('Fallback import must only upsert the two native record sets after conflict review')
    return {'passed': True, 'permissionLists': 2, 'roles': 2,
            'operationGrants': [len(manifest[k]['operations']) for k in ('read', 'write')],
            'rolesInNativeProject': True, 'roleDatHashVerified': True, 'targetAuthorizationVerified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle-root', type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.bundle_root), ensure_ascii=False))
    except (OSError, ValueError, KeyError, ET.ParseError) as exc:
        print(json.dumps({'passed': False, 'error': str(exc)}, ensure_ascii=False))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
