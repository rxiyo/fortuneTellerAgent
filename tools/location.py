"""Open-Meteo 省市地名查询；只返回指定省级地区的候选。"""
import json
import re
from typing import Annotated
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from langchain_core.tools import tool


GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"


def _region_key(value):
    """规范常见中文行政区后缀；不使用子串匹配，以免误认其他省。"""
    value = re.sub(r"\s+", "", value).casefold()
    for suffix in ("维吾尔自治区", "壮族自治区", "回族自治区", "特别行政区", "自治区", "省", "市"):
        if value.endswith(suffix):
            return value[:-len(suffix)]
    return value


def make_location_tool(facts=None):
    @tool("lookup_location")
    def lookup_location(
        name: Annotated[str, "单独填写城市或区县，优先使用完整名称（如佛山市），也可用已知拼音 Foshan；不要包含省份或逗号。"],
        province: Annotated[str, "单独填写用户指定的省、自治区、直辖市或一级行政区，例如广东；不得填入城市名或猜测。"],
        country_code: Annotated[str, "已知国家时填写两位国家代码；中国为 CN。"] = "",
    ) -> dict:
        """按城市和省级地区一起查询 WGS84 经纬度与时区。必须分别提供城市 name 和省级地区 province；缺失时询问用户。
        例如“广东佛山”先查询 name=佛山市、province=广东、country_code=CN，不要把“广东佛山”放在 name 中。
        两字地名可能只做精确匹配而漏掉带行政后缀的城市；无匹配时可改用完整行政名称或已知拼音（如 Foshan）重试，保持省份不变。
        工具先按城市、省份查询，必要时按城市重试，并只返回省份一致的候选；核对 name、admin1、admin2 与用户的出生地。
        多个候选无法确定时请用户澄清；多种名称仍未匹配、网络报错或时区缺失时，请用户补充资料或经度，不得猜测坐标或声称已做真太阳时修正。
        Open-Meteo/GeoNames 坐标是地名代表点，非精确出生地址；返回候选不等于用户已确认地点。"""
        name, province = name.strip(), province.strip()
        if len(name) < 2 or len(province) < 2:
            return {"error": "请输入城市或区县名及所属省级地区；地点不明确时请先询问用户。"}
        if "," in name or "," in province:
            return {"error": "城市与省级地区请分别填写，不要包含逗号。"}
        params = {"name": f"{name}, {province}", "count": 100, "language": "zh", "format": "json"}
        if country_code:
            if len(country_code) != 2 or not country_code.isascii() or not country_code.isalpha():
                return {"error": "country_code 必须是两位国家代码。"}
            params["countryCode"] = country_code.upper()

        def request(query):
            args = {**params, "name": query}
            req = Request(GEO_URL + "?" + urlencode(args), headers={"User-Agent": "metaphysics-agent/1.0"})
            with urlopen(req, timeout=10) as response:
                return json.load(response).get("results", [])

        try:
            candidates = request(params["name"])
            # API 的省级地区名称必须完全匹配；别名不匹配时按城市重试，仍严格核对返回的省。
            if not candidates:
                candidates = request(name)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            return {"error": f"地点查询失败：{exc}；可要求用户提供经度或稍后重试。"}
        fields = ("id", "name", "country", "country_code", "admin1", "admin2", "admin3", "admin4",
                  "latitude", "longitude", "timezone", "feature_code")
        matches = [{key: item[key] for key in fields if key in item} for item in candidates
                   if _region_key(str(item.get("admin1", ""))) == _region_key(province)]
        result = {"query": name, "province": province, "matches": matches,
                  "source": "Open-Meteo Geocoding / GeoNames", "coordinate_system": "WGS84",
                  "precision": "地名代表点，非具体出生地址",
                  "notice": "只返回省级地区一致的候选；无匹配或多个候选时请核对省市或询问用户。"}
        if facts is not None:
            facts.set_location(result)
        return result
    return lookup_location
