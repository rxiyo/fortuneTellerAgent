"""在 Jupyter 中观察 Ollama 流式生成进度，不输出模型思考内容。"""
from __future__ import annotations

import time
from typing import Optional

from ollama import Client


def ollama_chat_stream(
    messages,
    *,
    model: str,
    host: str,
    timeout: float = 600,
    json_mode: bool = False,
    progress_every: float = 5,
    max_predict: Optional[int] = None,
) -> str:
    """流式收集最终回答，打印阶段与 Ollama 返回的 token/耗时统计。

    timeout 是底层网络读写超时，流式模式下不是总耗时上限。
    未收到首个流式事件时无法定时打印进度；字符数仅作状态展示，不等于 token 数。
    max_predict 不设置时保留 Ollama 默认；设置后可能在 JSON 未完成时截断。
    """
    options = {"temperature": 0}
    if max_predict is not None:
        if max_predict <= 0:
            raise ValueError("max_predict 必须是正整数，或保持 None 使用默认值。")
        options["num_predict"] = max_predict

    start = time.monotonic()
    last_update = start
    first_event = None
    first_content = None
    reasoning_chars = 0
    content_parts = []
    last_part = None
    print(f"[Ollama] 开始请求：{model}；等待首个流式事件…", flush=True)

    # 只收集最终内容，不打印 thinking 文本，避免在 notebook 留下冗长推理。
    stream = Client(host=host, timeout=timeout).chat(
        model=model,
        messages=messages,
        format="json" if json_mode else "",
        options=options,
        stream=True,
    )
    for part in stream:
        now = time.monotonic()
        last_part = part
        if first_event is None:
            first_event = now - start
            print(f"[Ollama] 收到首个流式事件：{first_event:.1f} 秒", flush=True)
        message = getattr(part, "message", None)
        reasoning = getattr(message, "thinking", None) or ""
        content = getattr(message, "content", None) or ""
        reasoning_chars += len(reasoning)
        if content:
            if first_content is None:
                first_content = now - start
                print(f"[Ollama] 开始返回最终内容：{first_content:.1f} 秒", flush=True)
            content_parts.append(content)
        if now - last_update >= progress_every:
            stage = "最终内容" if first_content is not None else "思考/等待最终内容"
            print(f"[Ollama] {stage}；已用 {now-start:.1f} 秒；"
                  f"思考字符 {reasoning_chars}；最终内容字符 {sum(map(len, content_parts))}", flush=True)
            last_update = now

    elapsed = time.monotonic() - start
    if last_part is None or not getattr(last_part, "done", False):
        raise RuntimeError("Ollama 流未返回完成事件；请检查服务或网络连接。")
    reason = getattr(last_part, "done_reason", None)
    prompt_count = getattr(last_part, "prompt_eval_count", None)
    eval_count = getattr(last_part, "eval_count", None)
    load_ns = getattr(last_part, "load_duration", None)
    prompt_ns = getattr(last_part, "prompt_eval_duration", None)
    eval_ns = getattr(last_part, "eval_duration", None)
    def seconds(value):
        return round(value / 1_000_000_000, 2) if value is not None else None
    stats = {
        "墙钟耗时（秒）": round(elapsed, 2), "首事件（秒）": first_event,
        "首个最终内容（秒）": first_content, "结束原因": reason,
        "输入 token": prompt_count, "生成 token": eval_count,
        "加载耗时（秒）": seconds(load_ns), "输入处理耗时（秒）": seconds(prompt_ns),
        "生成耗时（秒）": seconds(eval_ns),
        "生成速度（token/秒）": round(eval_count / (eval_ns / 1e9), 2)
            if eval_count is not None and eval_ns else None,
    }
    print("[Ollama] 生成统计：", stats, flush=True)
    # 截断时不可把不完整内容当成有效 JSON 或完整回答。
    if reason == "length":
        raise RuntimeError("Ollama 达到生成长度上限，输出可能不完整；请检查统计并调整上限。")
    text = "".join(content_parts).strip()
    if not text:
        raise RuntimeError("Ollama 未返回最终内容；请检查模型与生成统计。")
    return text
