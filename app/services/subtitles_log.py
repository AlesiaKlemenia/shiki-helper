"""Сервис парсинга и валидации логов загрузки субтитров."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class SubtitlesLogPayload:
    """Извлеченные данные из лога заливки субтитров."""

    shiki_id: int
    episode_num: int
    raw_text: str


class SubtitlesLogParser:
    """Парсер входящих логов загрузки субтитров."""

    SUBTITLES_MARKER = "Тип субтитров: subtitles"

    @classmethod
    def is_subtitles_log(cls, text: str | None) -> bool:
        """Проверяет, содержит ли сообщение обязательный маркер субтитров."""
        if not text:
            return False
        return cls.SUBTITLES_MARKER.lower() in text.lower()

    @classmethod
    def parse(cls, text: str | None) -> Optional[SubtitlesLogPayload]:
        """Извлекает shiki_id и номер серии из лога субтитров.

        Логика извлечения:
        1. Обязательная проверка наличия маркера 'Тип субтитров: subtitles'.
        2. Извлечение shikimori_id:
           - Из строки пути вида: 'Путь: <shiki_id>/<ep>/...' или 'Path: <shiki_id>/<ep>/...'
           - Из ссылки: 'https://shikimori.one/animes/<id>' (или z<id>)
           - Из строки 'Shikimori ID: <id>' / 'ID: <id>'
        3. Извлечение episode_num:
           - Из строки 'Серия: <N>' / 'Серия <N>' / 'Episode: <N>'
           - Из пути: сегмент после shiki_id ('Путь: 40748/5/sub.ass' -> 5)

        Returns:
            SubtitlesLogPayload если удалось извлечь и ID, и номер серии, иначе None.
        """
        if not text or not cls.is_subtitles_log(text):
            return None

        shiki_id: Optional[int] = None
        episode_num: Optional[int] = None

        # 1. Попытка извлечь сразу из пути: Путь: 40748/5/... или Путь: /40748/5/...
        path_match = re.search(r"(?:путь|path)\s*[:=]\s*/*(\d+)/(\d+)", text, re.IGNORECASE)
        if path_match:
            shiki_id = int(path_match.group(1))
            episode_num = int(path_match.group(2))

        # 2. Если shiki_id еще не найден, ищем по ссылке на Shikimori или ID
        if shiki_id is None:
            url_match = re.search(r"/animes/(?:z|a)?(\d+)", text, re.IGNORECASE)
            if url_match:
                shiki_id = int(url_match.group(1))
            else:
                id_match = re.search(r"(?:shikimori\s*id|shiki\s*id|тайтл\s*id|id)\s*[:=]\s*(\d+)", text, re.IGNORECASE)
                if id_match:
                    shiki_id = int(id_match.group(1))

        # 3. Если episode_num еще не найден, ищем явное указание серии
        if episode_num is None:
            ep_match = re.search(r"(?:серия|эпизод|episode|ep)\s*[:#\s]\s*(\d+)", text, re.IGNORECASE)
            if ep_match:
                episode_num = int(ep_match.group(1))

        if shiki_id is not None and episode_num is not None:
            return SubtitlesLogPayload(
                shiki_id=shiki_id,
                episode_num=episode_num,
                raw_text=text,
            )

        return None
