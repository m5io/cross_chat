/**
 * 主播字幕条 — 底部固定栏，显示 host_text
 */
const HostBar = {
    _bar: null,
    _textEl: null,
    _hideTimer: null,

    init() {
        this._bar = document.getElementById("host-subtitle-bar");
        this._textEl = document.getElementById("host-text");
        AppState.on("hostText", (text) => this._show(text));
    },

    _show(text) {
        if (!this._bar || !this._textEl) return;
        this._textEl.textContent = text;
        this._bar.classList.add("visible");

        // 5 秒无更新后自动隐藏
        clearTimeout(this._hideTimer);
        this._hideTimer = setTimeout(() => {
            this._bar.classList.remove("visible");
        }, 5000);
    },
};
