# service/user/document_chunking.py
from __future__ import annotations

import re
from typing import Optional, List, Callable, Sequence

from langchain_text_splitters import RecursiveCharacterTextSplitter

DEFAULT_SEPARATORS: Sequence[str] = ["\n\n", "\n", " ", ""]


def build_splitter(
    *,
    chunk_size: int,
    chunk_overlap: int,
    strategy: str,
    length_function: Optional[Callable[[str], int]] = None,
    separators: Sequence[str] = DEFAULT_SEPARATORS,
):
    # MVP: recursive만
    if strategy != "recursive":
        raise ValueError(f"Unsupported chunk_strategy: {strategy}")

    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=length_function,
        separators=list(separators),
    )


def split_segments(*, text: str, separator: Optional[str]) -> list[str]:
    """
    1차 segment 분리
    - separator 없으면 전체를 하나로
    - separator == "\n\n" 이면 PDF 텍스트 특성(빈줄에 공백 포함) 고려해서 regex split
    """
    raw = (text or "").strip()
    if not raw:
        return []

    if not separator:
        return [raw]

    if separator == "\n\n":
        parts = re.split(r"\n\s*\n", raw)
    else:
        parts = raw.split(separator)

    parts = [p.strip() for p in parts]
    return [p for p in parts if p]


def clean_texts(texts: List[str]) -> List[str]:
    return [t.strip() for t in texts if t and t.strip()]
