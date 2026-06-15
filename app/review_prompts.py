# app/review_prompts.py
"""Prompt builders for the QC AI-review passes. Findings are concise suggestions
to help the QC work faster — not authoritative judgements."""

RUBRIC_PARSE_PROMPT = """You split a QC reviewer's rubric text into two buckets.
Return JSON with two string arrays: {"text": [...], "image": [...]}.
Put requirements about wording, structure, grammar, or written content into "text".
Put requirements about pictures, figures, or visuals into "image".
A single rubric line may map to one bucket. Omit empty buckets' items (use []).

Rubrics:
{rubrics}"""

_REVIEW_INSTRUCTIONS = """You are a QC assistant. Produce ONE concise finding (1-3 sentences,
in the rubric's language) that helps the reviewer act fast. If the content satisfies the
rubric, say so briefly. Include a short location hint when useful. Do not invent issues."""


def build_rubric_parse_prompt(rubrics: str) -> str:
    return RUBRIC_PARSE_PROMPT.format(rubrics=rubrics)


def build_rubric_review_prompt(*, rubric: str, content: str) -> str:
    return (
        f"{_REVIEW_INSTRUCTIONS}\n\nRubric:\n{rubric}\n\n"
        f"Content to review:\n{content}"
    )


def build_feedback_resolution_prompt(
    *, feedback_body: str, previous_content: str, current_content: str
) -> str:
    return (
        f"{_REVIEW_INSTRUCTIONS}\n\nA prior reviewer left this feedback:\n{feedback_body}\n\n"
        f"Previous version:\n{previous_content}\n\nCurrent version:\n{current_content}\n\n"
        f"State whether the current version addresses the feedback."
    )


def build_image_rubric_prompt(*, rubric: str) -> str:
    return (
        f"{_REVIEW_INSTRUCTIONS}\n\nRubric (applies to the attached image(s)):\n{rubric}"
    )


def build_image_feedback_prompt(*, feedback_body: str) -> str:
    return (
        f"{_REVIEW_INSTRUCTIONS}\n\nPrior reviewer feedback about the attached image(s):\n"
        f"{feedback_body}\n\nState whether the image addresses the feedback."
    )
