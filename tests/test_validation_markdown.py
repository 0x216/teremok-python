import pytest
from aiogram import Router
from aiogram.exceptions import TelegramBadRequest

from teremok import MockBot


def make_bot() -> MockBot:
    return MockBot(Router())


async def send_v2(bot: MockBot, text: str) -> None:
    await bot.send_message(chat_id=1, text=text, parse_mode="MarkdownV2")


async def test_valid_markdown_v2_passes() -> None:
    bot = make_bot()
    await send_v2(
        bot,
        "*bold* _italic_ __underline__ ~strike~ ||spoiler|| `code` "
        "[link](https://example.com) escaped dot\\. and \\* star\n"
        ">quote line",
    )


async def test_unescaped_reserved_char_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="reserved and must be escaped"):
        await send_v2(bot, "version 2.0")  # unescaped '.'


async def test_unbalanced_bold_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await send_v2(bot, "*bold")


async def test_unbalanced_spoiler_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await send_v2(bot, "||spoiler")


async def test_link_without_url_end_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await send_v2(bot, "[text](https://example.com")


async def test_reserved_chars_fine_inside_code() -> None:
    bot = make_bot()
    await send_v2(bot, "`a.b(c)!` and ```\nx = f(1). # ok\n```")


async def test_escaped_backslash_sequences() -> None:
    bot = make_bot()
    await send_v2(bot, "literal backslash \\\\ then escaped underscore \\_")


async def test_legacy_markdown_balanced_ok_and_reserved_not_required() -> None:
    bot = make_bot()
    await bot.send_message(
        chat_id=1, text="*bold* with a plain dot. and (parens)",
        parse_mode="Markdown",
    )


async def test_legacy_markdown_unbalanced_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await bot.send_message(chat_id=1, text="*oops", parse_mode="Markdown")


async def test_custom_emoji_syntax_passes() -> None:
    bot = make_bot()
    await send_v2(bot, "![👍](tg://emoji?id=5368324170671202286)")


async def test_unescaped_bang_still_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="reserved and must be escaped"):
        await send_v2(bot, "wow!")


async def test_legacy_escaped_delimiters_pass() -> None:
    bot = make_bot()
    await bot.send_message(
        chat_id=1, text="just an escaped star: \\* and underscore \\_",
        parse_mode="Markdown",
    )
