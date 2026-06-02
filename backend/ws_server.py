"""
WebSocket 服务器 — 本地桥梁
把弹幕数据 + 匹配结果推送给前端 Browser Source
"""
import asyncio
import json
import time
from websockets.asyncio.server import serve


class WsBridge:
    """WebSocket 桥: Pub-Sub 模式，服务器主动推送状态到前端"""

    def __init__(self, host: str = "localhost", port: int = 8765):
        self._host = host
        self._port = port
        self._clients: set = set()
        self._seq = 0
        # 最新状态快照
        self.state = {
            "host_text": "",
            "danmu_list": [],
            "matches": [],
        }

    # ---- public API ----

    async def start(self):
        print(f"[WsBridge] Starting ws://{self._host}:{self._port}")
        async with serve(self._handler, self._host, self._port):
            await asyncio.get_running_loop().create_future()  # run forever

    async def push_state(self):
        """推送全量状态快照"""
        await self._broadcast({
            "type": "state_update",
            "seq": self._seq,
            "timestamp": time.time(),
            "payload": self.state,
        })
        self._seq += 1

    async def push_new_danmu(self, danmu: dict):
        """推送增量弹幕事件"""
        await self._broadcast({
            "type": "new_danmu",
            "seq": self._seq,
            "payload": {"danmu": danmu},
        })
        self._seq += 1

    async def push_match_highlight(self, danmu_ids: list[int], host_text: str, duration_ms: int = 3000):
        """推送匹配高亮事件"""
        await self._broadcast({
            "type": "match_highlight",
            "seq": self._seq,
            "payload": {
                "danmu_ids": danmu_ids,
                "host_text": host_text,
                "duration_ms": duration_ms,
            },
        })
        self._seq += 1

    def update_state(self, **kwargs):
        """更新内部状态快照"""
        self.state.update(kwargs)

    # ---- internal ----

    async def _handler(self, ws):
        self._clients.add(ws)
        print(f"[WsBridge] Client connected (total={len(self._clients)})")
        try:
            # 首次连接 → 发送全量快照
            msg = json.dumps({
                "type": "state_update",
                "seq": self._seq,
                "timestamp": time.time(),
                "payload": self.state,
            }, ensure_ascii=False)
            await ws.send(msg)
            self._seq += 1
            print(f"[WsBridge] Initial snapshot sent, keeping connection alive")
            # 阻塞等待连接关闭
            await ws.wait_closed()
            print(f"[WsBridge] Connection closed normally")
        except Exception as e:
            print(f"[WsBridge] Handler error: {type(e).__name__}: {e}")
        finally:
            self._clients.discard(ws)
            print(f"[WsBridge] Client disconnected (total={len(self._clients)})")

    async def _broadcast(self, msg: dict):
        if not self._clients:
            return
        data = json.dumps(msg, ensure_ascii=False)
        await asyncio.gather(
            *(client.send(data) for client in list(self._clients)),
            return_exceptions=True,
        )
