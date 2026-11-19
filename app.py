"""终端入口。输入 /reset 开启新会话，输入 /quit 退出。"""
import os

from langchain_ollama import ChatOllama
from langgraph.errors import GraphRecursionError

from agent import create_graph
from agent_trace import SessionTrace


def main():
    # 1. 读取本次运行的模型配置。终端里设置的环境变量优先于代码里的默认值。
    model_name = os.environ.get("OLLAMA_MODEL", "deepseek-r1:8b")
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model = ChatOllama(
        model=model_name,
        base_url=base_url,
        temperature=0,
        # num_ctx 是模型的上下文容量。DeepSeek 的思考文本由接口单独返回。
        num_ctx=int(os.environ.get("OLLAMA_NUM_CTX", "16384")),
        # Qwen 的 Instruct-2507 是非思考版。其他 Qwen3 可请求独立的 thinking 字段。
        reasoning=True if model_name.startswith("deepseek-r1") or (
            model_name.startswith("qwen3") and "instruct" not in model_name.lower()
        ) else None,
    )
    # 2. 创建一个会话专用的执行图和日志。messages 保存已完成各轮的消息。
    graph = create_graph(model)
    trace = SessionTrace(model_name)
    messages = []
    print(f"八字 Agent（Ollama: {model_name}）。输入 /reset 清空，/quit 退出。")
    print(f"执行日志：{trace.path}")
    while True:
        # 3. 读取用户输入。空行直接跳过，/quit 和 /reset 在本地处理。
        try:
            user_input = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            break
        if not user_input:
            continue
        if user_input in ("/quit", "/exit"):
            break
        if user_input == "/reset":
            # 新图有自己的排盘对象表，上一会话的 r1 等引用也随之失效。
            graph = create_graph(model)
            trace = SessionTrace(model_name)
            messages = []
            print(f"已开启新对话。执行日志：{trace.path}")
            continue

        # 4. 执行这一轮并同步写日志。只有运行成功才用返回的消息替换历史。
        try:
            messages = trace.run_turn(graph, messages, user_input)
        except GraphRecursionError:
            print("\n本轮工具调用次数达到上限，请缩小问题范围后重试。")
            continue
        except KeyboardInterrupt:
            print("\n已中断本轮。")
            continue
        except Exception as exc:
            print(f"\n运行失败：{exc}")
            continue

        # 工具调用和结果已经写入文件。终端从最后一条消息取出模型回复。
        print("\n助手：" + messages[-1].text)


if __name__ == "__main__":
    main()
