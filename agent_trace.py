"""把一次会话的可观察执行步骤写入本地 Markdown。"""
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


# 以代码文件的位置为基准，从不同目录启动也会把日志写到项目下。
TRACE_DIR = Path(__file__).resolve().parent / ".agent_trace"


class SessionTrace:
    def __init__(self, model_name: str, directory: Path = TRACE_DIR):
        directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
        # 生成独立文件名，保留本机临时文件的仅当前用户可读写权限。
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory,
                                prefix=f"session-{timestamp}-", suffix=".md", delete=False) as stream:
            self.path = Path(stream.name)
            stream.write("# 命理解读 Agent 执行日志\n")
        self.turn = 0
        self.facts = {}
        self.record("会话开始", {"model": model_name})

    def record(self, title: str, data: dict):
        # 每个事件都附 UTC 时间，并作为一个 JSON 代码块追加到 Markdown。
        event = {
            "time_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            **data,
        }
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(f"\n### {title}\n\n```json\n")
            json.dump(event, stream, ensure_ascii=False, indent=2, default=str)
            stream.write("\n```\n")

    def record_message(self, message):
        # AIMessage 是模型产生的消息，既可能包含工具请求，也可能包含最终文字。
        if isinstance(message, AIMessage):
            # 仅在接口实际返回独立思考字段时记录，每次模型调用各记一次。
            thinking = message.additional_kwargs.get("reasoning_content")
            if thinking:
                self.record("模型思考", {"text": thinking})
            if message.tool_calls or message.invalid_tool_calls:
                self.record("模型请求调用工具", {
                    "tool_calls": message.tool_calls,
                    "invalid_tool_calls": message.invalid_tool_calls,
                })
            if not message.tool_calls:
                self.record("模型最终回复", {"text": message.text})
        elif isinstance(message, ToolMessage):
            # ToolMessage 是工具给模型的回执。能解析成 JSON 时展开，普通文字照录。
            result = message.content
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except ValueError:
                    pass
            # 用 tool_call_id 和模型请求中的 id 对照，尤其是同一轮有多个调用时。
            self.record("工具返回", {"tool": message.name, "tool_call_id": message.tool_call_id,
                                    "status": message.status, "result": result})

    def run_turn(self, graph, history, user_input):
        # 1. 打开本轮日志，把本次输入包装成 HumanMessage 并接到历史后面。
        self.turn += 1
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(f"\n## 第 {self.turn} 轮\n")
        self.record("用户输入", {"text": user_input})
        messages = [*history, HumanMessage(content=user_input)]
        seen = len(messages)
        evidence_recorded = False
        next_facts = self.facts
        try:
            # 2. 图每推进一步就返回一次状态。values 含全量消息，seen 记录已处理到的位置。
            for state in graph.stream({"messages": messages, "facts": self.facts}, stream_mode="values"):
                messages = state["messages"]
                next_facts = state.get("facts", next_facts)
                for message in messages[seen:]:
                    self.record_message(message)
                seen = len(messages)
                if not evidence_recorded and "evidence" in state:
                    self.record("本轮证据链", state["evidence"])
                    evidence_recorded = True
        except (Exception, KeyboardInterrupt) as exc:
            # 3. 保留已经落盘的步骤和中断原因，再把异常交给终端处理。
            # 已完成的工具可能改变 runtime 中的引用，保留图中已更新的事实以免两者不一致。
            self.facts = next_facts
            self.record("本轮中断", {"error_type": type(exc).__name__, "error": str(exc)})
            raise
        self.facts = next_facts
        return messages
