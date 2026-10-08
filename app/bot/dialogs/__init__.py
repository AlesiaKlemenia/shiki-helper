"""Экспорт диалогов aiogram-dialog."""
from __future__ import annotations

from app.bot.dialogs.onboarding.dialog import OnboardingSG, onboarding_dialog
from app.bot.dialogs.titles.dialog import TitlesSG, titles_dialog

__all__ = [
    "OnboardingSG",
    "onboarding_dialog",
    "TitlesSG",
    "titles_dialog",
]
