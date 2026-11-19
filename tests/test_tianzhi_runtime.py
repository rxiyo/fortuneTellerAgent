import unittest

from tianzhi_core import catalog

from tools.catalog import inspect_tianzhi_api
from tools.tianzhi_runtime import TianzhiRuntime


class TianzhiRuntimeTests(unittest.TestCase):
    def test_catalog_exposes_all_layers(self):
        layers = inspect_tianzhi_api.invoke({})["layers"]
        self.assertEqual(set(layers), set(catalog.layers()))
        self.assertEqual(sum(item["method_count"] for item in layers.values()), len(catalog.tools()))

    def test_chained_calls_keep_domain_objects(self):
        # 先排盘得到 r1，再用不同引用写法调用用神和大运，验证原始对象能正确传递。
        runtime = TianzhiRuntime()
        chart = runtime.call("bazi.chart.build_chart", {"dt": "2000-01-01 12:00", "use_true_solar": False})
        self.assertEqual(chart["ref"], "r1")
        self.assertIn("quad", chart["properties"])
        yongshen = runtime.call("bazi.yongshen.select", {
            "quad": {"$ref": "r1.quad"}, "month_siling": {"$ref": "r1.siling"},
        })
        self.assertEqual(yongshen["result"]["yong"], "木")
        auto_quad = runtime.call("bazi.yongshen.select", {"quad": {"$ref": "r1"}})
        self.assertEqual(auto_quad["result"]["yong"], "木")
        self.assertEqual(auto_quad["result"]["evidence"], yongshen["result"]["evidence"])
        compact_ref = runtime.call("bazi.yongshen.select", {"$ref": "r1"})
        self.assertEqual(compact_ref["result"]["yong"], "木")
        dayun = runtime.call("bazi.luck_cycle.dayun_list", {"chart": {"$ref": "r1"}, "count": 2})
        self.assertEqual(len(dayun["result"]), 2)

    def test_other_layers_and_invalid_method(self):
        # 用其他层验证通用执行入口，也检查错误方法名和未知引用的回执。
        runtime = TianzhiRuntime()
        self.assertEqual(runtime.call("qimen.ju.day_ganzhi", {"d": "2024-01-01"})["result"], "甲子")
        self.assertIn("result", runtime.call("ziwei.chart.kuiyue", {"gan": "甲"}))
        self.assertIn("error", runtime.call("os.system", {"command": "echo test"}))
        self.assertIn("error", runtime.call("bazi.yongshen.select", {"quad": {"$ref": "unknown.quad"}}))


if __name__ == "__main__":
    unittest.main()
