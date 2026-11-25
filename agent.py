"""用 LangGraph 循环执行模型选择的排盘与检索工具。"""
from __future__ import annotations

import json
import math
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.graph import START, END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from tools.catalog import inspect_tianzhi_api
from tools.date_info import make_date_tool
from tools.evidence import EvidenceChain
from tools.location import make_location_tool
from tools.rag import search_classics
from tools.session_state import SessionFacts
from tools.tianzhi_runtime import TianzhiRuntime


# 这段指令随每次模型请求发送。问题、历史和工具结果则来自图的 messages 状态。
SYSTEM_PROMPT = """你是传统术数与命理文化解读助手。

1. 理解问题和收集资料
根据用户问题选择适用的术数方法，包括八字和工具目录中的其他方法。
对于无关问题，说明你的用途并引导用户提出命理相关问题。
先理解问题、所用方法和时间范围，收集所需信息。
资料缺失时询问，不猜测性别、具体时刻、时区或其他口径。

2. 确认日期和出生地
日期未指定历法时默认公历，并在回答中说明。
用户明确指定农历时先转换成公历，闰月等不清楚时询问。
默认使用真太阳时；用户明确选择不修正时，按用户选择。
调用 lookup_location 查询出生地经度和时区，分别填写完整城市或区县名
name 和所属省级地区 province；中国可填 country_code=CN。
两字城市名可能漏匹配；查不到时保持省份不变，尝试完整名称或已知拼音。
不得猜测拼音、坐标或省市。省市不明时询问，不能仅凭城市搜索。
候选多个时核对省市区，仍无法确定则请用户澄清；
无匹配时请用户提供更具体地点或经度。城市坐标是近似值，须说明。

3. 查询日期与计算命盘
使用 inspect_tianzhi_api 按层查询方法，不要一次索取所有方法。
询问具体日期运势、黄历或宜忌时调用 get_date_info。
目标日期填写 purpose=target；出生日期的农历转换填写 purpose=birth，
不能混同。公历出生日期可直接排盘，无需额外查出生日期黄历。
通用黄历宜忌不同于命盘个人喜忌。
日期工具不做出生地真太阳时或时区修正，需要时说明口径。

使用 call_tianzhi_api 执行所需排盘和规则计算。
根据返回的实际结果决定接下来的计算。
当前命盘信息表由程序根据工具回执维护，是当前会话的事实来源。
命盘、十神、岁运、日期、喜忌均以工具结果为准，不凭记忆计算或抄错。
多轮追问可复用适用的结果引用；用户修改资料或口径时重新计算受影响的结果。
调用互相依赖时，先等前一个工具返回再调用下一个。

4. 检索古籍
根据问题和实际计算结果调用 search_classics，填写用户当前问题、
关键词和语义查询，以寻找解读依据。需要时调整查询再次检索。
当前古籍库主要是八字典籍；其他术数若未找到适用材料，要如实说明。

5. 解读和标注引用
区分工具计算事实、古籍规则和其他人的命例，检查规则的适用条件。
凡使用古籍支持的解读，必须在对应句子或段落旁标注实际采用的片段 ID。
格式为【实际片段ID】：方括号内只写工具返回的 passage_id 值，
不要加 passage_id:、书名或其他文字；多条依据分别标注。
例如工具返回 passage_id 为 example@0-10 时，标注【example@0-10】。
这个 ID 只是格式示例，不得将它作为实际来源，除非工具确实返回了它。
不要用【】包围“工具计算”“我的解释”等普通标题，以免误认为引用。
只能使用 search_classics 实际返回过的 ID 和片段，不得编造 ID、原文或出处，
也不得把不适用的命例当作本人的事实。
资料不足以支持某项解读时，应明确说明，不能编造古籍依据。

6. 工具调用与回答边界
工具调用必须使用结构化工具调用；只有收到实际回执后才称已查询或计算。
工具或资料不足时说明缺少什么。将解读表述为传统文化视角。"""


class AgentState(MessagesState):
    # 当前命盘与本轮证据随图状态传递；历史证据另写入日志。
    facts: dict
    evidence: dict


def create_graph(model, *, rag_tool=search_classics, budget_hint=None):
    """为一个对话创建执行图，排盘结果引用在这个对话内有效。"""
    # 1. 注册目录、排盘执行和古籍检索三个工具。测试可以传入替代的检索工具。
    evidence_chain = EvidenceChain()
    runtime = TianzhiRuntime()
    tools = [inspect_tianzhi_api, runtime.as_tool(), make_date_tool(), make_location_tool(), rag_tool]
    # bind_tools 把每个工具的名字、用途和参数格式告诉模型，供它发出调用请求。
    agent_model = model.bind_tools(tools)
    system_message = SystemMessage(content=SYSTEM_PROMPT)

    def decide(state: AgentState):
        # 2. 模型读取系统提示词和当前全部消息，返回带 tool_calls 的请求或文字回复。
        facts = state.get("facts") or SessionFacts().snapshot()
        current_facts = SystemMessage(content="当前会话命盘信息表（由工具返回自动更新）：\n" +
                                      json.dumps(facts, ensure_ascii=False, default=str))
        hints = [SystemMessage(content=budget_hint(state))] if budget_hint is not None else []
        response = agent_model.invoke([system_message, current_facts, *hints, *state["messages"]])
        # MessagesState 会把这条新消息合入历史，下面的节点便能读取它。
        return {"messages": [response], "facts": facts}

    def update_facts(state: AgentState):
        """读取本次 ToolNode 回执，更新图状态，而非让工具修改外部表。"""
        facts = SessionFacts(state.get("facts"))
        messages = state["messages"]
        # 只处理最近一次模型请求之后的工具回执，避免重复应用旧结果。
        start = next((i for i in range(len(messages) - 1, -1, -1)
                      if isinstance(messages[i], AIMessage)), -1)
        computations = []
        for message in messages[start + 1:]:
            if not isinstance(message, ToolMessage) or message.status != "success":
                continue
            try:
                result = json.loads(message.content) if isinstance(message.content, str) else message.content
            except (TypeError, ValueError):
                continue
            if not isinstance(result, dict) or "error" in result:
                continue
            if message.name == "get_date_info":
                facts.set_date(result)
            elif message.name == "lookup_location":
                facts.set_location(result)
            elif message.name == "call_tianzhi_api":
                reference = result.get("ref", "")
                record = runtime.take_record(reference)
                if record is None:
                    continue
                # 同批次工具可能并发完成；r 序号是在锁内分配的真实完成顺序。
                computations.append((int(reference[1:]), record))
        for _, record in sorted(computations, key=lambda item: item[0]):
            if record["name"] == "bazi.chart.build_chart":
                facts.set_chart(record["result"], record["arguments"])
                # 只有和实际排盘经度吻合的地点才进入命盘表；完整候选仍保留在工具回执中。
                longitude = record["arguments"].get("longitude")
                chosen = None
                if isinstance(longitude, (int, float)) and not isinstance(longitude, bool):
                    for prior in reversed(messages):
                        if not isinstance(prior, ToolMessage) or prior.name != "lookup_location" or prior.status != "success":
                            continue
                        try:
                            lookup = json.loads(prior.content) if isinstance(prior.content, str) else prior.content
                        except (ValueError, TypeError):
                            continue
                        if not isinstance(lookup, dict):
                            continue
                        matched = [item for item in lookup.get("matches", []) if isinstance(item, dict)
                                   and isinstance(item.get("longitude"), (int, float))
                                   and math.isclose(item["longitude"], longitude, rel_tol=0, abs_tol=1e-6)]
                        if len(matched) == 1:
                            chosen = {"status": "matched_chart_longitude", "location": matched[0],
                                      "source": lookup.get("source"), "coordinate_system": lookup.get("coordinate_system"),
                                      "precision": lookup.get("precision")}
                            break
                        if len(matched) > 1:
                            break
                facts.set_chart_location(chosen or {"status": "chart_longitude_unmatched", "longitude": longitude})
            elif record["name"].startswith("bazi."):
                facts.set_calculation(record["name"], {"arguments": record["arguments"],
                                                        "result": record["result"]})
        return {"facts": facts.snapshot()}

    def collect_evidence(state: AgentState):
        # 最终回复已写好，依据其中的引用 ID 回查真实 RAG 回执。
        record = evidence_chain.append_turn(state["messages"], state.get("facts", {}), rag_tool.name)
        return {"evidence": record}

    builder = StateGraph(AgentState)
    builder.add_node("agent", decide)
    builder.add_node("evidence", collect_evidence)
    builder.add_node("update_facts", update_facts)
    # 3. ToolNode 按模型请求调用 Python 工具，把结果或异常信息写为 ToolMessage。
    builder.add_node("tools", ToolNode(tools, handle_tool_errors=True))
    builder.add_edge(START, "agent")
    # 4. 检查最新回复。有工具调用就执行后回到模型，给出文字回复时结束本轮。
    builder.add_conditional_edges("agent", tools_condition, {"tools": "tools", "__end__": "evidence"})
    builder.add_edge("tools", "update_facts")
    builder.add_edge("update_facts", "agent")
    builder.add_edge("evidence", END)
    # 49 是 LangGraph 单轮执行步数的上限，用于结束反复调用工具的循环。
    return builder.compile().with_config({"recursion_limit": 49})
