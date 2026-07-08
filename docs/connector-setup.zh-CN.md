# ChatGPT Connector 设置

Bridge 优先使用官方 MCP Connector 工具，但不会假设你的账号一定能调用工具。

## 设置原则

- 用户必须确认连接授权。
- 不记录完整 Connector URL、token、cookie 或账号信息。
- 工具列表可见不等于工具真的可调用。
- 只有真实 tool call 和 audit 记录才能证明 Connector 能力。

## 能力判断

| 结果 | 含义 | 下一步 |
| --- | --- | --- |
| read/write 都可用 | Full Connector | ChatGPT 可读取任务并写回结构化结果 |
| 只有 read 可用 | Read-only Connector | ChatGPT 读取任务包，再输出结构化 JSON |
| 工具不可用 | 受控消息 / Packet fallback | Codex 发送确认过的上下文，ChatGPT 按固定格式回复 |

## 不能做什么

- 不要求用户反复重启或反复重建 Connector。
- 不抓取 ChatGPT DOM 当作产品协议。
- 不把本地 smoke、网页打开成功或工具列表可见当成 Full Connector verified。
