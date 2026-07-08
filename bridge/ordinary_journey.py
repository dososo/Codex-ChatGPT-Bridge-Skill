from __future__ import annotations

from copy import deepcopy
from typing import Any


ORDINARY_USER_JOURNEY: list[dict[str, Any]] = [
    {
        "step": 1,
        "id": "start_in_codex",
        "title": "在 Codex 里开始",
        "what_user_sees": "一个开始连接 ChatGPT 的入口。",
        "codex_does": [
            "读取当前仓库的 Bridge Skill。",
            "准备本地连接和首次检查。",
        ],
        "user_does": "在 Codex 中启动 Bridge 协同入口。",
        "requires_user_action": True,
        "user_action_type": "start",
        "done_when": "Codex 开始显示首次检查进度。",
    },
    {
        "step": 2,
        "id": "local_prepare",
        "title": "Codex 自动完成本地准备",
        "what_user_sees": "本地准备正在进行，不需要复制本地命令。",
        "codex_does": [
            "初始化当前仓库需要的本地状态。",
            "安装安全的本地连接配置。",
            "启动本机 Bridge 并检查状态。",
            "生成发送前预览和协同材料。",
        ],
        "user_does": "等待 Codex 给出下一步确认。",
        "requires_user_action": False,
        "user_action_type": "none",
        "done_when": "本地检查通过，Codex 显示可以进入 ChatGPT 协同。",
    },
    {
        "step": 3,
        "id": "login_chatgpt",
        "title": "用户登录 ChatGPT",
        "what_user_sees": "右侧打开官方 ChatGPT 页面。",
        "codex_does": [
            "只打开官方 ChatGPT 页面。",
            "不读取账号信息，不保存 cookie。",
        ],
        "user_does": "完成登录、二次验证或账号选择。",
        "requires_user_action": True,
        "user_action_type": "login_chatgpt",
        "done_when": "右侧 ChatGPT 可以正常发送消息。",
    },
    {
        "step": 4,
        "id": "connect_chatgpt_app",
        "title": "用户确认连接 ChatGPT App",
        "what_user_sees": "ChatGPT 显示连接授权或应用设置确认。",
        "codex_does": [
            "准备连接所需的公开入口。",
            "只在用户确认后协助进入授权页面。",
            "不把完整连接地址或敏感片段写进聊天。",
        ],
        "user_does": "确认是否连接这个 ChatGPT App。",
        "requires_user_action": True,
        "user_action_type": "app_connection",
        "done_when": "ChatGPT 显示连接完成，或 Codex 判断需要走受控回收。",
    },
    {
        "step": 5,
        "id": "detect_chatgpt_capability",
        "title": "Codex 自动判断可用协同方式",
        "what_user_sees": "Codex 告诉你当前能否自动接收 ChatGPT 回复。",
        "codex_does": [
            "检查本地记录和工具可用性。",
            "能自动接收就准备自动接收。",
            "不能自动接收时准备固定格式回复和人工带回兜底。",
        ],
        "user_does": "不需要理解底层模式，只看 Codex 给出的下一步。",
        "requires_user_action": False,
        "user_action_type": "none",
        "done_when": "状态卡显示下一步是生成任务单或审查请求。",
    },
    {
        "step": 6,
        "id": "choose_plan_or_review",
        "title": "用户选择让 ChatGPT 规划或审查",
        "what_user_sees": "两个普通入口：生成 Codex 任务单，或审查 Codex 执行结果。",
        "codex_does": [
            "按用户选择准备最小上下文。",
            "发送前展示摘要和安全边界。",
        ],
        "user_does": "选择这次要让 ChatGPT 做规划还是做审查。",
        "requires_user_action": True,
        "user_action_type": "choose_collaboration_goal",
        "done_when": "Codex 显示发送前确认。",
    },
    {
        "step": 7,
        "id": "confirm_context_send",
        "title": "用户确认发送上下文",
        "what_user_sees": "发送前预览和安全提醒。",
        "codex_does": [
            "展示将发送的任务说明。",
            "确认不包含敏感文件、账号信息或隐藏配置。",
            "用户确认前不发送给 ChatGPT。",
        ],
        "user_does": "确认可以把这次任务说明发给 ChatGPT。",
        "requires_user_action": True,
        "user_action_type": "send_context",
        "done_when": "右侧 ChatGPT 收到本次任务说明。",
    },
    {
        "step": 8,
        "id": "chatgpt_returns_plan",
        "title": "ChatGPT 生成任务单或审查意见",
        "what_user_sees": "ChatGPT 返回规划、风险点或审查意见。",
        "codex_does": [
            "优先自动接收回复。",
            "自动接收不可用时检查用户带回的完整回复。",
            "把 ChatGPT 内容当作不可信建议。",
        ],
        "user_does": "等待 ChatGPT 回复；自动接收不可用时，把完整回复带回 Codex。",
        "requires_user_action": True,
        "user_action_type": "return_chatgpt_reply",
        "done_when": "Codex 已接收并检查本次 ChatGPT 回复。",
    },
    {
        "step": 9,
        "id": "codex_reviews_reply",
        "title": "Codex 审阅 ChatGPT 回复",
        "what_user_sees": "一份 Codex 审阅清单。",
        "codex_does": [
            "检查任务范围、风险和建议动作。",
            "剔除不能直接执行的危险建议。",
            "把需要用户确认的动作列出来。",
        ],
        "user_does": "阅读审阅清单。",
        "requires_user_action": False,
        "user_action_type": "none",
        "done_when": "审阅清单明确哪些建议可以考虑执行。",
    },
    {
        "step": 10,
        "id": "confirm_codex_execution",
        "title": "用户确认 Codex 执行",
        "what_user_sees": "Codex 询问是否执行某条具体建议。",
        "codex_does": [
            "只执行用户明确批准的最小动作。",
            "不让 ChatGPT 直接改源码或执行命令。",
        ],
        "user_does": "确认要执行哪一条建议。",
        "requires_user_action": True,
        "user_action_type": "execute_code",
        "done_when": "Codex 开始修改代码、运行验证或生成文档。",
    },
    {
        "step": 11,
        "id": "codex_executes_and_verifies",
        "title": "Codex 修改并验证",
        "what_user_sees": "Codex 输出改动摘要和验证结果。",
        "codex_does": [
            "读仓库、改必要文件、运行验证命令。",
            "失败时只修阻断项，不扩范围。",
            "保留验证证据和未覆盖项。",
        ],
        "user_does": "等待 Codex 完成执行和验证。",
        "requires_user_action": False,
        "user_action_type": "none",
        "done_when": "Codex 给出通过、失败或未验证的明确结果。",
    },
    {
        "step": 12,
        "id": "send_handoff_for_review",
        "title": "用户确认把执行结果交给 ChatGPT 审查",
        "what_user_sees": "Codex 展示执行结果摘要和可发送审查请求。",
        "codex_does": [
            "生成本次执行结果摘要。",
            "发送前再次请求用户确认。",
        ],
        "user_does": "确认是否把执行结果发给 ChatGPT 做二次审查。",
        "requires_user_action": True,
        "user_action_type": "send_context",
        "done_when": "ChatGPT 收到执行结果审查请求。",
    },
    {
        "step": 13,
        "id": "chatgpt_reviews_execution",
        "title": "ChatGPT 做二次审查",
        "what_user_sees": "ChatGPT 返回风险、遗漏测试和下一步建议。",
        "codex_does": [
            "接收或检查 ChatGPT 回复。",
            "仍把回复当作不可信建议。",
        ],
        "user_does": "等待 ChatGPT 回复。",
        "requires_user_action": True,
        "user_action_type": "return_chatgpt_reply",
        "done_when": "Codex 已接收 ChatGPT 二次审查回复。",
    },
    {
        "step": 14,
        "id": "final_user_decision",
        "title": "用户决定是否采纳建议",
        "what_user_sees": "Codex 给出最终建议清单、验证结果和未覆盖项。",
        "codex_does": [
            "整合 ChatGPT 审查和本地验证结果。",
            "只在用户确认后继续执行额外建议。",
        ],
        "user_does": "决定是否采纳某条建议，或结束本次任务。",
        "requires_user_action": True,
        "user_action_type": "accept_suggestion",
        "done_when": "本次协同任务关闭，或进入下一条用户确认的动作。",
    },
]


CODEX_AUTO_RESPONSIBILITIES = [
    "本地准备、状态检查和协同材料生成由 Codex 自动完成。",
    "发送前由 Codex 做最小上下文整理和安全提醒。",
    "ChatGPT 回复先由 Codex 接收、检查和整理成审阅清单。",
    "代码修改、命令执行、测试验证和最终证据由 Codex 完成。",
]


USER_REQUIRED_RESPONSIBILITIES = [
    "登录 ChatGPT。",
    "确认连接 ChatGPT App。",
    "确认发送本次任务上下文。",
    "确认 Codex 是否执行某条建议。",
    "确认是否采纳 ChatGPT 审查后的下一步建议。",
]


def ordinary_user_journey() -> list[dict[str, Any]]:
    return deepcopy(ORDINARY_USER_JOURNEY)


def codex_auto_responsibilities() -> list[str]:
    return list(CODEX_AUTO_RESPONSIBILITIES)


def user_required_responsibilities() -> list[str]:
    return list(USER_REQUIRED_RESPONSIBILITIES)


def compact_journey_for_status(limit: int | None = None) -> list[dict[str, Any]]:
    items = ORDINARY_USER_JOURNEY if limit is None else ORDINARY_USER_JOURNEY[:limit]
    return [
        {
            "step": item["step"],
            "id": item["id"],
            "title": item["title"],
            "requires_user_action": item["requires_user_action"],
            "user_action_type": item["user_action_type"],
            "done_when": item["done_when"],
        }
        for item in items
    ]
