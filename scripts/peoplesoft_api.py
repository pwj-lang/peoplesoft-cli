#!/usr/bin/env python3
"""
peoplesoft_api.py — PeopleSoft IB REST API CLI 封装

封装 PeopleSoft 元数据相关接口，自动处理认证、token 缓存、JSON 转义/反转义。
输出为已解码的纯文本，减少 AI token 消耗。

用法:
  python peoplesoft_api.py <命令> [参数...]

   Token 缓存: ~/.peoplesoft/cache/.ps_token_cache.<environment>.json（服务端通常 12 小时有效，客户端缓存 11 小时）
"""

import sys, os, json, base64, re, urllib.request, urllib.error, argparse, time, getpass
from pathlib import Path
from urllib.parse import urlparse

# ── 输出编码 ──────────────────────────────────────────
# 管道/重定向时强制 UTF-8：Windows 中文环境默认 cp936，会让已正确解码的中文在
# print() 时被重新编码成 GBK，读取方按 UTF-8 解码即乱码。
# 交互式控制台（isatty）不干预 —— 交给 Python 原生的控制台写入，中文反而正常。
def _force_utf8_when_not_tty(stream):
    try:
        if stream is None or stream.isatty():
            return stream
        if hasattr(stream, "reconfigure"):
            # line_buffering：管道读取时 stdout 默认块缓冲、stderr 无缓冲，
            # 两者交错会让 PASS/FAIL 行跑到汇总行之后。与下面回退分支的
            # buffering=1 保持一致的语义。
            stream.reconfigure(encoding="utf-8", line_buffering=True)
            return stream
        # 回退方案：用 UTF-8 wrapper 替换（Python 3.6 及更早）
        return open(stream.fileno(), mode="w", encoding="utf-8", buffering=1, closefd=False)
    except Exception:
        return stream


sys.stdout = _force_utf8_when_not_tty(sys.stdout)
sys.stderr = _force_utf8_when_not_tty(sys.stderr)

# ── 路径 ──────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ASSETS_DIR = SKILL_DIR / "assets"
DEFAULT_DATA_DIR = Path.home() / ".peoplesoft"
DATA_DIR = Path(os.environ.get("PEOPLESOFT_DATA_DIR", str(DEFAULT_DATA_DIR)))
CONFIG_PATH = Path(os.environ.get("PEOPLESOFT_CONFIG", str(DATA_DIR / "config.json")))
TOKEN_CACHE_DIR = Path(os.environ.get("PEOPLESOFT_CACHE_DIR", str(DATA_DIR / "cache")))
LEGACY_TOKEN_CACHE = TOKEN_CACHE_DIR / ".ps_token_cache.json"
PROJECT_STATE_PATH = Path(os.environ.get("PEOPLESOFT_PROJECTS", str(DATA_DIR / "projects.json")))
TOKEN_CACHE_TTL = 11 * 60 * 60  # PeopleSoft token 通常有效 12 小时，提前 1 小时刷新

# IB REST 网关 URL 里的「本地节点名」段。PSFT_HR 是 PeopleSoft HCM 出厂默认，
# 但客户在实施时几乎都会改名（HCM_DEV / XX_HRMS 之类），所以必须可配置。
DEFAULT_NODE = "PSFT_HR"
NODE_ENV_VAR = "PEOPLESOFT_NODE"


# ── 配置 ──────────────────────────────────────────────
def _read_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"PeopleSoft 配置不存在: {CONFIG_PATH}。请创建该文件，或设置 PEOPLESOFT_CONFIG。"
        ) from exc


def _select_runtime(doc):
    """Return (config document, environment name, selected config, multi-env flag)."""
    environments = doc.get("environments")
    if environments is not None:
        if not isinstance(environments, dict) or not environments:
            raise ValueError("config.json 'environments' must be a non-empty object")
        active = doc.get("active_environment") or next(iter(environments))
        if active not in environments:
            raise ValueError(
                f"active environment '{active}' not found in config.json 'environments'"
            )
        selected = environments[active]
        if not isinstance(selected, dict):
            raise ValueError(f"environment '{active}' must be an object")
        return doc, active, selected, True

    # Backward compatibility with the original single-environment schema.
    selected = doc.get("peoplesoft")
    if not isinstance(selected, dict):
        raise ValueError("config.json must contain 'environments' or 'peoplesoft'")
    return doc, "default", selected, False


def _cache_path(environment, multi_env):
    if not multi_env:
        return LEGACY_TOKEN_CACHE
    safe = "".join(
        ch if ("a" <= ch <= "z" or "A" <= ch <= "Z" or "0" <= ch <= "9" or ch in "._-") else "_"
        for ch in str(environment)
    ) or "default"
    return TOKEN_CACHE_DIR / f".ps_token_cache.{safe}.json"


def _load_runtime():
    doc = _read_config()
    doc, environment, selected, multi_env = _select_runtime(doc)
    return doc, environment, selected, multi_env, _cache_path(environment, multi_env)


def _resolve_node(cfg):
    """目标库的本地节点名（IB REST 网关 URL 里那一段）。

    优先级：环境变量 > config.json 的 node 字段 > 出厂默认 PSFT_HR。
    写死会让改了节点名的环境完全无法使用，且报错与「接口未部署」不同、容易误判。
    """
    return (
        os.environ.get(NODE_ENV_VAR)
        or str(cfg.get("node") or "").strip()
        or DEFAULT_NODE
    )


def _ib_url(endpoint):
    """拼接 IB REST 网关地址：{PIA}/PSIGW/RESTListeningConnector/{本地节点}/{Service Operation}/"""
    return f"{BASE_URL}/PSIGW/RESTListeningConnector/{NODE}/{endpoint}"


_RUNTIME_ERROR = None
try:
    _CONFIG_DOC, ENVIRONMENT, _cfg, MULTI_ENV, TOKEN_CACHE = _load_runtime()
    BASE_URL = str(_cfg["pia_base_url"]).rstrip("/")
    USERNAME = _cfg["username"]
    PASSWORD = _cfg.get("password", "")
    NODE = _resolve_node(_cfg)
except (OSError, json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
    # Allow `env init` to bootstrap a machine with no config.json yet.
    _RUNTIME_ERROR = exc
    _CONFIG_DOC, ENVIRONMENT, _cfg, MULTI_ENV = {}, "", {}, True
    TOKEN_CACHE = LEGACY_TOKEN_CACHE
    BASE_URL = USERNAME = PASSWORD = ""
    NODE = DEFAULT_NODE


def _reload_runtime():
    """Reload the active environment after env use changes config.json."""
    global _CONFIG_DOC, ENVIRONMENT, _cfg, MULTI_ENV, TOKEN_CACHE, _RUNTIME_ERROR
    global BASE_URL, USERNAME, PASSWORD, NODE
    _CONFIG_DOC, ENVIRONMENT, _cfg, MULTI_ENV, TOKEN_CACHE = _load_runtime()
    BASE_URL = str(_cfg["pia_base_url"]).rstrip("/")
    USERNAME = _cfg["username"]
    PASSWORD = _cfg.get("password", "")
    NODE = _resolve_node(_cfg)
    _RUNTIME_ERROR = None


def _require_runtime():
    """Stop commands that need a valid environment configuration."""
    if _RUNTIME_ERROR is not None:
        print(f"ERROR: {_RUNTIME_ERROR}", file=sys.stderr)
        sys.exit(1)


def _write_json_atomic(path, doc):
    """Write JSON atomically so a crash cannot leave a truncated file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def _write_config(doc):
    """Write config atomically so a switch cannot leave a truncated JSON file."""
    _write_json_atomic(CONFIG_PATH, doc)


# ── Project 状态 ──────────────────────────────────────
# 「上次使用的 Project」，按环境分节存在同一个文件里，所以 env use 切换后自动跟随，
# 不需要在 _reload_runtime() 里重绑路径。
def _load_project_state():
    """读取 Project 状态。任何读取异常都退化为空状态 —— 该函数在 env init 的
    启动路径上被间接触发，抛异常会连带打断无 config 机器的初始化。"""
    try:
        state = json.loads(PROJECT_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return {}
    return state if isinstance(state, dict) else {}


def _active_project():
    """当前环境记录的活动 Project；没有记录时返回 None。"""
    entry = _load_project_state().get(ENVIRONMENT)
    if isinstance(entry, dict):
        name = entry.get("active_project")
        return str(name) if name else None
    return None


def _set_active_project(project_name):
    """把 project_name 记为当前环境的活动 Project。"""
    state = _load_project_state()
    state[ENVIRONMENT] = {"active_project": project_name}
    _write_json_atomic(PROJECT_STATE_PATH, state)


class PSAuthError(RuntimeError):
    """认证无法完成。

    detail 原样保留服务端响应体文本 —— SKILL.md 第2步要求 Agent 按响应内容
    （Routing 缺失 / 未经授权）分流到第3步，所以这里不能吞掉内容，也不能只抛状态码。
    """

    def __init__(self, detail, hint=""):
        super().__init__(detail)
        self.detail = detail
        self.hint = hint


def _ib_failure_reason(text):
    """把 IB 网关的失败响应归类成 (类别, 一行可操作的原因)。无法归类返回 (None, "")。

    「环境没准备好」阶段有两种响应，含义完全不同、修法也完全不同，不能混为一谈：

    - `Unable to find a Routing corresponding...`：节点名对，但该 Service Operation
      没部署 —— 要导入 AD 工程。
    - HTTP 500 + `找不到与入站请求消息对应的发送处理。 (158,505)`：节点名不对 ——
      改配置即可。若误判成上一种，用户会白跑一轮 AD 导入（含 DDL Build）。
    """
    flat = " ".join(str(text).split())
    if "158,505" in flat or "找不到与入站请求消息对应的发送处理" in flat:
        return "node", (
            f"节点名可能不正确（当前 node={NODE}）—— 请在目标 PeopleSoft 的 "
            "PeopleTools > 集成代理 > 集成设置 > 节点 里取标记为 Local Node 的那条名称，"
            f"再用 env init --node 或环境变量 {NODE_ENV_VAR} 修正。"
            "这是配置问题，不要重新导入 AD 工程"
        )
    if "routing corresponding" in flat.lower():
        return "routing", "接口未部署 —— 参考 references/ad-cli-project-import.md 导入 AD 工程"
    lowered = flat.lower()
    if "未经授权" in flat or any(t in lowered for t in (
        "not authorized", "not authorised", "access denied", "permission denied",
    )):
        return "authz", (
            "授权不足 —— 参考 references/rest-authorization.md，"
            "为该账号所用许可权列表授予对应 Service Operation 的完全访问"
        )
    return None, ""


# ── Token 缓存 ────────────────────────────────────────
def _load_cached_token():
    if TOKEN_CACHE.exists():
        try:
            cache = json.loads(TOKEN_CACHE.read_text(encoding="utf-8"))
            if time.time() - cache.get("ts", 0) < TOKEN_CACHE_TTL:
                return cache.get("token")
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    return None

def _save_token(token):
    TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_CACHE.write_text(
        json.dumps({"token": token, "ts": time.time()}, ensure_ascii=False),
        encoding="utf-8",
    )

def get_token(force_refresh=False):
    """获取 PS_TOKEN（优先使用 11 小时缓存，过期自动刷新）。

    失败时抛 PSAuthError，不直接 sys.exit —— _api_call() 依赖 get_token() 抛异常
    来实现「token 过期则强制刷新一次」的重试，在这里退出会架空那段逻辑。
    由 main() 统一收口打印。
    """
    cached = _load_cached_token()
    if cached and not force_refresh:
        return cached
    if not PASSWORD:
        print(
            "ERROR: 当前环境在 config.json 中没有保存密码，无法换取 PS_TOKEN。\n"
            "       请重新配置该环境的密码：\n"
            "       python scripts/peoplesoft_api.py env init <name> --url <url> "
            "--username <user> --force",
            file=sys.stderr,
        )
        sys.exit(1)
    credentials = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
    req = urllib.request.Request(
        _ib_url("PSTOKEN.v1/"),
        headers={"Authorization": f"Basic {credentials}"}
    )
    try:
        raw = urllib.request.urlopen(req).read()
    except urllib.error.HTTPError as exc:
        # 4xx/5xx：网关级失败，响应体里就是「Routing 缺失」或「未经授权」原文。
        # 必须走 _safe_decode —— PIA 默认 GBK，按 UTF-8 解会让中文提示变乱码。
        try:
            body = _safe_decode(exc.read())
        except Exception:
            body = ""
        detail = body.strip() or f"HTTP {exc.code} {exc.reason}"
        _, hint = _ib_failure_reason(detail)
        raise PSAuthError(detail, hint=hint) from exc
    except urllib.error.URLError as exc:
        raise PSAuthError(
            f"无法连接 {BASE_URL}：{exc.reason}",
            hint="请检查 PIA 地址、网络连通性和代理设置是否正确。",
        ) from exc

    text = _safe_decode(raw)
    try:
        resp = json.loads(_clean_json_text(text))
    except json.JSONDecodeError as exc:
        # HTTP 200 但返回 HTML（PIA 网关错误页），原文透出供 Agent 匹配
        detail = text.strip() or "认证接口返回了非 JSON 响应。"
        _, hint = _ib_failure_reason(detail)
        raise PSAuthError(detail, hint=hint) from exc

    token = (resp.get("data") or {}).get("psToken")
    if not token:
        # 业务级失败，例如 {"code":-1,"message":"Invalid username or password"}
        raise PSAuthError(
            str(resp.get("message") or "").strip() or text.strip(),
            hint="请检查当前环境的用户名和密码是否正确。",
        )
    _save_token(token)
    return token

def _safe_decode(raw_bytes):
    """安全解码 API 响应字节。

    PeopleSoft PIA 返回的数据可能混用 UTF-8 和 GBK：
    - JSON 结构本身应是 UTF-8（RFC 7159 强制要求）
    - 但 PeopleCode 内容可能包含 GBK 字节（PIA 页面的默认编码）

    策略：优先 UTF-8（JSON 标准），失败时回退 GBK，避免静默损坏数据。
    """
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        pass
    # UTF-8 失败 → 尝试 GBK（PeopleSoft PIA 默认编码）
    try:
        decoded = raw_bytes.decode("gbk")
        print("Warning: API response decoded as GBK (not UTF-8). Check server encoding config.", file=sys.stderr)
        return decoded
    except UnicodeDecodeError:
        pass
    # 最后兜底：逐字节替换（会损坏数据，但至少能继续）
    print("ERROR: API response is neither UTF-8 nor GBK. Data will be corrupted!", file=sys.stderr)
    return raw_bytes.decode("utf-8", errors="replace")

def _clean_json_text(raw):
    """把 JSON 字符串内部的裸控制字符转义，让 json.loads 能解析。"""
    cr, lf, tab = chr(13), chr(10), chr(9)
    return re.sub(
        r'"[^"]*"',
        lambda m: m.group(0).replace(cr + lf, '\\n').replace(lf, '\\n').replace(cr, '\\r').replace(tab, '\\t'),
        raw,
    )

def _shorten(text, limit=200):
    """压平空白并截断，用于单行错误摘要。"""
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[:limit] + "…"

def _api_call(endpoint, data=None):
    """通用 API 调用，自动带 PS_TOKEN，返回解析后的 data 字段。token 过期自动刷新一次。"""
    def do_call(tok):
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(
            _ib_url(endpoint),
            headers={"PS_TOKEN": tok, "Content-Type": "application/json"},
            data=body
        )
        try:
            raw = _safe_decode(urllib.request.urlopen(req).read())
        except urllib.error.HTTPError as e:
            raw = _safe_decode(e.read())
        return json.loads(_clean_json_text(raw))

    try:
        resp = do_call(get_token())
    except (json.JSONDecodeError, urllib.error.HTTPError):
        # Likely token expired (non-JSON response). Force refresh once.
        try:
            body = json.dumps(data).encode() if data else None
            req = urllib.request.Request(
                _ib_url(endpoint),
                headers={"PS_TOKEN": get_token(), "Content-Type": "application/json"},
                data=body
            )
            raw = _safe_decode(urllib.request.urlopen(req).read())
        except urllib.error.HTTPError as e:
            raw = _safe_decode(e.read())
        if "PSFT Authentication token failed" in raw:
            # get_token(force_refresh=True) 走的就是 Basic 认证换新 token 的流程
            resp = do_call(get_token(force_refresh=True))
        else:
            # Re-raise the original JSON decode / HTTP error
            raise

    if resp.get("code") != 0:
        print(f"API Error [{resp.get('code')}]: {resp.get('message')}", file=sys.stderr)
        sys.exit(1)
    return resp.get("data", {})

def json_escape(text):
    """JSON 转义（等同于 Commons StringEscapeUtils.escapeJson）"""
    return json.dumps(text)[1:-1]

# ═══════════════════════════════════════════════════════
#  子命令
# ═══════════════════════════════════════════════════════

# ── auth ──────────────────────────────────────────────
def cmd_auth(args):
    get_token(force_refresh=args.refresh)
    action = "refreshed" if args.refresh else "ready"
    print(f"PS_TOKEN {action} for environment: {ENVIRONMENT}")
    print("Token cached. Reused for up to 11 hours; server token is usually valid for 12 hours.")


# ── bundle-check ──────────────────────────────────────
def cmd_bundle_check(args):
    """Fail fast when the AD file project omits required local dependencies."""
    bundle_root = Path(args.bundle_root).resolve()
    project_dir = bundle_root / args.project
    xml_path = project_dir / f"{args.project}.XML"
    ini_path = project_dir / f"{args.project}.ini"
    failures = []
    if not xml_path.exists():
        failures.append(f"missing file project XML: {xml_path}")
    if not ini_path.exists():
        failures.append(f"missing file project INI: {ini_path}")
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        sys.exit(1)

    xml_text = xml_path.read_text(encoding="utf-8", errors="replace")
    ini_text = ini_path.read_text(encoding="utf-8", errors="replace")
    tools_release = re.search(r"(?m)^TOOLSREL=(.+)$", ini_text)
    print(f"Bundle: {project_dir}")
    print(f"TOOLSREL: {tools_release.group(1).strip() if tools_release else 'unknown'}")

    manifest_match = re.search(
        r'<rowset name="PjmPit"[^>]*>(.*?)</rowset>',
        xml_text,
        flags=re.DOTALL,
    )
    if not manifest_match:
        print("FAIL Project manifest PjmPit not found")
        sys.exit(1)
    manifest = manifest_match.group(1)
    rows = re.findall(r"<row>(.*?)</row>", manifest, flags=re.DOTALL)
    items = set()
    for row in rows:
        def value(index):
            match = re.search(
                rf"<szObjectValue_{index}>(.*?)</szObjectValue_{index}>",
                row,
                flags=re.DOTALL,
            )
            return match.group(1).strip() if match else ""

        type_match = re.search(r"<eObjectType>(\d+)</eObjectType>", row)
        if type_match:
            items.add((int(type_match.group(1)), value(0), value(1), value(2)))

    required_classes = {
        (58, "C_META_DATA_PKG", "MetaData", "OperFieldDefn"),
        (58, "C_META_DATA_PKG", "RecordQuery", "OperQueryRecord"),
        (58, "C_PORTAL_PKG", "Util", "JSONObject"),
    }
    for item in sorted(required_classes):
        if item not in items:
            failures.append(
                "Project manifest missing Application Package class: "
                + ":".join(item[1:])
            )

    sql_in_code = set(re.findall(r"SQL\.((?:C_AI|C_META)_[A-Z0-9_]+)", xml_text))
    project_sql = {value1 for typ, value1, _, _ in items if typ == 30}
    for sql_id in sorted(sql_in_code - project_sql):
        failures.append(f"Project manifest missing SQL Definition: {sql_id}")

    required_operations = {
        "AI_OPER_APP_ENGINE_POST", "AI_OPER_APP_PKG_POST",
        "AI_OPER_COMPONENT_DEFN_POST", "AI_OPER_FIELD_DEFN_POST",
        "AI_OPER_PAGE_DEFN_POST", "AI_OPER_PROJECT_DEFN_POST",
        "AI_OPER_RECORD_DEFN_POST", "AI_OPER_SQL_DEFN_POST",
        "AI_QUERY_RECORD_POST", "AI_SEARCH_DEFN_POST", "PSTOKEN_GET",
    }
    project_operations = {value1 for typ, value1, _, _ in items if typ == 80}
    for operation in sorted(required_operations - project_operations):
        failures.append(f"Project manifest missing Service Operation: {operation}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        sys.exit(1)
    print("PASS bundle manifest contains required local classes, SQL Definitions, and Service Operations.")


# ── healthcheck ───────────────────────────────────────
def _probe_api(endpoint, payload):
    """Call a read-only endpoint and classify access without printing response data."""
    try:
        token = get_token()
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            _ib_url(endpoint),
            headers={"PS_TOKEN": token, "Content-Type": "application/json"},
            data=body,
        )
        try:
            raw = _safe_decode(urllib.request.urlopen(req).read())
        except urllib.error.HTTPError as exc:
            raw = _safe_decode(exc.read())
    except PSAuthError as exc:
        # 认证层失败：透出服务端原文，让 Agent 能按 SKILL.md 第3步分流
        return False, _shorten(exc.detail)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError) as exc:
        return False, f"network or authentication error: {exc}"

    try:
        response = json.loads(_clean_json_text(raw))
    except json.JSONDecodeError:
        _, reason = _ib_failure_reason(raw)
        if reason:
            return False, reason
        return False, f"non-JSON response: {_shorten(raw, 160)}"

    code = response.get("code")
    message = str(response.get("message", "")).strip()
    detail = f"code={code}" + (f", {message}" if message else "")
    lowered = detail.lower()
    if code == 0:
        return True, "reachable"
    if any(term in lowered for term in (
        "not authorized", "not authorised", "access denied", "permission",
        "forbidden", "authentication", "psft authentication token failed",
    )):
        return False, detail
    # The SQL and AE probes intentionally use impossible names. A definition-not-found
    # reply proves the operation was reached and authorized without changing metadata.
    if any(term in lowered for term in (
        "not exist", "does not exist", "not found", "cannot find", "no rows",
    )):
        return True, f"reachable ({detail})"
    return False, f"application error ({detail})"


def _build_probes(package_root="C_META_DATA_PKG", record="JOB", component="JOB_DATA",
                  page="JOB_DATA1", field="EMPLID", query_record="JOB",
                  query_field="EMPLID", ae_id="__PS_METADATA_PROBE__",
                  sql_id="__PS_METADATA_PROBE__", project="C_META_DATA_PKG"):
    """10 个 Service Operation 的只读探测清单。healthcheck 与 preflight 共用。

    ae_id / sql_id 故意用不存在的名字：服务端回「找不到定义」恰好证明请求被到达
    且已放行，同时不会改动任何元数据。
    """
    return (
        ("AI_SEARCH_DEFN_POST", "AI_SEARCH_DEFN.v1/", {
            "definitionType": 104, "definitionName": package_root,
        }),
        ("AI_OPER_APP_PKG_POST", "AI_OPER_APP_PKG_POST.v1/", {
            "packageRoot": package_root, "operationType": "default",
        }),
        ("AI_OPER_APP_ENGINE_POST", "AI_OPER_APP_ENGINE.v1/", {
            "aeId": ae_id, "operationType": "struct",
        }),
        ("AI_OPER_COMPONENT_DEFN_POST", "AI_OPER_COMPONENT_DEFN.v1/", {
            "pnlGrpName": component, "operationType": "struct",
        }),
        ("AI_OPER_FIELD_DEFN_POST", "AI_OPER_FIELD_DEFN.v1/", [field]),
        ("AI_OPER_PAGE_DEFN_POST", "AI_OPER_PAGE_DEFN.v1/", {
            "pageName": page, "operationType": "struct",
        }),
        ("AI_OPER_PROJECT_DEFN_POST", "AI_OPER_PROJECT_DEFN.v1/", {
            "projectName": project, "operationType": "struct",
        }),
        ("AI_OPER_RECORD_DEFN_POST", "AI_OPER_RECORD_DEFN.v1/", {
            "recordName": record, "operationType": "struct",
        }),
        ("AI_OPER_SQL_DEFN_POST", "AI_OPER_SQL_DEFN.v1/", {
            "sqlId": sql_id, "operationType": "view",
        }),
        ("AI_QUERY_RECORD_POST", "AI_QUERY_RECORD.v1/", {
            "record": query_record, "fields": [query_field], "maxRows": 1,
        }),
    )


def cmd_preflight(args):
    """体检：报告「从零到能用」各阶段的状态，并给出下一步该做什么。

    只读 —— 不发任何写请求。这是新用户/新环境的统一入口：先跑它看清卡在哪，
    再按 NEXT 走，而不是自己猜该执行什么。
    """
    print(f"Preflight: environment={ENVIRONMENT}  node={NODE}  user={USERNAME}")
    print(f"  pia:    {BASE_URL}")
    print(f"  config: {CONFIG_PATH}")

    # [1] 认证。PSTOKEN 也走同一个网关，所以这一步同时反映节点名是否正确。
    auth_reason = None
    auth_kind = None
    try:
        get_token(force_refresh=args.refresh)
        print("  [1] 认证            OK")
    except PSAuthError as exc:
        auth_kind, reason = _ib_failure_reason(exc.detail)
        auth_reason = reason or _shorten(exc.detail, 300)
        print(f"  [1] 认证            FAIL  {auth_reason}")

    # [2] 接口可用性（部署 + 授权一次跑完）
    failures = []
    if auth_reason:
        print("  [2] 接口可用性      SKIP  依赖 [1]")
    else:
        for operation, endpoint, payload in _build_probes():
            ok, detail = _probe_api(endpoint, payload)
            if not ok:
                failures.append((operation, detail))
        passed = len(_build_probes()) - len(failures)
        total = len(_build_probes())
        print(f"  [2] 接口可用性      {'OK' if not failures else 'FAIL'}    {passed}/{total} 个 Service Operation 通过")

    # [3] 工作 Project
    active = _active_project()
    print(f"  [3] 工作 Project    {'OK' if active else '未设置'}    {active or ''}".rstrip())

    if failures:
        print("\n  FAIL 详情：")
        for operation, detail in failures:
            print(f"    {operation} — {detail}")

    # NEXT：只给一条最重要的下一步，避免让用户面对一堆选项
    print()
    if auth_kind == "node":
        print(f"NEXT: 修正节点名（当前 node={NODE}），改完重跑本命令；不要导入 AD 工程。")
    elif auth_kind == "routing":
        print("NEXT: 该环境缺少元数据 Api。读 references/ad-cli-project-import.md 导入 AD 工程。")
    elif auth_kind == "authz":
        print("NEXT: 接口已部署但授权不足。读 references/rest-authorization.md 完成授权，"
              "然后重跑本命令确认全部通过。")
    elif auth_reason:
        print("NEXT: 认证未通过，按上面 [1] 的报错原文处理（见 SKILL.md 第3步）。")
    elif any("导入 AD 工程" in d for _, d in failures):
        print("NEXT: 该环境缺少元数据 Api。读 references/ad-cli-project-import.md 导入 AD 工程。")
    elif failures:
        print("NEXT: 接口已部署但授权不足。读 references/rest-authorization.md 完成授权，"
              "然后重跑本命令确认全部通过。")
    elif not active:
        print("NEXT: 环境已就绪。用 `project use <name>` 选定工作 Project 后即可开始开发。")
    else:
        print("NEXT: 环境已就绪，可以开始开发。")

    if auth_reason or failures:
        sys.exit(1)


def cmd_healthcheck(args):
    """Verify PSTOKEN plus every ps-metadata operation with read-only probes."""
    probes = _build_probes(
        package_root=args.package_root,
        record=args.record,
        component=args.component,
        page=args.page,
        field=args.field,
        query_record=args.query_record,
        query_field=args.query_field,
        ae_id=args.ae_id,
        sql_id=args.sql_id,
        project=args.project,
    )
    print(f"Health check: environment={ENVIRONMENT} pia={BASE_URL} user={USERNAME}")
    failures = []
    try:
        get_token(force_refresh=args.refresh)
        print("PASS PSTOKEN_GET")
    except PSAuthError as exc:
        print(f"FAIL PSTOKEN_GET — {_shorten(exc.detail, 300)}")
        if exc.hint:
            print(exc.hint, file=sys.stderr)
        failures.append("PSTOKEN_GET")
        # 认证都过不了，逐个探测只会把同一个错误重复十遍
        print("Health check failed: PSTOKEN_GET", file=sys.stderr)
        print("PSTOKEN 未获取成功，已跳过其余接口探测。", file=sys.stderr)
        sys.exit(1)

    for operation, endpoint, payload in probes:
        ok, detail = _probe_api(endpoint, payload)
        if ok:
            print(f"PASS {operation} — {detail}")
        else:
            print(f"FAIL {operation} — {detail}")
            failures.append(operation)
    if failures:
        print("Health check failed: " + ", ".join(failures), file=sys.stderr)
        sys.exit(1)
    print("Health check passed: PSTOKEN_GET plus all 10 ps-metadata operations.")


# ── environment ───────────────────────────────────────
def _environment_map(doc):
    """Return (environments, active_name, is_multi_env) for either config schema."""
    environments = doc.get("environments")
    if isinstance(environments, dict) and environments:
        active = doc.get("active_environment") or next(iter(environments))
        if active not in environments:
            raise ValueError(
                f"active environment '{active}' not found in config.json 'environments'"
            )
        return environments, active, True

    # Allow an old one-environment config to be upgraded by `env use`.
    legacy = doc.get("peoplesoft")
    if isinstance(legacy, dict):
        active = doc.get("active_environment") or "default"
        return {active: legacy}, active, False

    raise ValueError("config.json must contain a non-empty 'environments' object")


def _print_environment(name, cfg, active):
    marker = "*" if name == active else " "
    url = str(cfg.get("pia_base_url", "")).rstrip("/")
    username = cfg.get("username", "")
    node = _resolve_node(cfg)
    note = "" if node == DEFAULT_NODE else "  ← 非默认节点"
    print(f"{marker} {name}: {url} (user={username}, node={node}){note}")


def _prompt_required(label, value=None):
    if value is None:
        try:
            value = input(label)
        except EOFError as exc:
            # 非交互环境（Agent 直接调用、stdin 关闭）没有可读输入，
            # 报出非交互用法而不是抛裸 traceback。
            raise ValueError(
                f"{label.rstrip(': ')} 未提供。非交互环境请改用参数传入：\n"
                "       python scripts/peoplesoft_api.py env init <name> "
                "--url <url> --username <user> --password-stdin"
            ) from exc
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label.rstrip(': ')} cannot be empty")
    return value


def _init_config(args):
    """Create or add one environment without exposing the password in argv."""
    name = _prompt_required("Environment name: ", args.name)
    url = _prompt_required("PIA URL: ", args.pia_url).rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("PIA URL must be an absolute http:// or https:// URL")
    username = _prompt_required("PeopleSoft username: ", args.username)

    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
    else:
        try:
            password = getpass.getpass("PeopleSoft password (hidden): ")
            confirm = getpass.getpass("Confirm password (hidden): ")
        except EOFError as exc:
            raise ValueError(
                "无法交互读取密码。非交互环境请通过 --password-stdin 从标准输入传入"
                "（不要写在命令行参数里，会泄漏到进程列表和 shell 历史）：\n"
                "       python scripts/peoplesoft_api.py env init <name> "
                "--url <url> --username <user> --password-stdin"
            ) from exc
        if password != confirm:
            raise ValueError("password confirmation does not match")
    if not password:
        raise ValueError("PeopleSoft password cannot be empty")

    if CONFIG_PATH.exists():
        try:
            doc = _read_config()
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"cannot read existing config.json: {exc}") from exc
        if not isinstance(doc, dict):
            raise ValueError("config.json root must be a JSON object")
    else:
        doc = {}

    existing_environments = doc.get("environments")
    if existing_environments is None:
        legacy = doc.get("peoplesoft")
        if legacy is not None:
            if not isinstance(legacy, dict):
                raise ValueError("config.json 'peoplesoft' must be an object")
            legacy_name = str(doc.get("active_environment") or "default")
            environments = {legacy_name: legacy}
            doc = {k: v for k, v in doc.items() if k not in ("peoplesoft", "active_environment")}
        else:
            environments = {}
            doc = {k: v for k, v in doc.items() if k != "active_environment"}
    elif isinstance(existing_environments, dict):
        environments = dict(existing_environments)
    else:
        raise ValueError("config.json 'environments' must be an object")

    was_existing = name in environments
    if was_existing and not args.force:
        raise ValueError(f"environment '{name}' already exists; use --force to replace it")

    entry = {
        "pia_base_url": url,
        "username": username,
        "password": password,
        "node": (args.node or "").strip() or DEFAULT_NODE,
    }
    environments[name] = entry
    old_active = doc.get("active_environment")
    doc["environments"] = environments
    if not args.keep_current or old_active not in environments:
        doc["active_environment"] = name
    else:
        doc["active_environment"] = old_active

    _write_config(doc)
    _reload_runtime()
    print(f"PeopleSoft environment {'updated' if args.force and was_existing else 'created'}: {name}")
    _print_environment(ENVIRONMENT, _cfg, ENVIRONMENT)
    if args.auth:
        get_token(force_refresh=True)
        print("PS_TOKEN refreshed and cached.")


def cmd_env(args):
    """List or switch the active PeopleSoft environment."""
    if args.op == "init":
        try:
            _init_config(args)
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    try:
        doc = _read_config()
        environments, active, is_multi_env = _environment_map(doc)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.auth and args.op != "use":
        print("ERROR: --auth can only be used with 'env use <name>'", file=sys.stderr)
        sys.exit(2)

    if args.op == "list":
        for name, cfg in environments.items():
            _print_environment(name, cfg, active)
        return

    if args.op == "current":
        _print_environment(active, environments[active], active)
        return

    if not args.name:
        print("ERROR: env use requires an environment name", file=sys.stderr)
        sys.exit(2)
    if args.name not in environments:
        print(
            f"ERROR: unknown environment '{args.name}'. Available: {', '.join(environments)}",
            file=sys.stderr,
        )
        sys.exit(2)

    if is_multi_env:
        new_doc = doc
    else:
        # Upgrade the legacy schema on the first explicit switch.
        new_doc = {k: v for k, v in doc.items() if k != "peoplesoft"}
        new_doc["environments"] = environments
    new_doc["active_environment"] = args.name
    _write_config(new_doc)
    _reload_runtime()

    print(f"Switched PeopleSoft environment to: {ENVIRONMENT}")
    _print_environment(ENVIRONMENT, _cfg, ENVIRONMENT)
    if args.auth:
        get_token(force_refresh=True)
        print("PS_TOKEN refreshed and cached.")

# ── search ────────────────────────────────────────────
def cmd_search(args):
    type_map = {
        "record": 1, "field": 2, "sql": 65, "apppkg": 104, "project": 105
    }
    if args.type not in type_map:
        print(f"Unknown type: {args.type}. Use: record, field, sql, apppkg, project", file=sys.stderr)
        sys.exit(1)
    payload = {"definitionType": type_map[args.type]}
    if args.name:
        payload["definitionName"] = args.name
    if args.desc and args.type == "record":
        payload["recordDescr"] = args.desc
    if args.desc and args.type == "apppkg":
        payload["appPackageDescr"] = args.desc
    if args.desc and args.type == "project":
        payload["projectDescr"] = args.desc
    data = _api_call("AI_SEARCH_DEFN.v1/", payload)
    items = data.get("list", [])
    if not items:
        print("(no results)")
        return
    for item in items:
        if args.type == "record":
            print(f"{item.get('recordName', '?')}  |  {item.get('recordDescr', '')}")
        elif args.type == "field":
            print(f"{item.get('fieldName', '?')}  type={item.get('fieldType', '?')}  len={item.get('length', '?')}")
        elif args.type == "sql":
            print(f"{item.get('sqlId', '?')}  type={item.get('sqlType', '?')}")
        elif args.type == "apppkg":
            print(f"{item.get('packageId', '?')}  |  {item.get('descr', '')}")
        elif args.type == "project":
            print(f"{item.get('projectName', '?')}  |  {item.get('projectDescr', '')}")

# ── app-pkg ───────────────────────────────────────────
def cmd_app_pkg(args):
    payload = {"packageRoot": args.pkg}
    if args.op == "struct":
        payload["operationType"] = "default"
        data = _api_call("AI_OPER_APP_PKG_POST.v1/", payload)
        _print_pkg_tree(data.get("packageTree", {}), indent=0)
        if data.get("comment"):
            print(f"\ndescr: {data.get('descr', '')}")
            print(f"lastUpdate: {data.get('lastUpdate', '')}")
    elif args.op == "view-code":
        payload["operationType"] = "viewPeopleCode"
        payload["classPath"] = args.classpath
        data = _api_call("AI_OPER_APP_PKG_POST.v1/", payload)
        print(data.get("peoplecode", ""))
    elif args.op == "modify-code":
        code = Path(args.file).read_text(encoding="utf-8") if Path(args.file).exists() else args.file
        payload["operationType"] = "modifyPeopleCode"
        payload["classPath"] = args.classpath
        payload["peoplecode"] = json_escape(code)
        data = _api_call("AI_OPER_APP_PKG_POST.v1/", payload)
        print("OK — code uploaded and compiled.")
    elif args.op == "insert-class":
        payload["operationType"] = "insertClass"
        payload["classPath"] = args.classpath
        data = _api_call("AI_OPER_APP_PKG_POST.v1/", payload)
        print(f"OK — class inserted: {args.classpath}")
    elif args.op == "insert-package":
        payload["operationType"] = "insertPackage"
        payload["classPath"] = args.classpath
        data = _api_call("AI_OPER_APP_PKG_POST.v1/", payload)
        print(f"OK — package inserted: {args.classpath}")

def _print_pkg_tree(node, indent):
    prefix = "  " * indent + ("├─ " if indent > 0 else "")
    tag = f"[{node.get('nodeType', '?')}]"
    print(f"{prefix}{node.get('nodeName', '?')} {tag}")
    for child in node.get("children", []):
        _print_pkg_tree(child, indent + 1)

# ── sql ───────────────────────────────────────────────
def cmd_sql(args):
    if args.op == "view":
        data = _api_call("AI_OPER_SQL_DEFN.v1/", {
            "sqlId": args.sqlid, "operationType": "view"
        })
        print(f"sqlId: {data.get('sqlId')}")
        print(f"sqlType: {data.get('sqlType')}")
        print(f"lastUpdate: {data.get('lastUpdate')}")
        for stmt in data.get("statements", []):
            print(f"\n--- [{stmt.get('market')}/{stmt.get('dbType')}] {stmt.get('effdt')} ---")
            print(stmt.get("sqlText", ""))
            if stmt.get("descr"):
                print(f"descr: {stmt.get('descr')}")
            if stmt.get("comment"):
                print(f"comment: {stmt.get('comment')}")
    elif args.op == "create":
        stmt_data = json.loads(Path(args.file).read_text(encoding="utf-8")) if Path(args.file).exists() else json.loads(args.file)
        for s in stmt_data.get("statements", []):
            if "sqlText" in s:
                s["sqlText"] = json_escape(s["sqlText"])
            if "comment" in s:
                s["comment"] = json_escape(s["comment"])
        data = _api_call("AI_OPER_SQL_DEFN.v1/", {
            "sqlId": args.sqlid, "operationType": "create", "statements": stmt_data.get("statements", [])
        })
        print(f"OK — SQL created: {args.sqlid}")
    elif args.op == "modify":
        payload = {
            "sqlId": args.sqlid, "operationType": "modify",
            "market": args.market, "dbType": args.dbtype, "effdt": args.effdt
        }
        if args.sqltext_file:
            payload["sqlText"] = json_escape(Path(args.sqltext_file).read_text(encoding="utf-8"))
        if args.comment_file:
            payload["comment"] = json_escape(Path(args.comment_file).read_text(encoding="utf-8"))
        data = _api_call("AI_OPER_SQL_DEFN.v1/", payload)
        print(f"OK — SQL modified: {args.sqlid}")

# ── ae ────────────────────────────────────────────────
def cmd_ae(args):
    if args.op == "struct":
        data = _api_call("AI_OPER_APP_ENGINE.v1/", {
            "aeId": args.aeid, "operationType": "struct"
        })
        print(f"AE: {args.aeid}")
        print(f"descr: {data.get('descr', '')}")
        print(f"lastUpdate: {data.get('lastUpdate', '')}")
        ms = data.get("mainSection", {})
        print(f"\nMain Section: {ms.get('sectionType', '')} publicAccess={ms.get('publicAccess', '')}")
        for detail in ms.get("detail", []):
            print(f"\n  [{detail.get('market')}/{detail.get('dbType')}] {detail.get('descr', '')} "
                  f"effdt={detail.get('effdt')} autoCommit={detail.get('autoCommit')}")
            for step in detail.get("steps", []):
                print(f"    Step: {step.get('stepId')} [{step.get('activeStatus')}] "
                      f"abend={step.get('abendAction')} commit={step.get('commitAfter')}")
                for action in step.get("actions", []):
                    print(f"      Action: {action.get('actionType')} {action.get('descr', '')}")
    elif args.op == "create":
        payload = {"aeId": args.aeid, "operationType": "createApplicationEngine"}
        if args.descr:
            payload["descr"] = args.descr
        if args.comment:
            payload["comment"] = json_escape(args.comment)
        data = _api_call("AI_OPER_APP_ENGINE.v1/", payload)
        print(f"OK — AE created: {args.aeid}")
    elif args.op == "insert-section":
        payload = {"aeId": args.aeid, "operationType": "insertSection"}
        if args.sectionid:
            payload["sectionId"] = args.sectionid
        if args.market:
            payload["market"] = args.market
        if args.dbtype:
            payload["dbType"] = args.dbtype
        if args.effdt:
            payload["effdt"] = args.effdt
        data = _api_call("AI_OPER_APP_ENGINE.v1/", payload)
        print(f"OK — Section inserted.")
    elif args.op == "insert-step":
        payload = {
            "aeId": args.aeid, "operationType": "insertStep",
            "sectionId": args.sectionid, "market": args.market,
            "dbType": args.dbtype, "effdt": args.effdt
        }
        if args.stepid:
            payload["stepId"] = args.stepid
        if args.descr:
            payload["descr"] = args.descr
        data = _api_call("AI_OPER_APP_ENGINE.v1/", payload)
        print(f"OK — Step inserted.")
    elif args.op == "insert-action":
        payload = {
            "aeId": args.aeid, "operationType": "insertAction",
            "sectionId": args.sectionid, "market": args.market,
            "dbType": args.dbtype, "effdt": args.effdt,
            "stepId": args.stepid, "actionType": args.actiontype
        }
        if args.descr:
            payload["descr"] = args.descr
        data = _api_call("AI_OPER_APP_ENGINE.v1/", payload)
        print(f"OK — Action inserted.")
    elif args.op == "view-sql":
        data = _api_call("AI_OPER_APP_ENGINE.v1/", {
            "aeId": args.aeid, "operationType": "viewSQL",
            "sectionId": args.sectionid, "market": args.market,
            "dbType": args.dbtype, "effdt": args.effdt,
            "stepId": args.stepid, "actionType": args.actiontype
        })
        print(f"sqlId: {data.get('sqlId')}  sqlType: {data.get('sqlType')}  stmtCount: {data.get('stmtCount')}")
        print(f"lastUpdate: {data.get('lastUpdate')}")
        print(f"\n{data.get('sqlText', '')}")
    elif args.op == "modify-sql":
        sql_text = Path(args.file).read_text(encoding="utf-8") if Path(args.file).exists() else args.file
        data = _api_call("AI_OPER_APP_ENGINE.v1/", {
            "aeId": args.aeid, "operationType": "modifySQL",
            "sectionId": args.sectionid, "market": args.market,
            "dbType": args.dbtype, "effdt": args.effdt,
            "stepId": args.stepid, "actionType": args.actiontype,
            "sqlText": json_escape(sql_text)
        })
        print("OK — SQL modified.")
    elif args.op == "view-code":
        data = _api_call("AI_OPER_APP_ENGINE.v1/", {
            "aeId": args.aeid, "operationType": "viewPeopleCode",
            "sectionId": args.sectionid, "market": args.market,
            "dbType": args.dbtype, "effdt": args.effdt,
            "stepId": args.stepid
        })
        print(data.get("peoplecode", ""))
    elif args.op == "modify-code":
        code = Path(args.file).read_text(encoding="utf-8") if Path(args.file).exists() else args.file
        data = _api_call("AI_OPER_APP_ENGINE.v1/", {
            "aeId": args.aeid, "operationType": "modifyPeopleCode",
            "sectionId": args.sectionid, "market": args.market,
            "dbType": args.dbtype, "effdt": args.effdt,
            "stepId": args.stepid,
            "peopleCode": json_escape(code)
        })
        print("OK — PeopleCode modified.")
    elif args.op == "insert-state-record":
        data = _api_call("AI_OPER_APP_ENGINE.v1/", {
            "aeId": args.aeid, "operationType": "insertStateRecord",
            "recName": args.recname
        })
        print(f"OK — State Record inserted: {args.recname}")
    elif args.op == "insert-temp-table":
        data = _api_call("AI_OPER_APP_ENGINE.v1/", {
            "aeId": args.aeid, "operationType": "insertTempTable",
            "recName": args.recname
        })
        print(f"OK — Temp Table inserted: {args.recname}")

# ── component ────────────────────────────────────────
def cmd_component(args):
    if args.op == "structDeep":
        payload = {"pnlGrpName": args.pnlgrpname, "operationType": "structDeep"}
        if args.market:
            payload["market"] = args.market
        data = _api_call("AI_OPER_COMPONENT_DEFN.v1/", payload)
        _print_component_struct_deep(data)
    elif args.op == "struct":
        if args.deep:
            payload_deep = {"pnlGrpName": args.pnlgrpname, "operationType": "structDeep"}
            if args.market:
                payload_deep["market"] = args.market
            data_deep = _api_call("AI_OPER_COMPONENT_DEFN.v1/", payload_deep)
            _print_component_struct_deep(data_deep)
        else:
            payload = {"pnlGrpName": args.pnlgrpname, "operationType": "struct"}
            if args.market:
                payload["market"] = args.market
            data = _api_call("AI_OPER_COMPONENT_DEFN.v1/", payload)
            _print_component_struct(data)
    elif args.op == "view-code":
        if not args.event:
            print("ERROR: view-code requires --event", file=sys.stderr)
            sys.exit(1)
        payload = {"pnlGrpName": args.pnlgrpname, "operationType": "viewPeopleCode", "event": args.event}
        if args.record:
            payload["recordName"] = args.record
        if args.field:
            payload["fieldName"] = args.field
        data = _api_call("AI_OPER_COMPONENT_DEFN.v1/", payload)
        code = data.get("peoplecode")
        if code:
            print(code)
        else:
            print("(no peoplecode)")
    elif args.op == "modify-code":
        if not args.file:
            print("ERROR: modify-code requires <file>")
            sys.exit(1)
        if not args.event:
            print("ERROR: modify-code requires --event", file=sys.stderr)
            sys.exit(1)
        code_path = Path(args.file)
        code = code_path.read_text(encoding="utf-8") if code_path.exists() else args.file
        payload = {"pnlGrpName": args.pnlgrpname, "operationType": "modifyPeopleCode", "event": args.event, "peoplecode": json_escape(code)}
        if args.record:
            payload["recordName"] = args.record
        if args.field:
            payload["fieldName"] = args.field
        data = _api_call("AI_OPER_COMPONENT_DEFN.v1/", payload)
        msg = (data or {}).get("message", "saved")
        print(f"OK — {msg}")

def _print_component_struct_deep(comp_data):
    """Component > Level > Record > Field 层级树（无 Page 层）"""
    print(f"Component: {comp_data.get('pnlGrpName')}")
    print(f"  market: {comp_data.get('market')}")
    print(f"  descr: {comp_data.get('descr', '')}")
    comp_events = comp_data.get("events", [])
    if comp_events:
        print(f"  events: {', '.join(comp_events)}")
    levels = comp_data.get("levels", [])
    if not levels:
        print("\n  (no fields)")
        return
    print()
    for li, lvl in enumerate(levels):
        is_last_lvl = (li == len(levels) - 1)
        lvl_prefix = "└── " if is_last_lvl else "├── "
        lvl_indent = "    " if is_last_lvl else "│   "
        print(f"{lvl_prefix}Level {lvl['level']}")

        recs = lvl.get("records", [])
        for ri, rec in enumerate(recs):
            is_last_rec = (ri == len(recs) - 1)
            rec_prefix = "└── " if is_last_rec else "├── "
            rec_indent = lvl_indent + ("    " if is_last_rec else "│   ")
            rec_label = f"Record: {rec['recName']}" if rec.get('recName') else "(unbound)"
            rec_events = rec.get("events", [])
            if rec_events:
                rec_label += f"  events={rec_events}"
            print(f"{lvl_indent}{rec_prefix}{rec_label}")

            fields = rec.get("fields", [])
            for fi, f in enumerate(fields):
                is_last_f = (fi == len(fields) - 1)
                f_prefix = "└── " if is_last_f else "├── "
                field_label = f"{f['fieldName']} [{f['fieldType']}]"
                fld_events = f.get("events", [])
                if fld_events:
                    field_label += f"  events={fld_events}"
                print(f"{rec_indent}{f_prefix}{field_label}")

def _print_component_struct(data):
    print(f"Component: {data.get('pnlGrpName')}")
    print(f"  market: {data.get('market')}")
    print(f"  descr: {data.get('descr', '')}")
    print(f"  searchRec: {data.get('searchRecName')}  addSrchRec: {data.get('addSrchRecName')}  searchPnl: {data.get('searchPnlName')}")
    print(f"  fluidMode: {data.get('fluidMode')}  layoutMode: {data.get('layoutMode')}")
    print(f"  disableSave: {data.get('disableSave')}  forceSearch: {data.get('forceSearch')}")
    print(f"  deferProc: {data.get('deferProc')}  allowActModeSel: {data.get('allowActModeSel')}")
    print(f"  inclNavigation: {data.get('inclNavigation')}")
    print(f"  header: {data.get('incHeader')}  footer: {data.get('incFooter')}  side: {data.get('incSide')}  search: {data.get('incSearch')}")
    print(f"  compType: {data.get('compType')}  showTbar: {data.get('showTbar')}")
    print(f"  primaryAction: {data.get('primaryAction')}  dfltAction: {data.get('dfltAction')}  actions: {data.get('actions')}")
    print(f"  pnlGrpUse: {data.get('pnlGrpUse')}")
    if data.get("descrLong"):
        print(f"  descrLong: {data.get('descrLong')}")
    print(f"  lastUpdate: {data.get('lastUpdate')}")
    pages = data.get("pages", [])
    print(f"\n  Pages ({data.get('pageCount', 0)}):")
    for pg in pages:
        hidden = " [hidden]" if pg.get("hidden") else ""
        sub_item_num = str(pg.get("subItemNum", "?"))
        pnl_name = str(pg.get("pnlName", ""))
        print(f"    {sub_item_num:>3}. {pnl_name:30s} item={pg.get('itemName')}{hidden}")
        if pg.get("itemLabel"):
            print(f"         label: {pg.get('itemLabel')}")
        if pg.get("folderTabLabel"):
            print(f"         tab: {pg.get('folderTabLabel')}")

# ── record ────────────────────────────────────────────
def cmd_record(args):
    if args.op == "struct":
        data = _api_call("AI_OPER_RECORD_DEFN.v1/", {
            "recordName": args.recname, "operationType": "struct"
        })
        _print_record_struct(data)
    elif args.op == "create":
        if not args.file:
            print("ERROR: create requires <file> or inline JSON", file=sys.stderr)
            sys.exit(1)
        rec_data = json.loads(Path(args.file).read_text(encoding="utf-8")) if Path(args.file).exists() else json.loads(args.file)
        payload = {"recordName": args.recname, "operationType": "createRecord", **rec_data}
        if "comment" in payload:
            payload["comment"] = json_escape(payload["comment"])
        data = _api_call("AI_OPER_RECORD_DEFN.v1/", payload)
        print(f"OK — Record created: {args.recname}")
    elif args.op == "build":
        data = _api_call("AI_OPER_RECORD_DEFN.v1/", {
            "recordName": args.recname, "operationType": "buildRecord",
            "createTable": [args.recname]
        })
        print(f"OK — Record built: {args.recname}")
        print(data.get("message", ""))
    elif args.op == "alter":
        data = _api_call("AI_OPER_RECORD_DEFN.v1/", {
            "recordName": args.recname, "operationType": "buildRecord",
            "alterTable": [args.recname]
        })
        print(f"OK — Record altered: {args.recname}")
    elif args.op == "modify":
        if not args.file:
            print("ERROR: modify requires <file> or inline JSON", file=sys.stderr)
            sys.exit(1)
        rec_data = json.loads(Path(args.file).read_text(encoding="utf-8")) if Path(args.file).exists() else json.loads(args.file)
        if "comment" in rec_data:
            rec_data["comment"] = json_escape(rec_data["comment"])
        data = _api_call("AI_OPER_RECORD_DEFN.v1/", {"recordName": args.recname, "operationType": "modifyRecord", **rec_data})
        print(f"OK — Record modified: {args.recname}")
    elif args.op == "create-view":
        data = _api_call("AI_OPER_RECORD_DEFN.v1/", {
            "recordName": args.recname, "operationType": "buildRecord",
            "createView": [args.recname]
        })
        print(f"OK — View created: {args.recname}")
    elif args.op == "view-sql":
        data = _api_call("AI_OPER_RECORD_DEFN.v1/", {
            "recordName": args.recname, "operationType": "viewSQL"
        })
        print(f"Record: {args.recname}  exists: {data.get('exists')}  sqlType: {data.get('sqlType')}")
        if data.get("lastUpdate"):
            print(f"lastUpdate: {data.get('lastUpdate')}")
        for stmt in data.get("statements", []):
            print(f"\n--- [{stmt.get('market')}/{stmt.get('dbType')}] {stmt.get('effdt')} ---")
            print(stmt.get("sqlText", ""))
            if stmt.get("descr"):
                print(f"descr: {stmt.get('descr')}")
            if stmt.get("comment"):
                print(f"comment: {stmt.get('comment')}")
    elif args.op == "modify-sql":
        if not args.file:
            print("ERROR: modify-sql requires <file> (SQL text)")
            sys.exit(1)
        sql_text = Path(args.file).read_text(encoding="utf-8") if Path(args.file).exists() else args.file
        data = _api_call("AI_OPER_RECORD_DEFN.v1/", {
            "recordName": args.recname, "operationType": "modifySQL",
            "sqlText": json_escape(sql_text)
        })
        print(f"OK — View SQL modified: {args.recname}")
    elif args.op == "view-code":
        if not args.fieldname or not args.event:
            print("ERROR: view-code requires --fieldname and --event", file=sys.stderr)
            sys.exit(1)
        data = _api_call("AI_OPER_RECORD_DEFN.v1/", {
            "recordName": args.recname, "operationType": "viewPeopleCode",
            "fieldName": args.fieldname, "event": args.event
        })
        code = data.get("peoplecode")
        if code:
            print(code)
        else:
            print("(no peoplecode)")
    elif args.op == "modify-code":
        if not args.file:
            print("ERROR: modify-code requires <file>")
            sys.exit(1)
        if not args.fieldname or not args.event:
            print("ERROR: modify-code requires --fieldname and --event", file=sys.stderr)
            sys.exit(1)
        code_path = Path(args.file)
        code = code_path.read_text(encoding="utf-8") if code_path.exists() else args.file
        data = _api_call("AI_OPER_RECORD_DEFN.v1/", {
            "recordName": args.recname, "operationType": "modifyPeopleCode",
            "fieldName": args.fieldname, "event": args.event,
            "peoplecode": json_escape(code)
        })
        print("OK — Record PeopleCode modified.")

def _print_record_struct(data):
    print(f"Record: {data.get('recName')}")
    print(f"  Type: {data.get('recordType')}  Fields: {data.get('fieldCount')}  Indexes: {data.get('indexCount')}")
    print(f"  descr: {data.get('descr', '')}")
    print(f"  lastUpdate: {data.get('lastUpdate', '')}")
    print(f"\nFields:")
    for f in data.get("fields", []):
        sub = " [sub]" if f.get("subRecord") == "Y" else ""
        props = ",".join(f.get("fieldProperty", [])) if f.get("fieldProperty") else ""
        print(f"  {f.get('fieldName'):30s} {f.get('fieldType', ''):12s} len={str(f.get('length', '?')):>5s}  {props}{sub}")
    print(f"\nIndexes:")
    for idx in data.get("indexes", []):
        keys = ", ".join(f"{k.get('fieldName')}({k.get('ascDesc')})" for k in idx.get("indexFields", []))
        print(f"  {idx.get('indexId'):6s} type={idx.get('indexType')} unique={idx.get('uniqueFlag')}  keys: {keys}")
        if idx.get("comment"):
            print(f"         comment: {idx.get('comment')}")

# ── query-record ─────────────────────────────────────
def cmd_query_record(args):
    """业务数据查询：AI_QUERY_RECORD_POST（RecordQuery 子包）"""
    payload = {"record": args.record, "fields": [f.strip() for f in args.fields.split(",") if f.strip()]}
    if args.filter:
        filt = json.loads(Path(args.filter).read_text(encoding="utf-8")) if Path(args.filter).exists() else json.loads(args.filter)
        payload["filter"] = filt
    if args.max_rows:
        payload["maxRows"] = int(args.max_rows)
    data = _api_call("AI_QUERY_RECORD.v1/", payload)
    fields = data.get("fields", [])
    rows = data.get("rows", [])
    print(f"Record: {data.get('record')}  rowCount: {data.get('rowCount', len(rows))}")
    if not fields:
        print("(no fields returned)")
        return
    headers = " | ".join(f.get("name", "?") for f in fields)
    print(headers)
    print("-" * len(headers))
    for row in rows:
        vals = row.get("v", [])
        print(" | ".join(str(v) for v in vals))

# ── project ─────────────────────────────────────────
def cmd_project(args):
    """操作 Project 定义：AI_OPER_PROJECT_DEFN_POST"""
    if args.op == "current":
        active = _active_project()
        if active:
            print(f"Current project for environment {ENVIRONMENT}: {active}")
        else:
            print(f"No project selected for environment {ENVIRONMENT} yet.")
            print("NEXT: python scripts/peoplesoft_api.py project use <name>")
        return

    if not args.projectname:
        print(f"ERROR: project {args.op} requires a project name", file=sys.stderr)
        sys.exit(2)

    if args.op == "use":
        _set_active_project(args.projectname)
        print(f"Current project for environment {ENVIRONMENT}: {args.projectname}")
        return

    payload = {"projectName": args.projectname}
    if args.op == "create":
        payload["operationType"] = "createProject"
        if args.descr:
            payload["descr"] = args.descr
        if args.comment:
            payload["comment"] = json_escape(args.comment)
        _api_call("AI_OPER_PROJECT_DEFN.v1/", payload)
        _set_active_project(args.projectname)
        print(f"OK — project created: {args.projectname}")
        print(f"Current project for environment {ENVIRONMENT}: {args.projectname}")
    elif args.op == "insert-item":
        payload["operationType"] = "insertItem"
        if args.object_type is None:
            print("ERROR: insert-item requires --object-type", file=sys.stderr)
            sys.exit(1)
        payload["objectType"] = args.object_type
        if args.value1:
            payload["objectValue1"] = args.value1
        if args.value2:
            payload["objectValue2"] = args.value2
        if args.value3:
            payload["objectValue3"] = args.value3
        if args.value4:
            payload["objectValue4"] = args.value4
        if args.upgrade_action is not None:
            payload["upgradeAction"] = args.upgrade_action
        # 默认勾上 Upgrade（takeAction=1），保证迁移时该定义会被带到目标库；
        # 服务器端未传时默认 0（不勾选），因此这里必须显式传 1。显式 --take-action 0 可关闭。
        payload["takeAction"] = args.take_action if args.take_action is not None else 1
        _api_call("AI_OPER_PROJECT_DEFN.v1/", payload)
        _set_active_project(args.projectname)
        print(f"OK — item inserted into project: {args.projectname} (takeAction={payload['takeAction']})")
        print(f"Current project for environment {ENVIRONMENT}: {args.projectname}")
    elif args.op == "modify":
        payload["operationType"] = "modifyProject"
        if args.descr:
            payload["descr"] = args.descr
        if args.comment:
            payload["comment"] = json_escape(args.comment)
        _api_call("AI_OPER_PROJECT_DEFN.v1/", payload)
        _set_active_project(args.projectname)
        print(f"OK — project modified: {args.projectname}")
        print(f"Current project for environment {ENVIRONMENT}: {args.projectname}")
    elif args.op == "struct":
        payload["operationType"] = "struct"
        data = _api_call("AI_OPER_PROJECT_DEFN.v1/", payload)
        print(f"Project: {data.get('projectName')}")
        items = data.get("items", [])
        if not items:
            print("(no items)")
            return
        print(f"Items ({len(items)}):")
        for it in items:
            print(f"  objectType={it.get('objectType')}  id1={it.get('objectId1')}  value1={it.get('objectValue1')}  value2={it.get('objectValue2')}  value3={it.get('objectValue3')}  value4={it.get('objectValue4')}  upgrade={it.get('upgradeAction')}  take={it.get('takeAction')}")

# ── get-field ────────────────────────────────────────
def cmd_get_field(args):
    """批量查询字段定义：AI_OPER_FIELD_DEFN"""
    field_list = [f.strip() for f in args.fields.split(",") if f.strip()]
    if not field_list:
        print("ERROR: at least one field name required", file=sys.stderr)
        sys.exit(1)
    try:
        data = _api_call("AI_OPER_FIELD_DEFN.v1/", field_list)
    except Exception as e:
        print(f"ERROR: AI_OPER_FIELD_DEFN 调用失败 ({type(e).__name__}): {e}", file=sys.stderr)
        sys.exit(1)
    for f in data.get("fields", []):
        print(f"{f.get('fieldName', '?'):30s} {f.get('fieldType', '?'):12s} len={str(f.get('length', '?')):>5s}  {f.get('comment', '')}")
        labels = f.get("labels", [])
        for lab in labels:
            print(f"    label[{lab.get('labelId')}]: {lab.get('longName')} / {lab.get('shortName')} (default={lab.get('defaultLabel')})")

# ── page ─────────────────────────────────────────────
def _print_page_struct(data, full=False):
    fields = data.get("fields", [])
    print(f"Page: {data.get('pnlName')}  type={data.get('pnlType')}  use={data.get('pnlUse')}  controls={len(fields)}")
    print(f"  descr: {data.get('descr')}")
    print(f"  {data.get('lastUpdate', '')}")
    if full and isinstance(data.get("raw"), dict):
        print(f"  raw.columns: {len(data['raw'])}")
    for f in fields:
        pos = f"[{f.get('fieldLeft')},{f.get('fieldTop')},{f.get('fieldRight')},{f.get('fieldBottom')}]"
        bind = ""
        if f.get("recName") or f.get("fieldName"):
            bind = f"{f.get('recName', '')}.{f.get('fieldName', '')}"
        ext_mark = " +ext" if "ext" in f else ""
        print(f"  #{f.get('pnlFldId'):>3} {str(f.get('fieldType')):14} lvl={f.get('occursLevel')} use={f.get('fieldUse')} {pos:22} {bind:36} {f.get('labelText', '')}{ext_mark}".rstrip())
    if full:
        print("  (full mode: raw/ext 全量列对象已包含在 --json 输出中)")


def cmd_page(args):
    """Page 定义操作：AI_OPER_PAGE_DEFN"""
    if args.op == "struct":
        payload = {"pageName": args.pagename, "operationType": "struct"}
        if args.full:
            payload["full"] = 1
        data = _api_call("AI_OPER_PAGE_DEFN.v1/", payload)
        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=1))
        else:
            _print_page_struct(data, full=args.full)
    elif args.op == "view-code":
        payload = {"pageName": args.pagename, "operationType": "viewPeopleCode"}
        data = _api_call("AI_OPER_PAGE_DEFN.v1/", payload)
        code = data.get("peoplecode")
        print(code if code else "(no Activate PeopleCode)")
    elif args.op == "modify-code":
        if not args.file:
            print("ERROR: modify-code requires --file", file=sys.stderr)
            sys.exit(1)
        with open(args.file, encoding="utf-8") as f:
            code = f.read()
        payload = {"pageName": args.pagename, "operationType": "modifyPeopleCode", "peoplecode": json_escape(code)}
        _api_call("AI_OPER_PAGE_DEFN.v1/", payload)
        print(f"OK — page PeopleCode updated: {args.pagename}")
    elif args.op == "create":
        payload = {"pageName": args.pagename, "operationType": "createPage"}
        if args.descr:
            payload["descr"] = args.descr
        if args.comment:
            payload["comment"] = json_escape(args.comment)
        if args.pnl_type is not None:
            payload["pnlType"] = args.pnl_type
        _api_call("AI_OPER_PAGE_DEFN.v1/", payload)
        print(f"OK — page created: {args.pagename}")
        print("NEXT: project insert-item <proj> --object-type 5 --value1 " + args.pagename)
    elif args.op == "modify-props":
        payload = {"pageName": args.pagename, "operationType": "modifyPageProps"}
        if args.descr:
            payload["descr"] = args.descr
        if args.comment:
            payload["comment"] = json_escape(args.comment)
        if args.pnl_type is not None:
            payload["pnlType"] = args.pnl_type
        if args.defer_proc is not None:
            payload["deferProc"] = args.defer_proc
        if args.panel_right is not None:
            payload["panelRight"] = args.panel_right
        if args.panel_bottom is not None:
            payload["panelBottom"] = args.panel_bottom
        _api_call("AI_OPER_PAGE_DEFN.v1/", payload)
        print(f"OK — page props updated: {args.pagename}")
    elif args.op == "add-control":
        if not args.control_type:
            print("ERROR: add-control requires --control-type", file=sys.stderr)
            sys.exit(1)
        payload = {"pageName": args.pagename, "operationType": "addControl", "controlType": args.control_type}
        for arg, key in (("--rec", "recName"), ("--field", "fieldName")):
            pass
        if args.rec:
            payload["recName"] = args.rec
        if args.field:
            payload["fieldName"] = args.field
        if args.label_text:
            payload["labelText"] = args.label_text
        if args.label_id:
            payload["labelId"] = args.label_id
        if args.left is not None:
            payload["left"] = args.left
        if args.top is not None:
            payload["top"] = args.top
        if args.right is not None:
            payload["right"] = args.right
        if args.bottom is not None:
            payload["bottom"] = args.bottom
        if args.occurs_level is not None:
            payload["occursLevel"] = args.occurs_level
        if args.required is not None:
            payload["required"] = args.required
        if args.invisible is not None:
            payload["invisible"] = args.invisible
        if args.display_only is not None:
            payload["displayOnly"] = args.display_only
        if args.on_value:
            payload["onValue"] = args.on_value
        if args.off_value:
            payload["offValue"] = args.off_value
        if args.sub_pnl_name:
            payload["subPnlName"] = args.sub_pnl_name
        if args.html_text:
            payload["htmlText"] = json_escape(args.html_text)
        if args.pb_display_type is not None:
            payload["pbDisplayType"] = args.pb_display_type
        data = _api_call("AI_OPER_PAGE_DEFN.v1/", payload)
        print(f"OK — control added: {args.control_type} pnlFldId={data.get('pnlFldId')} on {args.pagename}")
    elif args.op == "del-control":
        if args.pnl_fld_id is None:
            print("ERROR: del-control requires --pnl-fld-id", file=sys.stderr)
            sys.exit(1)
        payload = {"pageName": args.pagename, "operationType": "deleteControl", "pnlFldId": args.pnl_fld_id}
        _api_call("AI_OPER_PAGE_DEFN.v1/", payload)
        print(f"OK — control deleted: pnlFldId={args.pnl_fld_id} on {args.pagename}")
    elif args.op == "find":
        payload = {"pageName": args.pagename, "operationType": "findControls"}
        if args.rec:
            payload["recName"] = args.rec
        if args.field:
            payload["fieldName"] = args.field
        if args.label_text:
            payload["labelContains"] = args.label_text
        if args.field_type:
            payload["fieldType"] = args.field_type
        data = _api_call("AI_OPER_PAGE_DEFN.v1/", payload)
        print(f"Page: {data.get('pageName')}  matches={data.get('matchCount')}")
        for it in data.get("items", []):
            print(f"  #{it.get('pnlFldId'):>3} type={it.get('fieldType'):<3} {str(it.get('recName', ''))}.{str(it.get('fieldName', ''))}  label={it.get('labelText', '') or it.get('labelId', '')}  pos=({it.get('left')},{it.get('top')})")
    elif args.op == "mod-control":
        if args.pnl_fld_id is None:
            print("ERROR: mod-control requires --pnl-fld-id", file=sys.stderr)
            sys.exit(1)
        payload = {"pageName": args.pagename, "operationType": "modifyControl", "pnlFldId": args.pnl_fld_id}
        if args.label_text:
            payload["labelText"] = args.label_text
        if args.label_id:
            payload["labelId"] = args.label_id
        if args.left is not None:
            payload["left"] = args.left
        if args.top is not None:
            payload["top"] = args.top
        if args.right is not None:
            payload["right"] = args.right
        if args.bottom is not None:
            payload["bottom"] = args.bottom
        if args.occurs_level is not None:
            payload["occursLevel"] = args.occurs_level
        if args.required is not None:
            payload["required"] = args.required
        if args.invisible is not None:
            payload["invisible"] = args.invisible
        if args.display_only is not None:
            payload["displayOnly"] = args.display_only
        if args.edit_size is not None:
            payload["editSize"] = args.edit_size
        if args.label_type is not None:
            payload["labelType"] = args.label_type
        if args.label_loc is not None:
            payload["labelLoc"] = args.label_loc
        if args.field_style:
            payload["fieldStyle"] = args.field_style
        if args.label_style:
            payload["labelStyle"] = args.label_style
        if args.defer_proc is not None:
            payload["deferProc"] = args.defer_proc
        data = _api_call("AI_OPER_PAGE_DEFN.v1/", payload)
        ctl = data.get("control", {})
        print(f"OK — control modified: pnlFldId={args.pnl_fld_id} on {args.pagename}")
        print(f"  now: label={ctl.get('labelText', '') or ctl.get('labelId', '')} pos=({ctl.get('left')},{ctl.get('top')},{ctl.get('right')},{ctl.get('bottom')}) use={ctl.get('fieldUse')}")


# ═══════════════════════════════════════════════════════
#  CLI 入口
# ═══════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="PeopleSoft IB REST API CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # auth
    p = sub.add_parser("auth", help="Get/refresh PS_TOKEN")
    p.add_argument("--refresh", action="store_true", help="Ignore the cache and call PSTOKEN.v1")

    # preflight
    p = sub.add_parser("preflight", help="体检：报告当前环境距离可用还差什么，并给出下一步（只读）")
    p.add_argument("--refresh", action="store_true", help="Refresh PS_TOKEN before probing")

    # healthcheck
    p = sub.add_parser("healthcheck", help="Read-only verification of PSTOKEN and all ps-metadata operations")
    p.add_argument("--refresh", action="store_true", help="Refresh PS_TOKEN before probing")
    p.add_argument("--project", default="C_META_DATA_PKG")
    p.add_argument("--package-root", default="C_META_DATA_PKG")
    p.add_argument("--record", default="JOB")
    p.add_argument("--component", default="JOB_DATA")
    p.add_argument("--page", default="JOB_DATA1")
    p.add_argument("--field", default="EMPLID")
    p.add_argument("--query-record", default="JOB")
    p.add_argument("--query-field", default="EMPLID")
    p.add_argument("--ae-id", default="__PS_METADATA_PROBE__")
    p.add_argument("--sql-id", default="__PS_METADATA_PROBE__")

    # bundle-check
    p = sub.add_parser("bundle-check", help="Validate local AD file-project dependencies before import")
    p.add_argument("--bundle-root", default=str(SKILL_DIR))
    p.add_argument("--project", default="C_META_DATA_PKG")

    # environment
    p = sub.add_parser("env", help="List, switch, or initialize PeopleSoft environments")
    p.add_argument("op", choices=["list", "current", "use", "init"])
    p.add_argument("name", nargs="?", help="Environment name for 'use' or 'init'")
    p.add_argument("--auth", action="store_true", help="Refresh PS_TOKEN after switching or initializing")
    p.add_argument("--url", dest="pia_url", help="PIA URL for 'env init'")
    p.add_argument("--username", help="PeopleSoft username for 'env init'")
    p.add_argument("--node", help=f"IB 本地节点名 for 'env init' (默认 {DEFAULT_NODE})")
    p.add_argument("--password-stdin", action="store_true", help="Read the init password from stdin instead of prompting")
    p.add_argument("--force", action="store_true", help="Replace an existing environment during 'env init'")
    p.add_argument("--keep-current", action="store_true", help="Keep the current active environment during 'env init'")

    # search
    p = sub.add_parser("search", help="Search definitions")
    p.add_argument("type", choices=["record", "field", "sql", "apppkg", "project"])
    p.add_argument("name", nargs="?", default="")
    p.add_argument("--desc", default="")

    # app-pkg
    p = sub.add_parser("app-pkg", help="Operate Application Package")
    p.add_argument("op", choices=["struct", "view-code", "modify-code", "insert-class", "insert-package"])
    p.add_argument("pkg")
    p.add_argument("classpath", nargs="?")
    p.add_argument("file", nargs="?")

    # sql
    p = sub.add_parser("sql", help="Operate SQL definitions")
    p.add_argument("op", choices=["view", "create", "modify"])
    p.add_argument("sqlid")
    p.add_argument("--market", default="GBL")
    p.add_argument("--dbtype", default="")
    p.add_argument("--effdt", default="1900-01-01")
    p.add_argument("--sqltext-file")
    p.add_argument("--comment-file")
    p.add_argument("file", nargs="?")

    # ae
    p = sub.add_parser("ae", help="Operate Application Engine")
    p.add_argument("op", choices=[
        "struct", "create", "insert-section", "insert-step", "insert-action",
        "view-sql", "modify-sql", "view-code", "modify-code",
        "insert-state-record", "insert-temp-table"
    ])
    p.add_argument("aeid")
    p.add_argument("--sectionid")
    p.add_argument("--market", default="GBL")
    p.add_argument("--dbtype", default="")
    p.add_argument("--effdt", default="1900-01-01")
    p.add_argument("--stepid")
    p.add_argument("--actiontype")
    p.add_argument("--descr")
    p.add_argument("--comment")
    p.add_argument("--recname")
    p.add_argument("file", nargs="?")

    # component
    p = sub.add_parser("component", help="Operate Component definitions")
    p.add_argument("op", choices=["struct", "structDeep", "view-code", "modify-code"])
    p.add_argument("pnlgrpname")
    p.add_argument("--market", default="")
    p.add_argument("--deep", action="store_true", help="Show Page > Level > Record > Field hierarchy")
    p.add_argument("--record")
    p.add_argument("--field")
    p.add_argument("--event")
    p.add_argument("--file")

    # record
    p = sub.add_parser("record", help="Operate Record definitions")
    p.add_argument("op", choices=["struct", "create", "modify", "build", "alter", "create-view", "view-sql", "modify-sql", "view-code", "modify-code"])
    p.add_argument("recname")
    p.add_argument("file", nargs="?")
    p.add_argument("--fieldname")
    p.add_argument("--event")

    # query-record
    p = sub.add_parser("query-record", help="Query business data (AI_QUERY_RECORD_POST)")
    p.add_argument("record", help="Record name")
    p.add_argument("fields", help="Comma-separated field names, e.g. EMPLID,EMPL_RCD")
    p.add_argument("--filter", help="Filter JSON: [{\"field\":\"EMPLID\",\"op\":\"=\",\"value\":\"0001\"}] or path to JSON file")
    p.add_argument("--max-rows", help="Max rows (default 200)")

    # project
    p = sub.add_parser("project", help="Operate Project definitions (AI_OPER_PROJECT_DEFN_POST)")
    p.add_argument("op", choices=["create", "insert-item", "modify", "struct", "use", "current"])
    p.add_argument("projectname", nargs="?", help="Project name; omitted for 'current'")
    p.add_argument("--descr")
    p.add_argument("--comment")
    p.add_argument("--object-type", type=int)
    p.add_argument("--value1")
    p.add_argument("--value2")
    p.add_argument("--value3")
    p.add_argument("--value4")
    p.add_argument("--upgrade-action", type=int, help="Upgrade action: 0=Copy, 1=Delete, 2=None, 3=Copy Property (default 0)")
    p.add_argument("--take-action", type=int, help="Whether to include item in upgrade: 0/1 (default 1 = checked)")

    # page
    p = sub.add_parser("page", help="Operate Page definitions (AI_OPER_PAGE_DEFN_POST)")
    p.add_argument("op", choices=["struct", "view-code", "modify-code", "create", "modify-props", "add-control", "del-control", "find", "mod-control"])
    p.add_argument("pagename")
    p.add_argument("--control-type", help="editBox|dropDown|checkBox|staticText|groupBox|hrule|subPage|scrollArea|htmlArea|pushButton|hyperlink")
    p.add_argument("--rec")
    p.add_argument("--field")
    p.add_argument("--label-text")
    p.add_argument("--label-id")
    p.add_argument("--left", type=int)
    p.add_argument("--top", type=int)
    p.add_argument("--right", type=int)
    p.add_argument("--bottom", type=int)
    p.add_argument("--occurs-level", type=int)
    p.add_argument("--required", type=int)
    p.add_argument("--invisible", type=int)
    p.add_argument("--display-only", type=int)
    p.add_argument("--pnl-fld-id", type=int)
    p.add_argument("--descr")
    p.add_argument("--comment")
    p.add_argument("--pnl-type", type=int)
    p.add_argument("--defer-proc", type=int)
    p.add_argument("--panel-right", type=int)
    p.add_argument("--panel-bottom", type=int)
    p.add_argument("--on-value")
    p.add_argument("--off-value")
    p.add_argument("--sub-pnl-name")
    p.add_argument("--html-text")
    p.add_argument("--pb-display-type", type=int)
    p.add_argument("--field-type", type=int, help="findControls numeric FIELDTYPE filter (e.g. 4=editBox, 27=scrollArea)")
    p.add_argument("--edit-size", type=int)
    p.add_argument("--label-type", type=int)
    p.add_argument("--label-loc", type=int)
    p.add_argument("--field-style")
    p.add_argument("--label-style")
    p.add_argument("--full", action="store_true", help="Include all available raw PSPNLDEFN/PSPNLFIELD columns")
    p.add_argument("--json", action="store_true", help="Dump raw JSON response")
    p.add_argument("--file")

    # get-field
    p = sub.add_parser("get-field", help="Batch query field definitions (AI_OPER_FIELD_DEFN_POST)")
    p.add_argument("fields", help="Comma-separated field names, e.g. EMPLID,EFFDT")

    args = parser.parse_args()

    # `env init` is the one command allowed to run without an existing config.
    if not (
        (args.cmd == "env" and args.op == "init")
        or args.cmd == "bundle-check"
    ):
        _require_runtime()

    # 路由
    try:
        _dispatch(args)
    except PSAuthError as exc:
        # detail 原样透出：SKILL.md 第2/3步要求 Agent 按响应体文本分流
        detail = exc.detail if len(exc.detail) <= 2000 else exc.detail[:2000] + "…(truncated)"
        print(f"ERROR: {detail}", file=sys.stderr)
        if exc.hint:
            print(exc.hint, file=sys.stderr)
        sys.exit(1)


def _dispatch(args):
    if args.cmd == "auth":
        cmd_auth(args)
    elif args.cmd == "bundle-check":
        cmd_bundle_check(args)
    elif args.cmd == "preflight":
        cmd_preflight(args)
    elif args.cmd == "healthcheck":
        cmd_healthcheck(args)
    elif args.cmd == "env":
        cmd_env(args)
    elif args.cmd == "search":
        cmd_search(args)
    elif args.cmd == "app-pkg":
        cmd_app_pkg(args)
    elif args.cmd == "sql":
        cmd_sql(args)
    elif args.cmd == "ae":
        cmd_ae(args)
    elif args.cmd == "component":
        cmd_component(args)
    elif args.cmd == "record":
        cmd_record(args)
    elif args.cmd == "query-record":
        cmd_query_record(args)
    elif args.cmd == "project":
        cmd_project(args)
    elif args.cmd == "page":
        cmd_page(args)
    elif args.cmd == "get-field":
        cmd_get_field(args)

if __name__ == "__main__":
    main()
