"""Validate model replies and generate a final answer without tools."""
from langchain_core.messages import SystemMessage
from langchain_ollama import ChatOllama


def generation_metadata(reply):
    return {
        key: reply.response_metadata[key]
        for key in ("done", "done_reason", "prompt_eval_count", "eval_count")
        if key in reply.response_metadata
    }


def output_was_truncated(reply):
    return reply.response_metadata.get("done_reason") in {"length", "max_tokens"}


def reply_issue(reply, *, answer_is_valid=None, allow_tools=False, expect_done=False):
    metadata = reply.response_metadata
    if metadata.get("done") is False or (expect_done and metadata.get("done") is not True):
        return "incomplete_stream"
    if output_was_truncated(reply):
        if reply.tool_calls or reply.invalid_tool_calls or answer_is_valid is None or not answer_is_valid(reply):
            return "truncated_output"
        return None
    if reply.tool_calls and allow_tools:
        return None
    if reply.tool_calls or reply.invalid_tool_calls:
        return "invalid_tool_call"
    if not reply.text.strip():
        return "empty_output"
    if answer_is_valid is not None and not answer_is_valid(reply):
        return "unparsed"
    return None


class IncompleteReplyError(RuntimeError):
    def __init__(self, issue, reply, finalization_reason):
        super().__init__(f"最终回答未完成（{issue}，收束原因 {finalization_reason}）。")
        self.issue = issue
        self.reply = reply
        self.finalization_reason = finalization_reason


def generate_final_reply(model, messages, *, system_prompt, reason, instruction="", answer_is_valid=None):
    """Use the unbound model once and validate its visible answer."""
    guidance = (
        "请只依据已有资料给出简洁的最终回答。不得调用工具，也不得编造计算、引用或缺失资料。"
        "依据不足时如实说明。" + instruction
    )
    ollama = isinstance(model, ChatOllama)
    if ollama:
        model = model.bind(reasoning=False)
    system_message = SystemMessage(content=f"{system_prompt}\n\n{guidance}")
    reply = model.invoke([system_message, *messages])
    issue = reply_issue(reply, answer_is_valid=answer_is_valid, expect_done=ollama)
    if issue:
        raise IncompleteReplyError(issue, reply, reason)
    return reply.model_copy(update={"additional_kwargs": {**reply.additional_kwargs, "finalization_reason": reason}})
