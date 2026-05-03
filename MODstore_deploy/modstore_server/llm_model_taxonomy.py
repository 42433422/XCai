"""模型 ID → 展示分类（启发式，可随厂商命名迭代）。"""

from __future__ import annotations

from typing import Dict, List, Literal, Tuple

Category = Literal["llm", "vlm", "image", "video", "other"]

CATEGORY_ORDER: Tuple[Category, ...] = ("llm", "vlm", "image", "video", "other")


def category_labels_zh() -> Dict[str, str]:
    return {
        "llm": "语言大模型 (LLM)",
        "vlm": "视觉 / 多模态 (VLM)",
        "image": "图像生成",
        "video": "视频生成",
        "other": "其他",
    }


def supports_trial_chat(category: str) -> bool:
    return category in ("llm", "vlm")


def classify_model(provider: str, model_id: str) -> Category:
    s = (model_id or "").strip()
    if not s:
        return "other"
    low = s.lower()
    prov = (provider or "").strip().lower()

    # 明确非对话主场景：嵌入、审核、老补全、检索、语音转写等
    if any(
        x in low
        for x in (
            "embedding",
            "text-embedding",
            "moderation",
            "davinci",
            "babbage",
            "text-search",
            "ada-002",
            "ada-001",
            "whisper",
            "tts",
            "transcribe",
            "speech-",
            "rerank",
            "rank_",
        )
    ):
        return "other"
    if low.startswith("ada") and prov == "openai":
        return "other"

    # 图像
    if any(
        x in low
        for x in (
            "dall-e",
            "dall_e",
            "dalle",
            "gpt-image",
            "gpt_image",
            "imagen",
            "image-generation",
            "text-to-image",
            "image-preview",
        )
    ):
        return "image"

    # 视频（尽量窄匹配）
    if any(
        x in low
        for x in (
            "sora",
            "veo-",
            "veo_",
            "video-generation",
            "videogen",
            "kling",  # 部分兼容网关命名
        )
    ):
        return "video"

    # 多模态 / 视觉
    if "vision" in low or "vl-" in low or "vlm" in low:
        return "vlm"
    if "deepseek-vl" in low or "qwen-vl" in low or "llava" in low:
        return "vlm"
    if "omni" in low:
        return "vlm"
    if "gpt-4o" in low or "gpt-4.1" in low:
        return "vlm"
    if "gpt-4-turbo" in low:
        return "vlm"
    if prov == "google" and low.startswith("gemini") and "embed" not in low:
        # Gemini 1.5+ 默认按多模态入口归类
        if low.startswith("gemini-1.5") or low.startswith("gemini-2"):
            return "vlm"
    if prov == "anthropic" and ("claude-3" in low or "claude-sonnet" in low or "claude-opus" in low):
        return "vlm"

    # 聚合网关 / OpenAI 兼容：SiliconFlow、百炼、Kimi、MiniMax、Groq、Together、OpenRouter 等
    if prov in (
        "siliconflow",
        "together",
        "groq",
        "openrouter",
        "dashscope",
        "moonshot",
        "xiaomi",
        "minimax",
        "doubao",
        "wenxin",
        "hunyuan",
        "zhipu",
        "xunfei",
        "yi",
        "stepfun",
        "baichuan",
        "sensetime",
    ):
        if any(
            x in low
            for x in (
                "stable-diffusion",
                "sdxl",
                "flux.",
                "flux/",
                "flux-1",
                "flux.1",
                "text-to-image",
                "image-to-image",
                "kolors",
                "playground-v2",
                "dall-e",
                "wanx",
                "text2image",
                "wan2",
                "seedream",
            )
        ):
            return "image"
        if any(
            x in low
            for x in (
                "text-to-video",
                "image-to-video",
                "video-generation",
                "cogvideox",
                "wan-i2v",
                "kling",
                "i2v",
                "t2v",
                "video-01",
                "hailuo",
                "seedance",
            )
        ):
            return "video"
        if "embed" in low or "bge-" in low or "/rerank" in low or "reranker" in low:
            return "other"
        if "vl" in low or "vision" in low or "qwen-vl" in low or "llava" in low or "glm-4.5v" in low or "glm-4.6" in low:
            return "vlm"
        if "omni" in low:
            return "vlm"
        if prov == "minimax" and ("speech" in low or "voice" in low or "music" in low):
            return "other"

    return "llm"


def _category_sort_key(cat: str) -> int:
    try:
        return CATEGORY_ORDER.index(cat)  # type: ignore[arg-type]
    except ValueError:
        return len(CATEGORY_ORDER)


def build_models_detailed(provider: str, model_ids: List[str]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for mid in model_ids:
        mid = (mid or "").strip()
        if not mid:
            continue
        rows.append({"id": mid, "category": classify_model(provider, mid)})
    rows.sort(key=lambda r: (_category_sort_key(r["category"]), r["id"]))
    return rows
