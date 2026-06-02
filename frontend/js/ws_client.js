/**
 * WebSocket 客户端 — 连接后端 WsBridge，接收数据
 */
const WS_URL = "ws://localhost:8765";

class WsClient {
    constructor(url = WS_URL) {
        this._url = url;
        this._ws = null;
        this._handlers = {};       // { eventType: [callback, ...] }
        this._reconnectDelay = 1000;
        this._maxReconnectDelay = 30000;
    }

    // ---- public ----

    /** 注册事件回调: on("state_update", fn), on("new_danmu", fn), on("match_highlight", fn) */
    on(eventType, callback) {
        if (!this._handlers[eventType]) this._handlers[eventType] = [];
        this._handlers[eventType].push(callback);
        return this;
    }

    /** 开始连接 */
    connect() {
        this._connect();
    }

    // ---- internal ----

    _connect() {
        if (this._ws && (this._ws.readyState === WebSocket.OPEN || this._ws.readyState === WebSocket.CONNECTING)) {
            return;
        }
        console.log("[WsClient] Connecting to", this._url);
        this._ws = new WebSocket(this._url);

        this._ws.onopen = () => {
            console.log("[WsClient] Connected");
            this._reconnectDelay = 1000;
        };

        this._ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                this._dispatch(msg.type, msg.payload, msg);
            } catch (e) {
                console.warn("[WsClient] Parse error:", e);
            }
        };

        this._ws.onclose = (event) => {
            console.log("[WsClient] Disconnected code=" + event.code + " reason=" + (event.reason || "").substring(0, 50) + ", reconnecting in " + this._reconnectDelay + "ms");
            setTimeout(() => this._connect(), this._reconnectDelay);
            this._reconnectDelay = Math.min(this._reconnectDelay * 2, this._maxReconnectDelay);
        };

        this._ws.onerror = (err) => {
            console.warn("[WsClient] Error:", err);
        };
    }

    _dispatch(type, payload, fullMsg) {
        const cbs = this._handlers[type] || [];
        cbs.forEach(fn => {
            try { fn(payload, fullMsg); } catch (e) { console.error("[WsClient] Handler error:", e); }
        });
    }
}

// 全局单例
const wsClient = new WsClient();
