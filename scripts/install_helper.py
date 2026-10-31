#!/usr/bin/env python3
"""Agent-side installation preparation; no server writes or credential output.

prepare gives the user a private, editable login file. check validates it locally.
apply validates and merges all supplied CLI profiles in one write, defaulting nodes to PSFT_HR.
discover finds local AD candidates, never claiming their versions are the server's.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

SKILL_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("PEOPLESOFT_DATA_DIR", str(Path.home() / ".peoplesoft")))
CONFIG_PATH = Path(os.environ.get("PEOPLESOFT_CONFIG", str(DATA_DIR / "config.json")))
INSTALL_TEMPLATE = SKILL_ROOT / "install.example.json"
INSTALL_INPUT = SKILL_ROOT / "install.local.json"
DEFAULT_NODE = "PSFT_HR"
AUTHORIZATION_REMINDER = "配置填写和生成不会给用户名授权。请用户或管理员自行分配 C_PSCLI_READ（只读）或 C_PSCLI_WRITE（读写）角色，完成后再验证。"
LOGIN_FIELDS = {"pia_base_url": "登录地址", "username": "用户名", "password": "密码"}


def is_blank(value):
    return value is None or isinstance(value, str) and not value.strip()


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def read_object(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("配置存在重复字段或环境名，请删除重复项；未修改正式配置。")
            result[key] = value
        return result
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique_object)
    except json.JSONDecodeError as exc:
        # JSON error messages/source lines can contain a password. Return location only.
        raise ValueError(f"配置格式有误：第 {exc.lineno} 行，第 {exc.colno} 列；请检查引号和逗号。") from None
    except OSError:
        raise ValueError("无法读取配置文件；请检查文件是否存在和当前用户权限。") from None
    if not isinstance(doc, dict):
        raise ValueError("配置文件最外层必须是 JSON 对象。")
    return doc


def normalize_url(value):
    if not isinstance(value, str):
        raise ValueError("pia_base_url 必须是网址。")
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError:
        raise ValueError("PIA 地址格式无效。") from None
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username is not None or parsed.password is not None):
        raise ValueError("PIA 地址需要 http/https，且不能在地址中包含用户名或密码。")
    # A pasted login page is accepted; runtime needs only its origin.
    host = parsed.hostname
    if ":" in host:
        host = f"[{host}]"
    return f"{parsed.scheme}://{host}" + (f":{port}" if port is not None else "")


def environment_name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value):
        raise ValueError("环境名需为 1–64 位字母、数字、点、横线或下划线，以字母或数字开头。")
    return value


def runtime_environments(doc):
    if "environments" in doc:
        environments = doc["environments"]
        if not isinstance(environments, dict) or any(not isinstance(v, dict) for v in environments.values()):
            raise ValueError("现有环境配置结构无效，未修改原文件。")
        active = doc.get("active_environment")
        if environments and active is None:
            active = next(iter(environments))
        if active is not None and active not in environments:
            raise ValueError("现有 active_environment 无效，未修改原文件。")
        return dict(environments), active
    if "peoplesoft" in doc:
        if not isinstance(doc["peoplesoft"], dict):
            raise ValueError("现有单环境配置结构无效，未修改原文件。")
        name = doc.get("active_environment") or "default"
        return {name: doc["peoplesoft"]}, name
    if doc:
        raise ValueError("现有配置缺少 environments 或 peoplesoft，未修改原文件。")
    return {}, None


def secure_file(path):
    """Restrict this file to the current OS user. Refuse if restriction fails."""
    if os.name != "nt":
        path.chmod(0o600)
        return
    flags = subprocess.CREATE_NO_WINDOW
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
         "[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value"],
        capture_output=True, text=True, timeout=15, creationflags=flags)
    sid = result.stdout.strip()
    if result.returncode or not re.fullmatch(r"S-1-[0-9-]+", sid):
        raise ValueError("无法确定当前 Windows 用户，未创建含密码的配置文件。")
    result = subprocess.run(["icacls.exe", str(path), "/inheritance:r", "/grant:r", f"*{sid}:(F)"],
                            capture_output=True, timeout=15, creationflags=flags)
    if result.returncode:
        raise ValueError("无法限制配置文件访问权限，未写入密码。")


def private_path(path, install_input=False):
    path = Path(path).expanduser().absolute()
    if path.is_symlink():
        raise ValueError("配置文件不能是符号链接。")
    path = path.resolve()
    if path == SKILL_ROOT or SKILL_ROOT in path.parents:
        if not (install_input and path == INSTALL_INPUT):
            raise ValueError("项目内只允许填写 install.local.json；请勿修改公开模板或将正式环境配置写入项目。")
    return path


def write_private(path, content, replace=False, install_input=False):
    path = private_path(path, install_input=install_input)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not replace:
        # Claim the destination without overwriting a file the user has filled in.
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    fd, temp_name = tempfile.mkstemp(prefix=".ps-install-", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        os.close(fd)
        secure_file(temp_path)  # Set ACL before writing any credentials.
        temp_path.write_text(content, encoding="utf-8")
        os.replace(temp_path, path)
    except Exception:
        if not replace:
            path.unlink(missing_ok=True)  # Only the empty file claimed by this call.
        raise
    finally:
        temp_path.unlink(missing_ok=True)


def prepare(args):
    name = environment_name(args.environment) if args.environment else ""
    url = normalize_url(args.url) if args.url else ""
    path = private_path(args.file or INSTALL_INPUT, install_input=True)
    if path.exists():
        emit({"status": "existing", "file": str(path), "server_changed": False,
              "next": "继续使用已有填写文件，内容未覆盖；保存后由 Agent 执行 check。"})
        return
    template = read_object(INSTALL_TEMPLATE)
    if name:
        # Optional prefill remains useful when the user has already named one target.
        entry = dict(next(iter(template["environments"].values())))
        template["environments"] = {name: entry}
    else:
        entry = next(iter(template["environments"].values()))
    entry["pia_base_url"] = url
    if name and url and CONFIG_PATH.exists():
        environments, _ = runtime_environments(read_object(CONFIG_PATH))
        old = environments.get(name, {})
        if old and normalize_url(old.get("pia_base_url", "")) != url:
            raise ValueError("已有同名环境指向其他地址，未复制凭据或覆盖配置；需先核对目标。")
        for field in ("username", "password"):
            if isinstance(old.get(field), str):
                entry[field] = old[field]
    write_private(path, json.dumps(template, ensure_ascii=False, indent=2) + "\n", install_input=True)
    emit({"file": str(path), "environments": [
              {"name": key, "username_present": bool(value["username"]), "password_present": bool(value["password"])}
              for key, value in template["environments"].items()], "server_changed": False,
          "next": "把填写文件的链接交给用户，只填需要的环境，不用的全部留空即可；节点默认使用 PSFT_HR。"})


def validate_login(doc):
    missing = [key for key in ("environment", "pia_base_url", "username", "password")
               if not isinstance(doc.get(key), str) or is_blank(doc[key])]
    if missing:
        fields = [f"{LOGIN_FIELDS.get(key, '环境名')}（{key}）" for key in missing]
        raise ValueError("请在填写文件中补全：" + "、".join(fields) + "。")
    name = environment_name(doc.get("environment"))
    url = normalize_url(doc.get("pia_base_url"))
    if doc["username"] != doc["username"].strip():
        raise ValueError("username 首尾含空格，请在文件中核对；未自动修改。")
    if any(ch in doc["username"] + doc["password"] for ch in ("\r", "\n", "\x00")):
        raise ValueError("用户名和密码不能含换行或 NUL。")
    return name, url


def validate_install(doc):
    """Validate every input profile before any runtime write; retain legacy input support."""
    if "environments" not in doc:
        name, url = validate_login(doc)
        return {name: dict(doc, pia_base_url=url)}, ""
    if any(key in doc for key in ("environment", "pia_base_url", "username", "password")):
        raise ValueError("请勿混用单环境和多环境格式；将每个环境的信息放进 environments 中。")
    values = doc["environments"]
    if not isinstance(values, dict) or not values:
        raise ValueError("environments 至少需要一个以环境名为键的环境对象。")
    profiles, errors, skipped = {}, [], []
    for index, (name, entry) in enumerate(values.items(), 1):
        label = f"environments 第 {index} 项"
        try:
            environment_name(name)
            label = "environments." + name
            if not isinstance(entry, dict):
                raise ValueError("该环境必须是包含登录地址、用户名和密码的对象。")
            # Unused example blocks are optional; partially filled targets still fail.
            if all(is_blank(entry.get(key)) for key in LOGIN_FIELDS) and all(
                    key in LOGIN_FIELDS or key == "access_mode" or is_blank(value)
                    for key, value in entry.items()):
                skipped.append(name)
                continue
            _, url = validate_login(dict(entry, environment=name))
            profiles[name] = dict(entry, pia_base_url=url)
        except ValueError as exc:
            errors.append(label + "：" + str(exc))
    active = doc.get("active_environment", "")
    if not isinstance(active, str) or active and (active not in values or active in skipped):
        errors.append("active_environment：请留空，或填写已经填写连接信息的环境名；不能选空白示例。")
    if not profiles and not errors:
        errors.append("请至少填写一个环境的登录地址、用户名和密码；完全空白的示例环境会自动跳过。")
    if errors:
        raise ValueError("\n".join(errors))
    return profiles, active


def profile_summary(profiles):
    return [{"name": name, "pia_base_url": entry["pia_base_url"],
             "username_present": True, "password_present": True}
            for name, entry in profiles.items()]


def check(args):
    doc = read_object(private_path(args.file, install_input=True))
    profiles, active = validate_install(doc)
    summary = profile_summary(profiles)
    result = {"status": "ready", "environments": summary, "active_environment": active or None,
              "skipped_environments": [name for name in doc.get("environments", {}) if name not in profiles],
              "authorization_reminder": AUTHORIZATION_REMINDER,
              "scope": "仅完成已填写环境的本地格式检查；尚未验证各环境登录、AD 权限或服务端部署。"}
    if len(profiles) == 1:
        result.update(summary[0], environment=summary[0]["name"])
    emit(result)


def apply(args):
    source = private_path(args.file, install_input=True)
    doc = read_object(source)
    profiles, input_active = validate_install(doc)
    destination = private_path(CONFIG_PATH)
    if source == destination:
        raise ValueError("填写文件不能与运行配置是同一个文件。")
    original = read_object(destination) if destination.exists() else {}
    environments, active = runtime_environments(original)
    environments_before = dict(environments)
    changes = {}
    for name, profile in profiles.items():
        url = profile["pia_base_url"]
        previous = environments.get(name, {})
        if previous and normalize_url(previous.get("pia_base_url", "")) != url:
            raise ValueError("environments." + name + "：同名环境指向其他地址，全部未写入；需先核对或另选环境名。")
        node = args.node if args.node is not None else previous.get("node") or DEFAULT_NODE
        if not isinstance(node, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", node):
            raise ValueError("environments." + name + "：自定义节点名称格式无效；常规安装默认使用 PSFT_HR。")
        entry = dict(previous)
        entry.update(pia_base_url=url, username=profile["username"], password=profile["password"],
                     node=node, metadata_api_layout="split")
        changes[name] = entry
    environments.update(changes)
    selected = input_active or active or next(iter(profiles))
    if args.activate is not None:
        selected = (input_active or next(iter(profiles))) if args.activate is True else args.activate
        if not isinstance(selected, str) or selected not in environments:
            raise ValueError("--activate 必须指定填写文件或现有配置中的环境名；全部未写入。")
    merged = {k: v for k, v in original.items() if k not in ("peoplesoft", "environments", "active_environment")}
    merged.update(environments=environments, active_environment=selected)
    changed = merged != original
    changed_profiles = [name for name, entry in changes.items() if entry != environments_before.get(name)]
    backup = None
    if changed and destination.exists():
        backup = destination.with_name("config.backup-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
        write_private(backup, destination.read_text(encoding="utf-8-sig"))
    if changed:
        write_private(destination, json.dumps(merged, ensure_ascii=False, indent=2) + "\n", replace=destination.exists())
    # Invalidate only changed profile caches after their shared write succeeds.
    cache_dir = Path(os.environ.get("PEOPLESOFT_CACHE_DIR", str(DATA_DIR / "cache")))
    for name in changed_profiles:
        (cache_dir / f".ps_token_cache.{name}.json").unlink(missing_ok=True)
    summary = [dict(row, node=changes[row["name"]]["node"]) for row in profile_summary(profiles)]
    result = {"status": "configured", "environments": summary,
              "changed": changed, "changed_environments": changed_profiles,
              "skipped_environments": [name for name in doc.get("environments", {}) if name not in profiles],
              "authorization_reminder": AUTHORIZATION_REMINDER,
              "active_environment": selected, "backup": str(backup) if backup else None,
              "server_changed": False, "next": "Agent 按环境分别验证登录与部署；填写副本只留本机，不参与同步或打包。"}
    if len(profiles) == 1:
        result.update(summary[0], environment=summary[0]["name"])
    emit(result)


def run_check(args):
    """Run a bounded read check in one private profile without switching the real config."""
    name = environment_name(args.environment)
    environments, _ = runtime_environments(read_object(CONFIG_PATH))
    if name not in environments:
        raise ValueError("该环境尚未生成正式配置；请先完成填写检查和 apply。")
    if args.timeout <= 0 or args.request_timeout <= 0:
        raise ValueError("检查超时需要为正整数秒。")
    command = ["env", "current"] if args.probe == "current" else [args.probe, "--refresh"]
    if args.probe != "current":
        command.extend(["--timeout", str(args.request_timeout)])
    if args.probe == "healthcheck":
        for key in ("page", "component", "record", "field", "query_record", "query_field"):
            value = getattr(args, key)
            if value:
                command.extend(["--" + key.replace("_", "-"), value])
    with tempfile.TemporaryDirectory(prefix="ps-cli-install-check-") as folder:
        scoped = Path(folder) / "config.json"
        write_private(scoped, json.dumps({"active_environment": name,
                      "environments": {name: environments[name]}}, ensure_ascii=False))
        child_env = dict(os.environ, PEOPLESOFT_CONFIG=str(scoped))
        try:
            return subprocess.run([sys.executable, "-B", str(SKILL_ROOT / "scripts" / "peoplesoft_api.py"),
                                   *command], env=child_env, timeout=args.timeout).returncode
        except subprocess.TimeoutExpired:
            raise ValueError("该环境的检查已超时并停止；正式配置和当前环境未改变，修复连接后可继续检查。") from None


def discover(_args):
    ad = []
    notes = []
    if os.name == "nt":
        try:
            result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                     "-File", str(SKILL_ROOT / "scripts" / "discover_ad.ps1")],
                                    capture_output=True, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode:
                notes.append("AD 自动发现未完成，可从已打开的 AD 或用户提供的安装目录继续发现。")
            else:
                ad = json.loads(result.stdout.decode("utf-8-sig"))
        except (OSError, subprocess.TimeoutExpired, ValueError):
            notes.append("AD 自动发现未完成；未读取或输出进程命令行。")
    else:
        notes.append("本机不是 Windows；可准备安装和配置，原生导入需要 Windows AD。")
    environments = []
    if CONFIG_PATH.exists():
        existing, active = runtime_environments(read_object(CONFIG_PATH))
        for name, entry in existing.items():
            environments.append({"name": name, "active": name == active,
                                 "username_present": bool(entry.get("username")),
                                 "password_present": bool(entry.get("password")),
                                 "node": entry.get("node") or DEFAULT_NODE})
    emit({"python": sys.version.split()[0], "config_path": str(CONFIG_PATH),
          "environments": environments, "ad_candidates": ad, "notes": notes,
          "target_tools_release": None,
          "next": "客户端文件版本只作候选。Agent 核实目标版本并确认客户端；节点默认使用 PSFT_HR，无需额外发现或确认。"})


def main():
    parser = argparse.ArgumentParser(description="Agent 安装助手：发现 AD、生成填写文件、脱敏检查及合并配置。用户无需运行命令。")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("discover", help="只读发现本机 AD 与已有配置（不登录）").set_defaults(run=discover)
    p = sub.add_parser("prepare", help="从项目通用模板生成 install.local.json，不预设目标、不覆盖已有文件")
    p.add_argument("--environment", help="可选：预填用户已经确认的环境名")
    p.add_argument("--url", help="可选：预填用户已经提供的登录地址")
    p.add_argument("--file", help="可选填写副本路径；默认项目根目录 install.local.json")
    p.set_defaults(run=prepare)
    for command, runner in (("check", check), ("apply", apply)):
        p = sub.add_parser(command)
        p.add_argument("--file", default=str(INSTALL_INPUT), help="默认读取项目根目录的 install.local.json")
        p.set_defaults(run=runner)
        if command == "apply":
            p.add_argument("--node", help="高级可选覆盖；新环境默认 PSFT_HR，已有自定义节点保留，普通用户无需填写")
            p.add_argument("--activate", nargs="?", const=True, help="高级可选：指定要切换的环境；省略值时选填写文件的当前环境或首项")
    p = sub.add_parser("run", help="限定环境执行只读验收，不改变正式配置中的当前环境")
    p.add_argument("--environment", required=True)
    p.add_argument("probe", choices=["current", "auth", "preflight", "healthcheck"])
    p.add_argument("--timeout", type=int, default=180, help="整次检查的上限秒数")
    p.add_argument("--request-timeout", type=int, default=15, help="API 请求超时秒数")
    for key in ("page", "component", "record", "field", "query-record", "query-field"):
        p.add_argument("--" + key, help="healthcheck 使用的目标实际对象")
    p.set_defaults(run=run_check)
    args = parser.parse_args()
    try:
        return args.run(args) or 0
    except (OSError, ValueError, subprocess.SubprocessError):
        # Do not dump arbitrary exception text: filesystem and parser errors may contain secrets.
        exc = sys.exception() if hasattr(sys, "exception") else sys.exc_info()[1]
        message = str(exc) if isinstance(exc, ValueError) else "本地操作未完成，请核对路径、权限和文件占用；未输出配置内容。"
        emit({"status": "needs_attention", "message": message})
        return 1
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
