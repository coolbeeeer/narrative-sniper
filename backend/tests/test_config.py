import pytest
from app.core.config import settings


def test_settings_load():
    assert settings.APP_NAME == "Narrative Sniper"
    assert settings.PORT == 8000
    assert settings.PAPER_TRADING is True


def test_config_values():
    assert settings.MAX_POSITION_SIZE_USD == 1000.0
    assert settings.SLIPPAGE_BPS == 100
    assert settings.NARRATIVE_CONFIDENCE_THRESHOLD == 0.6