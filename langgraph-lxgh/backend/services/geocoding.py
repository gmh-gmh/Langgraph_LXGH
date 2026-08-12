"""服务层 — 地理编码与路线规划"""
import aiohttp
import os
from backend.utils.logger_handler import logger

AMAP_KEY = os.getenv("AMAP_KEY")
AMAP_GEO_API_URL = "https://restapi.amap.com/v3/geocode/geo"


async def geocode(address: str) -> str:
    """地址转坐标，返回 'lng,lat'"""
    if not AMAP_KEY:
        raise ValueError("请设置环境变量 AMAP_KEY")
    params = {"key": AMAP_KEY, "address": address}
    async with aiohttp.ClientSession() as session:
        async with session.get(AMAP_GEO_API_URL, params=params) as resp:
            data = await resp.json()
        if data.get("status") == "1" and data.get("geocodes"):
            return data["geocodes"][0]["location"]
        raise ValueError(f"无法找到地址 '{address}'")


async def plan_route(origin: str, destination: str, travel_mode: str = "car",
                     origin_name: str = "", dest_name: str = "") -> dict:
    """统一路线规划，支持 car/walk/ride/bus"""
    if not AMAP_KEY:
        raise ValueError("请设置环境变量 AMAP_KEY")

    urls = {
        "car": "https://restapi.amap.com/v3/direction/driving",
        "walk": "https://restapi.amap.com/v3/direction/walking",
        "ride": "https://restapi.amap.com/v3/direction/bicycling",
        "bus": "https://restapi.amap.com/v3/direction/transit/integrated",
    }
    api_url = urls.get(travel_mode, urls["car"])
    params = {"key": AMAP_KEY, "origin": origin, "destination": destination}

    if travel_mode == "car":
        params["strategy"] = 10
        params["extensions"] = "all"
    elif travel_mode == "bus":
        params["city"] = origin_name or origin
        params["cityd"] = dest_name or destination
        params["extensions"] = "all"

    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, params=params) as resp:
            raw = await resp.json()
        return _parse_route(raw, travel_mode, origin, destination, origin_name, dest_name)


def _parse_route(raw: dict, mode: str, origin_coord: str, dest_coord: str,
                 origin_name: str = "", dest_name: str = "") -> dict:
    """解析高德路线 API 响应为统一格式"""
    if not isinstance(raw, dict) or raw.get("status") != "1":
        return {"status": 0, "error": raw.get("info", "查询失败"), "routes": []}

    route_obj = raw.get("route", {}) or {}
    routes_raw = route_obj.get("transits" if mode == "bus" else "paths", [])
    if not isinstance(routes_raw, list) or not routes_raw:
        return {"status": 1, "routes": [], "raw_response": raw}

    parsed = []
    for idx, path in enumerate(routes_raw):
        if not isinstance(path, dict):
            continue
        if mode == "bus":
            dist = int(float(path.get("distance", 0)))
            dur = int(float(path.get("duration", 0)))
            steps_raw = path.get("segments", [])
            polyline = ";".join(s.get("polyline", "") for s in steps_raw if isinstance(s, dict))
            tolls = 0
        else:
            dist = int(path.get("distance", 0))
            dur = int(path.get("duration", 0))
            tolls = float(path.get("tolls", 0)) if mode == "car" else 0
            polyline = path.get("polyline", "")
            steps_raw = path.get("steps", [])

        parsed.append({
            "type": "route", "id": f"route_{idx}",
            "mode": mode, "mode_label": {"car": "驾车", "walk": "步行", "ride": "骑行", "bus": "公交"}.get(mode, mode),
            "distance": dist, "duration": dur, "tolls": tolls,
            "polyline": polyline,
            "origin_coord": origin_coord, "dest_coord": dest_coord,
            "origin_name": origin_name, "dest_name": dest_name,
            "map_url": _build_map_url(origin_coord, dest_coord, origin_name, dest_name, mode),
        })
    return {"status": 1, "routes": parsed, "raw_response": raw}


def _build_map_url(origin_coord, dest_coord, origin_name, dest_name, travel_mode):
    """生成高德地图导航链接"""
    import urllib.parse
    try:
        olng, olat = origin_coord.split(",")
        dlng, dlat = dest_coord.split(",")
        nav_type = {"car": "car", "walk": "walk", "ride": "ride", "bus": "bus"}.get(travel_mode, "car")
        params = []
        if origin_name: params.append(f"from%5Bname%5D={urllib.parse.quote(origin_name)}")
        if dest_name: params.append(f"to%5Bname%5D={urllib.parse.quote(dest_name)}")
        params.extend([f"from%5Blng%5D={olng}", f"from%5Blat%5D={olat}",
                       f"to%5Blng%5D={dlng}", f"to%5Blat%5D={dlat}", f"type={nav_type}"])
        return f"https://ditu.amap.com/dir?{'&'.join(params)}"
    except Exception:
        return ""
