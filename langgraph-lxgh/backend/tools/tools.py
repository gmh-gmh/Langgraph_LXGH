from langchain_core.tools import tool
import aiohttp
import json
import os
from typing import Optional
from backend.utils.logger_handler import logger
from backend.rag.retriever import RerankRetriever
from backend.rag.vectorstore import load_vectorstore

AMAP_KEY = os.getenv("AMAP_KEY")
AMAP_GEO_API_URL = "https://restapi.amap.com/v3/geocode/geo"
AMAP_DRIVING_API_URL = "https://restapi.amap.com/v3/direction/driving"
AMAP_WALKING_API_URL = "https://restapi.amap.com/v3/direction/walking"
AMAP_CYCLING_API_URL = "https://restapi.amap.com/v3/direction/bicycling"
AMAP_TRANSIT_API_URL = "https://restapi.amap.com/v3/direction/transit/integrated"

# 高德地图网页版导航URL（用于生成可点击的路线超链接）
AMAP_WEB_NAVI_URL = "https://ditu.amap.com/dir"
AMAP_URI_NAVI_URL = "https://uri.amap.com/navigation"

# 出行方式映射（中文 → API参数）
TRAVEL_MODE_MAP = {
    "driving": "car",
    "驾车": "car",
    "开车": "car",
    "walking": "walk",
    "步行": "walk",
    "走路": "walk",
    "cycling": "ride",
    "骑行": "ride",
    "骑车": "ride",
    "自行车": "ride",
    "transit": "bus",
    "公交": "bus",
    "地铁": "bus",
    "公共交通": "bus",
    "坐车": "bus",
}

# 出行方式显示名
TRAVEL_MODE_LABEL = {
    "car": "驾车",
    "walk": "步行",
    "ride": "骑行",
    "bus": "公交地铁",
}

_vectorstore = load_vectorstore()
_retriever = RerankRetriever(_vectorstore)


async def simple_geocode(address):
    """简单的地理编码函数，不使用装饰器"""
    if not AMAP_KEY or AMAP_KEY == "your_amap_api_key":
        raise ValueError("请设置环境变量 AMAP_API_KEY")

    params = {
        "key": AMAP_KEY,
        "address": address
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(AMAP_GEO_API_URL, params=params) as response:
                response.raise_for_status()
                data = await response.json()

            logger.info(f"地理编码响应: {data}")
            
            if isinstance(data, dict) and data.get("status") == "1" and data.get("geocodes"):
                return data["geocodes"][0]["location"]
            else:
                info = data.get("info", "未知错误") if isinstance(data, dict) else "未知错误"
                raise ValueError(f"无法找到地址 '{address}': {info}")
        except Exception as e:
            logger.error(f"地理编码失败: {e}")
            raise ValueError(f"地理编码失败: {str(e)}")


@tool
async def geocode(address):
    """
    将地名转换为高德坐标。用于获取起点、终点、途经点的经纬度坐标。

    Args:
        address: 地点名称，如 "北京天安门"

    Returns:
        坐标字符串，格式为 "lng,lat"，如 "116.397455,39.909187"
    """
    return await simple_geocode(address)


@tool
async def search_poi_around(location, keywords, radius=2000):
    """
    在指定坐标周围搜索地点（POI）。

    Args:
        location: 中心点坐标，格式为 "lng,lat"
        keywords: 搜索关键词，如 "加油站"、"停车场"
        radius: 搜索半径（米），默认2000米

    Returns:
        符合条件的地点列表。
    """
    if not AMAP_KEY or AMAP_KEY == "your_amap_api_key":
        raise ValueError("请设置环境变量 AMAP_API_KEY")

    params = {
        "key": AMAP_KEY,
        "location": location,
        "keywords": keywords,
        "radius": radius
        # 移除硬编码的 types，让它根据关键词搜索所有类型
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://restapi.amap.com/v3/place/around", params=params) as response:
                response.raise_for_status()
                data = await response.json()

            pois = []
            if isinstance(data, dict) and data.get("pois"):
                pois_list = data["pois"]
                if isinstance(pois_list, list):
                    for i, poi in enumerate(pois_list[:5]):
                        if isinstance(poi, dict):
                            pois.append({
                                "type": "poi",
                                "id": f"poi_{i}",
                                "name": poi.get("name", ""),
                                "address": poi.get("address", ""),
                                "location": poi.get("location", ""),
                                "distance": poi.get("distance", 0),
                                "rating": poi.get("rating", ""),
                                "summary": poi.get("name", "")
                            })

            return pois
        except Exception as e:
            logger.error(f"POI搜索失败: {e}")
            return []


def _get_amap_route_url(travel_mode: str = "car") -> str:
    """根据出行方式获取对应的高德路径规划API URL"""
    urls = {
        "car": AMAP_DRIVING_API_URL,
        "walk": AMAP_WALKING_API_URL,
        "ride": AMAP_CYCLING_API_URL,
        "bus": AMAP_TRANSIT_API_URL,
    }
    return urls.get(travel_mode, AMAP_DRIVING_API_URL)


async def get_route(origin, destination, travel_mode: str = "car",
                    origin_name: str = "", dest_name: str = "",
                    avoid_tolls=False, strategy=10, waypoints=None):
    """
    统一路线规划API，支持驾车/步行/骑行/公交。

    Args:
        origin: 起点坐标 "lng,lat"
        destination: 终点坐标 "lng,lat"
        travel_mode: 出行方式 car / walk / ride / bus
        origin_name: 起点名称（用于生成超链接）
        dest_name: 终点名称（用于生成超链接）
        avoid_tolls: 是否避开收费路段（仅驾车）
        strategy: 驾车策略（仅驾车）
        waypoints: 途经点列表（仅驾车）

    Returns:
        统一格式的路线结果
    """
    if not AMAP_KEY or AMAP_KEY == "your_amap_api_key":
        raise ValueError("请设置环境变量 AMAP_API_KEY")

    api_url = _get_amap_route_url(travel_mode)
    params = {
        "key": AMAP_KEY,
        "origin": origin,
        "destination": destination,
    }

    if travel_mode == "car":
        params["strategy"] = strategy
        params["extensions"] = "all"
        params["show_fields"] = "cost,polyline"
        if avoid_tolls:
            params["strategy"] = 1
        if waypoints:
            params["waypoints"] = waypoints
    elif travel_mode == "bus":
        # 公交需要城市信息，用起点终点名称作为城市名
        params["city"] = origin_name or origin
        params["cityd"] = dest_name or destination
        params["extensions"] = "all"
    else:
        # 步行/骑行：只需要 origin, destination
        pass

    async with aiohttp.ClientSession() as session:
        try:
            logger.info(f"请求路线规划API: {api_url}, 模式: {travel_mode}")
            async with session.get(api_url, params=params) as response:
                response.raise_for_status()
                raw_response = await response.json()
            return _parse_route_response(raw_response, travel_mode, origin, destination,
                                         origin_name, dest_name)
        except aiohttp.ClientError as e:
            logger.error(f"网络请求失败: {e}")
            return {"status": 0, "error": str(e), "routes": []}
        except json.JSONDecodeError as e:
            logger.error(f"响应解析失败: {e}")
            return {"status": 0, "error": "无效的JSON响应", "routes": []}


async def get_driving_route(origin, destination, avoid_tolls=False, strategy=10,
                            waypoints=None, show_fields="cost,polyline"):
    """兼容：仅驾车路线规划，内部调用统一函数"""
    return await get_route(origin, destination, travel_mode="car",
                           avoid_tolls=avoid_tolls, strategy=strategy, waypoints=waypoints)


def _parse_route_response(raw_response, travel_mode: str, origin_coord: str, dest_coord: str,
                          origin_name: str = "", dest_name: str = ""):
    """
    统一解析路线规划API响应，支持驾车/步行/骑行/公交。

    Returns:
        {"status": 1, "routes": [...], "raw_response": ...}
    """
    if not isinstance(raw_response, dict):
        logger.error(f"原始响应不是字典: {raw_response}")
        return {"status": 0, "error": "无效的响应格式", "routes": []}

    status_code = raw_response.get("status")
    if status_code != "1":
        info = raw_response.get("info", "UNKNOWN_ERROR")
        infocode = raw_response.get("infocode", "")
        logger.error(f"API返回错误: status={status_code}, info={info}, infocode={infocode}")
        return {"status": 0, "error": f"[{infocode}] {info}", "routes": []}

    route_obj = raw_response.get("route", {}) or {}

    if travel_mode == "bus":
        # 公交API返回 transits 数组
        routes_data_raw = route_obj.get("transits", [])
    else:
        routes_data_raw = route_obj.get("paths", [])

    if not isinstance(routes_data_raw, list):
        routes_data_raw = []

    if not routes_data_raw:
        logger.warning("API返回成功，但未找到可用路线")
        return {"status": 1, "routes": [], "raw_response": raw_response}

    parsed_routes = []
    for idx, path in enumerate(routes_data_raw):
        if not isinstance(path, dict):
            continue

        if travel_mode == "bus":
            # 公交路线格式不同
            distance = int(float(path.get("distance", 0)))
            duration = int(float(path.get("duration", 0)))
            steps_raw = path.get("segments", []) if isinstance(path.get("segments"), list) else []
            tolls = 0
            polyline = ""
            # 从steps中组装polyline
            all_pts = []
            formatted_steps = []
            for seg in steps_raw:
                if isinstance(seg, dict):
                    instruction = seg.get("instruction", "")
                    seg_dist = int(float(seg.get("distance", 0)))
                    seg_dur = int(float(seg.get("duration", 0)))
                    seg_polyline = seg.get("polyline", "")
                    if seg_polyline:
                        all_pts.append(seg_polyline)
                    formatted_steps.append({
                        "instruction": instruction,
                        "distance": seg_dist,
                        "duration": seg_dur,
                        "polyline": seg_polyline,
                    })
            polyline = ";".join(all_pts)
            # 公交无tolls/restriction/traffic_lights
            restriction = ""
            traffic_lights = 0
        else:
            # 驾车/步行/骑行：通用字段
            distance = int(path.get("distance", 0))
            duration = int(path.get("duration", 0))
            tolls = float(path.get("tolls", 0)) if travel_mode == "car" else 0
            traffic_lights = int(path.get("traffic_lights", 0)) if travel_mode == "car" else 0
            restriction = path.get("restriction", "") if travel_mode == "car" else ""
            polyline = path.get("polyline", "")
            steps_raw = path.get("steps", [])
            if not isinstance(steps_raw, list):
                steps_raw = []

            formatted_steps = []
            all_pts = []
            for step in steps_raw:
                if isinstance(step, dict):
                    step_polyline = step.get("polyline", "")
                    if step_polyline:
                        all_pts.append(step_polyline)
                    formatted_steps.append({
                        "instruction": step.get("instruction", ""),
                        "road": step.get("road", ""),
                        "distance": int(step.get("distance", 0)),
                        "duration": int(step.get("duration", 0)),
                        "polyline": step_polyline,
                        "orientation": step.get("orientation", ""),
                        "action": step.get("action", "") if travel_mode == "car" else "",
                    })
            if not polyline and all_pts:
                polyline = ";".join(all_pts)

        # 生成高德网页版路线链接（带地名和出行方式）
        map_url = generate_route_map_link(
            origin_coord, dest_coord,
            origin_name=origin_name, dest_name=dest_name,
            travel_mode=travel_mode
        )

        # 生成路线静态地图图片URL（只有驾车和骑行有polyline可画）
        route_image_url = generate_route_static_map(origin_coord, dest_coord, polyline) if polyline else ""

        # 出行方式显示名
        mode_label = TRAVEL_MODE_LABEL.get(travel_mode, "驾车")

        # summary
        dist_km = distance / 1000
        dur_min = duration / 60
        summary = f"{mode_label} · {dist_km:.1f}公里 · {dur_min:.0f}分钟"

        parsed_routes.append({
            "type": "route",
            "id": f"route_{idx}",
            "summary": summary,
            "mode": travel_mode,
            "mode_label": mode_label,
            "distance": distance,
            "duration": duration,
            "tolls": tolls,
            "traffic_lights": traffic_lights,
            "restriction": restriction,
            "polyline": polyline,
            "steps": formatted_steps,
            "map_url": map_url,
            "route_image_url": route_image_url,
            "origin_coord": origin_coord,
            "dest_coord": dest_coord,
            "origin_name": origin_name or "",
            "dest_name": dest_name or "",
        })

    logger.info(f"成功解析 {len(parsed_routes)} 条{travel_mode}路线")
    return {"status": 1, "routes": parsed_routes, "raw_response": raw_response}


def generate_route_map_link(origin_coord, dest_coord,
                            origin_name: str = "", dest_name: str = "",
                            travel_mode: str = "car"):
    """
    生成高德地图网页版导航链接。
    带上起点终点名称后，用户打开页面无需再输入。

    Args:
        origin_coord: 起点坐标 "lng,lat"
        dest_coord: 终点坐标 "lng,lat"
        origin_name: 起点名称（填入后高德自动显示）
        dest_name: 终点名称
        travel_mode: 出行方式 car/walk/ride/bus

    Returns:
        高德地图网页版导航链接
    """
    if not origin_coord or not dest_coord:
        return ""

    try:
        origin_parts = origin_coord.split(",")
        dest_parts = dest_coord.split(",")

        if len(origin_parts) != 2 or len(dest_parts) != 2:
            logger.warning(f"坐标格式错误 - origin: {origin_coord}, destination: {dest_coord}")
            return ""

        origin_lng, origin_lat = origin_parts
        dest_lng, dest_lat = dest_parts

        # 高德地图 type 参数
        nav_type = {"car": "car", "walk": "walk", "ride": "ride", "bus": "bus"}.get(travel_mode, "car")

        # 构建参数列表，带地名用户打开时不用再输入
        # 高德定向规约：from[name] / to[name] 填名称，from[lng]/from[lat]/to[lng]/to[lat] 填坐标
        import urllib.parse
        params = []
        if origin_name:
            params.append(f"from%5Bname%5D={urllib.parse.quote(origin_name)}")
        if dest_name:
            params.append(f"to%5Bname%5D={urllib.parse.quote(dest_name)}")
        params.extend([
            f"from%5Blng%5D={origin_lng}",
            f"from%5Blat%5D={origin_lat}",
            f"to%5Blng%5D={dest_lng}",
            f"to%5Blat%5D={dest_lat}",
            f"type={nav_type}",
        ])

        web_url = f"{AMAP_WEB_NAVI_URL}?{'&'.join(params)}"
        logger.info(f"生成路线链接: {web_url}")
        return web_url

    except Exception as e:
        logger.error(f"生成路线链接失败: {e}")
        return ""


def generate_route_static_map(origin_coord: str, dest_coord: str, polyline: str, size: str = "750x300") -> str:
    """
    生成高德静态地图URL，在真实地图上绘制路线折线。

    Args:
        origin_coord: 起点坐标 "lng,lat"
        dest_coord: 终点坐标 "lng,lat"
        polyline: 路线折线坐标串 "lng1,lat1;lng2,lat2;..."
        size: 图片尺寸，默认 "750x300"

    Returns:
        静态地图图片URL，若参数无效返回空字符串
    """
    if not AMAP_KEY or AMAP_KEY == "your_amap_api_key" or not polyline or not origin_coord or not dest_coord:
        return ""

    try:
        # 简化折线：点太多会导致URL超长，采样到最多80个点
        points = polyline.split(";")
        if len(points) > 80:
            step = len(points) // 80
            points = points[::step]

        # 起点红色标注 A，终点绿色标注 B
        markers = f"markers=mid,0xFF0000,A:{origin_coord}|mid,0x00FF00,B:{dest_coord}"

        # 路线折线：宽度6px，蓝色#0066FF，透明度0.8
        path_str = ";".join(points)
        paths = f"paths=6,0x0066FF,0.8,,:{path_str}"

        url = (
            f"https://restapi.amap.com/v3/staticmap?"
            f"size={size}&{markers}&{paths}&key={AMAP_KEY}"
        )
        logger.info(f"生成静态地图URL ({len(points)} 个轨迹点)")
        return url

    except Exception as e:
        logger.error(f"生成静态地图失败: {e}")
        return ""


@tool
def retrieve_traffic_knowledge(query):
    """
    查询交通管制，道路施工、景区开放等实时信息。
    
    Args:
        query: 自然语言查询语句（如 "北京到八达岭 沿途交通管制"）
    
    Returns:
        最相关的前5条文档内容（用换行符分隔）。
    """
    docs = _retriever.retrieve(query, top_n=5)
    if not docs:
        return "未找到相关的交通/景区信息。"
    return "\n\n".join([f"- {doc.page_content}" for doc in docs])


@tool
def retrieve_scenic_info(query):
    """
    从本地知识库检索与行程相关的实时信息，包括交通管制，道路施工、
    景区开放时间、充电桩位置等。
    
    Args:
        query: 自然语言查询，如 "北京到八达岭 沿途交通管制"。
    
    Returns:
        最相关的前 3 条知识片段，以换行分隔。
    """
    docs = _retriever.retrieve(query, top_n=3)
    if not docs:
        return "未找到相关景区信息。"
    return "\n\n".join([f"- {doc.page_content}" for doc in docs])
