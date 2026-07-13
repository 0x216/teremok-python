pytest_plugins = ["pytester"]


def test_mock_bot_fixture_is_auto_registered(pytester) -> None:
    pytester.makepyfile(
        """
        from aiogram import Router
        from aiogram.types import Message

        from teremok import MockMessageText

        router = Router()

        @router.message()
        async def echo(message: Message) -> None:
            await message.answer(message.text or "")

        async def test_echo(mock_bot):
            bot = mock_bot(router)
            await bot.dispatch(MockMessageText("hi"))
            assert bot.requests.send_message[0].text == "hi"
        """
    )
    result = pytester.runpytest("-o", "asyncio_mode=auto")
    result.assert_outcomes(passed=1)
