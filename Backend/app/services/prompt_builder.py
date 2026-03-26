from __future__ import annotations

from collections.abc import Sequence

from app.models.menu import MenuItem
from app.models.preferences import UserPreferences


def _format_menu_items(menu_items: Sequence[MenuItem], lang: str) -> str:
    lines: list[str] = []
    for item in menu_items:
        name = item.name_zh if lang == "zh" else item.name_en
        lines.append(
            "- "
            f"id={item.id}; name={name}; hall={item.hall_id.value}; meal={item.meal_slot.value}; "
            f"calories={item.calories}; macros(P/C/F)={item.macros.protein}/{item.macros.carbs}/{item.macros.fat}; "
            f"tags={','.join(tag.value for tag in item.tags)}; "
            f"allergens={','.join(tag.value for tag in item.allergens)}"
        )
    return "\n".join(lines) if lines else "- (无菜品候选)"


def build_daily_insight_prompt(
    user_query: str,
    lang: str,
    preferences: UserPreferences,
    menu_candidates: Sequence[MenuItem],
    rag_context: str,
) -> tuple[str, str]:
    schema_hint = """
你必须输出 JSON 对象，不要输出 markdown，不要包含解释文本。
JSON 字段要求：
{
  "title": string,
  "summary": string,
  "recommended_meal_slot": "breakfast" | "lunch" | "dinner" | null,
  "recommended_dish_ids": string[],
  "avoid_dish_ids": string[],
  "nutrition_focus": string[],
  "safety_alerts": string[],
  "confidence": number (0~1)
}
""".strip()

    system_prompt = (
        "你是大学食堂 AI 营养助手。你必须基于给定上下文给出谨慎、可执行的建议。"
        "对过敏原必须优先安全。推荐菜品 ID 必须来自候选菜单。"
    )

    user_prompt = f"""
用户语言: {lang}
用户请求: {user_query}

用户偏好:
- favorite_hall: {preferences.favorite_hall.value}
- ai_auto_push: {preferences.ai_auto_push}
- pref_tags: {[tag.value for tag in preferences.pref_tags]}
- allergen_tags: {[tag.value for tag in preferences.allergen_tags]}

候选菜品:
{_format_menu_items(menu_candidates, lang)}

RAG 上下文:
{rag_context}

请输出结构化每日饮食洞察。
{schema_hint}
""".strip()

    return system_prompt, user_prompt


def build_chat_prompt(
    user_message: str,
    lang: str,
    preferences: UserPreferences,
    menu_candidates: Sequence[MenuItem],
    rag_context: str,
) -> tuple[str, str]:
    schema_hint = """
返回 JSON：
{
  "reply": string,
  "recommended_dish_ids": string[],
  "avoid_dish_ids": string[],
  "citations": string[]
}
""".strip()

    system_prompt = (
        "你是大学食堂 AI 营养助手，回答要简洁且友好，优先安全，"
        "推荐菜品 ID 必须在候选菜单里，避免虚构。"
    )

    user_prompt = f"""
用户语言: {lang}
用户输入: {user_message}

用户偏好:
- favorite_hall: {preferences.favorite_hall.value}
- pref_tags: {[tag.value for tag in preferences.pref_tags]}
- allergen_tags: {[tag.value for tag in preferences.allergen_tags]}

候选菜品:
{_format_menu_items(menu_candidates, lang)}

RAG 上下文:
{rag_context}

请生成回复。
{schema_hint}
""".strip()

    return system_prompt, user_prompt
