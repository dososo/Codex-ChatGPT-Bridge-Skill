# 安全边界

Codex ChatGPT Bridge Skill 的安全模型是：Codex 主执行，ChatGPT 不可信协作，用户最终确认。

## 默认禁止

- 读取 secrets、`.env`、私钥、cookie、`.git`。
- 发送 Bridge token、完整 Connector URL、账号信息或登录态。
- 让右侧 ChatGPT 直接改源码。
- 让右侧 ChatGPT 执行 shell。
- 自动执行 ChatGPT 的 `suggested_actions`。

## 默认保护

- 最小上下文原则。
- 敏感信息扫描和脱敏。
- 路径限制和大小限制。
- 结果导入前预检。
- 导入后仍需 Codex 审阅。
- 执行前必须用户确认。

## 报告问题

请只提交脱敏材料。不要提交：

- token、API key、OAuth refresh token。
- 完整 Connector URL。
- 私有仓库源码。
- 登录截图、cookie、账号页面。
- 本地绝对路径中包含个人身份的信息。
