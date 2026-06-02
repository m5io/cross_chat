/**
 * 匹配高亮效果 — 匹配指示器
 */
const MatchEffects = {
    _indicator: null,
    _hideTimer: null,

    init() {
        this._indicator = document.getElementById("match-indicator");
        AppState.on("matchedIds", (ids) => this._onMatch(ids));
    },

    _onMatch(ids) {
        if (!ids || ids.length === 0) {
            this._hide();
            return;
        }
        if (this._indicator) {
            this._indicator.textContent = `Matched: ${ids.length} danmu(s)`;
            this._indicator.classList.add("visible");
        }
        clearTimeout(this._hideTimer);
        this._hideTimer = setTimeout(() => this._hide(), 3000);
    },

    _hide() {
        if (this._indicator) {
            this._indicator.classList.remove("visible");
        }
    },
};
