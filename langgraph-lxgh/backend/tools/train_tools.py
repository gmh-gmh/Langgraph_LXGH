"""12306 火车票查询工具（直接 JSON-RPC 通信，不依赖 MCP SDK）"""
import json
import asyncio
import datetime
from typing import Optional

_MCP_PROCESS: Optional[asyncio.subprocess.Process] = None
_MCP_LOCK = asyncio.Lock()
_request_id = 0


async def _ensure_server():
    """确保 12306-mcp 子进程在运行"""
    global _MCP_PROCESS
    if _MCP_PROCESS and _MCP_PROCESS.returncode is None:
        return

    async with _MCP_LOCK:
        if _MCP_PROCESS and _MCP_PROCESS.returncode is None:
            return

        print("[12306] 启动 12306-mcp 服务...")
        _MCP_PROCESS = await asyncio.create_subprocess_shell(
            "npx -y 12306-mcp",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        # 等服务器初始化（发一条空请求等响应）
        await asyncio.sleep(3)
        print(f"[12306] 服务已启动, PID={_MCP_PROCESS.pid}")


async def warmup():
    """预热：确保 MCP 服务器已就绪（请求第一个 tool 前调用）"""
    global _MCP_PROCESS
    await _ensure_server()
    # 发一条简单请求验证服务是否就绪
    try:
        ping = json.dumps({"jsonrpc":"2.0","id":0,"method":"tools/list","params":{}}) + "\n"
        if _MCP_PROCESS and _MCP_PROCESS.stdin and _MCP_PROCESS.stdout:
            _MCP_PROCESS.stdin.write(ping.encode("utf-8"))
            await _MCP_PROCESS.stdin.drain()
            resp = await asyncio.wait_for(_MCP_PROCESS.stdout.readline(), timeout=20)
            data = json.loads(resp.decode("utf-8"))
            if "result" in data:
                tools = [t.get("name") for t in data["result"].get("tools", [])]
                print(f"[12306] 服务就绪，可用工具: {tools}")
                return True
    except Exception as e:
        print(f"[12306] 服务尚未就绪: {e}")
    return False


async def _call_mcp(tool_name: str, args: dict, timeout: int = 30) -> str:
    """调用 MCP 工具（纯 JSON-RPC，无需 MCP SDK）"""
    global _request_id
    await _ensure_server()

    _request_id += 1
    request = {
        "jsonrpc": "2.0",
        "id": _request_id,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": args,
        }
    }

    payload = json.dumps(request, ensure_ascii=False) + "\n"
    proc = _MCP_PROCESS
    if proc is None or proc.stdin is None or proc.stdout is None:
        return ""

    try:
        proc.stdin.write(payload.encode("utf-8"))
        await proc.stdin.drain()

        response = await asyncio.wait_for(
            proc.stdout.readline(),
            timeout=timeout
        )
        data = json.loads(response.decode("utf-8"))

        if "result" in data:
            content = data["result"].get("content", [])
            texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
            return "\n".join(texts)
        elif "error" in data:
            return f"查询失败: {data['error'].get('message', '未知错误')}"
        return json.dumps(data, ensure_ascii=False)
    except asyncio.TimeoutError:
        return ""
    except Exception as e:
        return f""


async def shutdown():
    """关闭 MCP 子进程"""
    global _MCP_PROCESS
    if _MCP_PROCESS and _MCP_PROCESS.returncode is None:
        _MCP_PROCESS.kill()
        await _MCP_PROCESS.wait()
    _MCP_PROCESS = None


# ============================================================
# 查询函数
# ============================================================

async def query_tickets(from_station: str, to_station: str, date: str = "") -> str:
    """查询12306火车票"""
    if not date:
        date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

    # 先获取车站编码
    from_code = await _get_station_code(from_station)
    to_code = await _get_station_code(to_station)

    raw = await _call_mcp("get-tickets", {
        "date": date,
        "fromStation": from_code or from_station,
        "toStation": to_code or to_station,
        "format": "text",
        "limitedNum": 10,
    })
    if raw:
        return f"🚄 {from_station} → {to_station} ({date})\n\n{raw}"
    return ""


async def query_transfer(from_station: str, to_station: str, date: str = "") -> str:
    """查询中转路线"""
    if not date:
        date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    from_code = await _get_station_code(from_station)
    to_code = await _get_station_code(to_station)
    return await _call_mcp("get-interline-tickets", {
        "date": date,
        "fromStation": from_code or from_station,
        "toStation": to_code or to_station,
        "format": "text",
    })


async def search_stations(keyword: str) -> str:
    """搜索车站"""
    r = await _call_mcp("get-station-code-by-names", {"stationNames": keyword})
    if r:
        return f"📍 {keyword} 的车站信息：\n{r}"
    r = await _call_mcp("get-stations-code-in-city", {"city": keyword})
    if r:
        return f"📍 {keyword} 的火车站：\n{r}"
    return f"未找到「{keyword}」的车站信息"


async def _get_station_code(name: str) -> str:
    """根据城市名或站名获取 station_code"""
    r = await _call_mcp("get-station-code-by-names", {"stationNames": name})
    if r:
        try:
            data = json.loads(r)
            if isinstance(data, list) and data:
                return data[0].get("station_code", "") or data[0].get("telecode", "")
        except json.JSONDecodeError:
            pass
    r = await _call_mcp("get-station-code-of-citys", {"citys": name})
    if r:
        try:
            data = json.loads(r)
            if isinstance(data, dict):
                return data.get("station_code", "")
        except json.JSONDecodeError:
            pass
    return name


async def get_current_date() -> str:
    """获取当前日期"""
    return await _call_mcp("get-current-date", {})


async def get_train_route(train_code: str, date: str) -> str:
    """查询列车经停站"""
    return await _call_mcp("get-train-route-stations", {
        "trainCode": train_code,
        "departDate": date,
    })


# ============================================================
# LangChain 工具
# ============================================================
from langchain_core.tools import tool


@tool
async def query_12306_tickets(from_station: str, to_station: str, date: str = "") -> str:
    """查询12306火车票信息。根据出发站、到达站和日期查询可用的列车班次、座位和票价。

    Args:
        from_station: 出发站或城市名，如"北京"、"北京南"、"上海虹桥"、"合肥"
        to_station: 到达站或城市名，如"上海"、"蚌埠"、"南京"
        date: 出发日期，格式YYYY-MM-DD，留空则查询明天
    """
    return await query_tickets(from_station, to_station, date)


@tool
async def search_12306_stations(keyword: str) -> str:
    """搜索12306车站信息。根据关键词查找车站名称和代码。

    Args:
        keyword: 城市名或车站关键词，如"北京"、"上海虹"、"蚌埠"
    """
    return await search_stations(keyword)


@tool
async def query_12306_transfer(from_station: str, to_station: str, date: str = "") -> str:
    """查询12306中转路线。当没有直达火车时，搜索换乘方案。

    Args:
        from_station: 出发站或城市名
        to_station: 到达站或城市名
        date: 出发日期，格式YYYY-MM-DD
    """
    return await query_transfer(from_station, to_station, date)


_TRAIN_TOOLS = [query_12306_tickets, search_12306_stations, query_12306_transfer]
