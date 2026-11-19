"""用 LangGraph 循环执行模型选择的排盘与检索工具。"""
from __future__ import annotations

from langchain_core.messages import SystemMessage
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from tools.catalog import inspect_tianzhi_api
from tools.rag import search_classics
from tools.tianzhi_runtime import TianzhiRuntime


# 这段指令随每次模型请求发送。问题、历史和工具结果则来自图的 messages 状态。
SYSTEM_PROMPT = """你是传统术数与命理文化解读助手，支持根据用户的问题选择适用的术数方法，包括八字及工具目录中可用的其他方法。对于无关问题，说明你的用途并引导用户提出命理相关问题。

先理解问题、所用方法和时间范围，收集所选方法需要的信息。资料缺失或含义不明时询问用户，不猜测性别、日期、历法、时区、经度或排盘口径。使用 inspect_tianzhi_api 查询可用方法、参数和返回值，结合问题制定分析方案。

使用 call_tianzhi_api 执行所需排盘和规则计算，根据返回的实际结果决定接下来的计算。多轮追问可复用适用的结果引用；用户修改出生资料或计算口径时重新计算受影响的结果。相关调用互相依赖时，先等前一个工具返回再调用下一个。

根据问题和实际计算结果调用 search_classics，填写关键词和语义查询以寻找解读依据。当前古籍库主要是八字典籍；其他术数若未找到适用材料，要如实说明。需要时调整查询再次检索。

证据足够时，区分用户的计算结果、古籍规则和其他人的命例，结合规则适用条件回答，并在引用依据处标注工具返回的【passage_id】。工具或资料不足时说明缺少什么。工具调用必须使用结构化工具调用，只有收到实际回执后才称已查询或计算。将解读表述为传统文化视角。"""


def create_graph(model, *, rag_tool=search_classics):
    """为一个对话创建执行图，排盘结果引用在这个对话内有效。"""
    # 1. 注册目录、排盘执行和古籍检索三个工具。测试可以传入替代的检索工具。
    runtime = TianzhiRuntime()
    tools = [inspect_tianzhi_api, runtime.as_tool(), rag_tool]
    # bind_tools 把每个工具的名字、用途和参数格式告诉模型，供它发出调用请求。
    agent_model = model.bind_tools(tools)
    system_message = SystemMessage(content=SYSTEM_PROMPT)

    def decide(state: MessagesState):
        # 2. 模型读取系统提示词和当前全部消息，返回带 tool_calls 的请求或文字回复。
        response = agent_model.invoke([system_message, *state["messages"]])
        # MessagesState 会把这条新消息合入历史，下面的节点便能读取它。
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("agent", decide)
    # 3. ToolNode 按模型请求调用 Python 工具，把结果或异常信息写为 ToolMessage。
    builder.add_node("tools", ToolNode(tools, handle_tool_errors=True))
    builder.add_edge(START, "agent")
    # 4. 检查最新回复。有工具调用就执行后回到模型，给出文字回复时结束本轮。
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    # 49 是 LangGraph 单轮执行步数的上限，用于结束反复调用工具的循环。
    return builder.compile().with_config({"recursion_limit": 49})
