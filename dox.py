
# requires: aiohttp
# author: @ferguson
# version: 1.0.0
# description: Простой докс-модуль с заглушкой
# scop: kernel (min) v([__lastest__])

from utils import answer


def register(kernel):
    @kernel.register.command("dox")
    async def dox_handler(event):
        """
        Dox command - отвечает заглушкой
        
        Использование:
            .dox
        """
        try:
            await answer(event, "иди нахуй", as_html=False)
        except Exception as e:
            await kernel.handle_error(e, source="dox", event=event)
