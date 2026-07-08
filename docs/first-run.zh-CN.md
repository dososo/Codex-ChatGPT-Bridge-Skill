# 第一次使用

第一次使用的目标是让普通用户看懂“现在能不能让 ChatGPT 协助这次任务”，而不是解释底层协议。

## 用户看到什么

用户只需要看到：

1. 当前推荐动作：让 ChatGPT 生成任务单，或审查 Codex 执行结果。
2. Codex 将要发送的最小上下文。
3. 哪些步骤必须用户确认。
4. ChatGPT 回复后，Codex 如何接收、审阅并等待用户确认执行。

## Codex 自动完成什么

- 本地 Bridge 状态检查。
- 本地工具发现。
- 发送前预览。
- ChatGPT 协同消息生成。
- Packet fallback 材料准备。

## 用户必须参与什么

- 登录 ChatGPT、2FA 或账号切换。
- 确认是否发送上下文。
- 确认是否创建或授权 ChatGPT App / Connector。
- 确认是否导入 ChatGPT 回复。
- 确认是否执行 ChatGPT 建议。

## 推荐命令

```bash
python .agents/skills/codex-chatgpt-bridge/scripts/verify_first_use.py --dry-run --json
python .agents/skills/codex-chatgpt-bridge/scripts/first_run.py
python scripts/build_chatgpt_collaboration_session.py --dry-run
```

`--dry-run` 只展示流程，不打开 ChatGPT，不发送上下文，不创建真实任务，不执行建议。
