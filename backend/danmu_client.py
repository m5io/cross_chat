"""
B站弹幕客户端 — 基于 blivedm 封装
连接指定直播间，实时接收弹幕并维护滑动窗口缓存

blivedm 使用 Handler 模式：BaseHandler._on_danmaku 接收 DanmakuMessage 对象。
DanmuClient 继承 BaseHandler 处理弹幕，内部委托 BLiveClient 管理 WebSocket 连接。

兼容适配:
- Python 3.14: BLiveClient 延迟创建（需事件循环），brotli 升级到 1.2.0
- B站风控: 为 API 请求注入 WBI 签名，绕过 -352 错误
"""
import time
import asyncio
import hashlib
import functools
import urllib.parse
import aiohttp
from blivedm.handlers import BaseHandler
from blivedm.client import BLiveClient, ROOM_INIT_URL, DANMAKU_SERVER_CONF_URL

# B站 WBI 签名相关
_WBI_KEY_CACHE = None  # 缓存 mixed_key，避免每次请求都 nav

# 用户代理（较新 Chrome 版本，避免被风控识别为过旧浏览器）
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


async def _fetch_wbi_keys(session: aiohttp.ClientSession) -> str:
    """
    从 B站 nav 接口获取 img_key 和 sub_key，混合生成 32 位签名密钥。
    结果会被缓存，避免每次请求都 nav。
    """
    global _WBI_KEY_CACHE
    if _WBI_KEY_CACHE is not None:
        return _WBI_KEY_CACHE

    # B站 WBI 密钥混合表 (前 32 项 — 对应取 32 位混合 key)
    MIXIN_KEY_ENC_TAB = [
        46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
        27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    ]

    try:
        async with session.get(
            "https://api.bilibili.com/x/web-interface/nav",
            headers={"User-Agent": _USER_AGENT},
        ) as resp:
            data = await resp.json()
            wbi_img = data.get("data", {}).get("wbi_img", {})
            img_url = wbi_img.get("img_url", "")
            sub_url = wbi_img.get("sub_url", "")

            if not img_url or not sub_url:
                return ""

            # 从 URL 中提取 key（文件名不带扩展名）
            img_key = img_url.rsplit("/", 1)[-1].split(".")[0]
            sub_key = sub_url.rsplit("/", 1)[-1].split(".")[0]

            raw = img_key + sub_key
            _WBI_KEY_CACHE = "".join(raw[i] for i in MIXIN_KEY_ENC_TAB if i < len(raw))
            return _WBI_KEY_CACHE
    except Exception:
        # nav 接口挂了的话返回空 key，降级运行
        return ""


def _sign_params(params: dict, mixin_key: str) -> dict:
    """为请求参数添加 WBI 签名 (wts + w_rid)"""
    if not mixin_key:
        return params  # 无 key 时不签名
    params["wts"] = int(time.time())
    # 按 key 排序
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    # 构建 query string（注意：空格应编码为 %20，但 B站接受 urllib 默认编码）
    query = urllib.parse.urlencode(sorted_params)
    sign = hashlib.md5((query + mixin_key).encode()).hexdigest()
    params["w_rid"] = sign
    return params


class _PatchedBLiveClient(BLiveClient):
    """
    BLiveClient 子类：对 HTTP API 请求注入 WBI 签名，绕过 B站 -352 风控。
    仅在 _init_room_id_and_owner 和 _init_host_server 两个接口做签名。
    """

    async def _signed_get(self, url: str, params: dict) -> dict:
        """带 WBI 签名的 GET 请求"""
        mixin_key = await _fetch_wbi_keys(self._session)
        params = _sign_params(dict(params), mixin_key)
        async with self._session.get(
            url,
            headers={
                "User-Agent": _USER_AGENT,
                "Referer": "https://live.bilibili.com/",
            },
            params=params,
            ssl=self._ssl,
        ) as res:
            return await res.json()

    async def _init_room_id_and_owner(self):
        """重写：使用 WBI 签名请求"""
        try:
            resp = await self._signed_get(ROOM_INIT_URL, {"room_id": self._tmp_room_id})
            if resp["code"] != 0:
                import logging
                logging.getLogger("blivedm").warning(
                    "room=%d _init_room_id_and_owner() failed, message=%s",
                    self._tmp_room_id, resp.get("message", ""),
                )
                return False
            if not self._parse_room_init(resp["data"]):
                return False
        except (aiohttp.ClientConnectionError, asyncio.TimeoutError):
            import logging
            logging.getLogger("blivedm").exception(
                "room=%d _init_room_id_and_owner() failed:", self._tmp_room_id
            )
            return False
        return True

    async def _init_host_server(self):
        """重写：使用 WBI 签名请求"""
        try:
            resp = await self._signed_get(
                DANMAKU_SERVER_CONF_URL, {"id": self._room_id, "type": 0}
            )
            if resp["code"] != 0:
                import logging
                logging.getLogger("blivedm").warning(
                    "room=%d _init_host_server() failed, message=%s",
                    self._room_id, resp.get("message", ""),
                )
                return False
            if not self._parse_danmaku_server_conf(resp["data"]):
                return False
        except (aiohttp.ClientConnectionError, asyncio.TimeoutError):
            import logging
            logging.getLogger("blivedm").exception(
                "room=%d _init_host_server() failed:", self._room_id
            )
            return False
        return True


class DanmuClient(BaseHandler):
    """弹幕客户端: 连接 B 站直播间，缓存最近 N 条弹幕"""

    def __init__(self, room_id: int, buffer_size: int = 30):
        super().__init__()
        self._client = None  # 延迟到 start() 创建，因为 BLiveClient 需要事件循环
        self._room_id = room_id
        self._buffer: list[dict] = []
        self._buffer_size = buffer_size
        self._seq = 0
        self._on_update = None  # 回调: async fn(event_type, data)
        self.room_id = room_id
        print(f"[DanmuClient] Init room={room_id}, buffer={buffer_size}")

    # ---- public API ----

    @property
    def buffer(self) -> list[dict]:
        return list(self._buffer)

    def on_broadcast(self, callback):
        """注册广播回调: async fn(event_type: str, payload: dict)"""
        self._on_update = callback

    async def start(self):
        """启动弹幕采集（在事件循环内调用）"""
        if self._client is None:
            self._client = _PatchedBLiveClient(self._room_id)
            self._client.add_handler(self)
        self._client.start()

    # ---- BaseHandler callbacks ----

    async def _on_danmaku(self, client, message):
        """接收弹幕消息 (blivedm 回调)"""
        event = {
            "id": self._seq,
            "uid": message.uid,
            "uname": message.uname,
            "text": message.msg,
            "timestamp": time.time(),
        }
        self._seq += 1
        self._buffer.append(event)
        if len(self._buffer) > self._buffer_size:
            self._buffer.pop(0)

        # 通知外部
        if self._on_update:
            await self._on_update("new_danmu", {"danmu": event})


# ---- quick test ----
async def _test(room_id: int):
    client = DanmuClient(room_id)
    client.on_broadcast(lambda t, d: print(f"[{t}] {d['danmu']['uname']}: {d['danmu']['text']}"))
    print("[DanmuClient] Connecting... (Ctrl+C to stop)")
    await client.start()


if __name__ == "__main__":
    import sys
    room = int(sys.argv[1]) if len(sys.argv) > 1 else 123456
    asyncio.run(_test(room))
