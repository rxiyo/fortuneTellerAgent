"""供 Agent 查询 tianzhi-core 八字层实时 API 目录的元工具。"""
from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from langchain_core.tools import tool
from tianzhi_core import catalog


# @tool 让 LangChain 为函数生成工具名称、说明和参数格式，供 Agent 读取。
@tool
def inspect_tianzhi_api(
    layer: Annotated[str, "要查看的 API 层，例如 bazi 或 calendar。留空列出所有层。"] = "",
    module: Annotated[str, "指定 layer 后，可用子模块名筛选，例如 luck_cycle 或 yongshen。"] = "",
    name: Annotated[str, "完整方法名，例如 bazi.chart.build_chart。提供时直接查看该方法的详情。"] = "",
) -> dict:
    """在选择排盘或规则计算方法前查询 tianzhi-core 的实时目录。
    无参数时列出可用术数层；layer 选择如 bazi、ziwei、qimen、liuren 或 calendar 的一层，
    module 按子模块筛选；name 指定完整方法名时返回签名、参数含义和返回值。此工具只查询，不执行计算。
    """
    layers = catalog.layers()
    if name:
        # 已知完整方法名时直接给单个接口的签名和说明。例如 bazi.chart.build_chart。
        available = {item.name for item in catalog.tools()}
        if name not in available:
            return {"error": f"目录中没有方法：{name}", "layers": list(layers)}
        return {"name": name, "description": catalog.describe(name)}
    if not layer:
        # 没指定层时只给总目录，模型可以再选 bazi、calendar 等层来查。
        return {"layers": {key: {"description": value, "method_count": len(catalog.tools(key))}
                           for key, value in layers.items()}}
    if layer not in layers:
        return {"error": f"没有这一层：{layer}", "layers": list(layers)}
    available = catalog.tools(layer)
    modules = sorted({item.module for item in available})
    if module and module not in modules:
        return {"error": f"没有这一模块：{layer}.{module}", "modules": modules}
    # 目录项原本是 dataclass。asdict 将它转成可随工具结果返回的普通字典。
    selected = (item for item in available if not module or item.module == module)
    return {"layer": layer, "module": module or None, "modules": modules,
            "tools": [asdict(item) for item in selected]}
