from examples.echo_bot import router as echo_router
from examples.fsm_form_bot import router as form_router
from examples.photo_bot import router as photo_router
from teremok import MockBot, MockMessagePhoto, MockMessageText


async def test_echo_bot() -> None:
    bot = MockBot(echo_router)
    await bot.dispatch(MockMessageText("/start"))
    await bot.dispatch(MockMessageText("hello"))
    texts = [m.text for m in bot.requests.send_message]
    assert texts == ["Hi! Send me anything and I'll echo it.", "hello"]


async def test_fsm_form_bot_full_flow() -> None:
    bot = MockBot(form_router)
    await bot.dispatch(MockMessageText("/form"))
    await bot.dispatch(MockMessageText("Alice"))
    await bot.dispatch(MockMessageText("30"))
    assert bot.requests.send_message[-1].text == "Nice to meet you, Alice (30)!"
    assert await bot.get_state() is None


async def test_photo_bot() -> None:
    bot = MockBot(photo_router)
    bot.add_file("photo_1", b"0123456789")
    await bot.dispatch(MockMessagePhoto(file_id="photo_1"))
    assert bot.requests.send_message[0].text == "Got your photo: 10 bytes"
    assert bot.requests.send_photo[0].caption == "Right back at you!"
