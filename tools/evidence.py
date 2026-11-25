"""按最终回答中实际出现的引用 ID 建立每轮证据记录。"""
from copy import deepcopy
import json
import re
from threading import RLock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


class EvidenceChain:
    """一个图实例对应一条会话证据链；完整证据另由执行日志保存。"""

    def __init__(self):
        self._items = []
        self._lock = RLock()

    def append_turn(self, messages, facts, rag_tool_name="search_classics"):
        # 从最终回答的实际标注提取，而不是让模型再次生成一份可能不同的清单。
        answer = next((m.text for m in reversed(messages)
                       if isinstance(m, AIMessage) and not m.tool_calls), "")
        question_index = next((i for i in range(len(messages) - 1, -1, -1)
                               if isinstance(messages[i], HumanMessage)), None)
        question = messages[question_index].text if question_index is not None else ""
        ids = list(dict.fromkeys(re.findall(r"【([^【】\n]+)】", answer)))

        # 允许追问引用前一轮材料；同 ID 多次返回时优先选择最近的版本。
        by_id = {}
        for i, message in enumerate(messages):
            if not isinstance(message, ToolMessage) or message.name != rag_tool_name or message.status != "success":
                continue
            content = message.content
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except (ValueError, TypeError):
                    continue
            if not isinstance(content, dict) or not isinstance(content.get("passages"), list):
                continue
            for passage in content["passages"]:
                if isinstance(passage, dict) and isinstance(passage.get("passage_id"), str):
                    by_id[passage["passage_id"]] = {
                        "passage": deepcopy(passage),
                        "tool_call_id": message.tool_call_id,
                        "retrieved_this_turn": question_index is not None and i > question_index,
                    }
        references = []
        unresolved = []
        for pid in ids:
            if pid in by_id:
                references.append(by_id[pid])
            else:
                unresolved.append(pid)
        with self._lock:
            record = {"turn": len(self._items) + 1, "question": question,
                      "facts": deepcopy(facts), "answer": answer,
                      "references": references, "unresolved_citations": unresolved}
            self._items.append(record)
            return deepcopy(record)

    def snapshot(self):
        with self._lock:
            return deepcopy(self._items)
