"""每个会话唯一的当前命盘与目标日期；由工具回执更新。"""
from copy import deepcopy
from threading import RLock


class SessionFacts:
    def __init__(self, initial=None):
        self._lock = RLock()
        self._facts = {"chart": None, "chart_inputs": None, "calculation_results": {},
                       "date_info": None, "birth_date_info": None, "location_search": None}
        if initial:
            self._facts.update(deepcopy(initial))

    def snapshot(self):
        with self._lock:
            return deepcopy(self._facts)

    def set_chart(self, chart, inputs):
        with self._lock:
            birth_date = self._facts.get("birth_date_info")
            input_dt = inputs.get("dt") if isinstance(inputs, dict) else None
            if birth_date and isinstance(input_dt, str) and birth_date.get("date") != input_dt[:10]:
                self._facts["birth_date_info"] = None
            self._facts["chart"] = deepcopy(chart)
            self._facts["chart_inputs"] = deepcopy(inputs)
            self._facts["calculation_results"] = {}

    def set_calculation(self, name, result):
        with self._lock:
            self._facts["calculation_results"][name] = deepcopy(result)

    def set_date(self, result):
        with self._lock:
            if result.get("purpose") == "birth":
                self._facts["birth_date_info"] = deepcopy(result)
            elif result.get("purpose") == "target":
                self._facts["date_info"] = deepcopy(result)

    def set_location(self, result):
        with self._lock:
            # 候选保留在工具消息，不把无关的同名地点写进命盘与证据。
            # 已排出的命盘仍使用旧地点时，新查询不应改写该命盘的地点来源。
            if self._facts.get("chart") is not None:
                return
            self._facts["location_search"] = {
                "query": result.get("query"), "province": result.get("province"),
                "status": "awaiting_chart" if result.get("matches") else "no_match",
                "candidate_count": len(result.get("matches", [])),
            }

    def set_chart_location(self, result):
        with self._lock:
            self._facts["location_search"] = deepcopy(result)
