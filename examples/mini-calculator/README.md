# mini-calculator

这是 Codex ChatGPT Bridge Skill 的最小闭环示例项目。

目标：

- 本地测试先失败，证明存在明确 bug。
- Codex 只把最小文件和测试输出交给 Bridge。
- 右侧 ChatGPT 只回传不可信建议，不直接修改源码或执行命令。
- 用户确认后，Codex 才执行最小修复并重新测试。
