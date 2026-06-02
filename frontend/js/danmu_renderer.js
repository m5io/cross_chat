/**
 * 弹幕列表渲染器 — 垂直滚动列表
 */
const DanmuRenderer = {
    _container: null,
    _items: new Map(),   // danmu_id -> DOM element

    init() {
        this._container = document.getElementById("danmu-container");
        AppState.on("danmuList", (list) => this._renderList(list));
        AppState.on("newDanmu", (danmu) => this._addItem(danmu));
        AppState.on("matchedIds", (ids) => this._updateHighlights(ids));
    },

    // ---- internal ----

    _renderList(list) {
        // 全量刷新（用于首次 state_update）
        this._items.clear();
        if (this._container) {
            this._container.innerHTML = "";
        }
        list.forEach(dm => this._addItem(dm));
    },

    _addItem(danmu) {
        if (!this._container) return;
        if (this._items.has(danmu.id)) return;

        const el = document.createElement("div");
        el.className = "danmu-item";
        el.dataset.danmuId = danmu.id;
        el.innerHTML = `
            <span class="danmu-user">${this._esc(danmu.uname || "")}:</span>
            <span class="danmu-text">${this._esc(danmu.text || "")}</span>
            <div class="highlight-arrow"></div>
        `;
        this._container.appendChild(el);
        this._items.set(danmu.id, el);

        // 超过上限移除最旧节点
        while (this._items.size > 30) {
            const oldestKey = this._items.keys().next().value;
            this._removeItem(oldestKey);
        }
    },

    _removeItem(danmuId) {
        const el = this._items.get(danmuId);
        if (el) {
            el.classList.add("removing");
            setTimeout(() => el.remove(), 500);
            this._items.delete(danmuId);
        }
    },

    _updateHighlights(matchedIds) {
        const idSet = new Set(matchedIds);
        this._items.forEach((el, id) => {
            if (idSet.has(id)) {
                el.classList.add("matched");
            } else {
                el.classList.remove("matched");
            }
        });
    },

    _esc(s) {
        const div = document.createElement("div");
        div.textContent = s;
        return div.innerHTML;
    },
};
