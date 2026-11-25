"""以 lunar-python 查询公历日期与通用黄历信息。"""
from datetime import date, time
import re
from typing import Annotated, Literal

from langchain_core.tools import tool
from lunar_python import Lunar, Solar


def make_date_tool(facts=None):
    @tool("get_date_info")
    def get_date_info(
        date_text: Annotated[str, "目标日期，格式 YYYY-MM-DD；农历闰月另设 leap_month=true。"],
        purpose: Annotated[Literal["birth", "target"], "日期用途：birth 出生日期或历法转换；target 用户要分析或查询的日期。必填。"],
        sect: Annotated[int, "黄历宜忌口径，1 为库默认，2 为精确节气月口径。"] = 1,
        calendar: Annotated[str, "输入历法：solar 公历（默认）或 lunar 农历。"] = "solar",
        leap_month: Annotated[bool, "农历日期是否为闰月。"] = False,
        time_text: Annotated[str, "可选的当地钟表时间 HH:MM；不提供则以零时查询。"] = "",
    ) -> dict:
        """查询日期的公农历、干支、节气及通用黄历宜忌和冲煞；不是个人命盘喜忌。
        问具体日期运势或黄历时应调用。时间视作当地钟表时间，不做时区换算或真太阳时修正。"""
        try:
            if purpose not in ("birth", "target"):
                raise ValueError("purpose 必须为 birth 或 target")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_text):
                raise ValueError("日期格式必须为 YYYY-MM-DD")
            year, month, day = (int(part) for part in date_text.split("-"))
            t = time.fromisoformat(time_text) if time_text else time(0, 0)
            if t.tzinfo is not None:
                raise ValueError("time_text 不接受时区，请输入当地钟表时间")
            if sect not in (1, 2):
                raise ValueError("sect 必须为 1 或 2")
            if calendar == "solar":
                if leap_month:
                    raise ValueError("公历不能设置闰月")
                d = date(year, month, day)
                solar = Solar.fromYmdHms(d.year, d.month, d.day, t.hour, t.minute, t.second)
                lunar = solar.getLunar()
            elif calendar == "lunar":
                try:
                    lunar = Lunar.fromYmdHms(year, -month if leap_month else month, day,
                                             t.hour, t.minute, t.second)
                except Exception as exc:
                    # lunar-python 对不存在的农历月或日期抛出普通 Exception。
                    raise ValueError(f"无效农历日期：{exc}") from exc
                solar = lunar.getSolar()
            else:
                raise ValueError("calendar 必须为 solar 或 lunar")
            prev, nxt = lunar.getPrevJie(), lunar.getNextJie()
            def jie_info(jie):
                return {"name": jie.getName(), "time": jie.getSolar().toYmdHms()} if jie else None
            result = {"purpose": purpose, "input_date": date_text, "input_calendar": calendar, "leap_month": leap_month,
                      "date": solar.toYmd(), "time": t.isoformat(), "lunar_date": lunar.toString(),
                      "year_ganzhi": lunar.getYearInGanZhiExact(),
                      "month_ganzhi": lunar.getMonthInGanZhiExact(),
                      "day_ganzhi": lunar.getDayInGanZhi(),
                      "previous_jie": jie_info(prev), "next_jie": jie_info(nxt),
                      "almanac": {"yi": lunar.getDayYi(sect), "ji": lunar.getDayJi(sect),
                                  "chong": lunar.getDayChongDesc(), "sha": lunar.getDaySha()},
                      "source": "lunar-python", "yi_ji_sect": sect,
                      "basis": "按输入当地钟表时间查询，未提供时间时为零时；未做时区或真太阳时修正。"}
        except (ValueError, TypeError, IndexError) as exc:
            return {"error": str(exc)}
        if facts is not None:
            facts.set_date(result)
        return result
    return get_date_info
