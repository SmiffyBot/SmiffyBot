from __future__ import annotations

from asyncio import sleep
from datetime import datetime, timedelta
from random import choice
from time import mktime
from typing import TYPE_CHECKING, Iterable, List, Optional

from humanfriendly import InvalidTimespan, parse_timespan
from nextcord import Attachment, Color, Embed, Member, SlashOption, TextChannel
from nextcord import errors as nextcord_errors
from nextcord import slash_command, ui
from nextcord.ext.commands import errors

from converters import MessageConverter, RoleConverter
from enums import Emojis
from utilities import (
    CustomCog,
    CustomInteraction,
    PermissionHandler,
    check_giveaway_requirement,
)

if TYPE_CHECKING:
    from nextcord import Message, Role
    from nextcord.abc import GuildChannel

    from bot import Smiffy
    from typings import DB_RESPONSE


class RequirementModal(ui.Modal):
    def __init__(self, title: str, bot: Smiffy, requirement: str):
        super().__init__(title=title)

        self.requirement: str = requirement
        self.bot: Smiffy = bot

        if requirement == "lvl":
            self.input_value = ui.TextInput(label="Podaj wymagany level.", min_length=1)
        elif requirement == "role":
            self.input_value = ui.TextInput(label="Podaj nazwę roli lub jej ID.", min_length=1)
        else:
            self.input_value = ui.TextInput(label="Podaj ilość wymaganych zaproszeń.", min_length=1)

        self.add_item(self.input_value)

    async def callback(self, interaction: CustomInteraction):
        if not self.input_value.value or not interaction.guild:
            return await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd.")

        if self.requirement == "invites":
            try:
                invites: int = abs(int(self.input_value.value))
                # To make sure that the user does not pass a negative number

                if invites >= 100000 or invites <= 0:
                    raise IndexError

            except ValueError:
                return await interaction.send_error_message(
                    description="**Podałeś/aś nieprawidłową wartość**"
                )
            except IndexError:
                return await interaction.send_error_message(
                    description="**Podana ilość nie może być większa niż `100000` lub mniejsza niż `1`**"
                )

        if self.requirement == "lvl":
            try:
                level: int = int(self.input_value.value.replace("-", ""))
                # To make sure that the user does not pass a negative number
                if level >= 10000 or level <= 0:
                    raise IndexError

                response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
                    "SELECT * FROM levels WHERE guild_id = ?", (interaction.guild.id,)
                )

                if not response:
                    return await interaction.send_error_message(
                        description="**Levelowanie na serwerze jest wyłączone.**"
                    )

            except ValueError:
                return await interaction.send_error_message(
                    description="**Podałeś/aś nieprawidłową wartość**"
                )
            except IndexError:
                return await interaction.send_error_message(
                    description="**Podany level nie może być większy niż `10000` lub mniejszy niż `1`**"
                )

        if self.requirement == "role":
            try:
                role: Optional[Role] = await RoleConverter().convert(interaction, self.input_value.value)
                if not role:
                    raise errors.RoleNotFound(self.input_value.value)

                if (
                    role.is_bot_managed()
                    or role.is_premium_subscriber()
                    or role.is_default()
                    or role.is_integration()
                ):
                    raise ValueError

            except errors.RoleNotFound:  # pyright: ignore
                return await interaction.send_error_message(description="**Nie odnalazłem wpisanej roli**")

        await interaction.send("Pomyślnie utworzono konkurs!", ephemeral=True)
        self.stop()


class CommandGiveaway(CustomCog):
    def __init__(self, bot: Smiffy) -> None:
        super().__init__(bot=bot)

        self._req_title: dict[str, str] = {
            "lvl": "Konkurs - Wymagania  (Level)",
            "role": "Konkurs - Wymagania (Rola)",
            "invites": "Konkurs - Wymagania (zaproszenia)",
        }

        self.bot.loop.create_task(self.enable_running_giveaways())

    async def enable_running_giveaways(self):
        # Method to restore all working giveaways after bot restart

        await self.bot.wait_until_ready()
        await sleep(3)

        for guild in self.bot.guilds:
            response: Optional[Iterable[DB_RESPONSE]] = await self.bot.db.execute_fetchall(
                "SELECT * FROM giveaways WHERE guild_id = ?", (guild.id,)
            )

            if not response:
                continue

            for giveaway_data in response:
                _embed: Optional[Embed] = None
                try:
                    _channel: Optional[GuildChannel] = await self.bot.getch_channel(giveaway_data[1])
                    if not _channel:
                        raise nextcord_errors.NotFound  # pyright: ignore

                    assert isinstance(_channel, TextChannel)

                    _message: Optional[Message] = await _channel.fetch_message(giveaway_data[2])
                    _embed = _message.embeds[0]

                except (
                    nextcord_errors.NotFound,
                    nextcord_errors.Forbidden,
                    nextcord_errors.HTTPException,
                ):
                    await self.bot.db.execute_fetchone(
                        "DELETE FROM giveaways WHERE guild_id = ? AND channel_id = ? AND message_id = ?",
                        (guild.id, giveaway_data[1], giveaway_data[2]),
                    )

                    continue

                duration: int = int(giveaway_data[3])
                reward: str = giveaway_data[4]
                winners: int = giveaway_data[5]
                host: str = giveaway_data[6]
                if _embed:
                    self.bot.loop.create_task(
                        self.continue_the_giveaway(reward, duration, winners, _message, _embed, host)
                    )

    async def continue_the_giveaway(
        self,
        reward: str,
        duration: int,
        winners: int,
        message: Message,
        embed: Embed,
        host: str,
    ):
        assert message.guild

        now = datetime.utcnow()
        unix_timespan_now: int = int(mktime(now.timetuple()))

        while duration >= unix_timespan_now:
            now = datetime.utcnow()
            unix_timespan_now: int = int(mktime(now.timetuple()))
            await sleep(3)

            try:
                if embed.title:
                    reward = embed.title[4::]
                else:
                    raise TypeError
            except TypeError:
                continue

            response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
                "SELECT end_time FROM giveaways WHERE guild_id = ? AND reward = ?",
                (message.guild.id, reward),
            )
            if response and response[0]:
                duration = int(response[0])

        enters: List[str] = []
        try:
            message = await message.channel.fetch_message(message.id)
            assert message.channel and message.guild and message
        except (
            nextcord_errors.Forbidden,
            nextcord_errors.NotFound,
            nextcord_errors.HTTPException,
        ):
            return None

        for reaction in message.reactions:
            if reaction.emoji == "🎉":
                u = reaction.users()

                async for user in u:
                    if isinstance(user, Member):
                        if await check_giveaway_requirement(self.bot, user, message):
                            enters.append(user.mention)
                try:
                    if self.bot.user:
                        enters.remove(self.bot.user.mention)
                except ValueError:
                    pass

        reply_emoji: str = Emojis.REPLY.value

        embed.set_author(name="Giveaway Zakończony!")
        embed.colour = Color.green()
        embed.clear_fields()

        embed.add_field(name="`👥` Liczba wygranych", value=f"{reply_emoji} `{winners}`")
        embed.add_field(name="`👤` Osób w konkursie", value=f"{reply_emoji} `{len(enters)}`")

        embed.add_field(name="`⭐` Host", value=f"{reply_emoji} `{host}`")

        if len(enters) == 0:
            result_message = await message.reply("Brak osób w konkursie. Nikt nie wygrywa :(")
            embed.url = result_message.jump_url

            await message.edit(embed=embed, view=None)

            return await self.bot.db.execute_fetchone(
                "DELETE FROM giveaways WHERE guild_id = ? AND channel_id = ? AND message_id = ?",
                (message.guild.id, message.channel.id, message.id),
            )

        if len(enters) < winners:
            winners = len(enters)

        giveaway_winners: List[str] = []

        for _ in range(winners):
            rand = choice(enters)
            while rand in giveaway_winners:
                rand = choice(enters)

            giveaway_winners.append(rand)

        result_message = await message.reply(
            f"**Giveaway zakończony <:giveaway:997944144569831444>**\n"
            f"Nagroda: `{reward}` trafia do: {' '.join(giveaway_winners)}"
        )

        embed.url = result_message.jump_url
        await message.edit(embed=embed, view=None)

        await self.bot.db.execute_fetchone(
            "DELETE FROM giveaways WHERE guild_id = ? AND channel_id = ? AND message_id = ?",
            (message.guild.id, message.channel.id, message.id),
        )

    async def start_giveaway(
        self,
        reward: str,
        duration: datetime,
        winners: int,
        interaction: CustomInteraction,
        image: Optional[Attachment] = None,
        requirement: Optional[str] = None,
        requirement_value: Optional[str] = None,
    ) -> Optional[List[str]]:
        assert interaction.guild and interaction.channel and interaction.user

        unix_timespan: str = f"{int(mktime(duration.timetuple()))}"
        requirement_data: Optional[str] = None
        reply_emoji: str = "<:reply:1129168370642718833>"

        if requirement == "role" and requirement_value:
            try:
                _role: Optional[Role] = await RoleConverter().convert(interaction, requirement_value)
                if not _role:
                    raise errors.RoleNotFound(requirement_value)

                requirement_value = _role.name

                if (
                    _role.is_bot_managed()
                    or _role.is_premium_subscriber()
                    or _role.is_default()
                    or _role.is_integration()
                ):
                    requirement = None

                else:
                    requirement_data = str({requirement: _role.id})

            except errors.RoleNotFound:  # pyright: ignore
                requirement = None

        requirement_format: dict[str, str] = {
            "invites": "Zaproszenia:",
            "role": "Rola:",
            "lvl": "Level:",
        }

        embed = Embed(
            title=f"`🎉` {reward}",
            color=Color.yellow(),
            description=f"{Emojis.REPLY.value} *Dołącz do konkursu zaznaczając reakcje pod wiadomością*",
        )

        embed.add_field(name="`⏱️` Koniec", value=f"{reply_emoji} <t:{int(unix_timespan) + 7200}:R>")
        embed.add_field(
            name="`👥` Liczba wygranych",
            value=f"{reply_emoji} `{winners}`",
            inline=False,
        )
        embed.add_field(name="`⭐` Host", value=f"{reply_emoji} `{interaction.user}`")

        if requirement:
            req: str = requirement_format[requirement]
            embed.add_field(
                name="`⛔` Wymaganie",
                value=f"{reply_emoji} **{req}** `{requirement_value}`",
                inline=False,
            )

        embed.set_author(name="Konkurs - Smiffy", icon_url=self.bot.avatar_url)

        if image:
            embed.set_thumbnail(url=image)
        else:
            embed.set_thumbnail(url=interaction.guild_icon_url)

        if not isinstance(interaction.channel, TextChannel):
            return

        message: Message = await interaction.channel.send(embed=embed)
        await message.add_reaction("🎉")

        if requirement:
            if requirement != "role":
                requirement_data = str({requirement: requirement_value})
        else:
            requirement_data = None

        await self.bot.db.execute_fetchone(
            "INSERT INTO giveaways(guild_id, channel_id, message_id, end_time, reward, winners, host, requirement) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (
                interaction.guild.id,
                interaction.channel.id,
                message.id,
                unix_timespan,
                reward,
                winners,
                str(interaction.user),
                requirement_data,
            ),
        )

        await self.continue_the_giveaway(
            reward,
            int(unix_timespan),
            winners,
            message=message,
            embed=embed,
            host=interaction.user.name,
        )

    @slash_command(name="konkurs", dm_permission=False)
    async def giveaway_main(self, interaction: CustomInteraction):
        pass

    @giveaway_main.subcommand(name="rozpocznij", description="Rozpoczyna konkurs.")  # pyright: ignore
    @PermissionHandler(manage_messages=True, user_role_has_permission="konkurs")
    async def giveaway_start(
        self,
        interaction: CustomInteraction,
        reward: str = SlashOption(name="nagroda", description="Podaj nagrodę konkursu"),
        giveway_winners: str = SlashOption(
            name="liczba_wygranych", description="Podaj ile chcesz zwycięzców konkursu"
        ),
        time: str = SlashOption(name="czas", description="Podaj czas konkursu. np. 5m"),
        requiement: str = SlashOption(
            name="wymaganie",
            description="Wybierz wymaganie, aby dołączyć do konkursu",
            choices={
                "Odpowiedni Level": "lvl",
                "Odpowiednia rola": "role",
                "Odpowiednia ilość zaproszeń": "invites",
            },
            required=False,
        ),
        image: Attachment = SlashOption(
            name="obraz_konkursu",
            description="Opcjonalny obrazek do konkursu",
            required=False,
        ),
    ):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT message_id FROM giveaways WHERE guild_id = ? AND reward = ?",
            (interaction.guild.id, reward),
        )

        if response:
            return await interaction.send_error_message(
                description=f"Konkurs z nagrodą: `{reward}` już istnieje."
            )

        try:
            winners: int = int(giveway_winners)
            duration = datetime.utcnow() + timedelta(seconds=parse_timespan(time))
        except InvalidTimespan:
            return await interaction.send_error_message(
                description="**Wpisałeś/aś niepoprawną jednostkę czasu**\n> Przykład: 5m ||(5minut)||"
            )
        except ValueError:
            return await interaction.send_error_message(
                description="**Wpisałeś/aś niepoprawną ilość zwycięzców.**"
            )

        if image and image.content_type:
            if "image" not in image.content_type:
                return await interaction.send_error_message(
                    description="Nieprawidłowy format obrazu. Obsługiwane formaty: `.png`, `.jpg`"
                )

        if winners <= 0:
            return await interaction.send_error_message(description="**Minimalna ilość wygranych, to: 1**")

        if not requiement:
            await interaction.send("Pomyślnie utworzono konkurs!", ephemeral=True)

            return await self.start_giveaway(reward, duration, winners, interaction, image)

        modal: RequirementModal = RequirementModal(self._req_title[requiement], self.bot, requiement)
        await interaction.response.send_modal(modal)

        if not await modal.wait():
            value: Optional[str] = modal.input_value.value
            if value:
                return await self.start_giveaway(
                    reward, duration, winners, interaction, image, requiement, value
                )

    @giveaway_main.subcommand(name="relosuj", description="Relosuje wygranych w konkursie")  # pyright: ignore
    @PermissionHandler(manage_messages=True, user_role_has_permission="konkurs")
    async def reroll(
        self,
        interaction: CustomInteraction,
        message: str = SlashOption(name="wiadomość", description="Podaj ID wiadomości konkursu."),
        winners: int = SlashOption(name="ilość_zwyciezcow", description="Podaj ilość nowych wygranych"),
    ):
        try:
            if winners <= 0:
                return await interaction.send_error_message("Nieprawidłowa ilość wygranych.", ephemeral=True)

            await interaction.response.defer()

            giveaway_message: Optional[Message] = await MessageConverter().convert(interaction, message)
            if not giveaway_message:
                raise errors.MessageNotFound(message)

        except errors.MessageNotFound:  # pyright: ignore
            return await interaction.send_error_message(
                description="**Nieprawidłowe ID wiadomości lub link do wiadomości. "
                "Upewnij się, że wpisujesz komende na tym samym kanale co wiadomość konkursu.**",
                ephemeral=True,
            )

        try:
            for embed in giveaway_message.embeds:
                if str(embed.color) != "#2ecc71":
                    return await interaction.send_error_message(
                        "Podany konkurs nie został jeszcze zakończony",
                        ephemeral=True,
                    )
                enters: list[Optional[str]] = []

                for reaction in giveaway_message.reactions:
                    if reaction.emoji == "🎉":
                        reaction_users = reaction.users()

                        async for user in reaction_users:
                            enters.append(user.mention)

                        if self.bot.user:
                            enters.remove(self.bot.user.mention)
                        if len(enters) < winners:
                            winners = len(enters)

                if len(enters) == 0:
                    return await interaction.send("Brak osób w konkursie", ephemeral=True)

                giveaway_winners: List[str] = []
                for _ in range(winners):
                    _new_winner = choice(enters)
                    while _new_winner in giveaway_winners:  # pyright: ignore
                        _new_winner = choice(enters)

                    giveaway_winners.append(_new_winner)  # pyright: ignore

                await interaction.send(f"Nowi zwycięzcy konkursu: {' '.join(giveaway_winners)}")
                break

        except AttributeError:
            return await interaction.send_error_message(
                "**Nie mogłem znaleźć takiego Giveaway'u w mojej bazie.**",
                ephemeral=True,
            )

    @giveaway_main.subcommand(name="zakończ", description="Kończy giveaway przed czasem")  # pyright: ignore
    @PermissionHandler(manage_messages=True, user_role_has_permission="konkurs")
    async def giveaway_end_now(
        self,
        interaction: CustomInteraction,
        giveaway_name: str = SlashOption(name="nazwa_nagrody", description="Podaj nazwe nagrody konkursu"),
    ):
        assert interaction.guild

        await interaction.response.defer()

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT message_id FROM giveaways WHERE guild_id = ? AND reward = ?",
            (interaction.guild.id, giveaway_name),
        )

        if not response:
            try:
                message_id: int = int(giveaway_name)
            except ValueError:
                return await interaction.send_error_message(
                    "Niestety, ale nie odnalazłem wiadomości tego konkursu"
                )
        else:
            message_id: int = response[0]

        now = datetime.utcnow()
        unix_timespan_now: str = f"{int(mktime(now.timetuple()))}"

        message: Optional[Message] = await MessageConverter().convert(interaction, str(message_id))

        if not message:
            return await interaction.send_error_message(
                "Niestety, ale nie odnalazłem wiadomości tego konkursu"
            )

        await self.bot.db.execute_fetchone(
            "UPDATE giveaways SET end_time = ? WHERE guild_id = ? AND message_id = ?",
            (int(unix_timespan_now), interaction.guild.id, message_id),
        )

        return await interaction.send_success_message(
            title=f"Pomyślnie zakończono konkurs {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Zmiany pojawią się za kilka sekund.",
        )

    @giveaway_end_now.on_autocomplete("giveaway_name")
    async def giveaway_end_now_autocomplete(
        self, interaction: CustomInteraction, query: Optional[str]
    ) -> Optional[dict[str, str]]:
        assert interaction.guild

        response: Iterable[DB_RESPONSE] = await self.bot.db.execute_fetchall(
            "SELECT message_id, reward, end_time FROM giveaways WHERE guild_id = ?",
            (interaction.guild.id,),
        )

        if not response:
            return

        if not query:
            giveaways_data: dict[str, str] = {}
            index: int = 0
            for message_id, reward, end_time in response:
                reward = f"{reward} - ({datetime.fromtimestamp(int(end_time))})"
                giveaways_data[reward] = str(message_id)
                index += 1

                if index == 25:
                    break
        else:
            giveaways_data: dict[str, str] = {}
            index: int = 0
            for message_id, reward, end_time in response:
                if reward.lower().startswith(query.lower()):
                    giveaways_data[f"{reward} - ({datetime.fromtimestamp(int(end_time))})"] = str(message_id)

                    if index == 25:
                        break

        return giveaways_data


def setup(bot: Smiffy):
    bot.add_cog(CommandGiveaway(bot))
