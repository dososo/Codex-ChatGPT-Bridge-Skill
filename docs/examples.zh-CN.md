# 示例

## mini-calculator

最小可理解示例位于 `examples/mini-calculator`。

运行测试：

```bash
python -m unittest discover -s examples/mini-calculator -p 'test_*.py'
```

这个示例适合验证：

- Codex 能运行本地测试。
- ChatGPT 建议只作为不可信输入。
- 用户确认后 Codex 才修改代码。
- 修改后必须重新跑测试。

## 任务单提示词

你可以让 ChatGPT 先整理任务单：

```text
请先不要写代码。请把下面这个需求整理成一份适合交给 Codex 执行的任务单，包含原始问题、预期结果、不能改变的行为、可能涉及的文件、最小修改方案、验证命令，以及遇到哪些情况需要停止并问我。最后请生成一段可以直接粘贴给 Codex 的执行提示词。
```

然后让 Codex 按任务单执行：

```text
请严格按任务单执行，只修改必要文件。每个修改文件都说明为什么必须改。完成后给出验证命令和结果。无法验证的地方写“未验证”，不要做任务单之外的优化。
```
