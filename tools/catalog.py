"""供 Agent 查询 tianzhi-core 八字层实时 API 目录的元工具。"""
from __future__ import annotations

import json
from pathlib import Path
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
    """分层查询 tianzhi-core 目录，不执行计算。各层用途：
    calendar：节气、真太阳时和纪时；core：干支五行及基本关系；
    bazi：四柱、格局、用神、岁运和合盘；liuren：大六壬起课和占事；
    qimen：奇门遁甲定局排盘；ziwei：紫微斗数排盘、格局和运限。
    先用 layer 查看模块说明，再传 layer 和 module 查看该模块所有方法的完整说明；
    已知完整方法名时可用 name 直接查详情。无参数只列各层。
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
    if not module:
        with (Path(__file__).parent / "module_descriptions.json").open(encoding="utf-8") as stream:
            descriptions = json.load(stream).get(layer, {})
        return {"layer": layer, "modules": [
            {"name": name, "description": descriptions.get(name, "暂无模块说明，请查询模块方法。")}
            for name in modules
        ]}
    selected = catalog.tools(layer, module)
    return {"layer": layer, "module": module,
            "tools": [{"name": item.name, "description": catalog.describe(item.name)} for item in selected]}
