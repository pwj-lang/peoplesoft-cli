"""SQL execution CLI and lexical guard, mirrored by Utility:SqlTextGuard."""
import json
import re
from pathlib import Path

DDL = {'CREATE','ALTER','DROP','TRUNCATE','GRANT','REVOKE','COMMENT','RENAME','ANALYZE','AUDIT','NOAUDIT'}
DML = {'INSERT','UPDATE','DELETE','MERGE'}
CONTROL = {'BEGIN','DECLARE','COMMIT','ROLLBACK','SAVEPOINT','CALL','EXEC','EXECUTE','LOCK'}

def scan_sql(sql):
    """Return (word, parenthesis depth) and numeric bind positions.

    Strings, quoted identifiers, comments and Oracle q literals have no keywords.
    Semicolons are forbidden everywhere. Percent signs outside string literals
    (including comments/identifiers) are rejected to prevent meta-SQL expansion.
    """
    if not isinstance(sql,str) or not sql.strip() or len(sql)>20000 or '\0' in sql:
        raise ValueError('sql must be a nonblank string of at most 20000 characters without NUL')
    if ';' in sql:
        raise ValueError('Semicolons are not allowed, including inside strings/comments')
    words, binds = [], set()
    i = depth = 0
    while i < len(sql):
        c=sql[i]
        if sql.startswith('--',i):
            end=re.search(r'[\r\n]',sql[i+2:]); stop=len(sql) if end is None else i+2+end.start()
            if '%' in sql[i:stop]: raise ValueError('PeopleCode meta-SQL is not supported in comments')
            i=len(sql) if end is None else stop+1; continue
        if sql.startswith('/*',i):
            end=sql.find('*/',i+2)
            if end<0: raise ValueError('Unclosed SQL comment')
            if '%' in sql[i:end]: raise ValueError('PeopleCode meta-SQL is not supported in comments')
            i=end+2; continue
        if c in 'qQ' and i+2<len(sql) and sql[i+1]=="'":
            delim=sql[i+2]; closing={'[':']','{':'}','(':')','<':'>'}.get(delim,delim)
            if delim.isspace() or delim=="'": raise ValueError('Invalid q literal delimiter')
            end=sql.find(closing+"'",i+3)
            if end<0: raise ValueError('Unclosed q literal')
            i=end+2; continue
        if c in "'\"":
            quote=c; start=i; i+=1
            while i<len(sql):
                if sql[i]==quote:
                    if i+1<len(sql) and sql[i+1]==quote: i+=2; continue
                    i+=1; break
                i+=1
            else: raise ValueError('Unclosed SQL quote')
            if quote=='"' and '%' in sql[start:i]: raise ValueError('PeopleCode meta-SQL is not supported in identifiers')
            continue
        if c=='%': raise ValueError('PeopleCode meta-SQL is not supported')
        if c=='(': depth+=1; i+=1; continue
        if c==')':
            depth-=1
            if depth<0: raise ValueError('Unbalanced SQL parentheses')
            i+=1; continue
        if c==':':
            match=re.match(r':([1-9][0-9]*)(?![A-Za-z0-9_$#])',sql[i:])
            if not match: raise ValueError('Only numeric binds :1..:64 are supported')
            position=int(match.group(1))
            if position>64: raise ValueError('Bind position exceeds 64')
            binds.add(position); i+=len(match.group(0)); continue
        if c.isascii() and (c.isalpha() or c=='_'):
            end=i+1
            while end<len(sql) and (sql[end].isascii() and (sql[end].isalnum() or sql[end] in '_$#')): end+=1
            words.append((sql[i:end].upper(),depth)); i=end; continue
        i+=1
    if depth: raise ValueError('Unbalanced SQL parentheses')
    return words,binds

def validate_request(payload, write=False, resolved_sql=None):
    if not isinstance(payload,dict): raise ValueError('Request must be an object')
    if len(json.dumps(payload,ensure_ascii=False))>262144: raise ValueError('Request exceeds 262144 characters')
    allowed={'sql','binds','allowAllRows'} if write else {'sql','sqlId','binds','maxRows','columns'}
    if set(payload)-allowed: raise ValueError('Unknown request property')
    source=[key for key in ('sql','sqlId') if key in payload]
    if len(source)!=1 or (write and source!=['sql']): raise ValueError('Provide exactly one sql or sqlId; writes require sql')
    binds=payload.get('binds',[])
    if not isinstance(binds,list) or len(binds)>64 or any(not isinstance(x,str) or len(x)>4000 or '\0' in x for x in binds):
        raise ValueError('binds must be at most 64 strings, each at most 4000 characters without NUL')
    if write:
        if type(payload.get('allowAllRows',False)) is not bool: raise ValueError('allowAllRows must be boolean')
    else:
        rows=payload.get('maxRows',200)
        if type(rows) is not int or not 1<=rows<=1000: raise ValueError('maxRows must be an integer from 1 to 1000')
        if 'columns' in payload:
            columns=payload['columns']
            if not isinstance(columns,list) or not 1<=len(columns)<=128 or any(not isinstance(x,str) or not x.strip() or len(x)>128 or '\0' in x for x in columns):
                raise ValueError('columns must be 1..128 nonblank strings, each at most 128 characters without NUL')
    if source==['sqlId']:
        if not isinstance(payload['sqlId'],str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,29}',payload['sqlId']):
            raise ValueError('sqlId must be an ASCII SQL identifier of 1..30 characters')
        if resolved_sql is None: return
    sql=resolved_sql if resolved_sql is not None else payload['sql']
    words,positions=scan_sql(sql)
    if write and 'C_AI_SQLAUD' in sql.upper(): raise ValueError('Direct audit writes are not supported')
    if not words or words[0][1]!=0: raise ValueError('SQL must begin with a statement keyword')
    first=words[0][0]
    forbidden=DDL|CONTROL|(set() if write else DML)
    if first not in (DML if write else {'SELECT','WITH'}): raise ValueError('Only single DML statements' if write else 'Only SELECT/WITH queries are allowed')
    if any(word in forbidden for word,_ in words): raise ValueError('SQL contains a forbidden keyword')
    if write and any(word in {'PS_C_AI_SQLAUD','C_AI_SQLAUD','RETURNING'} for word,_ in words):
        raise ValueError('Direct audit writes and DML RETURNING are not supported')
    if not write and any(words[i][0]=='FOR' and words[i+1][0]=='UPDATE' for i in range(len(words)-1)):
        raise ValueError('FOR UPDATE is not allowed')
    if write and first in {'UPDATE','DELETE'} and not payload.get('allowAllRows',False) and ('WHERE',0) not in words:
        raise ValueError('UPDATE/DELETE require an outer WHERE or allowAllRows=true')
    if positions!=set(range(1,len(binds)+1)): raise ValueError('binds must match contiguous SQL positions :1..:n exactly')
    if len(json.dumps(payload,ensure_ascii=False))>262144: raise ValueError('Request exceeds 262144 characters')
    return first

def execute(api,args):
    write=args.op=='write'
    try:
        if args.op=='run':
            if not args.sqlid or args.file is not None or args.sql is not None or args.sql_file is not None: raise ValueError('run requires a SQL ID and accepts no SQL text/file')
            payload={'sqlId':args.sqlid}
        else:
            if args.sqlid is not None or args.file is not None or (args.sql is None)==(args.sql_file is None):
                raise ValueError('exec/write require exactly one --sql or --file and no positional SQL ID')
            payload={'sql':Path(args.sql_file).read_text('utf-8-sig') if args.sql_file else args.sql}
        payload['binds']=json.loads(args.bind)
        if write:
            if args.max_rows is not None or args.columns is not None: raise ValueError('write does not accept max-rows/columns')
            payload['allowAllRows']=args.allow_all_rows
        else:
            if args.allow_all_rows: raise ValueError('allow-all-rows applies only to write')
            payload['maxRows']=args.max_rows if args.max_rows is not None else 200
            if args.columns is not None: payload['columns']=json.loads(args.columns)
        validate_request(payload,write)
    except (ValueError,OSError) as e:
        raise api.PSAPIError(str(e)) from e
    # This occurs only after the full local guard. The server resolves and validates
    # registered SQL at execution time; CLI does not cache a definition as authority.
    result=api._api_call('AI_EXEC_SQL_WRITE.v1/' if write else 'AI_EXEC_SQL.v1/',payload)
    if args.output:
        path=Path(args.output).resolve(); path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
        print('Saved:',path)
    if write:
        print(f"{result['statementType']}: affectedRows={result['affectedRows']} auditId={result['auditId']}")
    else:
        columns=[c['name'] for c in result['columns']]
        print(' | '.join(columns))
        for row in result['rows']: print(' | '.join(json.dumps(x,ensure_ascii=False) for x in row['v']))
        print(f"rowCount={result['rowCount']} truncated={str(result['truncated']).lower()}")
    return result
