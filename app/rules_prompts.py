# agents/app/rules_prompts.py
"""Prompt builder for compiling NL rules into the report-rule IR."""

_INSTRUCTIONS = """Bạn là trợ lý biên dịch quy tắc cho Báo cáo nghiệm thu.
Chuyển mô tả quy tắc (tiếng Việt, có thể kèm bảng markdown) thành JSON theo schema:
{
  "version": 1,
  "rules": [
    {"id": "<slug>", "description": "<vi>", "target": "<field key>",
     "scope": "scalar|line_item", "type": "lookup_table",
     "inputs": ["..."],
     "match": [{"when": {"<field>": "<enum>" | [lo, hi]}, "value": <int>}],
     "default": <int>},
    {"id": "<slug>", "description": "<vi>", "target": "<field key>",
     "scope": "scalar|line_item", "type": "conditional_formula",
     "inputs": ["..."],
     "cases": [{"when": "<expr>", "value": "<expr>"}],
     "default": "keep" | "<expr>"}
  ],
  "warnings": [{"rule_hint": "<đoạn quy tắc>", "message": "<điều cần làm rõ>"}]
}
Quy tắc bắt buộc:
- Chỉ dùng field key có trong DANH SÁCH FIELD bên dưới. target phải có writable=true.
- range là [lo, hi] (bao gồm 2 đầu). Số tiền là số nguyên thuần (25000, không phải "25.000").
- Biểu thức (when/value của conditional_formula) chỉ dùng tên field + số + + - * / // % + so sánh + and/or/not + round/min/max/abs.
- NẾU quy tắc mơ hồ hoặc nhắc field không có trong danh sách: KHÔNG đoán bừa — thêm một mục vào "warnings".
Chỉ trả về JSON, không kèm giải thích."""


def build_analyze_prompt(*, markdown: str, registry: list[dict]) -> str:
    lines = [
        f'- {f["key"]} (scope={f["scope"]}, type={f["type"]}, '
        f'writable={f["writable"]}): {f["description"]}'
        + (f' [enum: {", ".join(f["enum_values"])}]' if f.get("enum_values") else "")
        for f in registry
    ]
    field_block = "\n".join(lines)
    return (
        f"{_INSTRUCTIONS}\n\nDANH SÁCH FIELD:\n{field_block}\n\n"
        f"QUY TẮC (markdown):\n{markdown}"
    )
