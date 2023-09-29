from cache import BotCache
from typings import Bot_Settings, BotLogger
from utilities import BotBase, CircuitBreaker, Database, bot_logger, bot_utils


class Smiffy(BotBase):
    __version__: str = "2.1"

    def __init__(self, **kwargs: Bot_Settings):
        """
        The __init__ function is called when the class is instantiated.
        It sets up all of the attributes that are needed for this bot to function properly.

        :param kwargs: Pass the bot settings to the super class
        :return: Bot instance
        """

        super().__init__(**kwargs)

        self.logger: BotLogger = bot_logger.get_logger
        self.db: Database = Database.setup(bot=self)
        self.circuit_breaker: CircuitBreaker = CircuitBreaker(client=self)
        self.cache: BotCache = BotCache(client=self)

        bot_utils.load_cogs(bot=self)
        self.loop.create_task(bot_utils.set_activity(bot=self))

    async def on_ready(self) -> None:
        """
        Called when the client is done preparing the data received from Discord.
        Usually after login is successful and the Client.guilds are filled up.

        :return: None
        """

        await self.cache.chunk_guilds(run_in_tasks=True)
        # enabled run_in_task starts chunking members in separate tasks.
        # This speeds up the bot launch process, but the members are not fully chunked before the bot is ready.

        bot_utils.print_welcome_message(bot=self)

    async def on_connect(self) -> None:
        """
        The on_connect function is called when the bot has successfully connected to discord.

        :return: None
        """

        await self.setup_checks()
        await self.setup_session()

        await super().on_connect()

        self.logger.info(f"Shard #{len(self.shards)} has been connected to Discord API.")


if __name__ == "__main__":
    bot = Smiffy(**bot_utils.get_bot_settings)
    bot.run(bot_utils.get_token)
    bot.db.close()
