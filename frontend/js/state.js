/**
 * 前端状态管理 — 单一数据源，SIMPLE pub-sub
 */
const AppState = {
    hostText: "",
    danmuList: [],       // [{id, uid, uname, text, timestamp}]
    matchedIds: new Set(),
    _listeners: {},

    // ---- update ----

    setHostText(text) {
        if (this.hostText === text) return;
        this.hostText = text;
        this._emit("hostText", text);
    },

    setDanmuList(list) {
        this.danmuList = list;
        this._emit("danmuList", list);
    },

    addDanmu(danmu) {
        this.danmuList.push(danmu);
        if (this.danmuList.length > 30) this.danmuList.shift();
        this._emit("danmuList", this.danmuList);
        this._emit("newDanmu", danmu);
    },

    setMatchedIds(ids, durationMs = 3000) {
        // 设置匹配高亮
        ids.forEach(id => this.matchedIds.add(id));
        this._emit("matchedIds", ids);

        // durationMs 后自动清除
        if (durationMs > 0) {
            setTimeout(() => {
                ids.forEach(id => this.matchedIds.delete(id));
                this._emit("matchedIds", []);
            }, durationMs);
        }
    },

    // ---- pub-sub ----

    on(event, callback) {
        if (!this._listeners[event]) this._listeners[event] = [];
        this._listeners[event].push(callback);
    },

    _emit(event, data) {
        (this._listeners[event] || []).forEach(fn => {
            try { fn(data); } catch (e) { console.error("[State] Handler error:", e); }
        });
    },
};
