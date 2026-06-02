from __future__ import annotations

MIN_TEXT_LENGTH = 20
MIN_QUESTION_MARKS = 6
MAX_LOW_HANGUL_COUNT = 4
MIN_QUESTION_MARK_RATIO = 0.15
MIN_REPLACEMENT_CHARS = 2


def find_encoding_loss_field(post_main: str, replies: list[str]) -> str | None:
    if has_encoding_loss(post_main):
        return "Post Main"
    for index, reply in enumerate(replies, start=1):
        if has_encoding_loss(reply):
            return f"Replies[{index}]"
    return None


def has_encoding_loss(text: str) -> bool:
    compact = "".join(char for char in text if not char.isspace())
    if len(compact) < MIN_TEXT_LENGTH:
        return False

    hangul_count = sum(1 for char in compact if _is_hangul_syllable(char))
    if hangul_count > MAX_LOW_HANGUL_COUNT:
        return False

    question_count = compact.count("?")
    if "??" in compact and question_count >= MIN_QUESTION_MARKS:
        return question_count / len(compact) >= MIN_QUESTION_MARK_RATIO

    return compact.count("\ufffd") >= MIN_REPLACEMENT_CHARS


def _is_hangul_syllable(char: str) -> bool:
    codepoint = ord(char)
    return 0xAC00 <= codepoint <= 0xD7A3
