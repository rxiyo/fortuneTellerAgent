"""把 tianzhi-core 目录中的方法按需开放为一个有状态的 LangChain 工具。"""
from __future__ import annotations

import dataclasses
import importlib
import inspect
import json
from collections.abc import Mapping
from datetime import date, datetime
from enum import Enum
from threading import Lock
from typing import Annotated, Any, get_type_hints

from langchain_core.tools import tool
from tianzhi_core import catalog
from tianzhi_core.bazi.chart import Chart


def _jsonable(value: Any) -> Any:
    # tianzhi-core 返回的日期、数据类和容器要转成模型能读的 JSON 数据。
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return _jsonable(value.value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {field.name: _jsonable(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item) for item in value]
    return str(value)


class TianzhiRuntime:
    """目录为允许列表；调用结果用 r1、r2 等引用在本次会话中传递。"""

    def __init__(self) -> None:
        # 原始对象表以 r1、r2 等为键。后续计算能直接取用真实的 Chart 对象。
        self._objects: dict[str, Any] = {}
        self._lock = Lock()

    def _resolve_ref(self, reference: str) -> Any:
        # r1 取整份结果，r1.quad 取其四柱，r2.0 可以取列表中的第一项。
        parts = reference.split(".")
        if not parts or parts[0] not in self._objects:
            raise ValueError(f"未知结果引用：{reference}")
        value = self._objects[parts[0]]
        for part in parts[1:]:
            # 根据当前对象的类型，把下一段当成字典键、列表下标或公开属性。
            if part.startswith("_"):
                raise ValueError(f"不允许访问私有属性：{part}")
            if isinstance(value, Mapping):
                value = value[part]
            elif isinstance(value, (list, tuple)) and part.isdecimal():
                value = value[int(part)]
            elif dataclasses.is_dataclass(value) or isinstance(getattr(type(value), part, None), property):
                value = getattr(value, part)
            else:
                raise ValueError(f"结果引用没有此字段：{reference}")
            if callable(value):
                raise ValueError(f"结果引用不能指向方法：{reference}")
        return value

    def _resolve(self, value: Any) -> Any:
        # 递归检查参数。引用对象可以放在普通字典或列表里，其他值原样保留。
        if isinstance(value, dict):
            if set(value) == {"$ref"}:
                reference = value["$ref"]
                if not isinstance(reference, str):
                    raise ValueError("$ref 必须是字符串")
                return self._resolve_ref(reference)
            return {key: self._resolve(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._resolve(item) for item in value]
        return value

    def call(self, name: str, arguments: dict[str, Any]) -> dict:
        """执行目录中的公开函数；arguments 可用 {"$ref": "r1.quad"} 引用先前结果。"""
        # 1. 先用库的公开目录确认方法存在，再加载它所在的模块。
        available = {item.name: item for item in catalog.tools()}
        item = available.get(name)
        if item is None:
            return {"error": f"目录中没有可调用方法：{name}"}
        if not isinstance(arguments, dict):
            return {"error": "arguments 必须是 JSON 对象", "signature": item.signature}
        try:
            module = importlib.import_module(f"tianzhi_core.{item.layer}.{item.module}")
            function = getattr(module, name.rsplit(".", 1)[1])
            signature = inspect.signature(function)
            hints = get_type_hints(function)
            if set(arguments) == {"$ref"}:
                # 只有一个必填参数时，允许直接传 {"$ref": "r1"} 作为简写。
                required = [param.name for param in signature.parameters.values()
                            if param.default is inspect.Parameter.empty]
                if len(required) == 1:
                    arguments = {required[0]: arguments}
            # 2. 还原引用，按函数签名补齐对象形式和日期类型，再实际调用。
            resolved = {key: self._resolve(value) for key, value in arguments.items()}
            for key, value in list(resolved.items()):
                if key.endswith("quad") and hasattr(value, "quad"):
                    # 接口要 Quad 而模型传入整张 Chart 时，从 Chart 取四柱和可用的月令司令。
                    if key == "quad" and "month_siling" in signature.parameters and "month_siling" not in resolved:
                        resolved["month_siling"] = getattr(value, "siling", None)
                    value = resolved[key] = value.quad
                hint = hints.get(key)
                if hint is datetime and isinstance(value, str):
                    resolved[key] = datetime.fromisoformat(value)
                elif hint is date and isinstance(value, str):
                    resolved[key] = date.fromisoformat(value)
            signature.bind(**resolved)
            result = function(**resolved)
            # 3. 给模型生成可阅读的快照，给下一次工具调用保留原始对象。
            serialized = _jsonable(result)
            if isinstance(result, Chart):
                # 库的快照补充十神、藏干和司令，原对象仍通过 ref 传给后续计算。
                serialized = {**_jsonable(result.to_dict()), **serialized}
        except (AttributeError, ImportError, IndexError, KeyError, TypeError, ValueError) as exc:
            # 把错误和签名交回模型，模型可以修正参数后再调用。
            return {"error": str(exc), "signature": item.signature}
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}", "signature": item.signature}

        # 同一轮独立的工具调用可能并发，集中分配结果引用。
        with self._lock:
            reference = f"r{len(self._objects) + 1}"
            self._objects[reference] = result
        # 4. 大结果只把预览发给模型，原始对象仍可通过 ref 读取具体字段。
        encoded = json.dumps(serialized, ensure_ascii=False, default=str)
        if len(encoded) > 20000:
            serialized = {"preview": encoded[:20000], "truncated": True}
        properties = sorted(key for key, member in vars(type(result)).items()
                            if isinstance(member, property) and not key.startswith("_"))
        return {"name": name, "ref": reference, "result": serialized, "properties": properties}

    def as_tool(self):
        """返回可传给 ChatOllama.bind_tools 的有状态工具。"""
        # 闭包捕获当前会话的 runtime，后续每次调用都访问同一份对象表。
        runtime = self

        @tool("call_tianzhi_api")
        def call_tianzhi_api(
            name: Annotated[str, "目录中的完整方法名，例如 bazi.chart.build_chart。"],
            arguments: Annotated[
                dict[str, Any],
                '以所选方法的参数名为键，按目录签名填写值。'
                '使用前次命盘时可传 {"chart":{"$ref":"r1"}}。无参数的方法传 {}。',
            ],
        ) -> dict:
            """需要排盘、岁运或其他规则计算时，执行 tianzhi-core 目录中的公开方法。
            先使用 inspect_tianzhi_api 确认方法和参数。name 是完整方法名，arguments 是参数名到值的 JSON 对象。
            返回 name、ref、result 和可引用的 properties。遇到 error 时检查参数或改用其他方法。
            日期和时间参数使用 ISO 格式。每个方法的具体参数类型和含义以目录详情为准。
            build_chart 的 dt 按出生地钟表时间和实际时区传入，例如北京时间中午是 2000-01-01T12:00:00+08:00。
            gender=0 表示男，gender=1 表示女；用户指定不做真太阳时修正时，传 use_true_solar=false。
            Chart、Quad 等参数可用 {"$ref":"r1"} 或 {"$ref":"r1.quad"} 引用前一个工具结果。
            """
            return runtime.call(name, arguments)

        return call_tianzhi_api
