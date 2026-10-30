"""按当前环境的服务布局把定义查询路由到独立只读操作。

split 模式不会在权限或部署失败时回退到旧混合端点。
"""
ROUTES = {
    "AI_OPER_APP_ENGINE.v1/": ("AI_READ_APP_ENGINE.v1/", "struct", frozenset(["struct","viewSQL","viewPeopleCode"])),
    "AI_OPER_APP_PKG_POST.v1/": ("AI_READ_APP_PKG.v1/", "default", frozenset(["default","viewPeopleCode"])),
    "AI_OPER_COMPONENT_DEFN.v1/": ("AI_READ_COMPONENT_DEFN.v1/", "struct", frozenset(["struct","structDeep","viewPeopleCode"])),
    "AI_OPER_FIELD_DEFN.v1/": ("AI_READ_FIELD_DEFN.v1/", "query", frozenset(["query","struct"])),
    "AI_OPER_PAGE_DEFN.v1/": ("AI_READ_PAGE_DEFN.v1/", "struct", frozenset(["struct","viewPeopleCode","findControls"])),
    "AI_OPER_PROJECT_DEFN.v1/": ("AI_READ_PROJECT_DEFN.v1/", "createProject", frozenset(["struct"])),
    "AI_OPER_RECORD_DEFN.v1/": ("AI_READ_RECORD_DEFN.v1/", "struct", frozenset(["struct","default","viewPeopleCode","viewSQL"])),
    "AI_OPER_SQL_DEFN.v1/": ("AI_READ_SQL_DEFN.v1/", "view", frozenset(["view"])),
    "AI_OPER_SERVICE_DEFN.v1/": ("AI_READ_SERVICE_DEFN.v1/", "", frozenset(["exists","view","struct","wsdl"])),
    "AI_OPER_SERVICE_OP.v1/": ("AI_READ_SERVICE_OP.v1/", "", frozenset(["exists","view","struct"])),
    "AI_OPER_MENU_DEFN.v1/": ("AI_READ_MENU_DEFN.v1/", "", frozenset(["exists","view","struct","viewCode"])),
    "AI_OPER_MESSAGE_CATALOG.v1/": ("AI_READ_MESSAGE_CATALOG.v1/", "", frozenset(["exists","view","struct"])),
    "AI_OPER_PORTAL_REGISTRY.v1/": ("AI_READ_PORTAL_REGISTRY.v1/", "", frozenset(["exists","view","struct","validate"])),
    "AI_OPER_HTML_DEFN.v1/": ("AI_READ_HTML_DEFN.v1/", "", frozenset(["exists","view","struct"])),
    "AI_OPER_STYLESHEET_DEFN.v1/": ("AI_READ_STYLESHEET_DEFN.v1/", "", frozenset(["exists","view","struct"])),
    "AI_OPER_CI_DEFN.v1/": ("AI_READ_CI_DEFN.v1/", "", frozenset(["exists","view","struct","viewCode"])),
}


def resolve(endpoint, payload, layout):
    if layout not in ("legacy", "split"):
        raise ValueError("metadata_api_layout must be legacy or split")
    if layout != "split" or endpoint not in ROUTES:
        return endpoint
    read_endpoint, default, read_actions = ROUTES[endpoint]
    if isinstance(payload, list) and endpoint == "AI_OPER_FIELD_DEFN.v1/":
        return read_endpoint
    action = payload.get("operationType", default) if isinstance(payload, dict) else default
    if action == "":
        action = default
    return read_endpoint if isinstance(action, str) and action in read_actions else endpoint
