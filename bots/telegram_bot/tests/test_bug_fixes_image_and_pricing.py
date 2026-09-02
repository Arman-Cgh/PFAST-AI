"""
Automated regression and bug fix test suite for:
1. Disabled Image Feature Gate (Zero AI calls when disabled)
2. Canonical Price Parsing and '/' Thousands Separator Formatting
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from database.db import init_db, set_plan_price, get_plan_prices, set_admin_action
from services.features.service import set_feature_status, toggle_feature
from utils.feature_gate import clear_feature_cache, check_feature_access
from utils.pricing import parse_price_value, parse_price_input, format_price
from handlers.message import handle_message, _handle_admin_action
from handlers.callbacks import callback_dispatcher
from services.ai.engine import AIEngine
from services.ai.intent_router import IntentRouter
from config import ADMIN_ID


@pytest.fixture(autouse=True)
def setup_db_and_cache():
    init_db()
    clear_feature_cache()
    yield
    clear_feature_cache()


# ==========================================================================
# 1. Price Parsing and Formatting Tests (Bug 2)
# ==========================================================================

def test_price_parsing_slash_with_emoji():
    """'200/000 💸' should represent numeric value 200000."""
    assert parse_price_value("200/000 💸") == 200000


def test_price_parsing_comma_separated():
    """'200,000' and '200،000' should represent numeric value 200000."""
    assert parse_price_value("200,000") == 200000
    assert parse_price_value("200،000 تومان") == 200000


def test_price_parsing_plain_numeric():
    """'200000' should represent numeric value 200000."""
    assert parse_price_value("200000") == 200000
    assert parse_price_value(200000) == 200000


def test_price_parsing_persian_digits_with_slash():
    """'۲۰۰/۰۰۰ 💸' should parse to 200000."""
    assert parse_price_value("۲۰۰/۰۰۰ 💸") == 200000


def test_price_parsing_multiple_slashes_and_large_numbers():
    """'1/500/000', '5/000/000', '10/000/000' must parse correctly."""
    assert parse_price_value("1/500/000") == 1500000
    assert parse_price_value("5/000/000") == 5000000
    assert parse_price_value("10/000/000") == 10000000


def test_price_parsing_word_units():
    """'350 هزار تومان' and '1.5 میلیون تومان' must parse correctly."""
    assert parse_price_value("350 هزار تومان") == 350000
    assert parse_price_value("1.5 میلیون تومان") == 1500000
    assert parse_price_value("200k") == 200000


def test_price_input_currency_detection():
    amount, currency = parse_price_input("200/000 💸")
    assert amount == 200000
    assert currency == "تومان"

    amount_irr, currency_irr = parse_price_input("2000000 ریال")
    assert amount_irr == 2000000
    assert currency_irr == "IRR"


def test_price_formatting_slash_separator():
    """format_price must format 200000 as '200/000 تومان'."""
    assert format_price(200000) == "200/000 تومان"
    assert format_price(1500000) == "1/500/000 تومان"
    assert format_price(5000000) == "5/000/000 تومان"
    assert format_price(10000000) == "10/000/000 تومان"
    assert format_price(0) == "0 تومان"
    assert format_price(200000, include_currency=False) == "200/000"


def test_set_plan_price_and_formatted_retrieval():
    """Ensure set_plan_price normalizes input and formatting displays '/' separator."""
    set_plan_price("pro", "350/000 💸", currency="تومان")
    prices = get_plan_prices()
    pro_plan = prices["pro"]
    assert pro_plan["price"] == 350000
    assert format_price(pro_plan["price"], pro_plan["currency"]) == "350/000 تومان"


# ==========================================================================
# 2. Image Feature Gate Tests (Bug 1: Zero AI calls when disabled)
# ==========================================================================

@pytest.mark.asyncio
async def test_user_callback_image_rejected_when_feature_disabled():
    """When image_generation is disabled, clicking feature:image edits message with disabled text and does NOT set pending_action."""
    set_feature_status("image_generation", enabled=False)
    clear_feature_cache()

    update = MagicMock()
    query = MagicMock()
    query.data = "feature:image"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.from_user = MagicMock(id=12345)
    update.callback_query = query

    context = MagicMock()
    context.user_data = {}

    await callback_dispatcher(update, context)

    # Must edit message with disabled message
    query.edit_message_text.assert_called_once()
    disabled_text = query.edit_message_text.call_args[0][0]
    assert "سرویس تولید تصویر هوش مصنوعی موقتاً در دسترس نیست" in disabled_text
    # Must NOT set pending_action
    assert "pending_action" not in context.user_data


@pytest.mark.asyncio
async def test_user_callback_image_allowed_when_feature_enabled():
    """When image_generation is enabled, clicking feature:image sets pending_action and prompts."""
    set_feature_status("image_generation", enabled=True)
    clear_feature_cache()

    update = MagicMock()
    query = MagicMock()
    query.data = "feature:image"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.from_user = MagicMock(id=12345)
    update.callback_query = query

    context = MagicMock()
    context.user_data = {}

    await callback_dispatcher(update, context)

    assert context.user_data.get("pending_action") == "image"
    query.edit_message_text.assert_called_once_with("🖼 متن تصویر را ارسال کنید.")


@pytest.mark.asyncio
async def test_message_handler_blocks_image_when_disabled_without_calling_ai():
    """
    When image_generation is disabled and a message with pending_action='image' arrives:
    - Reply with disabled message
    - Clear pending_action
    - NEVER call AI Engine or AI provider
    """
    set_feature_status("image_generation", enabled=False)
    clear_feature_cache()

    update = MagicMock()
    message = MagicMock()
    message.text = "یک تصویر از غروب خورشید در کوهستان"
    message.reply_text = AsyncMock()
    update.message = message
    update.effective_user = MagicMock(id=98765, username="tester", first_name="Test")

    context = MagicMock()
    context.user_data = {"pending_action": "image"}

    with patch("services.ai.engine.AIEngine.generate_response") as mock_ai_generate, \
         patch("services.ai.providers.manager.ProviderManager.generate") as mock_provider_gen:
        await handle_message(update, context)

        # AI Engine and Provider must NEVER be called
        mock_ai_generate.assert_not_called()
        mock_provider_gen.assert_not_called()

    # User received disabled message
    message.reply_text.assert_called_once()
    reply_text = message.reply_text.call_args[0][0]
    assert "سرویس تولید تصویر هوش مصنوعی موقتاً در دسترس نیست" in reply_text
    # pending_action was cleared
    assert "pending_action" not in context.user_data


@pytest.mark.asyncio
async def test_admin_action_blocks_image_when_disabled_without_calling_ai():
    """
    When image_generation is disabled and admin sends image prompt in admin image mode:
    - Reply with disabled message
    - Clear admin action
    - NEVER call AI Engine or provider
    """
    set_feature_status("image_generation", enabled=False)
    clear_feature_cache()

    set_admin_action(ADMIN_ID, "image")

    update = MagicMock()
    message = MagicMock()
    message.text = "طرح یک لوگوی مدرن"
    message.reply_text = AsyncMock()
    update.message = message
    update.effective_user = MagicMock(id=ADMIN_ID, username="admin", first_name="Admin")

    context = MagicMock()

    with patch("services.ai.engine.AIEngine.generate_response", new_callable=AsyncMock) as mock_ai_generate, \
         patch("services.ai.providers.manager.ProviderManager.generate", new_callable=AsyncMock) as mock_provider_gen:
        await handle_message(update, context)

        # AI Engine and Provider must NEVER be called
        mock_ai_generate.assert_not_called()
        mock_provider_gen.assert_not_called()

    message.reply_text.assert_called_once()
    reply_text = message.reply_text.call_args[0][0]
    assert "سرویس تولید تصویر هوش مصنوعی موقتاً در دسترس نیست" in reply_text


@pytest.mark.asyncio
async def test_ai_engine_blocks_image_intent_when_disabled_without_provider_call():
    """
    When an image keyword or intent reaches AIEngine.generate_response while image_generation
    is disabled, it returns the disabled response with provider='none' and NEVER calls ResponsePipeline or Provider.
    """
    set_feature_status("image_generation", enabled=False)
    clear_feature_cache()

    engine = AIEngine()

    with patch("services.ai.pipeline.response.ResponsePipeline.generate") as mock_pipeline_gen, \
         patch("services.ai.providers.manager.ProviderManager.generate") as mock_provider_gen:
        result = await engine.generate_response(
            user_id=12345,
            message="یک عکس از ماشین فضایی بساز",
        )

        mock_pipeline_gen.assert_not_called()
        mock_provider_gen.assert_not_called()

    assert result["provider"] == "none"
    assert "سرویس تولید تصویر هوش مصنوعی موقتاً در دسترس نیست" in result["response"]
