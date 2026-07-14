from aiogram.methods import EditMessageReplyMarkup, EditMessageText

from examples.pizza_order_bot import (
    ActionCb,
    LangCb,
    OrderStates,
    SizeCb,
    ToppingCb,
    create_router,
)
from teremok import MockBot, MockCallbackQuery, MockMessageText


def make_bot() -> MockBot:
    return MockBot(create_router())


async def start_order(bot: MockBot, lang: str = "en") -> None:
    """Drive the flow to the size screen in the given language."""
    await bot.dispatch(MockMessageText("/order"))
    await bot.dispatch(MockCallbackQuery(data=LangCb(code=lang).pack()))


async def to_toppings(bot: MockBot, size: str = "L", lang: str = "en") -> None:
    await start_order(bot, lang)
    await bot.dispatch(MockCallbackQuery(data=SizeCb(size=size).pack()))


async def test_order_shows_language_picker() -> None:
    bot = make_bot()
    result = await bot.dispatch(MockMessageText("/order"))
    assert result.handled
    sent = bot.requests.send_message[0]
    assert sent.text == "Choose your language:"
    lang_row = sent.reply_markup.inline_keyboard[0]
    assert [b.callback_data for b in lang_row] == [
        LangCb(code="en").pack(),
        LangCb(code="ru").pack(),
    ]
    assert await bot.get_state() == OrderStates.choosing_language.state


async def test_pick_language_shows_sizes_in_english() -> None:
    bot = make_bot()
    await start_order(bot, "en")
    edit = bot.requests.edit_message_text[0]
    assert edit.text == "Choose your size:"
    size_row = edit.reply_markup.inline_keyboard[0]
    assert [b.callback_data for b in size_row] == [
        SizeCb(size="S").pack(),
        SizeCb(size="M").pack(),
        SizeCb(size="L").pack(),
    ]
    assert len(bot.requests.answer_callback_query) == 1


async def test_pick_language_shows_sizes_in_russian() -> None:
    bot = make_bot()
    await start_order(bot, "ru")
    assert bot.requests.edit_message_text[0].text == "Выбери размер:"


async def test_pick_size_shows_toppings_all_unchecked() -> None:
    bot = make_bot()
    await to_toppings(bot, "L")
    edit = bot.requests.edit_message_text[-1]
    assert edit.text == "Pick your toppings:"
    topping_rows = edit.reply_markup.inline_keyboard[:-1]
    assert all(row[0].text.startswith("⬜ ") for row in topping_rows)
    assert (await bot.get_data())["size"] == "L"


async def test_toggle_topping_on_then_off() -> None:
    bot = make_bot()
    await to_toppings(bot)
    await bot.dispatch(MockCallbackQuery(data=ToppingCb(name="Cheese").pack()))
    first = bot.requests.edit_message_reply_markup[0]
    assert first.reply_markup.inline_keyboard[0][0].text == "✅ Cheese"
    await bot.dispatch(MockCallbackQuery(data=ToppingCb(name="Cheese").pack()))
    second = bot.requests.edit_message_reply_markup[1]
    assert second.reply_markup.inline_keyboard[0][0].text == "⬜ Cheese"
    assert (await bot.get_data())["toppings"] == []


async def test_toppings_accumulate_in_fsm_data() -> None:
    bot = make_bot()
    await to_toppings(bot)
    await bot.dispatch(MockCallbackQuery(data=ToppingCb(name="Cheese").pack()))
    await bot.dispatch(MockCallbackQuery(data=ToppingCb(name="Olives").pack()))
    assert (await bot.get_data())["toppings"] == ["Cheese", "Olives"]


async def test_done_asks_for_address() -> None:
    bot = make_bot()
    await to_toppings(bot)
    await bot.dispatch(MockCallbackQuery(data=ActionCb(action="done").pack()))
    assert bot.requests.edit_message_text[-1].text == "Send me your delivery address:"
    assert await bot.get_state() == OrderStates.entering_address.state


async def test_short_address_rejected_state_kept() -> None:
    bot = make_bot()
    await bot.set_state(OrderStates.entering_address)
    await bot.set_data({"size": "S", "toppings": []})
    await bot.dispatch(MockMessageText("abc"))
    assert bot.requests.send_message[-1].text == "Address looks too short, try again:"
    assert await bot.get_state() == OrderStates.entering_address.state


async def test_valid_address_shows_summary_with_exact_total() -> None:
    bot = make_bot()
    await bot.set_state(OrderStates.entering_address)
    await bot.set_data({"size": "L", "toppings": ["Cheese", "Olives"]})
    await bot.dispatch(MockMessageText("221B Baker Street"))
    summary = bot.requests.send_message[-1]
    assert "Size: L" in summary.text
    assert "Cheese, Olives" in summary.text
    assert "221B Baker Street" in summary.text
    assert "Total: $15.00" in summary.text
    assert await bot.get_state() == OrderStates.confirming.state


async def test_confirm_places_order_and_clears_state() -> None:
    bot = make_bot()
    await bot.set_state(OrderStates.confirming)
    await bot.set_data({"size": "L", "toppings": ["Cheese", "Olives"]})
    await bot.dispatch(MockCallbackQuery(data=ActionCb(action="confirm").pack()))
    assert bot.requests.edit_message_text[-1].text == "Order placed! Total: $15.00"
    assert await bot.get_state() is None


async def test_cancel_mid_flow_clears_state() -> None:
    bot = make_bot()
    await to_toppings(bot)
    await bot.dispatch(MockCallbackQuery(data=ActionCb(action="cancel").pack()))
    assert bot.requests.edit_message_text[-1].text == "Order cancelled"
    assert await bot.get_state() is None


async def test_cancel_from_language_screen() -> None:
    bot = make_bot()
    await bot.dispatch(MockMessageText("/order"))
    lang_kb = bot.requests.send_message[0].reply_markup
    assert lang_kb.inline_keyboard[-1][0].callback_data == ActionCb(action="cancel").pack()
    await bot.dispatch(MockCallbackQuery(data=ActionCb(action="cancel").pack()))
    assert bot.requests.edit_message_text[-1].text == "Order cancelled"
    assert await bot.get_state() is None


async def test_cancel_from_address_step() -> None:
    bot = make_bot()
    await to_toppings(bot)
    await bot.dispatch(MockCallbackQuery(data=ActionCb(action="done").pack()))
    prompt = bot.requests.edit_message_text[-1]
    assert prompt.reply_markup.inline_keyboard[0][0].callback_data == ActionCb(
        action="cancel"
    ).pack()
    await bot.dispatch(MockCallbackQuery(data=ActionCb(action="cancel").pack()))
    assert bot.requests.edit_message_text[-1].text == "Order cancelled"
    assert await bot.get_state() is None


async def test_unrelated_text_on_keyboard_step_unhandled() -> None:
    bot = make_bot()
    await start_order(bot)
    result = await bot.dispatch(MockMessageText("hello there"))
    assert not result.handled


async def test_full_flow_in_russian() -> None:
    bot = make_bot()
    await to_toppings(bot, size="M", lang="ru")
    assert bot.requests.edit_message_text[-1].text == "Выбери топпинги:"
    await bot.dispatch(MockCallbackQuery(data=ToppingCb(name="Cheese").pack()))
    markup = bot.requests.edit_message_reply_markup[-1]
    assert markup.reply_markup.inline_keyboard[0][0].text == "✅ Сыр"
    await bot.dispatch(MockCallbackQuery(data=ActionCb(action="done").pack()))
    assert bot.requests.edit_message_text[-1].text == "Пришли адрес доставки:"
    # locale survives the text-input step (lives in FSM data)
    await bot.dispatch(MockMessageText("ул. Пушкина, 1"))
    summary = bot.requests.send_message[-1]
    assert summary.text.startswith("Твой заказ:")
    assert "Итого: $11.50" in summary.text
    await bot.dispatch(MockCallbackQuery(data=ActionCb(action="confirm").pack()))
    assert bot.requests.edit_message_text[-1].text == "Заказ оформлен! Итого: $11.50"


async def test_each_callback_is_answered() -> None:
    bot = make_bot()
    await to_toppings(bot)
    await bot.dispatch(MockCallbackQuery(data=ToppingCb(name="Cheese").pack()))
    # language pick + size pick + toggle = 3 callbacks, each answered exactly once
    assert len(bot.requests.answer_callback_query) == 3


async def test_two_bots_get_independent_routers() -> None:
    # quirk #13: a Router attaches to one dispatcher only - the factory
    # pattern must keep two MockBots fully independent
    bot_a = make_bot()
    bot_b = make_bot()
    await bot_a.dispatch(MockMessageText("/order"))
    assert bot_b.requests.all == []
    assert await bot_b.get_state() is None


def test_edit_methods_are_typed_captures() -> None:
    # sanity: the typed capture accessors used above resolve to real methods
    bot = make_bot()
    assert bot.requests.edit_message_text == []
    assert bot.requests.edit_message_reply_markup == []
    assert EditMessageText.__name__ == "EditMessageText"
    assert EditMessageReplyMarkup.__name__ == "EditMessageReplyMarkup"
