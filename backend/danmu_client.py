"""
B站弹幕客户端 — 基于 blivedm 封装
连接指定直播间，实时接收弹幕并维护滑动窗口缓存
"""
import time
import asyncio
from blivedm import BLiveClient


class DanmuClient(BLiveClient):
    """弹幕客户端: 连接 B 站直播间，缓存最近 N 条弹幕"""

    def __init__(self, room_id: int, buffer_size: int = 30):
        super().__init__(room_id)
        self._buffer: list[dict] = []
        self._buffer_size = buffer_size
        self._seq = 0
        self._on_update = None  # 回调: async fn(EventType, data)
        print(f"[DanmuClient] Init room={room_id}, buffer={buffer_size}")

    # ---- public API ----

    @property
    def buffer(self) -> list[dict]:
        return list(self._buffer)

    def on_broadcast(self, callback):
        """注册广播回调: async fn(event_type: str, payload: dict)"""
        self._on_update = callback

    # ---- blivedm callbacks ----

    async def on_danmaku(self, danmaku):
        event = {
            "id": self._seq,
            "uid": danmaku.uid,
            "uname": danmaku.uname,
            "text": danmaku.msg,
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
