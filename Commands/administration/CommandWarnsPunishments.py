from __future__ import annotations
from typing import TYPE_CHECKING

from ast import literal_eval
from nextcord import Embed, Color, utils, slash_command, SlashOption, ui, SelectOption

from humanfriendly import parse_timespan, InvalidTimespan

from utilities import (
    CustomInteraction,
    CustomCog,
    PermissionHandler,
)
from enums import Emojis

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import Optional, DB_RESPONSE


class WarningsPunishmentsList(ui.Select):
    def __init__(self, bot: Smiffy, response: str):
        self.bot: Smiffy = bot

        if not response or response == "{}":
            options = [SelectOption(label="Brak", description="Brak kar za ustalone warny.", emoji="❌")]

        else:
            options: list[SelectOption] = []
            data: dict[str, tuple[str, str]] = literal_eval(response)

            for warn_count, action_data in data.items():
                action: str = action_data[0]
                action_duration: str = str(action_data[1])
                if action_duration == "0":
                    action_duration: str = f"{action_duration}s"

                options.append(
                    SelectOption(
                        label=f"Ilość warnów: {warn_count}",
                        description=f"Akcja: {action} ({action_duration})",
                        value=warn_count,
                        emoji=Emojis.A_GEARS.value,
                    )
                )

        super().__init__(placeholder="Wybierz którą kare chcesz usunąć.", options=options)

    async def callback(self, interaction: CustomInteraction):
        assert interaction.guild

        if self.values[0] == "Brak":
            return

        warn_count: int = int(self.values[0])

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM warnings_punishments WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        if not response:
            return await interaction.send_error_message(
                description="Wystąpił problem z bazą danych.", ephemeral=True
            )

        warn_data: dict = literal_eval(str(response[1]))
        action_data: tuple[str, str] = warn_data[warn_count]
        action: str = action_data[0]

        del warn_data[warn_count]

        await self.bot.db.execute_fetchone(
            "UPDATE warnings_punishments SET data = ? WHERE guild_id = ?",
            (str(warn_data), interaction.guild.id),
        )

        return await interaction.send_success_message(
            title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Usunięto karę `{action.capitalize()}` za `{warn_count}` ostrzeżeń",
            color=Color.dark_theme(),
        )


class PunishmentsListView(ui.View):
    def __init__(self, bot: Smiffy, response: str):
        super().__init__(timeout=None)

        self.add_item(WarningsPunishmentsList(bot, response))


class AddWarningPunishmentModal(ui.Modal):
    def __init__(self, action: str, bot: Smiffy):
        super().__init__(title="Dodawanie kary za ostrzeżenie")

        self.bot: Smiffy = bot
        self.warn_count = ui.TextInput(label="Podaj ilość ostrzeżeń.", max_length=2, min_length=1)

        self.action = action
        self.time = ui.TextInput(label="Podaj czas | np. 5m (5 minut)", max_length=10, min_length=1)

        self.add_item(self.warn_count)
        if action in ["tempban", "mute"]:
            self.add_item(self.time)

    async def callback(self, interaction: CustomInteraction):
        assert interaction.guild

        try:
            if not self.warn_count.value:
                raise ValueError

            warns_count: int = int(self.warn_count.value)
        except ValueError:
            return await interaction.send_error_message(description="Liczba ostrzeżeń musi być cyfrą!")

        if self.time.value:
            try:
                parse_timespan(self.time.value)
            except InvalidTimespan:
                return await interaction.send_error_message(
                    description="Niepoprawna jednostka czasu\n> Przykład: `15m` (`15 minut`)"
                )

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM warnings_punishments WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        if not response:
            warnings_data: dict = {}
            await self.bot.db.execute_fetchone(
                "INSERT INTO warnings_punishments(guild_id, data) VALUES(?,?)",
                (interaction.guild.id, str(warnings_data)),
            )
        else:
            warnings_data: dict = literal_eval(response[1])
            if len(list(warnings_data.keys())) >= 20:
                return await interaction.send_error_message(
                    description="Osiągnięto limit kar za warny. Limit: `20`"
                )

        if self.time.value and self.action.lower() in ["tempban", "mute"]:
            warnings_data[warns_count] = (self.action, self.time.value)
        else:
            warnings_data[warns_count] = (self.action, "0")

        await self.bot.db.execute_fetchone(
            "UPDATE warnings_punishments SET data = ? WHERE guild_id = ?",
            (str(warnings_data), interaction.guild.id),
        )

        return await interaction.send_success_message(
            title=f"Pomyślnie dodano {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Kara: `{self.action.capitalize()}` "
            f"za: **{warns_count}** ostrzeżeń została dodana",
        )


class SelectAction(ui.Select):
    def __init__(self, bot: Smiffy):
        self.bot: Smiffy = bot

        options = [
            SelectOption(
                label="Ban",
                description="Akcja Ban, banuje permanentnie użytkownika",
                value="ban",
                emoji="⛔",
            ),
            SelectOption(
                label="TempBan",
                description="Akcja TempBan, banuje użytkownika na określony czas",
                value="tempban",
                emoji="⏱️",
            ),
            SelectOption(
                label="Kick",
                description="Akcja Kick, wyrzuca użytkownika z serwera",
                value="kick",
                emoji="👋",
            ),
            SelectOption(
                label="Mute",
                description="Akcja Mute, Wycisza użytkownika na określony czas",
                value="mute",
                emoji="🚫",
            ),
        ]

        super().__init__(placeholder="Wybierz, którą akcje chcesz wykonać.", options=options)

    async def callback(self, interaction: CustomInteraction):
        add_punishment_modal = AddWarningPunishmentModal(self.values[0], self.bot)
        await interaction.response.send_modal(add_punishment_modal)


class SelectActionView(ui.View):
    def __init__(self, bot: Smiffy):
        super().__init__(timeout=None)

        self.add_item(SelectAction(bot))


class CommandWarnsPunishments(CustomCog):
    @slash_command(  # pyright: ignore
        name="karywarny",
        description="Zarządzaj karami za otrzymanie konkretnej ilości ostrzeżeń.",
        dm_permission=False,
    )
    @PermissionHandler(manage_guild=True, user_role_has_permission="karywarny")
    async def warnspunishments(
        self,
        interaction: CustomInteraction,
        option: str = SlashOption(
            name="opcja",
            description="Wybierz opcję, która cie interesuje.",
            choices={"Lista": "list", "Dodaj": "add", "Usuń": "remove"},
        ),
    ):
        assert interaction.guild

        if option == "list":
            await interaction.response.defer()

            response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
                "SELECT * FROM warnings_punishments WHERE guild_id = ?",
                (interaction.guild.id,),
            )
            if response and response[1] != "{}":
                warnings_data: dict[str, tuple] = literal_eval(response[1])

                embed = Embed(
                    title="`📜` Kary za ostrzeżenia na serwerze",
                    color=Color.dark_theme(),
                    timestamp=utils.utcnow(),
                )
                embed.set_thumbnail(url=interaction.guild_icon_url)
                embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)

                embed.set_footer(icon_url=self.bot.avatar_url, text=f"Smiffy v{self.bot.__version__}")

                for warn_count, action_data in warnings_data.items():
                    action: str = action_data[0]
                    action_duration: str = action_data[1]

                    if "mute" == action.lower() or "tempban" == action.lower():
                        embed.add_field(
                            name=f"`📌` Ilość warnów: {warn_count}",
                            value=f"{Emojis.REPLY.value} **Akcja:** "
                            f"`{action.capitalize()}` (`{action_duration}`)",
                            inline=False,
                        )
                    else:
                        embed.add_field(
                            name=f"`📌` Ilość warnów: {warn_count}",
                            value=f"{Emojis.REPLY.value} **Akcja:** `{action.capitalize()}`",
                            inline=False,
                        )

                return await interaction.send(embed=embed)

            return await interaction.send_error_message(
                description="Na serwerze aktualnie nie ma żadnych kar za warny.",
            )

        if option == "remove":
            response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
                "SELECT * FROM warnings_punishments WHERE guild_id = ?",
                (interaction.guild_id,),
            )
            if not response or response[1] == "{}":
                return await interaction.send_error_message(
                    description="Na serwerze aktualnie nie ma żadnych kar za warny."
                )

            data: str = response[1]
            punishments_list = PunishmentsListView(self.bot, data)

            embed = Embed(
                title="`❌` Wybierz karę z listy",
                color=Color.dark_theme(),
                description=f"{Emojis.REPLY.value} Wybierz z listy, którą karę chcesz usunąć.",
                timestamp=utils.utcnow(),
            )
            embed.set_footer(text=f"Smiffy v{self.bot.__version__}", icon_url=self.bot.avatar_url)
            embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
            embed.set_thumbnail(url=interaction.guild_icon_url)

            await interaction.send(embed=embed, view=punishments_list, ephemeral=True)

        if option == "add":
            view: SelectActionView = SelectActionView(self.bot)

            embed = Embed(
                title="`❌` Wybierz karę z listy",
                color=Color.green(),
                description=f"{Emojis.REPLY.value} Wybierz z listy akcję, "
                f"którą chcesz wykonywać po zdobyciu określonej ilości ostrzeżeń.",
                timestamp=utils.utcnow(),
            )
            embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
            embed.set_thumbnail(url=interaction.guild_icon_url)
            await interaction.send(embed=embed, view=view, ephemeral=True)


def setup(bot: Smiffy):
    bot.add_cog(CommandWarnsPunishments(bot))
