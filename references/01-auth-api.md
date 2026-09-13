# PSTOKEN.v1 — 登录接口

通过 Basic Auth 获取 PS_TOKEN，用于后续接口鉴权。

## 接口地址

```
GET {PSFT_BASE_URL}/PSIGW/RESTListeningConnector/{node}/PSTOKEN.v1/
```

> `{node}` 是目标 PeopleSoft 的 **IB 本地节点名**，取自 `config.json` 的 `node` 字段（缺省 `PSFT_HR`）。
> 客户实施时大多改过名（`HCM_DEV` 之类），写死或填错会返回 HTTP 500 `(158,505)`「找不到与入站请求消息对应的发送处理」——
> 这个报错**不是**接口未部署，不要据此去导入 AD 工程。其余接口文档里该段含义相同。

## 请求头

| Header | 值 | 必填 |
|--------|-----|------|
| `Authorization` | `Basic {base64(username:password)}` | 是 |
| LanguageCd | 登录语言(ZHS,ENG) | 否 |

证书是 `username:password` 拼接后做 Base64 编码。

## 响应格式

统一返回三个顶层字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | int | 0=成功，非0=失败 |
| `message` | string | 成功为 `"success"`，失败返回原因 |
| `data` | object | 成功时包含 token 信息，失败时为 `{}` |

## 请求示例

```bash
# 构建 Basic Auth
credentials=$(printf '%s:%s' "$PEOPLESOFT_USER" "$PEOPLESOFT_PASSWORD" | base64)

# 调用登录接口
curl -X GET "{PSFT_BASE_URL}/PSIGW/RESTListeningConnector/{node}/PSTOKEN.v1/" \
  -H "Authorization: Basic $credentials"
```

## 响应示例

### 成功

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "psToken": "<PS_TOKEN>",
    "userid": "<PEOPLESOFT_USER>",
    "description": "<用户描述>",
    "language": "ZHS"
  }
}
```

## Token 有效期

- 默认有效期：**720 分钟（12 小时）**，在 PeopleTools → 安全性 → 安全性对象 → 单点登录中配置。
- 登录接口返回 `data.tokenExpireTime` 字段时，**以该返回值为准**。
- 如果接口未返回 `tokenExpireTime`，按 **12 小时**有效期处理。

### 失败

```json
{
  "code": -1,
  "message": "Invalid username or password",
  "data": {}
}
```
