"""
匹配引擎 — MVP 关键词交集匹配
主播说话文本 vs 弹幕文本 → 返回匹配项
中文支持: 标点切分 + 字符级 bigram 互补，无需 jieba
"""
import re


# 中文分词的简单模拟: 按标点和空格切分
_SPLIT_RE = re.compile(r"[，。！？；、\s,.!?;]+")


def tokenize(text: str) -> set[str]:
    """
    简单分词: 标点切分 + 2-gram 互补
    对中文无空格文本也能生成有意义的 token
    """
    text = text.strip()
    if not text:
        return set()

    # 1. 按标点切分
    parts = [p for p in _SPLIT_RE.split(text) if p]
    tokens = set(parts)

    # 2. 对每个切分段生成字符 bigram（处理无空格中文）
    for part in parts:
        if len(part) >= 2:
            for i in range(len(part) - 1):
                tokens.add(part[i:i+2])

    return tokens


def match_keywords(
    host_text: str,
    danmu_list: list[dict],
    top_n: int = 5,
    min_overlap: int = 1,
) -> list[dict]:
    """
    MVP 关键词匹配

    Args:
        host_text: 主播最新一句话
        danmu_list: 弹幕列表 [{id, text, ...}]
        top_n: 只匹配最近 N 条 (0 = 全部)
        min_overlap: 最少共同关键词数

    Returns:
        [{danmu_id, keywords, score}, ...] 按 score 降序
    """
    if not host_text or not host_text.strip():
        return []

    host_words = tokenize(host_text)
    if not host_words:
        return []

    candidates = danmu_list[-top_n:] if top_n > 0 else danmu_list
    matches = []

    for dm in candidates:
        dm_words = tokenize(dm.get("text", ""))
        overlap = host_words & dm_words
        if len(overlap) >= min_overlap:
            matches.append({
                "danmu_id": dm["id"],
                "keywords": list(overlap),
                "score": len(overlap) / max(len(host_words), 1),
            })

    matches.sort(key=lambda m: m["score"], reverse=True)
    return matches


# ---- quick test ----
if __name__ == "__main__":
    danmu_list = [
        {"id": 0, "text": "主播好！"},
        {"id": 1, "text": "今天玩什么"},
        {"id": 2, "text": "大家好啊"},
    ]
    host = "大家好啊欢迎来到直播间"
    result = match_keywords(host, danmu_list, top_n=5)
    print(f"Host: {host}")
    print(f"Tokens: {tokenize(host)}")
    for m in result:
        dm = danmu_list[m["danmu_id"]]
        print(f"  -> Matched [{m['danmu_id']}] \"{dm['text']}\" keywords={m['keywords']} score={m['score']:.2f}")
