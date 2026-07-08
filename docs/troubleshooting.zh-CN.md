# 故障处理

## Bridge 没有运行

运行：

```bash
python .agents/skills/codex-chatgpt-bridge/scripts/status.py --json
python .agents/skills/codex-chatgpt-bridge/scripts/start_bridge.py
```

如果端口被占用，重新运行 setup 让 Bridge 选择可用端口：

```bash
python .agents/skills/codex-chatgpt-bridge/scripts/setup.py --json
```

## ChatGPT 看不到工具

这不等于项目失败。继续使用受控消息或 Packet fallback，让 ChatGPT 做任务单或审查，然后把结构化结果交回 Codex。

## ChatGPT 能读但不能写

使用只读路径：ChatGPT 读取任务包后输出 fenced `codex-bridge-result-json`，Codex 预检并在用户确认后导入。

## ChatGPT 回复不能导入

检查：

- 是否包含真实 `task_id`。
- JSON 顶层是否有 `summary`。
- 是否是 fenced `codex-bridge-result-json`。
- 是否包含危险命令或敏感信息。

导入前先预检：

```bash
python scripts/intake_chatgpt_result.py --stdin --json --repo-root <当前仓库绝对路径>
```

## Codex 不应该执行建议

正确。ChatGPT 建议必须先经过 Codex 审阅，再由用户确认。没有用户确认时，Codex 不应运行命令、应用 patch 或修改源码。
