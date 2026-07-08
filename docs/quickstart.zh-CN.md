# 快速开始

## 在 Codex 中使用

打开仓库后，对 Codex 说：

```text
使用 codex-chatgpt-bridge 帮我让 ChatGPT 协助规划这次任务。先做本地预检，生成发送给 ChatGPT 的任务单消息；发送前让我确认。
```

Codex 会自动完成：

1. 检查 Bridge 本地状态。
2. 准备最小上下文。
3. 生成 ChatGPT 任务单或审查消息。
4. 提醒哪些步骤需要你确认。

## 手动预览

```bash
python .agents/skills/codex-chatgpt-bridge/scripts/verify_first_use.py --dry-run --json
python .agents/skills/codex-chatgpt-bridge/scripts/first_run.py
python scripts/build_chatgpt_collaboration_session.py --dry-run
```

## 真正发送前

确认三件事：

- 发送内容不包含 secrets、`.env`、私钥、cookie、完整 Connector URL 或 `.git`。
- ChatGPT 只做任务单或审查，不写代码、不执行 shell。
- ChatGPT 的建议要回到 Codex 审阅，并由你确认后才执行。
