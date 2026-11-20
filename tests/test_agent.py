import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from agent import create_graph
from agent_trace import SessionTrace
from tools.catalog import inspect_tianzhi_api
from tools.rag import HybridRAG, reciprocal_rank_fusion, search_classics


def request_tool(tool_name, call_id, **args):
    # 造一条与真实模型同结构的工具请求，供 LangGraph 按正常路线执行。
    return AIMessage(content="", tool_calls=[{"name": tool_name, "id": call_id, "args": args}])


class StubModel:
    # 按测试预设的顺序返回消息，使每一步的工具路线都可重复验证。
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.inputs = []

    def bind_tools(self, tools):
        self.tools = {item.name: item for item in tools}
        return self

    def invoke(self, messages):
        self.inputs.append(messages)
        return next(self.outputs)


class FlowTests(unittest.TestCase):
    def test_inspect_tianzhi_api_reads_live_catalog(self):
        listing = inspect_tianzhi_api.invoke({"layer": "bazi", "module": "yongshen"})
        self.assertIn("bazi.yongshen.select", [item["name"] for item in listing["tools"]])
        detail = inspect_tianzhi_api.invoke({"name": "bazi.yongshen.select"})
        self.assertIn("YongShen", detail["description"])

    def test_agent_can_reply_without_tools(self):
        model = StubModel([AIMessage(content="请问出生时间是什么？")])
        result = create_graph(model).invoke({"messages": [HumanMessage(content="帮我排盘")]})
        self.assertEqual(result["messages"][-1].content, "请问出生时间是什么？")
        self.assertEqual(len(model.inputs), 1)
        self.assertFalse(any(isinstance(message, ToolMessage) for message in result["messages"]))

    def test_trace_links_tool_requests_and_results_across_turns(self):
        # 第一轮查工具，第二轮沿用历史。验证旧工具结果只写一次，便于回看。
        model = StubModel([
            request_tool("inspect_tianzhi_api", "signature", name="bazi.chart.nayin"),
            AIMessage(content="这是纳音接口。"),
            AIMessage(content="可以。"),
        ])
        graph = create_graph(model)
        with TemporaryDirectory() as directory:
            trace = SessionTrace("deepseek-r1:8b", Path(directory))
            first = trace.run_turn(graph, [], "请查接口")
            trace.run_turn(graph, first, "可以说明吗？")
            trace_text = trace.path.read_text(encoding="utf-8")

        self.assertIn('"model": "deepseek-r1:8b"', trace_text)
        self.assertIn('"id": "signature"', trace_text)
        self.assertIn('"tool_call_id": "signature"', trace_text)
        self.assertIn("nayin(ganzhi:", trace_text)
        self.assertIn("这是纳音接口。", trace_text)
        self.assertEqual(trace_text.count("### 工具返回"), 1)
        self.assertEqual(trace_text.count("### 模型最终回复"), 2)

    def test_trace_records_interrupted_turn(self):
        class FailingGraph:
            def stream(self, state, *, stream_mode):
                yield state
                raise RuntimeError("连接中断")

        with TemporaryDirectory() as directory:
            trace = SessionTrace("deepseek-r1:8b", Path(directory))
            with self.assertRaisesRegex(RuntimeError, "连接中断"):
                trace.run_turn(FailingGraph(), [], "请查接口")
            self.assertIn('"error": "连接中断"', trace.path.read_text(encoding="utf-8"))

    def test_trace_records_returned_thinking_with_tool_call(self):
        with TemporaryDirectory() as directory:
            trace = SessionTrace("test", Path(directory))
            message = request_tool("inspect_tianzhi_api", "call1", name="bazi.chart.nayin")
            message.additional_kwargs["reasoning_content"] = "先查询工具目录"
            trace.record_message(message)
            trace.record_message(AIMessage(content="回答"))
            content = trace.path.read_text(encoding="utf-8")
        self.assertIn("先查询工具目录", content)
        self.assertEqual(content.count("### 模型思考"), 1)
        self.assertIn('"id": "call1"', content)

    def test_agent_can_choose_tools_and_use_results_on_followup(self):
        # 目录和排盘使用真实工具。用替身记录 RAG 入参，再检查追问能否复用 r1。
        queries = []

        @tool
        def search_classics(keyword_queries: list[str], semantic_queries: list[str]) -> dict:
            """替代古籍索引，记录模型实际送入的两组查询。"""
            queries.extend([keyword_queries, semantic_queries])
            return {"passages": [{"passage_id": "sample@0-12", "text": "古籍片段"}]}

        model = StubModel([
            request_tool("inspect_tianzhi_api", "catalog", layer="bazi", module="chart"),
            request_tool("call_tianzhi_api", "chart", name="bazi.chart.build_chart",
                         arguments={"dt": "2000-01-01T12:00:00+08:00", "use_true_solar": False}),
            request_tool("search_classics", "rag", keyword_queries=["用神"], semantic_queries=["日主与月令"]),
            AIMessage(content="古籍依据见【sample@0-12】。"),
            request_tool("call_tianzhi_api", "followup", name="bazi.luck_cycle.dayun_list",
                         arguments={"chart": {"$ref": "r1"}, "count": 2}),
            AIMessage(content="已找到两步大运。"),
        ])
        graph = create_graph(model, rag_tool=search_classics)
        first = graph.invoke({"messages": [HumanMessage(content="请排盘并找古籍依据")]})
        self.assertEqual(queries, [["用神"], ["日主与月令"]])
        self.assertEqual(first["messages"][-1].content, "古籍依据见【sample@0-12】。")
        tool_results = {m.tool_call_id: json.loads(m.content) for m in first["messages"] if isinstance(m, ToolMessage)}
        self.assertEqual(tool_results["chart"]["ref"], "r1")
        self.assertIn("hidden", tool_results["chart"]["result"]["pillars"]["day"])

        followup = graph.invoke({"messages": [*first["messages"], HumanMessage(content="再看前两步大运")]})
        self.assertEqual(followup["messages"][-1].content, "已找到两步大运。")
        result = json.loads(followup["messages"][-2].content)
        self.assertEqual(len(result["result"]), 2)

    def test_tool_error_can_be_read_by_agent(self):
        model = StubModel([
            request_tool("call_tianzhi_api", "call", name="bazi.luck_cycle.dayun_list",
                         arguments={"chart": {"$ref": "r1"}}),
            AIMessage(content="请提供出生信息以排盘。"),
        ])
        result = create_graph(model).invoke({"messages": [HumanMessage(content="看大运")]})
        self.assertIn("未知结果引用", result["messages"][-2].content)
        self.assertIn("出生信息", result["messages"][-1].content)

    def test_rrf_counts_distinct_routes_and_one_rank_per_route(self):
        results = reciprocal_rank_fusion({"keyword": [1, 1, 2], "vector": [2]}, 2)
        self.assertEqual([item[0] for item in results], [2, 1])
        self.assertAlmostEqual(results[0][1], 1 / 63 + 1 / 61)
        self.assertEqual(results[0][2], {"keyword": 3, "vector": 1})

    def test_hybrid_search_requires_both_query_lists(self):
        schema = search_classics.get_input_jsonschema()
        self.assertEqual(set(schema["required"]), {"keyword_queries", "semantic_queries"})
        with self.assertRaisesRegex(ValueError, "同时提供"):
            search_classics.invoke({"keyword_queries": ["夫星"], "semantic_queries": []})

    def test_hybrid_search_reranks_candidates_before_applying_limit(self):
        class KeywordIndex:
            def search(self, queries):
                return [0, 1, 2]

        class VectorIndex:
            def search(self, queries):
                return [0, 1, 2], 0

        class Reranker:
            def rerank(self, candidates, question, keywords, phrases, limit):
                self.received = (candidates, question, keywords, phrases, limit)
                return [{**candidates[-1], "rerank_score": 9.0}], 1

        rag = HybridRAG()
        rag.passages = [{"passage_id": str(i), "book": "书", "chapter": "篇", "text": str(i)}
                        for i in range(3)]
        rag.keyword_index, rag.vector_index, rag.reranker = KeywordIndex(), VectorIndex(), Reranker()
        result = rag.search(["夫星"], ["婚姻规则"], limit=1, question="婚姻如何？")
        candidates, question, keywords, phrases, limit = rag.reranker.received
        self.assertEqual(len(candidates), 3)
        self.assertEqual((question, keywords, phrases, limit), ("婚姻如何？", ["夫星"], ["婚姻规则"], 1))
        self.assertEqual(result["passages"][0]["passage_id"], "2")
        self.assertEqual(result["passages"][0]["rerank_score"], 9.0)
        self.assertTrue(any("重排" in notice for notice in result["notices"]))


if __name__ == "__main__":
    unittest.main()
