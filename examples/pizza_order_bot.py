"""Pizza order wizard - a multi-step inline-keyboard bot with real i18n.

What this dogfoods beyond the simpler examples: CallbackData routing,
live keyboard editing (toggle buttons), mixed callback/text input,
validation branches, and aiogram's gettext i18n middleware running
through teremok's dispatch.

Note the `create_router()` factory: aiogram forbids attaching one Router
to two dispatchers, so tests build a fresh router per MockBot
(see docs/quirks.md #13).
"""

from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.i18n import FSMI18nMiddleware, I18n
from aiogram.utils.i18n import gettext as _

LOCALES_DIR = Path(__file__).parent / "pizza_locales"

SIZES = {"S": 8.0, "M": 10.0, "L": 12.0}
TOPPINGS = ("Cheese", "Mushrooms", "Pepperoni", "Olives")
TOPPING_PRICE = 1.5
MIN_ADDRESS_LEN = 5

i18n = I18n(path=LOCALES_DIR, default_locale="en", domain="messages")
i18n_middleware = FSMI18nMiddleware(i18n)


class OrderStates(StatesGroup):
    choosing_language = State()
    choosing_size = State()
    picking_toppings = State()
    entering_address = State()
    confirming = State()


class LangCb(CallbackData, prefix="lang"):
    code: str


class SizeCb(CallbackData, prefix="size"):
    size: str


class ToppingCb(CallbackData, prefix="top"):
    name: str


class ActionCb(CallbackData, prefix="act"):
    action: str


def total_price(size: str, toppings: list[str]) -> float:
    return SIZES[size] + TOPPING_PRICE * len(toppings)


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🇬🇧 English", callback_data=LangCb(code="en").pack()
                ),
                InlineKeyboardButton(
                    text="🇷🇺 Русский", callback_data=LangCb(code="ru").pack()
                ),
            ]
        ]
    )


def cancel_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=_("❌ Cancel"), callback_data=ActionCb(action="cancel").pack()
    )


def size_keyboard() -> InlineKeyboardMarkup:
    size_row = [
        InlineKeyboardButton(
            text=f"{size} ${price:.0f}", callback_data=SizeCb(size=size).pack()
        )
        for size, price in SIZES.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=[size_row, [cancel_button()]])


def toppings_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for name in TOPPINGS:
        mark = "✅" if name in selected else "⬜"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark} {_(name)}",
                    callback_data=ToppingCb(name=name).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=_("Done ➡️"), callback_data=ActionCb(action="done").pack()
            ),
            cancel_button(),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_("Confirm ✅"),
                    callback_data=ActionCb(action="confirm").pack(),
                ),
                cancel_button(),
            ]
        ]
    )


def order_summary(size: str, toppings: list[str], address: str) -> str:
    toppings_text = ", ".join(_(name) for name in toppings) if toppings else _("(none)")
    return _(
        "Your order:\n"
        "Size: {size}\n"
        "Toppings: {toppings}\n"
        "Address: {address}\n"
        "Total: ${total}"
    ).format(
        size=size,
        toppings=toppings_text,
        address=address,
        total=f"{total_price(size, toppings):.2f}",
    )


async def cmd_order(message: Message, state: FSMContext) -> None:
    await state.set_state(OrderStates.choosing_language)
    await message.answer(_("Choose your language:"), reply_markup=language_keyboard())


async def pick_language(
    callback: CallbackQuery, callback_data: LangCb, state: FSMContext
) -> None:
    await i18n_middleware.set_locale(state, callback_data.code)
    await state.set_state(OrderStates.choosing_size)
    await callback.answer()
    assert isinstance(callback.message, Message)
    await callback.message.edit_text(_("Choose your size:"), reply_markup=size_keyboard())


async def pick_size(
    callback: CallbackQuery, callback_data: SizeCb, state: FSMContext
) -> None:
    await state.update_data(size=callback_data.size, toppings=[])
    await state.set_state(OrderStates.picking_toppings)
    await callback.answer()
    assert isinstance(callback.message, Message)
    await callback.message.edit_text(
        _("Pick your toppings:"), reply_markup=toppings_keyboard([])
    )


async def toggle_topping(
    callback: CallbackQuery, callback_data: ToppingCb, state: FSMContext
) -> None:
    data = await state.get_data()
    selected: list[str] = data["toppings"]
    if callback_data.name in selected:
        selected.remove(callback_data.name)
    else:
        selected.append(callback_data.name)
    await state.update_data(toppings=selected)
    await callback.answer()
    assert isinstance(callback.message, Message)
    await callback.message.edit_reply_markup(reply_markup=toppings_keyboard(selected))


async def toppings_done(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OrderStates.entering_address)
    await callback.answer()
    assert isinstance(callback.message, Message)
    await callback.message.edit_text(_("Send me your delivery address:"))


async def enter_address(message: Message, state: FSMContext) -> None:
    address = (message.text or "").strip()
    if len(address) < MIN_ADDRESS_LEN:
        await message.answer(_("Address looks too short, try again:"))
        return
    data = await state.update_data(address=address)
    await state.set_state(OrderStates.confirming)
    await message.answer(
        order_summary(data["size"], data["toppings"], address),
        reply_markup=confirm_keyboard(),
    )


async def confirm_order(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    total = total_price(data["size"], data["toppings"])
    await state.clear()
    await callback.answer()
    assert isinstance(callback.message, Message)
    await callback.message.edit_text(
        _("Order placed! Total: ${total}").format(total=f"{total:.2f}")
    )


async def cancel_order(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    assert isinstance(callback.message, Message)
    await callback.message.edit_text(_("Order cancelled"))


def create_router() -> Router:
    """Build a fresh wired router.

    A factory (not a module-level router) because aiogram forbids attaching
    one Router instance to a second dispatcher - each MockBot needs its own.
    """
    router = Router()
    i18n_middleware.setup(router)
    router.message.register(cmd_order, Command("order"))
    router.callback_query.register(
        pick_language, OrderStates.choosing_language, LangCb.filter()
    )
    router.callback_query.register(pick_size, OrderStates.choosing_size, SizeCb.filter())
    router.callback_query.register(
        toggle_topping, OrderStates.picking_toppings, ToppingCb.filter()
    )
    router.callback_query.register(
        toppings_done, OrderStates.picking_toppings, ActionCb.filter(F.action == "done")
    )
    router.message.register(enter_address, OrderStates.entering_address, F.text)
    router.callback_query.register(
        confirm_order, OrderStates.confirming, ActionCb.filter(F.action == "confirm")
    )
    router.callback_query.register(cancel_order, ActionCb.filter(F.action == "cancel"))
    return router
