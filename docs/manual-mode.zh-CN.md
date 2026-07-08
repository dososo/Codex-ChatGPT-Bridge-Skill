# Manual / Packet fallback

当 ChatGPT 当前页面不能调用官方工具时，仍然可以使用受控消息或 Packet fallback。

## 适用场景

- ChatGPT 账号或模型没有 MCP 工具入口。
- Connector 工具列表不可用。
- 用户暂时不想创建 Connector。
- 只需要让 ChatGPT 做任务单、方案比较或审查。

## 流程

1. Codex 生成最小上下文和 ChatGPT 消息。
2. 用户确认后发送给 ChatGPT。
3. ChatGPT 输出任务单或审查意见。
4. 如果有真实 Bridge `task_id`，ChatGPT 输出 fenced `codex-bridge-result-json`。
5. Codex 预检并在用户确认后导入。
6. Codex 生成审阅清单。
7. 用户确认后，Codex 才执行建议。

## 安全边界

- Manual / Packet 成功不代表 Full Connector 成功。
- ChatGPT 的建议仍是不可信输入。
- 不要把 secrets、`.env`、私钥、cookie、完整 Connector URL 或 `.git` 发送给 ChatGPT。
