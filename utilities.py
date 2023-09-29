#  pylint: disable=invalid-overridden-method

from __future__ import annotations

from ast import literal_eval
from asyncio import AbstractEventLoop, get_event_loop, new_event_loop, set_event_loop
from logging import DEBUG, INFO, Logger, StreamHandler, basicConfig, getLogger
from os import listdir
from traceback import format_exc
from typing import TYPE_CHECKING, Any, Iterable, Optional, Union

from aiofiles import open as aioopen
from aiohttp import ClientSession, ClientTimeout, client_exceptions
from aiosqlite import connect
from colorama import Fore
from colorama import init as initialize_colarama
from colorlog import ColoredFormatter
from cooldowns import CallableOnCooldown
from cordcutter import Cordcutter, TCallback
from nextcord import (
    AllowedMentions,
    Asset,
    ButtonStyle,
    CallbackWrapper,
    Color,
    Embed,
    Game,
    Intents,
    Interaction,
    Member,
    MemberCacheFlags,
    Message,
    Permissions,
    SlashApplicationCommand,
    Status,
)
from nextcord import errors as nextcord_errors
from nextcord import ui, utils
from nextcord.abc import GuildChannel
from nextcord.ext.application_checks import ApplicationMissingPermissions
from nextcord.ext.commands import AutoShardedBot, Cog
from nextcord.ext.commands import RoleConverter as ncRoleConverter
from nextcord.ext.commands import errors
from orjson import loads

from cache import BotCache
from converters import RoleConverter
from errors import (
    ApplicationCommandIsGuildOnly,
    InvalidServerData,
    MissingBotToken,
    MissingMusicPermissions,
)
from typings import DB_RESPONSE, RED_COLOR, Bot_Settings

if TYPE_CHECKING:
    from aiohttp import ClientResponse
    from aiosqlite import Connection, Cursor, Row
    from mafic import NodePool
    from nextcord import (
        BaseApplicationCommand,
        Guild,
        PartialInteractionMessage,
        Role,
        ShardInfo,
        SlashApplicationSubcommand,
        WebhookMessage,
    )
    from nextcord.ext.commands import Context
    from nextcord.state import ConnectionState
    from nextcord.types.interactions import InteractionType as InteractionPayload

    from bot import Smiffy
    from typings import InterT, UserType


class CircuitBreaker(Cordcutter):
    def __init__(self, client: Smiffy):
        """
        CircuitBreaker is responsible for blocking the command
        if it raises a specific quantity of errors at a specific time.

        :param client: Pass the client object to the super class, which is used for logging
        :return: A instance of the class
        """

        super().__init__(
            client=client,
            threshold=2,
            ignore_exceptions=client.ignore_exceptions,
        )

        self.on_tripped_call(callback=self.tripped_callback)  # pyright: ignore[reportGeneralTypeIssues]

    @staticmethod
    async def tripped_callback(
        command: TCallback,  # pyright: ignore  # pylint: disable=unused-argument
        interaction: CustomInteraction,
        **kwargs: dict[str, Any],  # pylint: disable=unused-argument
    ) -> None:
        """
        The tripped_callback function is called when the command has been tripped.
        This function should be used to send an error message to the user, explaining that something went wrong.

        :param command: Get the command that was called
        :param interaction: Used to send message to the user
        :return: None
        """

        await interaction.send_error_message(
            description="Wygłąda na to, że ta komenda ma aktualnie jakieś problemy. **Spróbuj ponownie za minutę.**"
        )
        return


class BotUtils:
    __slots__ = ("config_data",)

    def __init__(self) -> None:
        """
        BotUtils includes several important features that are necessary for the bot to work properly

        :return: None
        """

        loop: AbstractEventLoop = get_event_loop()
        self.config_data: dict[str, Any] = loop.run_until_complete(self.load_config())

        initialize_colarama()

    @staticmethod
    async def set_activity(bot: Smiffy) -> None:
        """
        The set_activity function is a coroutine that sets the bot activity to 'Running' at startup
        and then changes it to '/pomoc' once the bot has finished loading.

        :param bot: Bot object to change status
        :return: None
        """

        if not bot.is_ready():
            await bot.change_presence(
                activity=Game(name="Running..."),
                status=Status.idle,
            )
            await bot.wait_until_ready()

        await bot.change_presence(
            activity=Game(name="/pomoc"),
            status=Status.dnd,
        )

    def print_welcome_message(self, bot: Smiffy) -> None:
        """
        The print_welcome_message function prints a welcome message to the console when the bot is ready.

        :param bot: Bot object to get name and to check if it is connected to any guilds
        :return: None
        """

        _members: int = sum((guild.member_count for guild in bot.guilds))  # pyright: ignore
        _commands: int = len(bot.get_all_application_commands())
        _guilds: int = len(bot.guilds)
        _bot_name: str = bot.user.name if bot.user else "None"
        _shards: int = len(bot.shards)

        message: str = (
            Fore.GREEN
            + f"""
• {_bot_name} is ready •
╭ ▸ Servers: {_guilds}
│ ▸ Total Members: {_members}
│ ▸ Shards: {_shards}
│ ▸ Commands: {_commands}
╰ ▸ HTTP Session: {bot.session}
"""
        )
        print(message)

        if self.get_value_from_config("SHARDS_CHECK") is True:
            self.shards_check(bot)

    @staticmethod
    def shards_check(bot: Smiffy) -> None:
        """
        The shards_check function is used to check if the bot has enough shards.
        It does this by dividing the amount of guilds by 1100 and rounding it up,
        then comparing that number with the actual amount of shards. If there is a bigger difference
        between the suggested shards and the bot's shards then a warning message will be displayed.

        :param bot: Access the bot's guilds and shards
        :return: None
        """

        guilds: int = len(bot.guilds)
        shards: int = len(bot.shards)
        ratio: float = round(guilds / 1100, 3)

        suggested_shards: int = round(ratio + 0.5)

        if (
            shards
            not in (
                suggested_shards,
                suggested_shards + 1,
            )
            or ratio <= 0.3
            and shards != 1
        ):
            description: str = (
                Fore.RED
                + f"""------- SHARDS CHECK -------
┏ Status: Action required
┗ Suggested amount of shards: {suggested_shards}
"""
            )
        else:
            description: str = (
                Fore.GREEN
                + f"""------- SHARDS CHECK -------
┏ Status: OK
┗ Ratio: {ratio}
            """
            )

        print(description)

    @staticmethod
    async def load_config() -> dict[str, Any]:
        """
        The load_config function is used to load the config.json file into a dictionary object,
        which can then be accessed by other functions in the bot.

        :return: A dictionary
        """
        async with aioopen("Data/config.json", "r") as file:
            config_data: dict[str, Any] = loads(await file.read())

            return config_data

    def get_value_from_config(self, key: str, default_value: Any = None) -> Any:
        """
        The get_value_from_config function is a helper function that allows you to retrieve values from the config file.

        :param key: Specify the key of the value that we want to get from our config file
        :param default_value: Set a default value for the key if it is not found in the config file

        :return: The value of the key in the config_data dictionary
        """

        return self.config_data.get(key, default_value)

    @property
    def get_token(self) -> Optional[str]:
        """
        The get_token property is used to retrieve the bot token from the config.json file.
        If no token is found, it will raise a MissingBotToken exception.

        :return: The token that is stored in the config if exists
        """

        token: Optional[str] = self.get_value_from_config("TOKEN")
        if token not in (" ", "", None):
            return token

        raise MissingBotToken

    @property
    def get_bot_intents(self) -> Intents:
        """
        The get_bot_intents property returns a intents for proper bot running

        :return: intents of the bot
        """

        intents = Intents.all()
        return intents

    @property
    def get_bot_settings(self) -> Bot_Settings:
        """
        The get_bot_intents property returns the bot settings

        :return: dict with bot settings
        """

        shards: int = self.get_value_from_config("SHARDS", 1)

        chunk_guilds_status: Optional[bool] = self.get_value_from_config("CHUNK_GUILDS_AT_STARTUP", True)

        _settings: Bot_Settings = {
            "command_prefix": "sf!",
            "intents": self.get_bot_intents,
            "case_insensitive": True,
            "allowed_mentions": AllowedMentions(everyone=False, roles=False),
            "shard_count": shards,
            "member_cache_flags": MemberCacheFlags(voice=True, joined=False),
            "chunk_guilds_at_startup": chunk_guilds_status,
        }

        return _settings

    @staticmethod
    def load_cogs(bot: Smiffy) -> None:
        """
        The load_cogs function is used to load all the cogs in the bot.
            It takes a single argument, which is an instance of Smiffy.
            The function then loads all cogs from two folders: Commands and Events.

        :param bot: Pass the bot object to the function
        :return: None
        """

        bot.load_cog("Commands.music.__main__", "__main__")
        bot.load_cog(
            "Commands.economy.__main__",
            "__main__",
        )

        cog_folders: list[str] = [
            "./Commands",
            "./Events",
        ]

        for cog_folder in cog_folders:
            for file_or_folder in listdir(cog_folder):
                if file_or_folder.endswith(".py"):
                    extenstion_path: str = f"{cog_folder[2::]}.{file_or_folder[:-3]}"
                    bot.load_cog(
                        extenstion_path,
                        file_or_folder,
                    )
                else:
                    # this is folder with cogs
                    for file in listdir(f"./{cog_folder}/{file_or_folder}"):
                        if file.endswith(".py") and file != "__main__.py":
                            extenstion_path: str = f"{cog_folder[2::]}.{file_or_folder}.{file[:-3]}"
                            bot.load_cog(
                                extenstion_path,
                                file,
                            )


class BotLogger:
    __slots__ = ("log", "__logger")

    log_level: int = DEBUG
    log_format: str = "%(log_color)s%(levelname)s | %(filename)s | %(asctime)s > %(message)s"

    def __init__(self) -> None:
        """
        Logger sets up the logging module and creates a logger object that can be used to log messages.
        The logger object has a set level, which determines what kind of messages are logged (debug, info, warning etc.)
        The formatter defines how the message will look like in the console.

        :return: None
        """

        if bot_utils.get_value_from_config("LOGS_FILE"):
            basicConfig(
                level=self.log_level,
                format="%(levelname)s | %(filename)s | %(asctime)s | %(message)s",
                datefmt="%H:%M:%S",
                filename="Data/logs.txt",
                filemode="w",
            )

        formatter = ColoredFormatter(self.log_format, datefmt="%H:%M:%S")
        stream = StreamHandler()
        stream.setLevel(INFO)
        stream.setFormatter(formatter)

        self.__logger = getLogger("SmiffyCFG")
        self.__logger.setLevel(self.log_level)
        self.__logger.addHandler(stream)

    @property
    def get_logger(self) -> Logger:
        """
        The get_logger property returns a logger object that can be used to log messages.

        :return: The logger object
        """
        return self.__logger


class Avatars:
    @staticmethod
    def get_user_avatar(
        user: Optional[UserType],
    ) -> str:
        """
        The get_user_avatar function takes a user object and returns the URL of their avatar.
        If they don't have an avatar, it will return the default Discord avatar.

        :param user: Specify the user
        :return: The url of the user's avatar
        """

        if not user:
            return "https://cdn.siasat.com/wp-content/uploads/2021/05/Discord.jpg"

        try:
            avatar: Asset = user.display_avatar  # pyright: ignore
        except AttributeError:
            avatar: str = user.default_avatar.url

        return str(avatar)

    @staticmethod
    def get_guild_icon(
        guild: Optional[Guild],
    ) -> str:
        """
        The get_guild_icon function takes in a Guild object and returns the URL of its icon.
        If the guild has no icon, it will return a default Discord server logo.

        :param guild: Pass the guild
        :return: The guild icon if it exists, otherwise returns the default discord logo
        """

        default_icon: str = (
            "https://www.howtogeek.com/wp-content/uploads/2021/07/Discord-Logo-Lede.png"
            "?height=200p&trim=2,2,2,2"
        )

        if not guild:
            return default_icon

        try:
            icon: str = guild.icon.url  # pyright: ignore
        except AttributeError:
            icon: str = default_icon

        return icon


class CustomInteraction(Interaction["Smiffy"]):
    __slots__: tuple[str, ...] = ("avatars",)

    def __init__(
        self,
        *,
        data: InteractionPayload,
        state: ConnectionState,
    ) -> None:
        """
        CustomInteraction adds some new functionality to the original interaction.

        :param *: Indicate that all the following parameters are keyword only
        :param data: Pass the data to the class
        :param state: Store the state of the interaction
        :return: None
        """

        super().__init__(data=data, state=state)  # pyright: ignore

        self.avatars: Avatars = Avatars()

    @property
    def bot(self) -> Smiffy:
        """
        Alias for .client property

        :return: The bot object
        """

        return self.client

    @property
    def user_avatar_url(self) -> str:
        """
        The user_avatar_url function returns the URL of a user's avatar.

        :return: The avatar url of the user
        """
        return self.avatars.get_user_avatar(self.user)  # pyright: ignore[reportGeneralTypeIssues]

    @property
    def guild_icon_url(self) -> str:
        """
        The guild_icon_url function returns the URL of the guild's icon.

        :return: The guild icon url
        """

        return self.avatars.get_guild_icon(self.guild)

    def get_bot_latency(self, guild: Optional[Guild] = None) -> tuple[int, int]:
        """
        The get_bot_latency function returns the latency of the bot in milliseconds and shard id.

        :param guild: Get the guild object
        :return: The latency of the bot in milliseconds and the shard id
        """

        if not guild:
            guild = self.guild

        if not guild:
            return 0, 0

        shard_id: int = guild.shard_id
        shard: Optional[ShardInfo] = self.bot.get_shard(shard_id)

        if not shard:
            return 0, 0

        latency: int = round(shard.latency * 1000)

        return latency, shard.id + 1

    async def send_error_message(
        self,
        description: str,
        ephemeral: bool = False,
        delete_after: Optional[int] = None,
    ) -> Union[WebhookMessage, PartialInteractionMessage, None]:
        """
        The send_error_message function is used to send an error message to the chat.

        :param description: Specify the error message content
        :param ephemeral: Determine whether the message is ephemeral or not
        :param delete_after: Seconds after that message is supposed to disappear
        :return: A message object or webhook object

        """

        embed = Embed(
            title="<a:redbutton:919647776885850182> Wystąpił błąd.",
            color=Color.from_rgb(*RED_COLOR),
            timestamp=utils.utcnow(),
            description=f"<:reply:1129168370642718833> {description}",
        )
        embed.set_author(
            name=self.user,
            icon_url=self.user_avatar_url,
        )
        embed.set_thumbnail(url=self.guild_icon_url)
        embed.set_footer(
            text=f"Smiffy v{self.bot.__version__}",
            icon_url=self.bot.avatar_url,
        )

        return await self.send(
            embed=embed,
            ephemeral=ephemeral,
            delete_after=delete_after,
        )

    async def send_success_message(
        self,
        title: str,
        description: str = "",
        color: Color = Color.green(),
        ephemeral: bool = False,
        delete_after: Optional[int] = None,
    ) -> Union[WebhookMessage, PartialInteractionMessage, None]:
        """
        The send_success_message function is a helper function that sends a success message to the user.

        :param title: Set the title of the message
        :param description: Set the description of the embed
        :param color: Define the color of the embed
        :param ephemeral: Determine whether the message is ephemeral or not
        :param delete_after: Seconds after that message is supposed to disappear
        :return: A message object or webhook object
        """

        embed = Embed(
            title=title,
            description=description,
            timestamp=utils.utcnow(),
            colour=color,
        )
        embed.set_author(
            name=self.user,
            icon_url=self.user_avatar_url,
        )
        embed.set_thumbnail(url=self.guild_icon_url)
        embed.set_footer(
            text=f"Smiffy v{self.bot.__version__}",
            icon_url=self.bot.avatar_url,
        )

        return await self.send(
            embed=embed,
            ephemeral=ephemeral,
            delete_after=delete_after,
        )

    def get_command_mention(
        self,
        command_name: str,
        cmd_type: int = 1,
        guild: Optional[Guild] = None,
        sub_command: Optional[str] = None,
    ) -> str:
        """
        The get_command_mention function is used to get the mention for a command.

        :param command_name: Get the command name
        :param cmd_type: Specify the type of command
        :param guild: Server the command is used on
        :param sub_command: sub command name
        :return: A string with the mention of a command
        """
        guild_id: Optional[int] = guild.id if guild else None

        command: Optional[
            Union[
                BaseApplicationCommand,
                SlashApplicationCommand,
            ]
        ] = self.bot.get_application_command_from_signature(
            name=command_name,
            cmd_type=cmd_type,
            guild_id=guild_id,
        )

        if not command:
            return f"/{command_name}"

        if isinstance(command, SlashApplicationCommand):
            if sub_command:
                sub_command_object: Optional[SlashApplicationSubcommand] = command.children.get(sub_command)
                if not sub_command_object:
                    return f"/{command_name} {sub_command}"

                if guild:
                    try:
                        return sub_command_object.get_mention(guild=guild)
                    except ValueError:
                        return f"/{command_name} {sub_command}"

                return sub_command_object.get_mention()

            if guild:
                try:
                    return command.get_mention(guild=guild)
                except ValueError:
                    return f"/{command_name}"

            return command.get_mention()

        command_ids: dict[int | None, int] = command.command_ids
        for command_id in command_ids.values():
            # Due to the fact that smiffy has all the global commands then the same id is assigned to each server.
            # So command_ids.values() contains all the same id - so we can return the first better one.

            if sub_command:
                return f"</{command_name}:{command_id} {sub_command}>"

            return f"</{command_name}:{command_id}>"

        return f"/{command_name}"


class CustomCog(Cog):
    def __init__(self, bot: Smiffy) -> None:
        """
        Currently, CustomCog has no major use.
        Actually, it just adds some helper functions to execute db commands.

        :param bot: Pass the bot object to the cog
        :return: None
        """

        self.bot: Smiffy = bot
        self.avatars: Avatars = Avatars()

    async def get_logs_channel(self, guild: Guild) -> Optional[GuildChannel]:
        """
        The get_logs_channel function is used to retrieve the channel ID of a server's logs channel.

        :param guild: Guild: Get the guild id from the database
        :return: logs channel if logs are enabled
        """

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM server_logs WHERE guild_id = ?",
            (guild.id,),
        )
        if not response:
            return None

        channel: Optional[GuildChannel] = await self.bot.getch_channel(response[1])

        if not channel:
            await self.bot.db.execute_fetchone(
                "DELETE FROM servers_logs WHERE guild_id = ?",
                (guild.id,),
            )

        return channel

    async def get_guild_invites_data(self, guild: Guild) -> Optional[DB_RESPONSE]:
        invites_response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM server_invites WHERE guild_id = ?",
            (guild.id,),
        )

        if not invites_response or not invites_response[0]:
            return None

        return invites_response

    async def get_user_invites(self, guild_id: int, user_id: int) -> tuple[int, ...]:
        user_response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT normal, left, fake, bonus FROM user_invites WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )

        if not user_response:
            normal, left, fake, bonus = 0, 0, 0, 0
        else:
            (
                normal,
                left,
                fake,
                bonus,
            ) = user_response

        return normal, left, fake, bonus


class Database:
    __slots__ = ("connection",)

    def __init__(self, connection: Connection) -> None:
        """
        The __init__ function is called when the class is instantiated.
        It sets up the connection to be used by all of the other functions in this class.

        :param connection: Connection to database
        :return: None
        """

        self.connection: Connection = connection

    @classmethod
    def setup(
        cls,
        bot: Smiffy,
        db_path: str = "./Data/database.db",
    ) -> Database:
        """
        The setup classmethod is used to create a connection to the database.
        It takes in two arguments:
            bot (Smiffy): The Smiffy instance that will be using this database.
            db_path (str): The path of the SQLite3 file that will be used as a database.

        :param bot: Pass the bot object to the database class
        :param db_path: Specify the path to the database
        :return: A database object
        """

        async def connect_db() -> Connection:
            db_connection: Connection = await connect(db_path)
            bot.logger.info("The connection to the database has been established.")

            return db_connection

        connection: Connection = get_event_loop().run_until_complete(connect_db())
        return cls(connection)

    async def execute_fetchall(
        self,
        expression: str,
        args: Optional[tuple] = None,
    ) -> Iterable[Row]:
        """
        The execute_fetchall function executes a SQL expression and returns the result of fetchall() method

        :param expression: Pass in the sql expression to be executed
        :param args: tuple with expression arguments
        :return: A list of rows from the database
        """

        cursor: Cursor = await self.connection.cursor()

        await cursor.execute(sql=expression, parameters=args)
        response: Iterable[Row] = await cursor.fetchall()

        await self.connection.commit()
        await cursor.close()

        return response

    async def execute_fetchone(
        self,
        expression: str,
        args: Optional[tuple] = None,
    ) -> Optional[Row]:
        """
        The execute_fetchone function executes a SQL expression and returns the first row of the result.

        :param expression: Pass in the sql query to be executed
        :param args: tuple with expression arguments
        :return: A single row from the database if exists
        """

        cursor: Cursor = await self.connection.cursor()

        await cursor.execute(sql=expression, parameters=args)
        response: Optional[Row] = await cursor.fetchone()

        await self.connection.commit()
        await cursor.close()

        return response

    def close(self) -> None:
        """
        The close function is used to close the connection to the database.
        It does this by committing any changes made and then closing the connection.

        :return: None
        """

        async def async_runner() -> None:
            await self.connection.commit()
            await self.connection.close()

        loop: AbstractEventLoop = get_event_loop()

        if loop.is_closed():
            loop: AbstractEventLoop = new_event_loop()
            set_event_loop(loop)

        loop.run_until_complete(async_runner())


class BotSession(ClientSession):
    def __init__(self, timeout: ClientTimeout, bot: BotBase) -> None:
        """
        BotSession inherits the ClientSession class and adds some new features to HTTP requests.

        :param timeout: Set the timeout for the client
        :param bot: Store the bot object in the class
        :return: NOne
        """

        super().__init__(timeout=timeout)

        self.bot: BotBase = bot

    def __repr__(self) -> str:
        connector_limit: int = self.connector.limit if self.connector else 0

        return f"<HTTPClient(alive={not self.closed}, limit={connector_limit})>"

    @property
    def get_default_headers(self) -> dict:
        """
        The get_default_headers function returns a dictionary of headers that are used by the requests library.

        :return: A dictionary with headers
        """

        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0",
            "Cache-Control": "no-cache",
        }

    async def post(self, url: str, **kwargs: Any) -> ClientResponse:
        return await self.request("POST", url, **kwargs)

    async def get(self, url: str, **kwargs: Any) -> ClientResponse:
        return await self.request("GET", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> ClientResponse:
        return await self.request("PATCH", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> ClientResponse:
        return await self.request("DELETE", url, **kwargs)

    async def request(  # pylint: disable=invalid-overridden-method
        self,
        method: str,
        url: str,
        default_headers: bool = True,
        **kwargs: Any,
    ) -> ClientResponse:
        """
        Overridden request function allows you to control the status of default header's
        and additionally adds requests logs


        :param method: Specify the http method
        :param url: Pass the url to be requested
        :param default_headers: Determine whether the default headers should be used or not
        :param kwargs: Pass in any number of keyword arguments
        :return: A clientresponse object
        """

        provided_headers: dict = kwargs.get("headers", {})
        headers: dict[str, Any] = provided_headers

        if default_headers:
            headers = self.merge_headers(
                self.get_default_headers,
                provided_headers,
            )

        kwargs["headers"] = headers

        self.bot.logger.debug(f"Sending Request {method} | {url}")

        response: ClientResponse = await super().request(method, url, **kwargs)

        self.bot.logger.debug(f"Recived Response: {method} | {response.status}")

        return response

    async def send_api_request(
        self,
        interaction: CustomInteraction,
        method: str,
        url: str,
        default_headers: bool = True,
        **kwargs: Any,
    ) -> Optional[ClientResponse]:
        """
        The send_api_request function is a wrapper for the request function.
        It sends an API request to the specified URL with the given method and kwargs.
        If the request is not received correctly, the method will automatically send an error_message.


        :param interaction: Send error messages to the channel
        :param method: Specify the type of request we want to send
        :param url: Specify the url of the request
        :param default_headers: Determine whether the default headers should be used
        :param kwargs: Pass a dictionary of arguments to the function
        :return: A clientresponse object (or none if the status is not 200 or 204)
        """

        try:
            response: ClientResponse = await self.request(
                method,
                url,
                default_headers,
                **kwargs,
            )
        except (
            client_exceptions.ClientConnectorError,
            client_exceptions.ServerTimeoutError,
            TimeoutError,
        ) as e:
            await interaction.send_error_message(description="Wystąpił błąd z API. Spróbuj ponownie później.")
            interaction.bot.logger.warning(f"API: {url} returned status: {type(e)}")
            return None

        if response.status not in (200, 204):
            await interaction.send_error_message(description="Wystąpił błąd z API. Spróbuj ponownie później.")
            interaction.bot.logger.warning(f"API: {url} returned status: {response.status}")

            return None

        return response

    @staticmethod
    def merge_headers(default: dict, provided: dict) -> dict:
        """
        The merge_headers function takes two dictionaries as input, and returns a single dictionary.
        The first argument is the default headers that are used for most requests to the API. The second
        argument is any additional headers that may be required by a specific request (e.g., an authorization token).
        The function merges these two dictionaries into one, and returns it.

        :param default: The default headers that will be used if no other headers are provided
        :param provided: Provide a dictionary of headers to the function
        :return: A merged headers
        """

        res: dict = {**default, **provided}
        return res


class BotBase(AutoShardedBot):
    session: BotSession
    pool: NodePool
    logger: Logger
    cache: BotCache

    def __init__(self, **kwargs: Bot_Settings) -> None:
        """
        BotBase is supposed to have additional features that I don't want to junk the main Smiffy class

        :param kwargs: Bot settings
        :return: None
        """

        super().__init__(**kwargs)

        self.ignore_exceptions: tuple[type[Exception], ...] = (
            ApplicationMissingPermissions,
            CallableOnCooldown,
            nextcord_errors.ApplicationCheckFailure,
            MissingMusicPermissions,
            ApplicationCommandIsGuildOnly,
        )

    @property
    def avatar_url(self) -> str:
        """
        The avatar_url function is a property that returns the URL of the bot avatar.

        :return: The avatar url of the bot
        """
        return Avatars.get_user_avatar(self.user)  # pyright: ignore

    def load_cog(self, path: str, name: str) -> None:
        """
        The load_cog function is a wrapper for the load_extension function.
        It takes in two arguments: path and name. The path argument is the filepath to the cog,
        and name is used to logger

        :param path: Specify the path to the cog
        :param name: Specify the name of the file
        :return: None
        """

        self.load_extension(path)
        self.logger.debug(f"Extenstion: {name} loaded.")

    async def on_error(
        self,
        event_method: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        The on_error function is called whenever an exception occurs in the client.

        :param event_method: Specify the name of the event that caused an error
        :param args: Catch any extra parameters that may be passed to the function
        :param kwargs: Pass in a dictionary of keyword arguments
        :return: None
        """

        await super().on_error(event_method, *args, **kwargs)

        kwargs["traceback"] = format_exc()

        self.dispatch("client_error", *args, **kwargs)

    @staticmethod
    async def check_global_ban(
        interaction: InterT,  # pyright: ignore
    ) -> bool:
        """
        The check_global_ban function is a coroutine that checks if the user has been globally banned.
        If so, it sends them an error message and returns False. Otherwise, it returns True.

        :param interaction: Get the user's id from the interaction object
        :return: A bool value
        """

        assert isinstance(interaction, CustomInteraction) and interaction.user

        response: Optional[DB_RESPONSE] = await interaction.bot.db.execute_fetchone(
            "SELECT * FROM global_bans WHERE user_id = ?",
            (interaction.user.id,),
        )

        if not response:
            return True

        account_link: str = "https://discord.com/users/965069058292719666"

        await interaction.send_error_message(
            description="**Niestety, ale wygląda na to, że twój dostęp do bota został zablokowany.**\n"
            f"Chcesz zgłosić odwołanie? Napisz do [xxenvy]({account_link})"
        )

        return False

    async def getch_role(
        self,
        guild: Guild,
        role_id: int,
        fetch: bool = False,
    ) -> Optional[Role]:
        """
        The getch_role function is a helper function that attempts to retrieve a role from the guild's cache.
        If it fails, it will attempt to fetch the roles from Discord and then return the result of that search.
        This is useful for when you need to get a role by ID but don't want your bot to crash if it isn't cached.

        :param guild: Specify the guild that we are looking for a role in
        :param role_id: Get the role id
        :param fetch: bool: Determine whether or not the function should fetch roles
        :return: A role object or None
        """

        role: Optional[Role] = guild.get_role(role_id)

        if not fetch:
            return role

        self.logger.warning(f"Role: {role_id} was not found in the cache. Sending HTTP Request.")

        roles: list[Role] = await guild.fetch_roles(cache=True)
        result = filter(
            lambda _role: _role if _role.id == role_id else None,
            roles,
        )

        if not list(result):
            return None

        return list(result)[0]

    async def getch_guild(self, guild_id: int) -> Optional[Guild]:
        """
        The getch_guild function is a wrapper for the get_guild and fetch_guild functions.
        It first tries to get the guild from cache, if it fails then it will try to fetch
        the guild. If that fails too, then None is returned.

        :param guild_id: Get the guild id of a server
        :return: The guild object or None
        """
        guild: Optional[Guild] = self.get_guild(guild_id)

        if guild:
            return guild

        self.logger.warning(f"Guild: {guild_id} was not found in the cache. Sending HTTP Request.")

        try:
            guild: Optional[Guild] = await self.fetch_guild(guild_id)

            return guild
        except (
            nextcord_errors.Forbidden,
            nextcord_errors.HTTPException,
        ):
            return None

    async def getch_channel(self, channel_id: int) -> Optional[GuildChannel]:
        """
        The getch_channel function is a wrapper for the get_channel and fetch_channel functions.
        It first tries to get the channel from cache, if it fails then it will try to fetch
        the channel. If that fails too, then None is returned.

        :param channel_id: Get the channel id
        :return: The channel object or None
        """

        channel = self.get_channel(channel_id)

        if isinstance(channel, GuildChannel):
            return channel

        try:
            self.logger.warning(f"Channel: {channel_id} was not found in the cache. Sending HTTP Request.")

            channel = await self.fetch_channel(channel_id)

            if not isinstance(channel, GuildChannel):
                return None

            return channel
        except (
            nextcord_errors.Forbidden,
            nextcord_errors.HTTPException,
        ):
            return None

    async def getch_member(self, guild: Guild, member_id: int) -> Optional[Member]:
        """
        The getch_member function tries to retrieve the `Member` object from the cache thanks to the .get method
        if it fails it will try again, but this time with a request to discord using .fetch method

        :param guild: Guild: Get the guild object
        :param member_id: int: Get the member id of a user
        :return: A member object if it exists in the guild, or none if it does not
        """

        member: Optional[Member] = await self.cache.get_member(guild.id, member_id)
        return member

    async def setup_session(self) -> None:
        """
        The setup_session function is a coroutine that creates an instance of the BotSession class.
        The BotSession class is used to send requests for commands that use some api.

        :return: None
        """

        if not getattr(self, "session", None):
            timeout: Optional[float | int] = bot_utils.get_value_from_config("SESSION_TIMEOUT")

            if not isinstance(timeout, (float, int)):
                self.logger.warning("Session timeout is invalid. Setting to default value -> 300s")
                timeout = 300.0

            client_timeout = ClientTimeout(total=float(timeout))

            self.session: BotSession = BotSession(timeout=client_timeout, bot=self)

    async def setup_checks(self) -> None:
        """
        The setup_checks function adds a check to the bot command handler,
        which will be run before any commands.

        :return: None
        """

        if not getattr(self, "session", None):
            self.add_application_command_check(self.check_global_ban)

    def get_interaction(self, data, *, cls=CustomInteraction) -> InterT:  # pyright: ignore
        # pylint: disable=useless-parent-delegation

        """
        Function that overrides the method in the AutoShardedBot class
        and allows you to provide your own Custominteraction object.

        :param data: Get the data from the interaction
        :param cls: Specify the class of the interaction
        :return: Interaction Object
        """

        return super().get_interaction(data, cls=cls)  # pyright: ignore


class DiscordSupportButton(ui.View):
    def __init__(self):
        """
        DiscordSupportButton is a View class that has a button with a link
        to the bot server obtained from the config.json file.

        :return: None
        """

        super().__init__(timeout=None)

        guild_invite: Optional[str] = bot_utils.get_value_from_config("BOT_GUILD_INVITE")

        if guild_invite in (None, ""):
            raise InvalidServerData

        self.add_item(ui.Button(label="Discord Bota", style=ButtonStyle.link, url=guild_invite, row=2))


def PermissionHandler(**perms):
    """
    The PermissionHandler function is a decorator that can be used to wrap any command function.
    It will check if the user has the permission specified in its argument, and if not, it will send an error message.

    :param perms: Required permissions
    :return: A decorator that can be used to check if the user has a specific permission
    """

    class Handler(CallbackWrapper):
        original_error_callback: Optional[TCallback] = None  # pyright: ignore

        def modify(self, app_cmd: BaseApplicationCommand) -> None:
            """
            The modify function is used to modify the behavior of an application command.

            :param app_cmd: Pass the command object to the function
            :return: None
            """

            if not perms:
                raise ValueError("Permissions are missing.")

            if app_cmd.has_error_handler():
                self.original_error_callback = app_cmd.error_callback  # pyright: ignore

            app_cmd.add_check(func=self.user_has_permissions)  # pyright: ignore
            app_cmd.error(callback=self.app_error)  # pyright: ignore

        async def app_error(
            self,
            cog: CustomCog,
            inter: CustomInteraction,
            error: Exception,
        ) -> None:
            """
            The app_error function is a function that will be called when an error occurs in the application command.

            :param cog: Get the cog instance that is currently running
            :param inter: Interaction object
            :param error: Get the error that was raised
            :return: None
            """

            if inter.response.is_done():
                # Global ban check can response to the inter.
                return

            if self.original_error_callback:
                # Calling the original error handler. If exists.
                await self.original_error_callback(cog, inter, error)  # pyright: ignore

                # If the orignal handler has already responded to interaction.
                if inter.response.is_done():
                    return

            await inter.response.defer()

            if isinstance(
                error,
                ApplicationMissingPermissions,
            ):
                permission: str = error.missing_permissions[0].capitalize()

                await inter.send_error_message(
                    description=f"Niestety, ale nie posiadasz permisji: `{permission}`"
                )
                return

            if isinstance(error, MissingMusicPermissions):
                await inter.send_error_message(
                    description="Niestety, ale nie posiadasz wymaganej roli, aby użyć tej komendy."
                )
                return
            if isinstance(
                error,
                ApplicationCommandIsGuildOnly,
            ):
                await inter.send_error_message(
                    description="Komendy bota działają tylko i wyłącznie na serwerach."
                )
                return

        @staticmethod
        async def user_has_permissions(
            interaction: CustomInteraction,
        ) -> bool:
            """
            The user_has_permissions function checks if the user has the required permissions.

            :param interaction:  Get the user's permissions and channel
            :return: A boolean value
            """

            async def check_database_permissions() -> bool:
                invalids: set[str] = set(perms) - set(Permissions.VALID_FLAGS)

                if not invalids:
                    return False

                for invalid in invalids:
                    if invalid != "user_role_has_permission":
                        raise TypeError(f"Invalid permission(s): {', '.join(invalid)}")

                    # invalid = user_role_has_permission
                    command_name: Optional[str] = perms.get(invalid)

                    if not command_name:
                        return False

                    if await user_role_has_permission(command_name, interaction):
                        return True

                return False

            def check_basic_permissions() -> bool:
                ch = interaction.channel
                try:
                    permissions = ch.permissions_for(interaction.user)  # type: ignore
                except AttributeError:
                    if not interaction.guild:
                        command: str = "None"
                        if interaction.application_command:
                            command = interaction.application_command.name or "None"

                        raise ApplicationCommandIsGuildOnly(command)  # pylint: disable=raise-missing-from

                    return False

                missing: list[str] = [
                    perm for perm, v in perms.items() if getattr(permissions, perm, None) != v
                ]

                if not missing or "".join(missing) == "user_role_has_permission":
                    return True

                raise ApplicationMissingPermissions(missing)

            if await check_database_permissions():
                return True

            return check_basic_permissions()

    def wrapper(func) -> CallbackWrapper:
        return Handler(func)

    return wrapper


async def user_role_has_permission(
    command_name: str,
    interaction: CustomInteraction,
) -> bool:
    if command_name == "music" and not await user_role_has_music_permissions(interaction):
        raise MissingMusicPermissions("You do not have the required role to run this command.")

    if not interaction.user or not interaction.guild:
        return False

    bot: Smiffy = interaction.bot
    response: Optional[Iterable[Row]] = await bot.db.execute_fetchall(
        "SELECT * FROM permissions WHERE guild_id = ?",
        (interaction.guild.id,),
    )
    if not response:
        return False

    roles_list: list[int] = [role.id for role in interaction.user.roles]  # pyright: ignore

    for data in response:
        if data[1] in roles_list:
            if command_name in literal_eval(data[2]):
                return True

    return False


async def user_role_has_music_permissions(
    interaction: CustomInteraction,
) -> bool:
    """
    The user_role_has_music_permissions function is a coroutine that checks if the user has music permissions.

    :param interaction: Access the user and guild
    :return: A boolean value
    """

    assert isinstance(interaction.user, Member) and interaction.guild

    if interaction.user == interaction.guild.owner:
        return True

    bot: Smiffy = interaction.bot

    response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
        "SELECT permission_roles FROM music_settings WHERE guild_id = ?",
        (interaction.guild.id,),
    )

    if not response or not response[0]:
        return True

    role_ids: list[int] = literal_eval(response[0])
    user_roles: list[int] = [role.id for role in interaction.user.roles]

    for role_id in role_ids:
        if role_id in user_roles:
            return True

    return False


async def check_giveaway_requirement(
    bot: Smiffy,
    member: Member,
    inter_or_message: Union[CustomInteraction, Message],
) -> bool:
    """
    The check_giveaway_requirement function checks if a member has met the requirements for a giveaway.

    :param bot: Access the bot object, which is used to get the database connection
    :param member: Check if the member met the requirements
    :param inter_or_message: Get the context
    :return: A bool, true if the user meets the requirements and false if they don't
    """

    if isinstance(inter_or_message, CustomInteraction) and not inter_or_message.message:
        return False

    if not inter_or_message.guild:
        return False

    guild: Guild = inter_or_message.guild

    if isinstance(inter_or_message, Message):
        message: Optional[Message] = inter_or_message
    else:
        message: Optional[Message] = inter_or_message.message

    if not message:
        return False

    response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
        "SELECT requirement FROM giveaways WHERE guild_id = ? AND message_id = ?",
        (guild.id, message.id),
    )

    if response and response[0]:
        data: dict[str, str] = literal_eval(response[0])

        requirement: Optional[str] = None
        value: Optional[int] = None

        for req, val in data.items():
            requirement, value = req, int(val)
            break

        if not requirement or not value:
            return False

        if requirement == "lvl":
            levels_response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
                "SELECT level FROM levels_users WHERE guild_id = ? AND user_id = ?",
                (guild.id, member.id),
            )

            if not levels_response:
                return False

            lvl: int = levels_response[0]
            if lvl < value:
                return False

        elif requirement == "role":
            try:
                if isinstance(inter_or_message, Message):
                    context: Context = await bot.get_context(inter_or_message)

                    role: Optional[Role] = await ncRoleConverter().convert(
                        context,  # pyright: ignore
                        str(value),
                    )
                    if not role:
                        raise errors.RoleNotFound(str(value))

                else:
                    role: Optional[Role] = await RoleConverter().convert(
                        inter_or_message,  # pyright: ignore
                        str(value),
                    )
                if not role:
                    raise errors.RoleNotFound(str(value))

                member_roles: list[int] = [role.id for role in member.roles]
                if role.id not in member_roles:
                    return False
                return True

            except errors.RoleNotFound:
                return True

        elif requirement == "invites":
            user_response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
                "SELECT normal, left, bonus FROM user_invites WHERE guild_id = ? AND user_id = ?",
                (guild.id, member.id),
            )

            if not user_response:
                normal, left, bonus = 0, 0, 0
            else:
                (
                    normal,
                    left,
                    bonus,
                ) = user_response

            total: int = (normal - left) + bonus

            if total < value:
                return False

        return True

    return True


bot_utils: BotUtils = BotUtils()
bot_logger: BotLogger = BotLogger()
