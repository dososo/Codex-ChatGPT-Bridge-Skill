# Codex ChatGPT Bridge Skill

> 让 Codex 和右侧 ChatGPT 形成受控协同：ChatGPT 负责规划和审计，Codex 负责读仓库、改代码、跑测试和交付 diff。

[English README](README.en.md)

![Codex ChatGPT Bridge 协同流程](assets/screenshots/codex-chatgpt-bridge-flow.svg)

<p align="center">
  <img src="assets/screenshots/chatgpt-collaboration-loop.png" alt="Codex 与右侧 ChatGPT 协同界面示例" width="920">
</p>

<p align="center">
  <sub>Codex 负责本地执行与验证，右侧 ChatGPT 负责规划、审计和结构化建议；真实 Connector 能力仍以工具调用和 audit 记录为准。</sub>
</p>

## 最快入口

在 Codex 桌面版里打开这个仓库，然后直接说：

```text
使用 codex-chatgpt-bridge 帮我让 ChatGPT 协助规划这次任务。请先完成本地预检，生成发送给 ChatGPT 的任务单消息；发送前让我确认，不要读取 secrets、.env、私钥、cookie 或 .git，不要执行 ChatGPT 的建议。
```

如果你已经完成了一轮 Codex 修改，想让 ChatGPT 做审查，可以说：

```text
使用 codex-chatgpt-bridge 帮我把本次 Codex 执行结果交给 ChatGPT 审查。请只发送我确认过的 diff、测试结果和最小上下文；ChatGPT 的建议必须先回到 Codex 审阅，再由我确认是否执行。
```

手动运行也可以：

```bash
python .agents/skills/codex-chatgpt-bridge/scripts/verify_first_use.py --dry-run --json
python .agents/skills/codex-chatgpt-bridge/scripts/first_run.py
python scripts/build_chatgpt_collaboration_session.py --dry-run
```

## 它是什么

Codex ChatGPT Bridge Skill 是一个本地优先的 Codex Skill 和 MCP Bridge。它不是让 ChatGPT 自由读取你的仓库，也不是让 ChatGPT 直接写代码。

它的核心分工很明确：

| 角色 | 负责什么 | 不负责什么 |
| --- | --- | --- |
| Codex | 读取本地仓库、修改文件、运行命令、修测试、生成验证证据 | 不把未经确认的建议直接执行 |
| ChatGPT | 整理需求、比较方案、生成 Codex 任务单、审查 diff 和风险 | 不直接改源码、不执行 shell、不读取 secrets |
| Bridge | 最小上下文打包、任务同步、结果导入、权限边界、audit 记录 | 不把本地预检伪装成真实外部能力 |
| 用户 | 授权发送上下文、确认连接、确认是否执行建议 | 不需要理解底层 MCP 模式或手敲一堆命令 |

这个项目解决的是一个很常见的问题：复杂任务直接丢给 Codex，Codex 会先花大量上下文读仓库、猜边界、边改边验证。更稳的做法是先让 ChatGPT 把需求整理成一页任务单，再让 Codex 按任务单执行。Bridge 把这件事做成受控流程：准备上下文、打开右侧 ChatGPT、回收结构化建议、交给 Codex 审阅，最后由用户确认。

## 工作效果

一次典型协同会变成这样：

1. Codex 自动完成本地预检、Bridge 状态检查和最小上下文准备。
2. 用户确认后，Codex 打开右侧 ChatGPT，并发送任务单或审查请求。
3. ChatGPT 只做规划或审计，输出结构化结果。
4. Codex 预检并导入 ChatGPT 结果，生成审阅清单。
5. 用户确认后，Codex 执行必要修改并跑验证。

对用户的直接收益：

- 任务边界更清楚，Codex 不需要一上来大范围猜测。
- ChatGPT Pro 的长上下文和规划能力可以用于需求整理、方案比较和审计。
- Codex 仍然掌握本地读写和验证，不把源码控制权交给右侧模型。
- Connector 可用时走官方工具；不可用时自动降级到受控消息和结构化导入，不中断工作流。

## 核心能力

| 能力 | 命令 / 入口 | 结果 |
| --- | --- | --- |
| 首次能力门诊 | `first_run.py` | 告诉用户当前能走哪条协同路径 |
| 一键首次预检 | `verify_first_use.py` | 本地 setup、status、smoke、协同材料预检 |
| 任务单协同 | `build_chatgpt_collaboration_message.py --mode task-brief` | 生成可发给 ChatGPT 的 Codex 执行任务单请求 |
| 执行结果审查 | `build_chatgpt_collaboration_message.py --mode review` | 生成可发给 ChatGPT 的 diff / 测试审查请求 |
| 受控任务同步 | `bridge_push_task` / `bridge_fetch_task_packet` / `bridge_pull_task` | 让 ChatGPT 读取最小任务包 |
| 结构化结果导入 | `intake_chatgpt_result.py --stdin` | 预检 ChatGPT 回传 JSON，用户确认后导入 |
| 结果审阅 | `review_result.py` | 把 ChatGPT 建议转成 Codex 审阅清单 |
| Packet fallback | `build_packet.py` | 官方工具不可用时生成脱敏任务包 |

## 示例

仓库内置了一个小白也能看懂的真实例子：

```bash
python -m unittest discover -s examples/mini-calculator -p 'test_*.py'
```

这个例子演示了 Bridge 的基本闭环：

1. Codex 准备一个小计算器任务。
2. ChatGPT 给出审查建议。
3. Codex 把建议当作不可信输入审阅。
4. 用户确认后，Codex 修改代码并跑测试。

## 第一次使用怎么走

普通用户不需要理解 Full Connector、Read-only、Packet、Manual 这些底层模式。界面应该只给你看四件事：

1. 现在要不要让 ChatGPT 协助规划或审查。
2. Codex 将发送哪些最小上下文。
3. 哪些步骤必须你确认。
4. ChatGPT 回复后，Codex 如何审阅并等待你确认执行。

推荐流程：

```bash
python .agents/skills/codex-chatgpt-bridge/scripts/verify_first_use.py --dry-run --json
python .agents/skills/codex-chatgpt-bridge/scripts/first_run.py
python scripts/build_chatgpt_collaboration_session.py --dry-run
```

当你确认发送时，Codex 才会创建真实 Bridge task，并生成带真实 `task_id` 的 ChatGPT 消息。仅生成消息不会打开网页、不会发送上下文、不会执行建议。

### 界面引导示例

<table>
  <tr>
    <td width="33%" valign="top">
      <img src="assets/screenshots/chatgpt-app-connect.jpeg" alt="ChatGPT 连接确认界面" width="100%">
      <br>
      <sub>1. 在 ChatGPT 侧确认连接。Codex 会说明用途和安全边界，连接前不会发送项目上下文。</sub>
    </td>
    <td width="33%" valign="top">
      <img src="assets/screenshots/chatgpt-app-settings.jpeg" alt="ChatGPT 应用设置界面" width="100%">
      <br>
      <sub>2. 连接后可以在应用设置里查看权限。Bridge 只暴露受控工具，不让 ChatGPT 直接改源码或执行命令。</sub>
    </td>
    <td width="33%" valign="top">
      <img src="assets/screenshots/codex-confirmation-guide.jpeg" alt="Codex 创建前确认引导" width="100%">
      <br>
      <sub>3. 遇到账号授权、创建应用、发送上下文等关键动作时，Codex 会停下来让用户确认。</sub>
    </td>
  </tr>
</table>

## MCP Connector 能力说明

Bridge 优先使用官方 MCP 工具，但不会假设你的 ChatGPT 账号一定能调用工具。

- 如果 ChatGPT 当前模型真的能调用 read/write 工具，可以走 Full Connector。
- 如果只有只读工具可用，可以读取任务包，然后用结构化 JSON 回到 Codex。
- 如果工具不可用，仍然可以走受控 ChatGPT 消息和结构化导入。

无论哪条路径，ChatGPT 都是“不可信协作者”。它的建议必须先回到 Codex 审阅，再由用户确认是否执行。

## 数据隐私与安全边界

默认边界：

- 不读取 secrets、`.env`、私钥、cookie、`.git`。
- 不发送 Bridge token、完整 Connector URL、账号资料或登录态。
- 右侧 ChatGPT 不能直接改源码，不能执行 shell。
- Packet 和任务上下文会做敏感信息扫描和大小限制。
- ChatGPT 回传结果只是不可信建议。
- `suggested_actions` 不会自动执行，必须用户确认。

如果你要报告问题，请只提交脱敏日志和最小复现，不要提交 token、完整连接地址、私有仓库内容或账号截图。

## 目录结构

```text
.
├── .agents/skills/codex-chatgpt-bridge/   # Codex Skill 入口、脚本和提示词
├── bridge/                                # 本地 Bridge、MCP 协议、权限和状态管理
├── scripts/                               # 协同消息、浏览器协助、结果导入等公开工具
├── examples/                              # 可运行示例项目
├── tests/                                 # 公开核心测试
├── docs/                                  # 使用、安全、故障处理文档
├── assets/screenshots/                    # README 图片
├── README.md                              # 中文说明
├── README.en.md                           # English README
├── SECURITY.md                            # 安全说明
└── LICENSE                                # Apache-2.0
```

## 本地验证

```bash
python -m compileall -q bridge .agents/skills/codex-chatgpt-bridge/scripts scripts examples tests
python -m unittest \
  tests.test_bridge_health \
  tests.test_task_flow \
  tests.test_tool_schemas \
  tests.test_mcp_protocol \
  tests.test_http_auth \
  tests.test_secret_scan \
  tests.test_redaction \
  tests.test_path_safety \
  tests.test_review_result \
  tests.test_intake_chatgpt_result \
  tests.test_push_task_confirmation \
  tests.test_fallback_and_capability \
  tests.test_chatgpt_collaboration_message
python -m unittest discover -s examples/mini-calculator -p 'test_*.py'
```

## 发布状态

当前版本：`v0.5.0`。

这个版本面向本地可用的协同内核和开源预览：本地 Bridge、受控上下文、任务单生成、审查导入、安全边界和 fallback 流程已经可用。真实 ChatGPT Connector 的 read/write 能力仍以用户账号、模型和官方工具调用为准；没有真实 tool call 和审计记录时，不应声称 Full Connector 已验证。

## 关于作者

作者：BLCaptain / dososo

GitHub: [https://github.com/dososo](https://github.com/dososo)

## License

Apache-2.0
