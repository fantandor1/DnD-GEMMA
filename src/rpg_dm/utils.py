from __future__ import annotations

import re
from datetime import datetime, timezone

GROUP_TAG_PREFIX = "group:"
SYS_META_PATTERN = re.compile(r"^\[SYS_META(?P<meta>[^\]]*)\]\s*(?P<body>.*)$", re.DOTALL)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def slugify(value: str) -> str:
    base = re.sub(r"[^\w]+", "-", value.lower(), flags=re.UNICODE).strip("-")
    return base or "entity"


def compact_text(value: str, limit: int = 220) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "..."


def estimate_tokens(text: str) -> int:
    """Very rough token estimate for prompt budgeting.

    Works reasonably for mixed Cyrillic/Latin text. We intentionally avoid model-specific tokenizers
    to keep dependencies minimal. Used only for "should we recap?" heuristics.
    """
    if not text:
        return 0
    # Average ~3-4 chars per token in many BPE tokenizers; for Cyrillic it can be a bit worse.
    # Use a conservative divisor to avoid overshooting context limits.
    return max(1, int(len(text) / 3.2))


def with_group_tag(tags: list[str] | None, group_path: str | None) -> list[str]:
    clean_tags = [tag for tag in (tags or []) if not str(tag).startswith(GROUP_TAG_PREFIX)]
    normalized_group = " / ".join(part.strip() for part in (group_path or "").split("/") if part.strip())
    if normalized_group:
        clean_tags.insert(0, f"{GROUP_TAG_PREFIX}{normalized_group}")
    return clean_tags


def extract_group_path(tags: list[str] | None) -> str | None:
    for tag in tags or []:
        if isinstance(tag, str) and tag.startswith(GROUP_TAG_PREFIX):
            return tag[len(GROUP_TAG_PREFIX) :].strip() or None
    return None


def decode_system_meta(text: str) -> tuple[dict[str, str], str]:
    match = SYS_META_PATTERN.match((text or "").strip())
    if not match:
        return {}, (text or "").strip()

    raw_meta = match.group("meta").strip()
    body = match.group("body").strip()
    meta: dict[str, str] = {}
    for token in raw_meta.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        meta[key.strip()] = value.strip()
    return meta, body


def encode_system_meta(body: str, **meta_values: object) -> str:
    parts = []
    for key, value in meta_values.items():
        if value is None or value == "":
            continue
        if isinstance(value, bool):
            parts.append(f"{key}={'1' if value else '0'}")
        else:
            parts.append(f"{key}={value}")

    clean_body = (body or "").strip()
    if not parts:
        return clean_body
    return f"[SYS_META {' '.join(parts)}] {clean_body}".strip()


def decode_quest_state(progress_note: str) -> dict[str, object]:
    meta, body = decode_system_meta(progress_note)
    turns_remaining = None
    turns_total = None
    turns_value = meta.get("turns")
    if turns_value and "/" in turns_value:
        left, right = turns_value.split("/", 1)
        if left.isdigit():
            turns_remaining = int(left)
        if right.isdigit():
            turns_total = int(right)

    auto_value = meta.get("auto")
    auto_decrement = auto_value in {"1", "true", "yes", "on"}
    kind = (meta.get("kind") or "").strip() or None
    return {
        "kind": kind,
        "turns_remaining": turns_remaining,
        "turns_total": turns_total,
        "auto_decrement": auto_decrement,
        "body": body,
    }


def encode_quest_state(
    body: str,
    *,
    kind: str | None = None,
    turns_remaining: int | None = None,
    turns_total: int | None = None,
    auto_decrement: bool = False,
) -> str:
    turns = None
    if turns_remaining is not None and turns_total is not None:
        turns = f"{turns_remaining}/{turns_total}"
    return encode_system_meta(
        body,
        kind=kind or None,
        turns=turns,
        auto=auto_decrement if turns else None,
    )
