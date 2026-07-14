import pytest
from aiogram import Router
from aiogram.exceptions import TelegramBadRequest

from teremok import MockBot


def make_bot() -> MockBot:
    return MockBot(Router())


async def send(bot: MockBot, text: str) -> None:
    await bot.send_message(chat_id=1, text=text, parse_mode="HTML")


async def test_valid_html_passes() -> None:
    bot = make_bot()
    await send(
        bot,
        '<b>bold <i>nested</i></b> <a href="https://example.com">link</a> '
        '<code class="language-python">x=1</code> <pre>block</pre> '
        '<span class="tg-spoiler">shh</span> <tg-spoiler>shh</tg-spoiler> '
        "<blockquote>q</blockquote> <blockquote expandable>q</blockquote> "
        "5 &lt; 6 &amp; 7 &#128512;",
    )
    # reaching this line without TelegramBadRequest IS the assertion
    assert len(bot.requests.send_message) == 1


async def test_unclosed_tag_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await send(bot, "<b>oops")


async def test_mismatched_nesting_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await send(bot, "<b><i>x</b></i>")


async def test_unsupported_tag_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="Unsupported start tag"):
        await send(bot, "<div>nope</div>")


async def test_stray_lt_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await send(bot, "5 < 6")


async def test_bare_ampersand_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await send(bot, "you & me")


async def test_bare_gt_accepted() -> None:
    # docs say to escape '>' but the real API accepts it; we must not false-400
    bot = make_bot()
    await send(bot, "5 > 4")


async def test_a_requires_href() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await send(bot, "<a>link</a>")


async def test_span_requires_tg_spoiler_class() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await send(bot, '<span class="highlight">x</span>')


async def test_unknown_attribute_rejected() -> None:
    bot = make_bot()
    with pytest.raises(TelegramBadRequest, match="can't parse entities"):
        await send(bot, '<b style="color:red">x</b>')


async def test_plain_text_without_parse_mode_ignores_html() -> None:
    bot = make_bot()
    msg = await bot.send_message(chat_id=1, text="<b>not parsed")
    assert msg.message_id >= 1
