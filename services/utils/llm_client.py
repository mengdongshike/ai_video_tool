"""
LLM 通用工具类 — 支持多模型文案生成
新增模型只需在 MODELS 中添加配置
"""
import json, httpx
from pathlib import Path
from typing import Optional

SETTINGS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "settings.json"

class LLMClient:
    MODELS = {
        "deepseek": {
            "url": "https://api.deepseek.com/v1/chat/completions",
            "model": "deepseek-chat",
            "auth": lambda key: {"Authorization": f"Bearer {key}"},
            "parse": lambda data: data["choices"][0]["message"]["content"],
        },
    }

    # YYKA 风格的词库
    STYLES = {
        "口语闲聊风": "熟人闲聊口吻，短句生活化，无书面话术",
        "犀利通透风": "直白点破误区，简洁有力，三观正向",
        "治愈共情风": "温柔走心，共情为主，拒绝空洞鸡汤",
        "干货落地风": "条理清晰，内容实用，方法可直接照搬",
        "幽默自嘲风": "轻松调侃，氛围松弛，不带攻击性",
        "真诚走心风": "第一人称实拍感受，朴实有信任感",
        "反差颠覆风": "打破固有认知，制造悬念提升吸引力",
        "极简短句风": "短句拆分，信息直白，阅读无压力",
    }
    PERSONAS = {
        # 毒舌/犀利型
        "毒舌博主": "句句扎心，专骂恋爱脑和摆烂怪，骂完再给方案",
        "暴躁学姐": "脾气爆但句句在理，最烦磨叽和废话",
        "人间清醒姐": "不煽情不画饼，用冷水泼醒你",

        # 温暖/治愈型
        "知心姐姐": "温柔有力量，擅长把大道理讲成小故事",
        "树洞先生": "话不多，但句句都能接住你的情绪",
        "治愈系路人": "和你一样的普通人，陪你慢慢变好",

        # 理性/逻辑型
        "理性军师": "不站队不煽动，只用数据和逻辑说话",
        "商业教练": "不教理论只教实战，专治犹豫不决",
        "拆解狂魔": "什么都能拆成123，复杂事情简单讲",

        # 幽默/接地气型
        "段子手老铁": "正经话用玩笑说，专治各种无聊",
        "隔壁老王": "普通人视角，说的都是你身边的事",
        "反向鸡汤师": "不鼓励你，但让你觉得不努力也没关系",

        # 硬核/专业型
        "硬核技术宅": "不讲废话，只说实操和源码",
        "效率狂人": "把效率卷到极致，只分享能落地的工具",
        "避坑专家": "专讲别人踩过的坑，让你少走弯路",

        # 真实/成长型
        "逆袭路人": "大专毕业到年薪50w，全踩过所有坑",
        "创业幸存者": "开垮过3家公司，现在告诉你哪些不能碰",
        "自律失败者": "自律了100次失败了101次，但还在坚持",

        # 中立/观察型
        "冷静看客": "不站队不跟风，只讲事实不讲情绪",
        "局外人": "跳出圈子看问题，给你一个全新视角",
    }


    def __init__(self):
        self._settings = self._load_settings()

    def _load_settings(self) -> dict:
        if SETTINGS_FILE.exists():
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return {"text_model": "glm4", "api_key": "", "api_keys": {}}

    def reload(self):
        self._settings = self._load_settings()

    @property
    def model_name(self) -> str:
        return self._settings.get("text_model", "glm4")

    @property
    def api_key(self) -> str:
        model = self.model_name
        return self._settings.get("api_keys", {}).get(model, "") or self._settings.get("api_key", "")

    @property
    def model_config(self) -> Optional[dict]:
        return self.MODELS.get(self.model_name)

    def check(self) -> str:
        if not self.model_config:
            return f"不支持的模型: {self.model_name}"
        if not self.api_key:
            return f"未配置 {self.model_name} 的 API Key"
        return ""

    async def chat(self, messages: list, **kwargs) -> str:
        err = self.check()
        if err:
            raise ValueError(err)
        cfg = self.model_config
        headers = cfg["auth"](self.api_key)
        payload = {
            "model": cfg["model"],
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.8),
            "max_tokens": kwargs.get("max_tokens", 8192),
        }
        # 自动重试最多 3 次，应对限流
        for attempt in range(3):
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(cfg["url"], json=payload, headers=headers)
                if r.status_code == 429:
                    import asyncio
                    wait = (attempt + 1) * 2
                    print(f">> 限流，{wait}秒后重试...", flush=True)
                    await asyncio.sleep(wait)
                    continue
                if r.status_code != 200:
                    raise RuntimeError(f"{self.model_name} API 错误 ({r.status_code}): {r.text[:200]}")
                return cfg["parse"](r.json())
        raise RuntimeError(f"{self.model_name} API 限流，多次重试后仍失败")

    async def generate(self, topic: str, style: str = "口语闲聊风",
                       persona: str = "冷静看客",
                       length: int = 200, brand_words: str = "",
                       language: str = "中文") -> str:
        """YYKA 风格文案生成"""
        sp = self.STYLES.get(style, "口语闲聊风")
        pp = self.PERSONAS.get(persona, "冷静看客")
        user_prompt = f"""主题：{topic}，
风格：{sp}，
人设：{pp}，
字数：请严格约束在{length}字左右，误差在30字以内。
品牌植入：文案自然软性植入，{brand_words}，无生硬广告感，
语言：请使用{language}输出文案，"""
        return await self.chat([
            {"role": "system", "content": f"你是专业的短视频口播文案作者。直接输出{language}文案，不要分析、不要草稿、不要分步骤、不要解释。仅输出纯口播文案，无语速、停顿、表演描述，口语短句，无特殊符号，结尾带互动引导。"},
            {"role": "user", "content": user_prompt},
        ])

    async def optimize(self, content: str, style: str = "口语闲聊风",
                       persona: str = "知心姐姐",
                       length: int = 200, brand_words: str = "",
                       language: str = "中文") -> str:
        """YYKA 风格文案优化"""
        sp = self.STYLES.get(style, "口语闲聊风")
        pp = self.PERSONAS.get(persona, "知心姐姐")
        user_prompt = f"""原文：{content}，
风格：{sp}，
人设：{pp}，
字数：请严格约束在{length}字左右，误差在30字以内。
品牌植入：文案自然软性植入，{brand_words}，无生硬广告感，
语言：请使用{language}输出优化后的文案，"""
        return await self.chat([
            {"role": "system", "content": f"你是专业的文案优化大师。直接输出{language}优化后的文案，不要分析、不要草稿、不要分步骤、不要解释。请不要改变原文的含义和意图。仅输出纯口播文案，无语速、停顿、表演描述，口语短句，无特殊符号，结尾带互动引导。"},
            {"role": "user", "content": user_prompt},
        ])

async def generate_copy(topic: str, style: str = "口语闲聊风",
                        persona: str = "知心姐姐",
                        length: int = 200, brand_words: str = "",
                        language: str = "中文") -> str:
    return await LLMClient().generate(topic, style, persona, length, brand_words, language)

async def optimize_copy(content: str, style: str = "口语闲聊风",
                        persona: str = "知心姐姐",
                        length: int = 200, brand_words: str = "",
                        language: str = "中文") -> str:
    return await LLMClient().optimize(content, style, persona, length, brand_words, language)
