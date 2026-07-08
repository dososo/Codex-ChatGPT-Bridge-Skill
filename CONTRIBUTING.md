# Contributing

欢迎提交 issue 和 PR。请保持改动小、可验证、边界清楚。

基本规则：

- 不要让右侧 ChatGPT 获得源码写入或 shell 执行能力。
- 不要放宽 secrets、`.env`、cookie、私钥、`.git`、Connector URL 或 token 的保护边界。
- 改动 Bridge 工具 schema、任务 schema 或结果 schema 时，必须同步测试和文档。
- 涉及安全边界的改动必须补测试。
- issue、日志和截图必须脱敏，不要提交完整本地路径、token、私有仓库内容或账号信息。

本地建议验证：

```bash
python -m compileall -q bridge .agents/skills/codex-chatgpt-bridge/scripts scripts examples tests
python -m unittest tests.test_bridge_health tests.test_task_flow tests.test_tool_schemas tests.test_secret_scan tests.test_redaction
python -m unittest discover -s examples/mini-calculator -p 'test_*.py'
```
