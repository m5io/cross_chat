/**
 * App 入口 — 组装所有模块，连接 WebSocket
 */
(function () {
    "use strict";

    // 1. 初始化所有 UI 模块
    DanmuRenderer.init();
    HostBar.init();
    MatchEffects.init();

    // 2. 绑定 WebSocket 事件 → 更新 State
    wsClient
        .on("state_update", (payload) => {
            if (payload.host_text !== undefined) {
                AppState.setHostText(payload.host_text);
            }
            if (payload.danmu_list) {
                AppState.setDanmuList(payload.danmu_list);
            }
            if (payload.matches && payload.matches.length > 0) {
                const ids = payload.matches.map(m => m.danmu_id);
                AppState.setMatchedIds(ids, 3000);
            }
        })
        .on("new_danmu", (payload) => {
            if (payload.danmu) {
                AppState.addDanmu(payload.danmu);
            }
        })
        .on("match_highlight", (payload) => {
            if (payload.danmu_ids) {
                AppState.setMatchedIds(payload.danmu_ids, payload.duration_ms || 3000);
            }
            if (payload.host_text) {
                AppState.setHostText(payload.host_text);
            }
        });

    // 3. 启动连接
    wsClient.connect();

    console.log("[CrossChat] Frontend initialized.");
})();
