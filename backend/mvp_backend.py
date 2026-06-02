#!/usr/bin/env python3
"""
Cross Chat MVP — 后端主程序
组装弹幕采集 + 语音读取 + 匹配引擎 + WebSocket 桥接，一键启动

用法:
    python mvp_backend.py [--room-id ROOM_ID]

配置:
    编辑下方 ROOM_ID 或通过命令行 --room-id 传入直播间号
"""
import asyncio
import os
import sys
import time
import argparse

from danmu_client import DanmuClient
from ws_server import WsBridge
from matching import match_keywords


# ============================================================
# 配置
# ============================================================
ROOM_ID = 0                # 你的 B 站直播间 ID (数字)，0 表示必须通过 --room-id 指定
SUBTITLE_FILE = ""         # obs-localvocal 输出的字幕文件路径 (留空 = 不启用语音匹配)
POLL_INTERVAL = 0.1        # 字幕文件轮询间隔 (秒)
MATCH_TOP_N = 5            # 只匹配最近 N 条弹幕
MATCH_MIN_OVERLAP = 1      # 最少共同关键词数
HIGHLIGHT_DURATION_MS = 3000  # 高亮持续毫秒


class CrossChatApp:
    """Cross Chat 主应用"""

    def __init__(self, room_id: int, subtitle_file: str = ""):
        self.room_id = room_id
        self.subtitle_file = subtitle_file
        self.bridge = WsBridge()
        self.danmu = DanmuClient(room_id)
        self._last_file_pos = 0
        self._last_host_text = ""
        self._running = False

    # ---- 启动 ----

    async def run(self):
        self._running = True
        print(f"[CrossChat] Starting MVP backend...")
        print(f"[CrossChat] Room ID: {self.room_id}")
        print(f"[CrossChat] Subtitle file: {self.subtitle_file or '(disabled)'}")
        print(f"[CrossChat] WS: ws://localhost:8765")

        # 注册弹幕回调
        self.danmu.on_broadcast(self._on_danmu_event)

        # 并行: 弹幕采集 + WS 服务 + 字幕轮询
        tasks = [
            asyncio.create_task(self.danmu.start()),
            asyncio.create_task(self.bridge.start()),
        ]
        if self.subtitle_file:
            tasks.append(asyncio.create_task(self._poll_subtitle()))

        print("[CrossChat] All services started. Waiting for events...")
        await asyncio.gather(*tasks, return_exceptions=True)

    # ---- 弹幕事件处理 ----

    async def _on_danmu_event(self, event_type: str, payload: dict):
        if event_type == "new_danmu":
            danmu = payload["danmu"]
            print(f"[Danmu] #{danmu['id']} {danmu['uname']}: {danmu['text']}")

            # 更新 bridge 状态
            self.bridge.update_state(danmu_list=self.danmu.buffer)

            # 尝试匹配
            if self._last_host_text:
                matches = match_keywords(
                    self._last_host_text,
                    self.danmu.buffer,
                    top_n=MATCH_TOP_N,
                    min_overlap=MATCH_MIN_OVERLAP,
                )
                if matches:
                    ids = [m["danmu_id"] for m in matches]
                    self.bridge.update_state(matches=matches)
                    await self.bridge.push_match_highlight(
                        ids, self._last_host_text, HIGHLIGHT_DURATION_MS
                    )

            # 推送状态
            print(f"[Danmu] Pushing state, buffer size={len(self.danmu.buffer)}, clients={len(self.bridge._clients)}")
            await self.bridge.push_state()

    # ---- 字幕文件轮询 ----

    async def _poll_subtitle(self):
        """轮询 obs-localvocal 输出的字幕文件，检测新增文本"""
        print(f"[SubtitlePoll] Watching: {self.subtitle_file}")
        while self._running:
            try:
                if os.path.exists(self.subtitle_file):
                    with open(self.subtitle_file, "r", encoding="utf-8") as f:
                        f.seek(self._last_file_pos)
                        new_text = f.read()
                        if new_text:
                            lines = new_text.strip().split("\n")
                            latest = lines[-1].strip()
                            if latest and latest != self._last_host_text:
                                self._last_host_text = latest
                                self.bridge.update_state(host_text=latest)
                                print(f"[SubtitlePoll] Host said: {latest[:50]}...")

                                # 对已有弹幕做回溯匹配
                                matches = match_keywords(
                                    latest, self.danmu.buffer,
                                    top_n=MATCH_TOP_N, min_overlap=MATCH_MIN_OVERLAP,
                                )
                                if matches:
                                    ids = [m["danmu_id"] for m in matches]
                                    self.bridge.update_state(matches=matches)
                                    await self.bridge.push_match_highlight(
                                        ids, latest, HIGHLIGHT_DURATION_MS
                                    )

                                await self.bridge.push_state()
                            self._last_file_pos = f.tell()
            except Exception as e:
                print(f"[SubtitlePoll] Error: {e}")
            await asyncio.sleep(POLL_INTERVAL)


# ============================================================
# 入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Cross Chat MVP Backend")
    parser.add_argument("--room-id", type=int, default=ROOM_ID,
                        help=f"B站直播间 ID (默认: {ROOM_ID})")
    parser.add_argument("--subtitle-file", type=str, default=SUBTITLE_FILE,
                        help="obs-localvocal 字幕文件路径")
    args = parser.parse_args()

    if not args.room_id:
        print("[ERROR] 请指定直播间 ID: python mvp_backend.py --room-id 你的直播间号")
        sys.exit(1)

    subtitle_file = args.subtitle_file

    # 检查文件是否存在
    if subtitle_file and not os.path.exists(subtitle_file):
        print(f"[WARN] 字幕文件不存在: {subtitle_file}")
        print(f"[WARN] 将继续运行但不启用语音匹配")

    app = CrossChatApp(args.room_id, subtitle_file)
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        print("\n[CrossChat] Shutting down...")


if __name__ == "__main__":
    main()
