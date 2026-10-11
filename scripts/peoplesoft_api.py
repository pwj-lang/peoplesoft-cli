#!/usr/bin/env python3
"""
peoplesoft_api.py — PeopleSoft IB REST 命令行工具 封装

封装 PeopleSoft 元数据相关接口，自动处理认证、token 缓存、JSON 转义/反转义。
输出为已解码的纯文本，减少 AI token 消耗。

用法:
  python peoplesoft_api.py <命令> [参数...]

   Token 缓存: ~/.peoplesoft/cache/.ps_token_cache.<environment>.json（服务端通常 12 小时有效，客户端缓存 11 小时）
"""

import sys, os, json, base64, re, urllib.request, urllib.error, argparse, time, getpass, tempfile
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
DEFAULT_NODE = "PSFT_HR"
NODE_ENV_VAR = "PEOPLESOFT_NODE"
TOKEN_CACHE_TTL = 11 * 60 * 60  # PeopleSoft token 通常有效 12 小时，提前 1 小时刷新


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
    """Preserve configurable local IB nodes from earlier releases."""
    return os.environ.get(NODE_ENV_VAR) or str(cfg.get("node") or "").strip() or DEFAULT_NODE


def _ib_url(endpoint):
    """Build the IB gateway URL using the target environment's local node."""
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
# 「上次使用的 Project」记录在 config.json 当前环境的 active_project 字段，
# env use 切换环境后自动跟随，不需要单独的状态文件。
def _active_project():
    """当前环境记录的活动 Project；没有记录时返回 None。"""
    name = _cfg.get("active_project")
    if not name:
        # Earlier public releases stored Project choices outside config.json.
        try:
            legacy = json.loads(PROJECT_STATE_PATH.read_text(encoding="utf-8"))
            entry = legacy.get(ENVIRONMENT, {}) if isinstance(legacy, dict) else {}
            name = entry.get("active_project") if isinstance(entry, dict) else None
        except (OSError, ValueError, TypeError):
            name = None
    return str(name) if name else None


def _set_active_project(project_name):
    """把 project_name 记为当前环境的活动 Project（写回 config.json）。"""
    doc = _read_config()
    environments, active, is_multi_env = _environment_map(doc)
    if not is_multi_env:
        # 旧单环境 schema 在首次写入时升级为 environments 结构。
        doc = {k: v for k, v in doc.items() if k != "peoplesoft"}
    entry = dict(environments.get(active) or {})
    entry["active_project"] = project_name
    environments[active] = entry
    doc["environments"] = environments
    doc["active_environment"] = active
    _write_config(doc)
    _reload_runtime()


class PSAuthError(RuntimeError):
    """认证无法完成。

    detail 原样保留服务端响应体文本 —— SKILL.md 的环境检查（preflight 故障分流表）
    要求 Agent 按响应内容分流到对应参考文档，所以这里不能吞掉内容，也不能只抛状态码。
    """

    def __init__(self, detail, hint=""):
        super().__init__(detail)
        self.detail = detail
        self.hint = hint


class PSAPIError(RuntimeError):
    """接口调用无法完成（非 JSON 响应、网络失败等）。

    与 PSAuthError 一样保留服务端响应原文，让 Agent 能按 SKILL.md 的环境检查的
    故障分流表识别「Routing 缺失」「未经授权」等原因，而不是拿到一句裸 traceback。
    """

    def __init__(self, detail, hint=""):
        super().__init__(detail)
        self.detail = detail
        self.hint = hint


def _ib_failure_reason(text):
    """把 IB 网关的失败响应归类成 (类别, 一行可操作的原因)。无法归类返回 (None, "")。

    「环境没准备好」阶段有两种响应，修法不同，不能混为一谈：
    接口未部署要导入 AD 工程；已部署但没授权要去配许可权列表。
    """
    flat = " ".join(str(text).split())
    if "158,505" in flat or "找不到与入站请求消息对应的发送处理" in flat:
        return "node", f"节点名可能不正确（node={NODE}）；使用 env init --node 或 {NODE_ENV_VAR} 修正后重试。"
    if "routing corresponding" in flat.lower():
        return "routing", "接口未部署 —— 参考 references/01-auth-api.md#安装 导入 AD 工程"
    lowered = flat.lower()
    if "未经授权" in flat or any(t in lowered for t in (
        "not authorized", "not authorised", "access denied", "permission denied",
    )):
        return "authz", (
            "授权不足 —— 参考 references/01-auth-api.md#授权，"
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


def _artifact_dir():
    """Return the directory for local read-only PeopleSoft artifacts.

    A caller may provide PEOPLESOFT_TMP_DIR explicitly. When the CLI is run
    from a normal workspace, use its tmp directory; when it is run from this
    skill directory, keep the skill checkout clean and use a system temp
    directory instead.
    """
    explicit = os.environ.get("PEOPLESOFT_TMP_DIR")
    if explicit:
        return Path(explicit).expanduser()

    cwd = Path.cwd().resolve()
    skill_dir = SKILL_DIR.resolve()
    try:
        cwd.relative_to(skill_dir)
    except ValueError:
        return cwd / "tmp"
    return Path(tempfile.gettempdir()) / "peoplesoft"


def _safe_filename(value, fallback="artifact"):
    """Make a deterministic filename component safe on Windows and POSIX."""
    name = re.sub(r"[<>:\"/\\|?*\x00-\x1f]+", "_", str(value))
    name = re.sub(r"\s+", "_", name).strip(" ._")
    return (name or fallback)[:120]


def _cache_artifact(name, suffix, text):
    """Cache a read-only code/SQL response and return its absolute path."""
    path = (_artifact_dir() / (_safe_filename(name) + suffix)).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text or "", encoding="utf-8")
    return path

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
        raise PSAuthError(
            "当前环境在 config.json 中没有保存密码，无法换取 PS_TOKEN。",
            hint=(
                "请重新配置该环境的密码："
                " python scripts/peoplesoft_api.py env init <name> --url <url>"
                " --username <user> --force"
            ),
        )
    credentials = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
    req = urllib.request.Request(
        _ib_url("PSTOKEN.v1/"),
        headers={"Authorization": f"Basic {credentials}"}
    )
    try:
        raw = urllib.request.urlopen(req, timeout=PROBE_TIMEOUT).read()
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
    except (TimeoutError, urllib.error.URLError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(exc, TimeoutError) or "timed out" in str(exc).lower():
            reason = f"请求超过 {PROBE_TIMEOUT} 秒无响应"
        raise PSAuthError(
            f"无法连接 {BASE_URL}：{reason}",
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
    """Escape bare control characters inside strings, respecting escaped quotes."""
    result = []
    in_string = escaped = False
    for char in raw:
        if in_string:
            if escaped:
                result.append(char)
                escaped = False
                continue
            if char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            elif ord(char) < 32:
                result.append(json.dumps(char)[1:-1])
                continue
        elif char == '"':
            in_string = True
        result.append(char)
    return "".join(result)

def _shorten(text, limit=200):
    """压平空白并截断，用于单行错误摘要。"""
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[:limit] + "…"

# 单次 API 请求超时（秒）；None = 不限制。真实业务操作（如 record build / ae 修改）
# 可能合法地跑很久，所以默认不限；通过子命令选项 --timeout <秒> 设置上限，
# 避免网关假死时客户端无限挂起。
REQUEST_TIMEOUT = None


def _urlopen(req):
    if REQUEST_TIMEOUT is not None:
        return urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)
    return urllib.request.urlopen(req)


def _api_call(endpoint, data=None):
    """通用 API 调用，自动带 PS_TOKEN，返回解析后的 data 字段。token 过期自动刷新一次。"""
    def do_call(tok):
        """发一次请求并返回响应原文；HTTP 错误页也取原文，供上层判断。"""
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(
            _ib_url(endpoint),
            headers={"PS_TOKEN": tok, "Content-Type": "application/json"},
            data=body
        )
        try:
            return _safe_decode(_urlopen(req).read())
        except urllib.error.HTTPError as e:
            return _safe_decode(e.read())
        except (TimeoutError, urllib.error.URLError, OSError) as e:
            reason = getattr(e, "reason", e)
            if isinstance(e, TimeoutError) or "timed out" in str(reason).lower():
                reason = f"请求超过 {REQUEST_TIMEOUT} 秒无响应（--timeout 可调整）"
            raise PSAPIError(
                f"无法连接 {BASE_URL}：{reason}",
                hint="请检查 PIA 地址、网络连通性和代理设置是否正确。",
            ) from e

    def parse(raw_text):
        try:
            value = json.loads(raw_text)
        except json.JSONDecodeError:
            try:
                value = json.loads(_clean_json_text(raw_text))
            except json.JSONDecodeError:
                return None
        return value if isinstance(value, dict) else None

    def fail(raw_text):
        _, reason = _ib_failure_reason(raw_text)
        detail = _shorten(raw_text, 300) or "服务端返回了空响应"
        hint = reason or (
            "服务端返回非 JSON 响应，通常是网关报错或 token 失效；"
            "先运行 preflight 查看故障分流。"
        )
        raise PSAPIError(detail, hint=hint)

    raw = do_call(get_token())
    resp = parse(raw)
    if resp is None:
        # Only retry reads or explicit authentication failures. A malformed
        # mutation response can follow a committed save; resubmitting duplicates it.
        read_actions = {"view", "struct", "structDeep", "default", "exists",
                        "viewPeopleCode", "viewCode", "viewSQL", "list", "search"}
        action = data.get("operationType") if isinstance(data, dict) else None
        is_read = endpoint.startswith(("AI_SEARCH_DEFN.", "AI_QUERY_RECORD.", "AI_OPER_FIELD_DEFN.")) or action in read_actions
        if "psft authentication token failed" in raw.lower():
            raw = do_call(get_token(force_refresh=True))
            resp = parse(raw)
        elif is_read:
            raw = do_call(get_token())
            resp = parse(raw)
        if resp is None:
            if not is_read:
                raise PSAPIError(_shorten(raw, 300), hint="写入响应无法解析，保存可能已经完成；先回读目标，不要直接重复提交。")
            fail(raw)

    if resp.get("code") != 0:
        print(f"API Error [{resp.get('code')}]: {resp.get('message')}", file=sys.stderr)
        sys.exit(1)
    return resp.get("data", {})

def json_escape(text):
    """JSON 转义（等同于 Commons StringEscapeUtils.escapeJson）"""
    return json.dumps(text)[1:-1]


def _normalize_dbtype(value):
    """Normalize names/metadata character codes to the legacy API platform codes."""
    value = str(value).strip().upper()
    aliases = {"": "", "DEFAULT": "", "32": "", "DB2": "1", "49": "1",
               "ORACLE": "2", "50": "2", "INFORMIX": "3", "51": "3",
               "DB2UNIX": "4", "52": "4", "TIMESTEN": "5", "53": "5",
               "SYBASE": "6", "54": "6", "MICROSOFT": "7", "SQLSERVER": "7", "55": "7"}
    if value in aliases:
        return aliases[value]
    if value in {"1", "2", "3", "4", "5", "6", "7"}:
        return value
    raise PSAPIError(f"Unsupported dbType: {value}", hint="Use DEFAULT/32, ORACLE/50, or legacy codes 1–7.")


def _peoplecode_signature(code):
    """Ignore compiler formatting and comments while preserving string literals."""
    tokens = re.findall(r'"(?:[^"]|"")*"|/\*[\s\S]*?\*/|\bREM\b[^;]*;|\s+|.', code or "", re.I)
    return "".join(t if t.startswith('"') else t.casefold()
                   for t in tokens if not t.isspace() and not t.startswith("/*")
                   and not re.match(r"^REM\b", t, re.I))


def _write_verified_peoplecode(endpoint, payload, code):
    if not isinstance(code, str) or not code.strip():
        raise PSAPIError("Empty PeopleCode is not deletion; use delete-code to remove the native program.")
    _api_call(endpoint, payload)
    view = {k: v for k, v in payload.items() if k.lower() != "peoplecode"}
    view["operationType"] = "viewPeopleCode"
    actual = _api_call(endpoint, view).get("peoplecode") or ""
    if _peoplecode_signature(actual) != _peoplecode_signature(code):
        raise PSAPIError("PeopleCode write was acknowledged but readback differs.",
                         hint="Inspect the server compilation result and saved source before continuing.")
    return actual


def _delete_verified_peoplecode(endpoint, payload, args):
    """Delete the native program, independently verify absence, then register it."""
    project = getattr(args, "project", None) or _active_project()
    if not project:
        raise PSAPIError("delete-code requires --project or an active Project.")
    project_payload = {"projectName": project, "operationType": "struct"}
    _api_call("AI_OPER_PROJECT_DEFN.v1/", project_payload)
    view = dict(payload, operationType="viewPeopleCode")
    before = _api_call(endpoint, view)
    if before.get("programExists") is not True:
        raise PSAPIError("No native PeopleCode program was confirmed; deploy the deletion handler or check the exact key.")
    snapshot = _cache_artifact("delete_" + str(time.time_ns()) + "_" + "_".join(str(v) for v in payload.values()),
        ".pcode", before.get("peoplecode") or "")
    dry = bool(getattr(args, "dry_run", False))
    result = _api_call(endpoint, dict(payload, operationType="deletePeopleCode", dryRun=dry,
        expectedCode=json_escape(before.get("peoplecode") or "")))
    item = result.get("projectItem")
    required = {"objectType"} | {f"objectId{i}" for i in range(1, 5)} | {f"objectValue{i}" for i in range(1, 5)}
    if not isinstance(item, dict) or not required <= set(item):
        raise PSAPIError("Deletion response lacks the complete Project key; inspect program and Project state.")
    if result.get("dryRun") is not dry or result.get("deleted") is not (not dry) or result.get("programExists") is not dry:
        raise PSAPIError("Server did not confirm the requested native deletion state; inspect before retrying.")
    actual = _api_call(endpoint, view)
    if actual.get("programExists") is not dry:
        raise PSAPIError("Independent native PeopleCode existence readback differs.")
    if dry:
        if actual.get("peoplecode") != before.get("peoplecode"):
            raise PSAPIError("PeopleCode changed during dry-run; read the latest source.")
    else:
        try:
            def matches():
                rows = _api_call("AI_OPER_PROJECT_DEFN.v1/", project_payload).get("items", [])
                return [r for r in rows if _project_item_key(r) == _project_item_key(item)]
            rows = matches()
            if not rows:
                _api_call("AI_OPER_PROJECT_DEFN.v1/", dict(item, projectName=project, operationType="insertItem", upgradeAction=1, takeAction=1))
                rows = matches()
            if len(rows) != 1:
                raise PSAPIError("Expected one exact Project deletion item.")
            flags = {"upgradeAction": 1, "takeAction": 1, "copyDone": 0}
            if any(rows[0].get(k) != v for k, v in flags.items()):
                _api_call("AI_OPER_PROJECT_DEFN.v1/", dict(item, projectName=project, operationType="updateItem", **flags))
            rows = matches()
            if len(rows) != 1 or any(rows[0].get(k) != v for k, v in flags.items()):
                raise PSAPIError("Project deletion flags did not match after readback.")
        except (PSAPIError, SystemExit) as exc:
            raise PSAPIError("Native program deletion succeeded, but Project registration failed; inspect the saved key before retrying.") from exc
    result.update(environment=ENVIRONMENT, project=project, snapshotPath=str(snapshot), readbackVerified=True)
    if getattr(args, "output", None):
        _write_json_atomic(Path(args.output).resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result

def _load_json_arg(spec, label):
    """解析 <file> 或内联 JSON 参数；内容非法时给干净错误而不是裸 traceback。"""
    try:
        path = Path(spec)
        text = path.read_text(encoding="utf-8") if path.exists() else spec
        return json.loads(text)
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        print(
            f"ERROR: {label} 不是有效的 JSON，也不是可读取的 JSON 文件：{exc}",
            file=sys.stderr,
        )
        sys.exit(1)

# ═══════════════════════════════════════════════════════
#  子命令
# ═══════════════════════════════════════════════════════

# ── auth ──────────────────────────────────────────────
def cmd_auth(args):
    get_token(force_refresh=args.refresh)
    action = "refreshed" if args.refresh else "ready"
    print(f"PS_TOKEN {action} for environment: {ENVIRONMENT}")
    print("Token cached. Reused for up to 11 hours; server token is usually valid for 12 hours.")


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
            raw = _safe_decode(urllib.request.urlopen(req, timeout=PROBE_TIMEOUT).read())
        except urllib.error.HTTPError as exc:
            raw = _safe_decode(exc.read())
    except PSAuthError as exc:
        # 认证层失败：透出服务端原文，让 Agent 能按 SKILL.md 的环境检查的故障分流表处理
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


# 探测用哨兵值：故意用不存在的名字，让服务端回「找不到定义」或返回 0 行，
# 既证明该 Service Operation 已部署且被放行，又不会改动/读取任何真实数据。
PROBE_VALUE = "__PS_METADATA_PROBE__"

# 探测与认证本该快速返回，设上界避免网关不响应时客户端无限挂起。
# 真实业务操作（如 record build / ae 修改）可能合法地跑很久，故 _api_call 不设此上界。
PROBE_TIMEOUT = 60


def _build_probes(package_root="C_META_DATA_PKG", record="JOB", component="JOB_DATA",
                  page="JOB_DATA1", field="EMPLID", query_record="JOB",
                  query_field="EMPLID", ae_id=PROBE_VALUE,
                  sql_id=PROBE_VALUE, project="C_META_DATA_PKG"):
    """15 个 Service Operation 的只读探测清单。healthcheck 与 preflight 共用。

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
            "record": query_record,
            "fields": [query_field],
            # 必须带 filter。不带过滤条件的 JOB 查询等于 SELECT EMPLID FROM PS_JOB
            # 全表扫描，实测网关直接 504 —— maxRows 只是服务端返回行数上限，
            # 不会变成 SQL 的 ROWNUM/TOP，压不住代价。用不存在的值做等值过滤走
            # 索引 seek，返回 0 行，同样能证明接口已放行。
            "filter": [{"field": query_field, "op": "=", "value": PROBE_VALUE}],
            "maxRows": 1,
        }),
        ("AI_OPER_SERVICE_DEFN_POST", "AI_OPER_SERVICE_DEFN.v1/", {
            "kind": "service", "operationType": "exists", "name": PROBE_VALUE}),
        ("AI_OPER_SERVICE_OP_POST", "AI_OPER_SERVICE_OP.v1/", {
            "kind": "operation", "operationType": "exists", "name": PROBE_VALUE}),
        ("AI_OPER_MENU_DEFN_POST", "AI_OPER_MENU_DEFN.v1/", {
            "kind": "menu", "operationType": "exists", "name": PROBE_VALUE}),
        ("AI_OPER_MESSAGE_CATALOG_POST", "AI_OPER_MESSAGE_CATALOG.v1/", {
            "kind": "catalog", "operationType": "exists", "name": "32767"}),
        ("AI_OPER_PORTAL_REGISTRY_POST", "AI_OPER_PORTAL_REGISTRY.v1/", {
            "kind": "portal", "operationType": "exists", "name": PROBE_VALUE,
            "PortalName": "EMPLOYEE", "RefType": "F"}),
    )


def cmd_preflight(args):
    """体检：报告「从零到能用」各阶段的状态，并给出下一步该做什么。

    只读 —— 不发任何写请求。这是新用户/新环境的统一入口：先跑它看清卡在哪，
    再按 NEXT 走，而不是自己猜该执行什么。
    """
    print(f"Preflight: environment={ENVIRONMENT}  user={USERNAME}")
    print(f"  pia:    {BASE_URL}")
    print(f"  config: {CONFIG_PATH}")

    # [1] 认证
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
        print("NEXT: 修正目标环境的 IB 本地节点配置，然后重跑 preflight。")
    elif auth_kind == "routing":
        print("NEXT: 该环境缺少元数据 Api。读 references/01-auth-api.md#安装 导入 AD 工程。")
    elif auth_kind == "authz":
        print("NEXT: 接口已部署但授权不足。读 references/01-auth-api.md#授权 完成授权，"
              "然后重跑本命令确认全部通过。")
    elif auth_reason:
        print("NEXT: 认证未通过，按上面 [1] 的报错原文处理（见 SKILL.md 的环境检查）。")
    elif any("导入 AD 工程" in d for _, d in failures):
        print("NEXT: 该环境缺少元数据 Api。读 references/01-auth-api.md#安装 导入 AD 工程。")
    elif any("节点名可能不正确" in d for _, d in failures):
        print("NEXT: 修正目标环境的 IB 本地节点配置，然后重跑 preflight。")
    elif any(_ib_failure_reason(d)[0] == "authz" for _, d in failures):
        print("NEXT: 接口已部署但授权不足。读 references/01-auth-api.md#授权 完成授权，"
              "然后重跑本命令确认全部通过。")
    elif failures:
        print("NEXT: 按 FAIL 详情排查部署、源码兼容性或运行时错误，再重跑 preflight。")
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
    print(f"Health check passed: PSTOKEN_GET plus all {len(probes)} ps-metadata operations.")


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
    print(f"{marker} {name}: {url} (user={username})")


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
    }
    previous = environments.get(name)
    node = getattr(args, "node", None)
    if node:
        entry["node"] = node.strip()
    elif isinstance(previous, dict) and previous.get("node"):
        entry["node"] = previous["node"]
    if isinstance(previous, dict) and previous.get("active_project"):
        # 覆盖已有环境时保留上次使用的 Project。
        entry["active_project"] = previous["active_project"]
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
    if args.op == "delete-code":
        parts = (args.classpath or "").split(":")
        if not 2 <= len(parts) <= 4 or parts[0] != args.pkg or any(not p for p in parts):
            raise PSAPIError("delete-code requires a complete class path under the given package root.")
        return _delete_verified_peoplecode("AI_OPER_APP_PKG_POST.v1/", dict(payload, classPath=args.classpath), args)
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
        code = data.get("peoplecode", "")
        print(code)
        path = _cache_artifact(f"{args.pkg}_{args.classpath}", ".pcode", code)
        print(f"Cached: {path}")
    elif args.op == "modify-code":
        if not args.file:
            print("ERROR: modify-code requires <file>", file=sys.stderr)
            sys.exit(1)
        code = Path(args.file).read_text(encoding="utf-8") if Path(args.file).exists() else args.file
        payload["operationType"] = "modifyPeopleCode"
        payload["classPath"] = args.classpath
        payload["peoplecode"] = json_escape(code)
        _write_verified_peoplecode("AI_OPER_APP_PKG_POST.v1/", payload, code)
        print("OK — code saved; readback verified.")
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
            sql_text = stmt.get("sqlText", "")
            print(sql_text)
            path = _cache_artifact(
                f"{args.sqlid}_{stmt.get('market')}_{stmt.get('dbType')}_{stmt.get('effdt')}",
                ".sql",
                sql_text,
            )
            print(f"Cached: {path}")
            if stmt.get("descr"):
                print(f"descr: {stmt.get('descr')}")
            if stmt.get("comment"):
                print(f"comment: {stmt.get('comment')}")
    elif args.op == "create":
        if not args.file:
            print("ERROR: create requires <file> or inline JSON", file=sys.stderr)
            sys.exit(1)
        stmt_data = _load_json_arg(args.file, "create 的 JSON")
        for s in stmt_data.get("statements", []):
            if "dbType" in s:
                s["dbType"] = _normalize_dbtype(s["dbType"])
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
        if args.sqltext_file:
            actual = _api_call("AI_OPER_SQL_DEFN.v1/", {"sqlId": args.sqlid, "operationType": "view"})
            expected_db = 32 if args.dbtype == "" else 48 + int(args.dbtype)
            matching = [s for s in actual.get("statements", [])
                        if s.get("market") == args.market and int(s.get("dbType", -1)) == expected_db
                        and str(s.get("effdt", ""))[:10] == args.effdt]
            expected_text = Path(args.sqltext_file).read_text(encoding="utf-8")
            if len(matching) != 1 or re.sub(r"\s+", " ", matching[0].get("sqlText", "")).strip() != re.sub(r"\s+", " ", expected_text).strip():
                raise PSAPIError("SQL write was acknowledged but the target Statement readback differs.")
        print(f"OK — SQL modified: {args.sqlid}")

# ── ae ────────────────────────────────────────────────
def cmd_ae(args):
    if args.op == "delete-code":
        if not args.sectionid or not args.stepid:
            raise PSAPIError("AE delete-code requires --sectionid and --stepid.")
        return _delete_verified_peoplecode("AI_OPER_APP_ENGINE.v1/", dict(aeId=args.aeid,
            sectionId=args.sectionid, market=args.market, dbType=args.dbtype,
            effdt=args.effdt, stepId=args.stepid), args)
    if args.op == "struct":
        data = _api_call("AI_OPER_APP_ENGINE.v1/", {
            "aeId": args.aeid, "operationType": "struct"
        })
        print(f"AE: {args.aeid}")
        print(f"descr: {data.get('descr', '')}")
        print(f"lastUpdate: {data.get('lastUpdate', '')}")
        ms = data.get("program", {})
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
        sql_text = data.get("sqlText", "")
        print(f"\n{sql_text}")
        path = _cache_artifact(
            f"{args.aeid}_{args.sectionid}_{args.stepid}_{args.actiontype}",
            ".sql",
            sql_text,
        )
        print(f"Cached: {path}")
    elif args.op == "modify-sql":
        if not args.file:
            print("ERROR: modify-sql requires <file>", file=sys.stderr)
            sys.exit(1)
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
        code = data.get("peoplecode", "")
        print(code)
        path = _cache_artifact(
            f"{args.aeid}_{args.sectionid}_{args.stepid}",
            ".pcode",
            code,
        )
        print(f"Cached: {path}")
    elif args.op == "modify-code":
        if not args.file:
            print("ERROR: modify-code requires <file>", file=sys.stderr)
            sys.exit(1)
        code = Path(args.file).read_text(encoding="utf-8") if Path(args.file).exists() else args.file
        _write_verified_peoplecode("AI_OPER_APP_ENGINE.v1/", {
            "aeId": args.aeid, "operationType": "modifyPeopleCode",
            "sectionId": args.sectionid, "market": args.market,
            "dbType": args.dbtype, "effdt": args.effdt,
            "stepId": args.stepid,
            "peopleCode": json_escape(code)
        }, code)
        print("OK — PeopleCode modified; readback verified.")
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
    if args.op == "delete-code":
        if not args.event or (args.field and not args.record):
            raise PSAPIError("Component delete-code requires --event; --field also requires --record.")
        payload = dict(pnlGrpName=args.pnlgrpname, market=args.market or "GBL", event=args.event)
        if args.record:
            payload["recordName"] = args.record
        if args.field:
            payload["fieldName"] = args.field
        return _delete_verified_peoplecode("AI_OPER_COMPONENT_DEFN.v1/", payload, args)
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
        payload = {"pnlGrpName": args.pnlgrpname, "market": args.market or "GBL", "operationType": "viewPeopleCode", "event": args.event}
        if args.record:
            payload["recordName"] = args.record
        if args.field:
            payload["fieldName"] = args.field
        data = _api_call("AI_OPER_COMPONENT_DEFN.v1/", payload)
        code = data.get("peoplecode")
        print(code if code else "(no peoplecode)")
        path = _cache_artifact(
            f"{args.pnlgrpname}_{args.record}_{args.field}_{args.event}",
            ".pcode",
            code or "",
        )
        print(f"Cached: {path}")
    elif args.op == "modify-code":
        if not args.file:
            print("ERROR: modify-code requires <file>")
            sys.exit(1)
        if not args.event:
            print("ERROR: modify-code requires --event", file=sys.stderr)
            sys.exit(1)
        code_path = Path(args.file)
        code = code_path.read_text(encoding="utf-8") if code_path.exists() else args.file
        payload = {"pnlGrpName": args.pnlgrpname, "market": args.market or "GBL", "operationType": "modifyPeopleCode", "event": args.event, "peoplecode": json_escape(code)}
        if args.record:
            payload["recordName"] = args.record
        if args.field:
            payload["fieldName"] = args.field
        _write_verified_peoplecode("AI_OPER_COMPONENT_DEFN.v1/", payload, code)
        print("OK — Component PeopleCode saved; readback verified.")

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
    if args.op == "delete-code":
        if not args.fieldname or not args.event:
            raise PSAPIError("Record delete-code requires --fieldname and --event.")
        return _delete_verified_peoplecode("AI_OPER_RECORD_DEFN.v1/", dict(recordName=args.recname,
            fieldName=args.fieldname,event=args.event), args)
    if args.op == "struct":
        data = _api_call("AI_OPER_RECORD_DEFN.v1/", {
            "recordName": args.recname, "operationType": "struct"
        })
        _print_record_struct(data)
    elif args.op == "create":
        if not args.file:
            print("ERROR: create requires <file> or inline JSON", file=sys.stderr)
            sys.exit(1)
        rec_data = _load_json_arg(args.file, "create 的 JSON")
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
        rec_data = _load_json_arg(args.file, "modify 的 JSON")
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
            sql_text = stmt.get("sqlText", "")
            print(sql_text)
            path = _cache_artifact(
                f"{args.recname}_{stmt.get('market')}_{stmt.get('dbType')}_{stmt.get('effdt')}",
                ".sql",
                sql_text,
            )
            print(f"Cached: {path}")
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
        print(code if code else "(no peoplecode)")
        path = _cache_artifact(
            f"{args.recname}_{args.fieldname}_{args.event}",
            ".pcode",
            code or "",
        )
        print(f"Cached: {path}")
    elif args.op == "modify-code":
        if not args.file:
            print("ERROR: modify-code requires <file>")
            sys.exit(1)
        if not args.fieldname or not args.event:
            print("ERROR: modify-code requires --fieldname and --event", file=sys.stderr)
            sys.exit(1)
        code_path = Path(args.file)
        code = code_path.read_text(encoding="utf-8") if code_path.exists() else args.file
        _write_verified_peoplecode("AI_OPER_RECORD_DEFN.v1/", {
            "recordName": args.recname, "operationType": "modifyPeopleCode",
            "fieldName": args.fieldname, "event": args.event,
            "peoplecode": json_escape(code)
        }, code)
        print("OK — Record PeopleCode modified; readback verified.")

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
QUERY_OPERATORS = frozenset(("=", "!=", "<>", ">", ">=", "<", "<=", "LIKE", "NOT LIKE"))
QUERY_MAX_ROWS = 1000
QUERY_MAX_FIELDS = 64
QUERY_MAX_FILTERS = 50


def _validate_query_request(payload):
    """Reject malformed query inputs before authentication or HTTP.

    This is a CLI guard, not a substitute for server-side metadata validation
    and bind parameters. Values remain strings for the deployed 8.60 handler.
    """
    def fail(detail):
        raise PSAPIError(f"query-record 参数错误：{detail}")

    def identifier(value, label):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,127}", value):
            fail(f"{label} 必须是单一名称，只能包含 ASCII 字母、数字和下划线，并以字母开头。")
        return value.upper()

    result = {"record": identifier(payload.get("record"), "record")}
    fields = payload.get("fields")
    if not isinstance(fields, list) or not 1 <= len(fields) <= QUERY_MAX_FIELDS:
        fail(f"fields 必须包含 1～{QUERY_MAX_FIELDS} 个字段。")
    result["fields"] = [identifier(value, f"fields[{index}]") for index, value in enumerate(fields, 1)]
    if len(set(result["fields"])) != len(result["fields"]):
        fail("fields 不能包含重复字段。")

    filters = payload.get("filter", [])
    if not isinstance(filters, list) or len(filters) > QUERY_MAX_FILTERS:
        fail(f"filter 必须是数组，最多 {QUERY_MAX_FILTERS} 项。")
    result["filter"] = []
    for index, item in enumerate(filters, 1):
        label = f"filter[{index}]"
        if not isinstance(item, dict) or set(item) != {"field", "op", "value"}:
            fail(f"{label} 必须是仅含 field、op、value 的对象。")
        field = identifier(item["field"], label + ".field")
        operator = item["op"]
        if not isinstance(operator, str) or operator.upper() not in QUERY_OPERATORS:
            fail(f"{label}.op 仅支持 =、!=、<>、>、>=、<、<=、LIKE、NOT LIKE。")
        value = item["value"]
        if not isinstance(value, str):
            fail(f'{label}.value 必须是字符串；数字也须写成 "104"，不能写成 104。')
        if len(value) > 4000 or "\x00" in value:
            fail(f"{label}.value 最多 4000 个字符，不能包含 NUL。")
        result["filter"].append({"field": field, "op": operator.upper(), "value": value})

    max_rows = payload.get("maxRows", 200)
    if type(max_rows) is not int:
        fail("maxRows 必须是整数。")
    # Preserve the deployed handler's documented <=0 default behavior.
    if max_rows <= 0:
        max_rows = 200
    if max_rows > QUERY_MAX_ROWS:
        fail(f"maxRows 不能超过 {QUERY_MAX_ROWS}。")
    result["maxRows"] = max_rows
    return result


def cmd_query_record(args):
    """业务数据查询：AI_QUERY_RECORD_POST（RecordQuery 子包）"""
    payload = {"record": args.record, "fields": [f.strip() for f in args.fields.split(",")]}
    if args.filter:
        filt = _load_json_arg(args.filter, "--filter")
        payload["filter"] = filt
    if args.max_rows is not None:
        payload["maxRows"] = args.max_rows
    data = _api_call("AI_QUERY_RECORD.v1/", _validate_query_request(payload))
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
PROJECT_ACTION_NAMES = {0: "Copy", 1: "Delete", 2: "None", 3: "CopyProp"}
PROJECT_FLAG_FIELDS = ("upgradeAction", "takeAction", "copyDone")


def _parse_project_action(value):
    actions = {"copy": 0, "delete": 1, "copyprop": 3}
    try:
        return actions[value.lower()]
    except KeyError:
        raise argparse.ArgumentTypeError("Action must be Copy, Delete or CopyProp.") from None


def _parse_project_check(value):
    states = {"on": 1, "off": 0, "checked": 1, "unchecked": 0,
              "true": 1, "false": 0, "1": 1, "0": 0}
    try:
        return states[value.lower()]
    except KeyError:
        raise argparse.ArgumentTypeError("Use on/off, checked/unchecked, true/false or 1/0.") from None


def _validate_project_action(object_type, action):
    if action == 3 and object_type not in (0, 2):
        raise PSAPIError("CopyProp (upgradeAction=3) is only supported for Record (objectType=0) and Field (objectType=2).")


def _project_item_key(item):
    """Keep all native IDs; normalize only PeopleTools trailing blank padding."""
    return (item.get("objectType"),) + tuple(
        (item.get(f"objectId{i}"), (item.get(f"objectValue{i}") or "").rstrip())
        for i in range(1, 5))


def _project_item_flags(item):
    if any(name not in item for name in PROJECT_FLAG_FIELDS):
        raise PSAPIError("Project flag readback is incomplete; deploy the ps-cli 2.3.0 server Project first.")
    return {name: item[name] for name in PROJECT_FLAG_FIELDS}


def _format_project_flags(item):
    action = item.get("upgradeAction")
    def check(name):
        value = item.get(name)
        return {0: "unchecked", 1: "checked"}.get(value, "unknown") + f" ({value})"
    return (f"Action={PROJECT_ACTION_NAMES.get(action, 'unknown')} ({action}) "
            f"Upgrade={check('takeAction')} Done={check('copyDone')}")


def _update_project_item(args, payload):
    changes = {name: getattr(args, attr, None) for name, attr in (
        ("upgradeAction", "upgrade_action"), ("takeAction", "take_action"), ("copyDone", "copy_done"))}
    changes = {name: value for name, value in changes.items() if value is not None}
    if not changes:
        raise PSAPIError("update-item requires --action, --upgrade or --done (numeric aliases are also supported).")
    for name, value in changes.items():
        allowed = (0, 1, 2, 3) if name == "upgradeAction" else (0, 1)
        if value not in allowed:
            raise PSAPIError(f"Invalid {name}: {value}; expected {allowed}.")
    if args.object_type is None or not args.value1:
        raise PSAPIError("update-item requires --object-type and --value1; supply every nonblank --value2..--value4.")
    _validate_project_action(args.object_type, changes.get("upgradeAction"))
    ids = [getattr(args, f"id{i}", None) for i in range(1, 5)]
    if any(value is not None for value in ids) and any(value is None for value in ids):
        raise PSAPIError("Provide all four --id1..--id4 or omit all four to resolve them from project struct.")
    values = [(getattr(args, f"value{i}", None) or "").rstrip() for i in range(1, 5)]
    query = dict(payload, operationType="struct")
    before = _api_call("AI_OPER_PROJECT_DEFN.v1/", query)
    matches = [item for item in before.get("items", [])
               if item.get("objectType") == args.object_type
               and [(item.get(f"objectValue{i}") or "").rstrip() for i in range(1, 5)] == values
               and (ids[0] is None or [item.get(f"objectId{i}") for i in range(1, 5)] == ids)]
    if len(matches) != 1:
        raise PSAPIError(f"Expected one exact Project item, found {len(matches)}; check project struct and all key values/IDs.")
    target = matches[0]
    expected = dict(_project_item_flags(target), **changes)
    payload.update(operationType="updateItem", objectType=args.object_type, **changes)
    for i in range(1, 5):
        payload[f"objectId{i}"] = target[f"objectId{i}"]
        payload[f"objectValue{i}"] = target[f"objectValue{i}"]
    result = _api_call("AI_OPER_PROJECT_DEFN.v1/", payload)
    if result.get("updated") is not True:
        raise PSAPIError("Server did not confirm the Project item update.")
    after = _api_call("AI_OPER_PROJECT_DEFN.v1/", query)
    matches = [item for item in after.get("items", []) if _project_item_key(item) == _project_item_key(target)]
    if len(matches) != 1 or _project_item_flags(matches[0]) != expected:
        raise PSAPIError("Project flag readback does not match the requested state; inspect project struct before retrying.")
    print(f"OK — project item updated and verified: {args.projectname}")
    print(f"  objectType={target['objectType']} " + " ".join(f"value{i}={values[i-1]!r}" for i in range(1, 5)))
    print(f"  {_format_project_flags(matches[0])}")


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
        if getattr(args, "copy_done", None) is not None:
            raise PSAPIError("Set Done with project update-item after inserting the item.")
        payload["operationType"] = "insertItem"
        if args.object_type is None:
            print("ERROR: insert-item requires --object-type", file=sys.stderr)
            sys.exit(1)
        _validate_project_action(args.object_type, args.upgrade_action)
        payload["objectType"] = args.object_type
        if args.value1:
            payload["objectValue1"] = args.value1
        if args.value2 is not None:
            payload["objectValue2"] = args.value2
        elif args.object_type == 30:
            payload["objectValue2"] = "0"
        if args.value3:
            payload["objectValue3"] = args.value3
        if args.value4:
            payload["objectValue4"] = args.value4
        if args.upgrade_action is not None:
            payload["upgradeAction"] = args.upgrade_action
        # 默认勾上 Upgrade（takeAction=1），保证迁移时该定义会被带到目标库；
        # 服务器端未传时默认 0（不勾选），因此这里必须显式传 1。显式 --take-action 0 可关闭。
        payload["takeAction"] = args.take_action if args.take_action is not None else 1
        result = _api_call("AI_OPER_PROJECT_DEFN.v1/", payload)
        _set_active_project(args.projectname)
        if result.get("inserted") is False:
            print(f"OK — item already exists in project: {args.projectname}; existing flags preserved. Use update-item to change flags.")
        else:
            print(f"OK — item inserted into project: {args.projectname} (takeAction={payload['takeAction']})")
        print(f"Current project for environment {ENVIRONMENT}: {args.projectname}")
    elif args.op == "update-item":
        _update_project_item(args, payload)
    elif args.op == "delete-item":
        if args.object_type is None or any(getattr(args, f"id{i}") is None for i in range(1, 5)):
            raise PSAPIError(f"{args.op} requires --object-type and all four --id1..--id4 from project struct.")
        payload.update(operationType="deleteItem", objectType=args.object_type)
        for i in range(1, 5):
            payload[f"objectId{i}"] = getattr(args, f"id{i}")
            payload[f"objectValue{i}"] = getattr(args, f"value{i}") or ""
        _api_call("AI_OPER_PROJECT_DEFN.v1/", payload)
        print(f"OK — project item removed: {args.projectname}")
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
        if getattr(args, "json", False):
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return
        print(f"Project: {data.get('projectName')}")
        items = data.get("items", [])
        if not items:
            print("(no items)")
            return
        print(f"Items ({len(items)}):")
        for it in items:
            keys = "  ".join(f"id{i}={it.get(f'objectId{i}')} value{i}={it.get(f'objectValue{i}')}" for i in range(1, 5))
            print(f"  objectType={it.get('objectType')}  {keys}  {_format_project_flags(it)}")

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
    if args.op == "delete-code":
        return _delete_verified_peoplecode("AI_OPER_PAGE_DEFN.v1/", {"pageName": args.pagename}, args)
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
        path = _cache_artifact(f"{args.pagename}_Activate", ".pcode", code or "")
        print(f"Cached: {path}")
    elif args.op == "modify-code":
        if not args.file:
            print("ERROR: modify-code requires --file", file=sys.stderr)
            sys.exit(1)
        code_path = Path(args.file)
        code = code_path.read_text(encoding="utf-8") if code_path.exists() else args.file
        payload = {"pageName": args.pagename, "operationType": "modifyPeopleCode", "peoplecode": json_escape(code)}
        _write_verified_peoplecode("AI_OPER_PAGE_DEFN.v1/", payload, code)
        print(f"OK — page PeopleCode updated; readback verified: {args.pagename}")
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
    parser = argparse.ArgumentParser(description="PeopleSoft IB REST 命令行工具")
    sub = parser.add_subparsers(dest="cmd", required=True)
    from object_operations import add_parsers
    add_parsers(sub)

    # auth
    p = sub.add_parser("auth", help="获取或刷新 PS_TOKEN")
    p.add_argument("--refresh", action="store_true", help="忽略缓存，调用 PSTOKEN.v1")

    # preflight
    p = sub.add_parser("preflight", help="体检：报告当前环境距离可用还差什么，并给出下一步（只读）")
    p.add_argument("--refresh", action="store_true", help="探测前刷新 PS_TOKEN")

    # healthcheck
    p = sub.add_parser("healthcheck", help="只读验证认证与全部元数据操作")
    p.add_argument("--refresh", action="store_true", help="探测前刷新 PS_TOKEN")
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

    # environment
    p = sub.add_parser("env", help="列出、切换或初始化 PeopleSoft 环境")
    p.add_argument("op", choices=["list", "current", "use", "init"])
    p.add_argument("name", nargs="?", help="use 或 init 的环境名")
    p.add_argument("--auth", action="store_true", help="切换或初始化后刷新 PS_TOKEN")
    p.add_argument("--url", dest="pia_url", help="env init 的 PIA 地址")
    p.add_argument("--username", help="env init 的 PeopleSoft 用户名")
    p.add_argument("--node", help="目标环境的本地 IB 节点，默认 PSFT_HR")
    p.add_argument("--password-stdin", action="store_true", help="从标准输入读取初始化密码")
    p.add_argument("--force", action="store_true", help="env init 时替换已有环境配置")
    p.add_argument("--keep-current", action="store_true", help="env init 时保留当前活动环境")

    # search
    p = sub.add_parser("search", help="搜索定义")
    p.add_argument("type", choices=["record", "field", "sql", "apppkg", "project"])
    p.add_argument("name", nargs="?", default="")
    p.add_argument("--desc", default="")

    # app-pkg
    p = sub.add_parser("app-pkg", help="维护应用包")
    p.add_argument("op", choices=["struct", "view-code", "modify-code", "delete-code", "insert-class", "insert-package"])
    p.add_argument("pkg")
    p.add_argument("classpath", nargs="?")
    p.add_argument("file", nargs="?")

    p.add_argument("--project", help="delete-code 迁移登记工程，默认当前工程")
    p.add_argument("--dry-run", action="store_true", help="验证完整程序键和快照，不删除或登记")
    p.add_argument("--output", help="保存 delete-code 验证结果 JSON")

    # sql
    p = sub.add_parser("sql", help="维护 SQL 定义")
    p.add_argument("op", choices=["view", "create", "modify"])
    p.add_argument("sqlid")
    p.add_argument("--market", default="GBL")
    p.add_argument("--dbtype", default="")
    p.add_argument("--effdt", default="1900-01-01")
    p.add_argument("--sqltext-file")
    p.add_argument("--comment-file")
    p.add_argument("file", nargs="?")

    # ae
    p = sub.add_parser("ae", help="维护 AE 定义")
    p.add_argument("op", choices=[
        "struct", "create", "insert-section", "insert-step", "insert-action",
        "view-sql", "modify-sql", "view-code", "modify-code", "delete-code",
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

    p.add_argument("--project", help="delete-code 迁移登记工程，默认当前工程")
    p.add_argument("--dry-run", action="store_true", help="验证完整程序键和快照，不删除或登记")
    p.add_argument("--output", help="保存 delete-code 验证结果 JSON")

    # component
    p = sub.add_parser("component", help="维护 Component 定义")
    p.add_argument("op", choices=["struct", "structDeep", "view-code", "modify-code", "delete-code"])
    p.add_argument("pnlgrpname")
    p.add_argument("--market", default="")
    p.add_argument("--deep", action="store_true", help="显示 Page → 层级 → Record → Field 结构")
    p.add_argument("--record")
    p.add_argument("--field")
    p.add_argument("--event")
    p.add_argument("--file")

    p.add_argument("--project", help="delete-code 迁移登记工程，默认当前工程")
    p.add_argument("--dry-run", action="store_true", help="验证完整程序键和快照，不删除或登记")
    p.add_argument("--output", help="保存 delete-code 验证结果 JSON")

    # record
    p = sub.add_parser("record", help="维护 Record 定义")
    p.add_argument("op", choices=["struct", "create", "modify", "build", "alter", "create-view", "view-sql", "modify-sql", "view-code", "modify-code", "delete-code"])
    p.add_argument("recname")
    p.add_argument("file", nargs="?")
    p.add_argument("--fieldname")
    p.add_argument("--event")

    p.add_argument("--project", help="delete-code 迁移登记工程，默认当前工程")
    p.add_argument("--dry-run", action="store_true", help="验证完整程序键和快照，不删除或登记")
    p.add_argument("--output", help="保存 delete-code 验证结果 JSON")

    # query-record
    p = sub.add_parser("query-record", help="查询业务数据（AI_QUERY_RECORD_POST）")
    p.add_argument("record", help="Record 名称")
    p.add_argument("fields", help="逗号分隔的字段名，例如 EMPLID,EMPL_RCD")
    p.add_argument("--filter", help="Filter JSON: [{\"field\":\"EMPLID\",\"op\":\"=\",\"value\":\"0001\"}] or path to JSON file")
    p.add_argument("--max-rows", type=int, help="最多返回行数，默认 200，上限 1000；<=0 使用默认值")

    # project
    p = sub.add_parser("project", help="维护 Project 定义（AI_OPER_PROJECT_DEFN_POST）")
    p.add_argument("op", choices=["create", "insert-item", "update-item", "delete-item", "modify", "struct", "use", "current"])
    p.add_argument("projectname", nargs="?", help="Project 名称；current 时省略")
    p.add_argument("--descr")
    p.add_argument("--comment")
    p.add_argument("--object-type", type=int)
    p.add_argument("--value1")
    p.add_argument("--value2")
    p.add_argument("--value3")
    p.add_argument("--value4")
    for i in range(1, 5):
        p.add_argument(f"--id{i}", type=int, help="从 Project 结构取得的完整 ObjectID，仅用于更新/删除")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--action", dest="upgrade_action", type=_parse_project_action,
                       metavar="Copy|Delete|CopyProp", help="Project 条目 Action，不区分大小写；CopyProp 仅适用 Record/Field")
    group.add_argument("--upgrade-action", type=int, choices=[0, 1, 2, 3],
                       help="Action 数字编码：0=Copy，1=Delete，2=None（历史兼容），3=CopyProp")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--upgrade", dest="take_action", type=_parse_project_check,
                       metavar="on|off", help="Upgrade 标记；插入默认 on，更新省略则保留")
    group.add_argument("--take-action", type=int, choices=[0, 1], help="Upgrade 数字编码：0/1")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--done", dest="copy_done", type=_parse_project_check,
                       metavar="on|off", help="Done 标记，仅 update-item；省略则保留")
    group.add_argument("--copy-done", type=int, choices=[0, 1], help="Done 数字编码：0/1，仅 update-item")
    p.add_argument("--json", action="store_true", help="以 JSON 输出 Project 结构")

    # page
    p = sub.add_parser("page", help="维护 Page 定义（AI_OPER_PAGE_DEFN_POST）")
    p.add_argument("op", choices=["struct", "view-code", "modify-code", "delete-code", "create", "modify-props", "add-control", "del-control", "find", "mod-control"])
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
    p.add_argument("--field-type", type=int, help="findControls 的数值 FIELDTYPE 过滤，例如 4=editBox、27=scrollArea")
    p.add_argument("--edit-size", type=int)
    p.add_argument("--label-type", type=int)
    p.add_argument("--label-loc", type=int)
    p.add_argument("--field-style")
    p.add_argument("--label-style")
    p.add_argument("--full", action="store_true", help="包含可用的 PSPNLDEFN/PSPNLFIELD 原始列")
    p.add_argument("--json", action="store_true", help="输出原始 JSON 响应")
    p.add_argument("--file")

    p.add_argument("--project", help="delete-code 迁移登记工程，默认当前工程")
    p.add_argument("--dry-run", action="store_true", help="验证完整程序键和快照，不删除或登记")
    p.add_argument("--output", help="保存 delete-code 验证结果 JSON")

    # get-field
    p = sub.add_parser("get-field", help="批量查询 Field 定义（AI_OPER_FIELD_DEFN_POST）")
    p.add_argument("fields", help="逗号分隔的字段名，例如 EMPLID,EFFDT")

    # 所有子命令统一的请求超时选项
    for child in sub.choices.values():
        child.add_argument(
            "--timeout", type=int, metavar="SECONDS",
            help="单个 API 请求的超时秒数（默认不限；网关无响应时使用）",
        )

    args = parser.parse_args()

    global REQUEST_TIMEOUT
    REQUEST_TIMEOUT = args.timeout

    # `env init` is the one command allowed to run without an existing config.
    if not (args.cmd == "env" and args.op == "init"):
        _require_runtime()

    # 路由
    try:
        _dispatch(args)
    except (PSAuthError, PSAPIError) as exc:
        # detail 原样透出：SKILL.md 的环境检查故障分流表要求 Agent 按响应体文本分流
        detail = exc.detail if len(exc.detail) <= 2000 else exc.detail[:2000] + "…(truncated)"
        print(f"ERROR: {detail}", file=sys.stderr)
        if exc.hint:
            print(exc.hint, file=sys.stderr)
        sys.exit(1)


def _dispatch(args):
    if args.cmd in ("service", "service-op", "menu", "message-catalog", "portal"):
        from object_operations import execute
        return execute(sys.modules[__name__], args)
    if hasattr(args, "dbtype"):
        args.dbtype = _normalize_dbtype(args.dbtype)
    if args.cmd == "auth":
        cmd_auth(args)
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
