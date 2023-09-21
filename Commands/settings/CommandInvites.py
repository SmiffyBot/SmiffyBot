from __future__ import annotations

from ast import literal_eval
from asyncio import exceptions
from itertools import islice
from time import mktime
from typing import TYPE_CHECKING, Iterable, Optional

from nextcord import (
    Color,
    Embed,
    Guild,
    Member,
    SlashOption,
    TextChannel,
    slash_command,
    user_command,
    utils,
)

from converters import GuildChannelConverter
from enums import Emojis, GuildChannelTypes
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from nextcord import Message

    from bot import Smiffy
    from typings import DB_RESPONSE


class CommandInvites(CustomCog):
    @user_command(name="zaproszenia")
    async def avatar_application(self, interaction: CustomInteraction, member: Member) -> None:
        await self.invites_check(interaction, member)

    @slash_command(name="zaproszenia", dm_permission=False)
    async def invites(self, interaction: CustomInteraction):
        pass

    @invites.subcommand(name="włącz", description="Włącza system zaproszeń na serwerze")  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def invites_on(self, interaction: CustomInteraction):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM server_invites WHERE guild_id = ?", (interaction.guild.id,)
        )
        if response:
            return await interaction.send_error_message(description="System zaproszeń już jest włączony.")

        guild_invites_data: list[dict] = []

        for invite in await interaction.guild.invites():
            if invite.id and invite.inviter:
                guild_invites_data.append(
                    {
                        "invite_id": invite.id,
                        "invite_uses": invite.uses,
                        "inviter_id": invite.inviter.id,
                    }
                )

        timestamp = int(mktime(utils.utcnow().timetuple()))

        await self.bot.db.execute_fetchone(
            "INSERT INTO server_invites(guild_id, invites_data, enabled_at, notify_data) VALUES(?,?,?,?)",
            (interaction.guild.id, str(guild_invites_data), timestamp, None),
        )

        await interaction.send_success_message(
            title="Pomyślnie włączono",
            description=f"{Emojis.REPLY.value} System zaproszeń został włączony.",
        )

    @invites.subcommand(name="wyłącz", description="Wyłącza system zaproszeń na serwerze")  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def invites_off(self, interaction: CustomInteraction):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM server_invites WHERE guild_id = ?", (interaction.guild.id,)
        )

        if not response:
            return await interaction.send_error_message(description="System zaproszeń już jest wyłączony.")

        await self.bot.db.execute_fetchone(
            "DELETE FROM server_invites WHERE guild_id = ?", (interaction.guild.id,)
        )

        await interaction.send_success_message(
            title="Pomyślnie wyłączono",
            description=f"{Emojis.REPLY.value} System zaproszeń został wyłączony.",
        )

    @invites.subcommand(name="sprawdź", description="Pokazuje zaproszenia wybranej osoby")
    async def invites_check(
        self,
        interaction: CustomInteraction,
        member: Optional[Member] = SlashOption(name="osoba", description="Wybierz osobę"),
    ):
        assert isinstance(interaction.user, Member) and interaction.guild

        user: Member = member or interaction.user

        guild_data: Optional[DB_RESPONSE] = await self.get_guild_invites_data(interaction.guild)
        if not guild_data:
            return await interaction.send_error_message(
                description="System zaproszeń na serwerze jest wyłączony."
            )

        normal, left, fake, bonus = await self.get_user_invites(interaction.guild.id, user.id)

        total: int = (normal - left) + bonus

        timestamp: int = guild_data[2] + 7200

        description: str = (
            f"{Emojis.REPLY.value} Zaproszenia są liczone od: <t:{timestamp}:f>\n\n"
            f"- `🌴` **Dołączenia:** `{normal}`\n"
            f"- `❌` **Wyjścia:** `{left}`\n"
            f"- `⛔` **Fałszywe:** `{fake}`\n"
            f"- `🎁` **Bonusowe:** `{bonus}`\n\n"
            f"- "
            f"Podsumowując {user.mention} ma `{total}` zaproszenia!"
        )

        await interaction.send_success_message(
            title=f"<a:ping:987762816062726224> Zaproszenia {user}",
            description=description,
            color=Color.dark_theme(),
        )

    @invites.subcommand(name="topka", description="Top 10 w zaproszeniach na serwerze")
    async def invites_leaderboard(self, interaction: CustomInteraction):
        assert interaction.guild

        await interaction.response.defer()

        guild_data: Optional[DB_RESPONSE] = await self.get_guild_invites_data(interaction.guild)
        if not guild_data:
            return await interaction.send_error_message(
                description="System zaproszeń na serwerze jest wyłączony."
            )

        leaderboard_data: Optional[dict[Member, int]] = await self.get_leaderboard(interaction.guild)
        if not leaderboard_data:
            return await interaction.send_error_message(
                description="Aktualnie na serwerze nie ma żadnych danych zaproszeń."
            )

        timestamp: int = guild_data[2] + 7200

        embed = Embed(
            title="`🌟` Topka ilości zaproszeń na serwerze.",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
            description=f"{Emojis.REPLY.value} Zaproszenia są liczone od: <t:{timestamp}:f>",
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.set_footer(text=f"Smiffy v{self.bot.__version__}", icon_url=self.bot.avatar_url)

        index: int = 1
        for member, invites in leaderboard_data.items():
            embed.add_field(
                name=f"Top. {index}",
                value=f"- {member.mention} ({member})\n" f"{Emojis.REPLY.value} `{invites}` zaproszenia.",
                inline=False,
            )
            index += 1

        await interaction.send(embed=embed)

    async def get_leaderboard(self, guild: Guild) -> Optional[dict[Member, int]]:
        response: Iterable[DB_RESPONSE] = await self.bot.db.execute_fetchall(
            "SELECT user_id, normal, left, bonus FROM user_invites WHERE guild_id = ?",
            (guild.id,),
        )
        if not response:
            return

        invites_data: dict[Member, int] = {}

        for user_id, normal, left, bonus in response:
            member: Optional[Member] = await self.bot.getch_member(guild, user_id)
            if member:
                invites_data[member] = (normal - left) + bonus

        if not invites_data:
            return

        sorted_lb = dict(sorted(invites_data.items(), key=lambda item: item[1], reverse=True))
        return dict(islice(sorted_lb.items(), 10))

    @invites.subcommand(
        "powiadomienia",
        description="Pozwala zarządzać powiadomieniami o zaproszonych osobach",
    )  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def invites_notify(
        self,
        interaction: CustomInteraction,
        state: str = SlashOption(
            name="status",
            description="Włącz lub wyłącz powiadomienia",
            choices={"Włącz": "on", "Wyłącz": "off"},
        ),
    ):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT notify_data FROM server_invites WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        if not response:
            await interaction.send_error_message(description="System zaproszeń jest wyłączony na serwerze.")

        if state == "on":
            if response and response[0]:
                return await interaction.send_error_message(description="Powiadomienia już są włączone.")

            embed = Embed(
                title="`🛠️` Konfigurowacja powiadomień o zaproszeniach.",
                color=Color.dark_theme(),
                timestamp=utils.utcnow(),
                description=f"{Emojis.REPLY.value} Oznacz lub podaj ID kanału na którym chcesz mieć powiadommienia.\n\n"
                f"*Na odpowiedź masz 60 sekund. Inaczej konfiguracja zostanie przerwana. "
                f"Aby przerwać ją teraz, wpisz `stop`.*",
            )
            embed.set_footer(text="Etap 1/2")
            embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
            await interaction.send(embed=embed)

            try:
                channel_message: Message = await self.bot.wait_for(
                    "message",
                    check=lambda message: message.author == interaction.user,
                    timeout=60,
                )
                await channel_message.delete()

            except exceptions.TimeoutError:
                embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
                embed.description = f"{Emojis.REPLY.value} Instalacja przerwana (Upłynął limit czasu)."
                embed.colour = Color.red()
                embed.set_footer()
                return await interaction.edit_original_message(embed=embed)

            if channel_message.content.lower() == "stop":
                embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
                embed.description = f"{Emojis.REPLY.value} Instalacja przerwana (Wstrzymana ręcznie)."
                embed.colour = Color.red()
                embed.set_footer()

                return await interaction.edit_original_message(embed=embed)

            channel_converter: GuildChannelConverter = GuildChannelConverter()[
                GuildChannelTypes.text_channels
            ]

            channel: Optional[TextChannel] = channel_converter.convert(interaction, channel_message.content)

            if not channel:
                embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
                embed.description = f"{Emojis.REPLY.value} Instalacja przerwana (Nieprawidłowy kanał)."
                embed.colour = Color.red()
                embed.set_footer()

                return await interaction.edit_original_message(embed=embed)

            description: str = """
## Dostępne atrybuty:

`📕` **Serwer**
- `{guild_name}` = Nazwa serwera
- `{guild_total_members}` = Liczba wszystkich użytkowników
- `{guild_id}` = ID Serwera

`➕` **Dołączający**
- `{user}` = Nazwa użytkownika + hasztag
- `{user_name}` = Nazwa użytkownika
- `{user_mention}` = Oznaczenie użytkownika
- `{user_discriminator}` = Hasztag użytkownika
- `{user_id}` = ID Użytkownika

`🔑` **Zapraszający**
- `{inviter}` = Nazwa zapraszającego + hasztag
- `{inviter_name}` = Nazwa zapraszającego
- `{inviter_mention}` = Oznaczanie zapraszającego
- `{inviter_discriminator}` = Hasztag zapraszającego
- `{inviter_id}` = ID zapraszającego
- `{inviter_total_invites}` = Aktualna liczba zaproszeń zapraszającego

`💢` **Ważne**
- Na odpowiedź masz 10 minut. Wpisz `stop`, aby przerwać konfiguracje teraz.
- Wszystkie atrybuty zamienią się z danymi osoby i zapraszającego.
- Przykład:
```{user_mention} Dołączył/a z zaproszenia **{inviter}**, który ma teraz `{inviter_total_invites}` zaproszeń! ```
"""

            embed = Embed(
                title="`🛠️` Konfiguracja wiadomości powiadomienia",
                color=Color.dark_theme(),
                timestamp=utils.utcnow(),
                description=f"{Emojis.REPLY.value} Wpisz treść wiadmości przy wysłaniu powiadomienia."
                + description,
            )
            embed.set_footer(text="Etap 2/2")
            embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
            await interaction.edit_original_message(embed=embed)

            try:
                message_notify: Message = await self.bot.wait_for(
                    "message",
                    check=lambda message: message.author == interaction.user,
                    timeout=600,
                )

                await message_notify.delete()

                embed.set_footer(text=f"Smiffy v{self.bot.__version__}", icon_url=self.bot.avatar_url)

            except exceptions.TimeoutError:
                embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
                embed.description = f"{Emojis.REPLY.value} Instalacja przerwana (Upłynął limit czasu)."
                embed.colour = Color.red()
                return await interaction.edit_original_message(embed=embed)

            if message_notify.content.lower() == "stop":
                embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
                embed.description = f"{Emojis.REPLY.value} Instalacja przerwana (Wstrzymana ręcznie)."
                embed.colour = Color.red()

                return await interaction.edit_original_message(embed=embed)

            if len(message_notify.content) >= 1200:
                embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
                embed.description = f"{Emojis.REPLY.value} Instalacja przerwana (Limit `1200` znaków)."
                embed.colour = Color.red()

                return await interaction.edit_original_message(embed=embed)

            embed.title = f"Instalacja pomyślnie zakończona {Emojis.GREENBUTTON.value}"
            embed.description = (
                f"{Emojis.REPLY.value} Przypisano powiadomienia o zaproszeniach "
                f"do kanału: {channel.mention}."
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)

            await interaction.edit_original_message(embed=embed)

            notify_data: dict[str, int | str] = {
                "notify_content": message_notify.content,
                "notify_channel": channel.id,
            }

            await self.bot.db.execute_fetchone(
                "UPDATE server_invites SET notify_data = ? WHERE guild_id = ?",
                (str(notify_data), interaction.guild.id),
            )

        else:
            if response and not response[0]:
                return await interaction.send_error_message(
                    description="Powiadomienia o zaproszeniach już są wyłączone."
                )

            await self.bot.db.execute_fetchone(
                "UPDATE server_invites SET notify_data = ? WHERE guild_id = ?",
                (None, interaction.guild.id),
            )

            await interaction.send_success_message(
                title=f"Pomyślnie wyłączono {Emojis.GREENBUTTON.value}",
                description=f"{Emojis.REPLY.value} Powiadomienia o zaproszeniach zostały wyłączone.",
            )

    @invites.subcommand(name="dodaj", description="Dodaje zaproszenia wybranej osobie")  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def invites_add(
        self,
        interaction: CustomInteraction,
        member: Member = SlashOption(name="osoba", description="Podaj osobę której chcesz dodać zaproszenia"),
        amount: int = SlashOption(name="ilość", description="Podaj ilość zaproszeń"),
    ):
        amount = abs(amount)

        if amount > 100000:
            return await interaction.send_error_message(
                description="Nie możesz dodać więcej niż `100.000` zaproszeń."
            )

        if member.bot:
            return await interaction.send_error_message(description="Nie możesz dodać zaproszeń dla bota.")

        await interaction.response.defer()

        assert isinstance(interaction.user, Member) and interaction.guild

        user: Member = member or interaction.user

        guild_data: Optional[DB_RESPONSE] = await self.get_guild_invites_data(interaction.guild)
        if guild_data is None:
            return await interaction.send_error_message(
                description="System zaproszeń na serwerze jest wyłączony."
            )

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT bonus FROM user_invites WHERE guild_id = ? AND user_id = ?",
            (interaction.guild.id, user.id),
        )

        bonus: int = amount
        if response:
            bonus += response[0]
            if bonus > 100_000:
                return await interaction.send_error_message(
                    description="Bonusowe zaproszenia nie mogą przekraczać ilości `100.000`."
                )

            await self.bot.db.execute_fetchone(
                "UPDATE user_invites SET bonus = ? WHERE guild_id = ? AND user_id = ?",
                (bonus, interaction.guild.id, user.id),
            )

        else:
            await self.bot.db.execute_fetchone(
                "INSERT INTO user_invites(guild_id, user_id, normal, left, fake, bonus, invited) VALUES(?,?,?,?,?,?,?)",
                (interaction.guild.id, user.id, 0, 0, 0, bonus, "[]"),
            )

        await interaction.send_success_message(
            title=f"Pomyślnie dodano zaproszenia {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Dodano: `{amount}` bonusowych zaproszeń dla: {user.mention}.",
        )

    @invites.subcommand(name="usuń", description="Usuwa zaproszenia wybranej osobie")  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def invites_remove(
        self,
        interaction: CustomInteraction,
        member: Member = SlashOption(name="osoba", description="Podaj osobę której chcesz dodać zaproszenia"),
        amount: int = SlashOption(name="ilość", description="Podaj ilość zaproszeń"),
    ):
        amount = abs(amount)

        if amount > 100000:
            return await interaction.send_error_message(
                description="Nie możesz usunąć więcej niż `100.000` zaproszeń."
            )

        if member.bot:
            return await interaction.send_error_message(description="Nie możesz dodać zaproszeń dla bota.")

        await interaction.response.defer()

        assert isinstance(interaction.user, Member) and interaction.guild

        user: Member = member or interaction.user

        guild_data: Optional[DB_RESPONSE] = await self.get_guild_invites_data(interaction.guild)

        if guild_data is None:
            return await interaction.send_error_message(
                description="System zaproszeń na serwerze jest wyłączony."
            )

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT bonus FROM user_invites WHERE guild_id = ? AND user_id = ?",
            (interaction.guild.id, user.id),
        )

        bonus: int = -amount

        if response:
            bonus += response[0]

            if bonus < -100_000:
                return await interaction.send_error_message(
                    description="Bonusowe zaproszenia nie mogą przekraczać ilości `-100.000`."
                )

            await self.bot.db.execute_fetchone(
                "UPDATE user_invites SET bonus = ? WHERE guild_id = ? AND user_id = ?",
                (bonus, interaction.guild.id, user.id),
            )

        else:
            await self.bot.db.execute_fetchone(
                "INSERT INTO user_invites(guild_id, user_id, normal, left, fake, bonus, invited) VALUES(?,?,?,?,?,?,?)",
                (interaction.guild.id, user.id, 0, 0, 0, bonus, "[]"),
            )

        await interaction.send_success_message(
            title=f"Pomyślnie usunięto zaproszenia {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Usunięto: `{amount}` bonusowych zaproszeń dla: {user.mention}.",
        )

    @invites.subcommand(name="info", description="Sprawdza kto zaprosił danego użytkownika")
    async def invites_info(
        self,
        interaction: CustomInteraction,
        member: Member = SlashOption(name="osoba", description="Wybierz użytkownika"),
    ):
        assert interaction.guild

        if member.bot:
            return await interaction.send_error_message(description="To nie działa na boty :(")

        await interaction.response.defer()

        guild_data: Optional[DB_RESPONSE] = await self.get_guild_invites_data(interaction.guild)

        if guild_data is None:
            return await interaction.send_error_message(
                description="System zaproszeń na serwerze jest wyłączony."
            )

        users: Iterable[DB_RESPONSE] = await self.bot.db.execute_fetchall(
            "SELECT * FROM user_invites WHERE guild_id = ?", (interaction.guild.id,)
        )

        inviter: Optional[Member] = None

        for user_data in users:
            invited: str = user_data[6]

            if invited != "[]":
                invited_users: list[int] = literal_eval(invited)

                if member.id in invited_users:
                    inviter_id: int = user_data[1]

                    inviter = await self.bot.getch_member(interaction.guild, inviter_id)

        if not inviter:
            return await interaction.send_error_message(
                description=f"Nie jestem w stanie sprawdzić kto zaprosił: {member.mention}"
            )

        await interaction.send_success_message(
            title="`📕` Informacje o zaproszeniu.",
            description=f"{Emojis.REPLY.value} {inviter.mention} zaprosił/a {member.mention} ({member})",
            color=Color.dark_theme(),
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandInvites(bot))
