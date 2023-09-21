from __future__ import annotations

from ast import literal_eval
from asyncio import exceptions
from io import BytesIO
from itertools import islice
from typing import TYPE_CHECKING, Iterable, Optional

from easy_pil import Canvas, Editor, Font, load_image_async
from nextcord import (
    ButtonStyle,
    Color,
    Embed,
    File,
    Guild,
    Member,
    Message,
    Role,
    SelectOption,
    SlashOption,
    TextChannel,
    slash_command,
    ui,
    utils,
)

from converters import GuildChannelConverter, RoleConverter
from enums import Emojis, GuildChannelTypes
from typings import DB_RESPONSE, UserlevelingData
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from bot import Smiffy


class ConfirmReset(ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=None)
        self.author_id: int = author_id

    async def interaction_check(self, interaction: CustomInteraction) -> bool:
        assert interaction.user

        if interaction.user.id == self.author_id:
            return True

        await interaction.send_error_message(
            description="Tylko autor użytej komendy może tego użyć.", ephemeral=True
        )
        return False

    @ui.button(label="Potwierdź", style=ButtonStyle.green, emoji=Emojis.GREENBUTTON.value)  # pyright: ignore
    async def confirm(
        self, button: ui.Button, interaction: CustomInteraction
    ):  # pylint: disable=unused-argument
        assert interaction.guild

        bot: Smiffy = interaction.bot

        await bot.db.execute_fetchone("DELETE FROM levels WHERE guild_id = ?", (interaction.guild.id,))

        await bot.db.execute_fetchone("DELETE FROM levels_users WHERE guild_id = ?", (interaction.guild.id,))

        await interaction.send_success_message(
            title=f"Pomyślnie zresetowano {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Levelowanie zostało całkowicie zresetowane.",
            color=Color.dark_theme(),
        )

        if interaction.message:
            await interaction.message.delete()

    @ui.button(label="Anuluj", style=ButtonStyle.red, emoji=Emojis.REDBUTTON.value)  # pyright: ignore
    async def cancel(
        self, button: ui.Button, interaction: CustomInteraction
    ):  # pylint: disable=unused-argument
        if interaction.message:
            await interaction.message.delete()


class RemoveRoleRewardSelect(ui.Select):
    def __init__(self, roles_data: dict[int, int], guild: Guild) -> None:
        self.guild: Guild = guild

        options: list[SelectOption] = []

        for level, role_id in roles_data.items():
            role: Optional[Role | str] = guild.get_role(role_id)

            if not role:
                role = "Deleted role"

            options.append(
                SelectOption(
                    label=f"Level: {level}",
                    description=f"Rola: {role}",
                    emoji="<a:roleicon:1151668825457168405:>",
                    value=str(level),
                )
            )

        super().__init__(placeholder="Wybierz rolę", options=options)

    async def callback(self, interaction: CustomInteraction):
        assert interaction.guild

        level: int = int(self.values[0])

        bot: Smiffy = interaction.bot

        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT * FROM levels WHERE guild_id = ?", (interaction.guild.id,)
        )
        if not response:
            return await interaction.send_error_message(description="Levelowanie jest wyłączone.")

        roles_data: dict[int, int] = literal_eval(response[1])
        try:
            role_id: int = roles_data[level]

            role: Optional[Role | str] = await bot.getch_role(interaction.guild, int(role_id))
            role_mention: str = role.mention if role else "Deleted role"

            del roles_data[level]

        except KeyError:
            return await interaction.send_error_message(
                description="Nie mogłem odnaleźć takiej roli w bazie."
            )

        roles_to_db: Optional[str] = str(roles_data) if len(roles_data) else None

        await bot.db.execute_fetchone(
            "UPDATE levels SET roles_data = ? WHERE guild_id = ?",
            (roles_to_db, interaction.guild.id),
        )

        await interaction.send_success_message(
            title=f"Pomyślnie usunięto {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Usunięto role: {role_mention} za zdobycie `{level}` levelu.",
        )


class RemoveRoleRewardView(ui.View):
    def __init__(self, roles_data: dict[int, int], guild: Guild):
        super().__init__(timeout=None)

        self.add_item(RemoveRoleRewardSelect(roles_data, guild))


class SelectRolesMenus(ui.Select):
    def __init__(self) -> None:
        options = [
            SelectOption(
                label="Dodaj",
                description="Dodaj rolę za level.",
                emoji=Emojis.GREENBUTTON.value,
            ),
            SelectOption(label="Lista", description="Lista roli z nagrodami za level.", emoji="📃"),
            SelectOption(
                label="Usuń",
                description="Usuń rolę za level.",
                emoji=Emojis.REDBUTTON.value,
            ),
        ]

        super().__init__(placeholder="Wybierz opcję", options=options)

    async def callback(self, interaction: CustomInteraction):
        option: str = self.values[0]
        if option == "Lista":
            return await self.list_roles_for_levels(interaction)
        if option == "Dodaj":
            return await self.add_role_for_level(interaction)
        if option == "Usuń":
            return await self.remove_role_for_level(interaction)

    @staticmethod
    async def add_role_for_level(inter: CustomInteraction):
        assert inter.guild and isinstance(inter.user, Member)

        bot: Smiffy = inter.bot

        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT * FROM levels WHERE guild_id = ?", (inter.guild.id,)
        )

        if not response:
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                color=Color.red(),
                timestamp=utils.utcnow(),
                description=f"{Emojis.REPLY.value} Levelowanie jest wyłączone.",
            )
            embed.set_thumbnail(url=inter.guild_icon_url)
            embed.set_author(name=inter.user, icon_url=inter.user_avatar_url)
            return await inter.send(embed=embed)

        embed = Embed(
            title="`🛠️` Konfigurowanie roli za level.",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
            description="- Oznacz role lub podaj ID roli, która chcesz ustawić.\n"
            "- Na odpowiedź masz **60** sekund. Inaczej konfiguracja zostanie przerwana. "
            "**Aby przerwać ją teraz, wpisz `stop`.**",
        )
        embed.set_footer(text="Etap 1/2")
        embed.set_author(name=inter.user, icon_url=inter.user_avatar_url)
        embed.set_thumbnail(url=inter.guild_icon_url)
        await inter.send(embed=embed)

        try:
            role_message: Message = await bot.wait_for(
                "message",
                check=lambda message: message.author == inter.user,
                timeout=60,
            )
            await role_message.delete()
        except exceptions.TimeoutError:
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Instalacja przerwana (Upłynął limit czasu).\n\n"
                f"Wiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

            await inter.edit_original_message(embed=embed)
            return await inter.delete_original_message(delay=20)

        if role_message.content.lower() == "stop":
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Instalacja przerwana (Wstrzymana ręcznie). \n\n"
                f"Wiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

            await inter.edit_original_message(embed=embed)
            return await inter.delete_original_message(delay=20)

        role: Optional[Role] = await RoleConverter().convert(inter, role_message.content)

        if not role:
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Podałeś/aś nieprawidłową role. Instalacja przerwana.\n\n"
                f"Wiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

            await inter.edit_original_message(embed=embed)
            return await inter.delete_original_message(delay=20)

        if inter.user.top_role.position <= role.position and inter.guild.owner_id != inter.user.id:
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Podana rola posiada większe uprawnienia od ciebie.\n\n"
                f"Wiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

            await inter.edit_original_message(embed=embed)
            return await inter.delete_original_message(delay=20)

        if not role.is_assignable() or role.is_premium_subscriber():
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Podana rola posiada większe uprawnienia od bota.\n\n"
                f"Wiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

            await inter.edit_original_message(embed=embed)
            return await inter.delete_original_message(delay=20)

        embed.description = (
            f"{Emojis.REPLY.value} Dobrze, a teraz podaj `level` za który ma być nadawana "
            f"rola: {role.mention}\n\n- Level nie może być niższy niz `0` lub wyższy niż `1000`\n"
            f"- Na odpowiedź masz **60** sekund. "
            f"Inaczej konfiguracja zostanie przerwana. **Aby przerwać ją teraz, wpisz `stop`.**"
        )

        embed.set_footer(text="Etap 2/2")
        await inter.edit_original_message(embed=embed)

        try:
            level_message: Message = await bot.wait_for(
                "message",
                check=lambda message: message.author == inter.user,
                timeout=60,
            )
            await level_message.delete()
        except exceptions.TimeoutError:
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Instalacja przerwana (Upłynął limit czasu). \n\n"
                f"Wiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer()
            await inter.edit_original_message(embed=embed)
            return await inter.delete_original_message(delay=20)

        if role_message.content.lower() == "stop":
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Instalacja przerwana. \n\n"
                f"Wiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer()

            await inter.edit_original_message(embed=embed)
            return await inter.delete_original_message(delay=20)

        try:
            level: int = int(level_message.content)
            if level <= 0 or level > 1000:
                raise ValueError
        except ValueError:
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Podałeś/aś nieprawidłowy level. "
                f"Instalacja zostaje przerwana."
                f"\n\nWiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer()

            await inter.edit_original_message(embed=embed)
            return await inter.delete_original_message(delay=20)

        if not response[1]:
            await bot.db.execute_fetchone(
                "UPDATE levels SET roles_data = ? WHERE guild_id = ?",
                (str({level: role.id}), inter.guild.id),
            )
        else:
            roles_data: dict[int, int] = literal_eval(response[1])
            if len(roles_data) > 20:
                embed = Embed(
                    title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                    color=Color.red(),
                    timestamp=utils.utcnow(),
                    description=f"{Emojis.REPLY.value} Osiągnięto limit 20 ról za level.",
                )
                embed.set_author(name=inter.user, icon_url=inter.user_avatar_url)
                return await inter.edit_original_message(embed=embed)

            roles_data[level] = role.id
            await bot.db.execute_fetchone(
                "UPDATE levels SET roles_data = ? WHERE guild_id = ?",
                (str(roles_data), inter.guild.id),
            )

        embed.title = f"Instalacja zakończona {Emojis.GREENBUTTON.value}"
        embed.colour = Color.dark_theme()
        embed.set_thumbnail(url=inter.guild_icon_url)
        embed.description = (
            f"{Emojis.REPLY.value} Rola: {role.mention} będzie nadawana w "
            f"momencie zdobycia `{level}` levelu."
        )

        embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)
        await inter.edit_original_message(embed=embed)

    @staticmethod
    async def list_roles_for_levels(inter: CustomInteraction):
        assert inter.guild

        bot: Smiffy = inter.bot

        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT * FROM levels WHERE guild_id = ?", (inter.guild.id,)
        )
        if not response or not response[1]:
            return await inter.send_error_message(
                description="Na serwerze nie ma żadnych skonfigurowanych ról za level."
            )

        roles_data: dict[int, int] = literal_eval(response[1])

        embed = Embed(
            title="`📄` Smiffy levelowanie: Role za level",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )
        embed.set_thumbnail(url=inter.guild_icon_url)
        embed.set_author(name=inter.user, icon_url=inter.user_avatar_url)

        for level, role_id in roles_data.items():
            role: Optional[Role] = await bot.getch_role(inter.guild, int(role_id))

            if role:
                role_mention: str = role.mention
            else:
                role_mention: str = "Deleted Role"

            embed.add_field(name=f"`🔖` Level: {level}", value=f"{Emojis.REPLY.value} {role_mention}")

        await inter.send(embed=embed)

    @staticmethod
    async def remove_role_for_level(inter: CustomInteraction):
        assert inter.guild

        bot: Smiffy = inter.bot

        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT * FROM levels WHERE guild_id = ?", (inter.guild.id,)
        )
        if not response or not response[1]:
            return await inter.send_error_message(
                description="Na serwerze nia ma żadnych skonfigurowanych ról za level."
            )

        roles_data: dict[int, int] = literal_eval(response[1])
        new_view = RemoveRoleRewardView(roles_data, inter.guild)

        embed = Embed(
            title="`❌` Usuwanie roli za level",
            description=f"{Emojis.REPLY.value} Wybierz rolę z listy, którą chcesz usunąć.",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )
        embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)
        embed.set_author(name=inter.user, icon_url=inter.user_avatar_url)
        embed.set_thumbnail(url=inter.guild_icon_url)
        await inter.response.edit_message(embed=embed, view=new_view)


class SelectNotifyMenus(ui.Select):
    def __init__(self) -> None:
        options = [
            SelectOption(
                label="Kanał",
                description="Wysyłaj wiadomość na kanale serwera",
                emoji="📌",
                value="channel",
            ),
            SelectOption(
                label="Pv (DM)",
                description="Wysyłaj wiadomość w prywatnej wiadomości",
                emoji="👤",
                value="dm",
            ),
            SelectOption(
                label="Obie opcje",
                description="Wysyłaj wiadomość na kanale i w prywatnej wiadmości",
                emoji="📋",
                value="both",
            ),
        ]

        super().__init__(placeholder="Wybierz sposób informowania o levelach", options=options)

    async def callback(self, interaction: CustomInteraction):
        notify: str = self.values[0]

        if notify == "channel":
            return await self.channel(interaction)
        if notify == "dm":
            return await self.dm(interaction)
        if notify == "both":
            return await self.both(interaction)

    @staticmethod
    async def get_notify_content(embed: Embed, inter: CustomInteraction) -> Optional[str]:
        bot: Smiffy = inter.bot

        try:
            notify_message: Message = await bot.wait_for(
                "message",
                check=lambda message: message.author == inter.user,
                timeout=600,
            )
            await notify_message.delete()

        except exceptions.TimeoutError:
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Instalacja przerwana (Upłynął limit czasu).\n\n"
                "Wiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer(text=f"Smiffy v{bot.__version__} | Etap 1/1", icon_url=bot.avatar_url)
            await inter.edit_original_message(embed=embed)
            await inter.delete_original_message(delay=20)
            return None

        if notify_message.content.lower() == "stop":
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Instalacja przerwana (Wstrzymana ręcznie).\n\n"
                "Wiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer(text=f"Smiffy v{bot.__version__} | Etap 1/1", icon_url=bot.avatar_url)
            await inter.edit_original_message(embed=embed)
            await inter.delete_original_message(delay=20)
            return None

        if len(notify_message.content) > 1000:
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Instalacja przerwana (Wiadomość przekracza 1000 znaków)."
                "\n\nWiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer(text=f"Smiffy v{bot.__version__} | Etap 1/1", icon_url=bot.avatar_url)

            await inter.edit_original_message(embed=embed)
            await inter.delete_original_message(delay=20)
            return None

        if notify_message.content.lower() == "domyślny":
            return "Gratulacje {user}! Osiągnąłeś nowy poziom: **{level}**."

        return notify_message.content

    @staticmethod
    async def get_notify_channel(embed: Embed, inter: CustomInteraction) -> Optional[TextChannel]:
        bot: Smiffy = inter.bot

        try:
            channel_message: Message = await bot.wait_for(
                "message",
                check=lambda message: message.author == inter.user,
                timeout=60,
            )
            await channel_message.delete()
        except exceptions.TimeoutError:
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Instalacja przerwana (Upłynął limit czasu).\n\n"
                "Wiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)
            await inter.edit_original_message(embed=embed)
            await inter.delete_original_message(delay=20)
            return None

        if channel_message.content.lower() == "stop":
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Instalacja przerwana (Wstrzymana ręcznie).\n\n"
                "Wiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)
            await inter.edit_original_message(embed=embed)
            await inter.delete_original_message(delay=20)
            return None

        channel: Optional[TextChannel] = GuildChannelConverter()[GuildChannelTypes.text_channels].convert(
            interaction=inter,
            argument=channel_message.content,
        )

        if not channel:
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Instalacja przerwana (Nieprawidłowy kanał).\n\n"
                "Wiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)
            await inter.edit_original_message(embed=embed)
            await inter.delete_original_message(delay=20)
            return None

        return channel

    async def channel(self, inter: CustomInteraction):
        assert inter.guild and inter.user

        bot: Smiffy = inter.bot

        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT * FROM levels WHERE guild_id = ?", (inter.guild.id,)
        )

        if not response:
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                color=Color.red(),
                timestamp=utils.utcnow(),
                description=f"{Emojis.REPLY.value} Levelowanie jest wyłączone.",
            )
            embed.set_thumbnail(url=inter.guild_icon_url)
            embed.set_author(name=inter.user, icon_url=inter.user_avatar_url)
            return await inter.send(embed=embed)

        embed = Embed(
            title="`🛠️` Konfigurowanie powiadomień na kanale",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
            description=f"{Emojis.REPLY.value} Oznacz lub podaj ID kanału, który chcesz ustawić.\n\n"
            f"Na odpowiedź masz **60** sekund. Inaczej konfiguracja zostanie przerwana. "
            f"Aby przerwać ją teraz, wpisz `stop`.",
        )
        embed.set_footer(text="Etap 1/2")
        embed.set_thumbnail(url=inter.guild_icon_url)
        embed.set_author(name=inter.user, icon_url=inter.user_avatar_url)
        await inter.send(embed=embed)

        notify_channel: Optional[TextChannel] = await self.get_notify_channel(embed, inter)
        if not notify_channel:
            return

        notify_attributes: str = """## Dostępne atrybuty:
```
{level} = Nowy poziom.
{user} = Nick użytkownika, który awansował.
{user.mention} = Oznacznie użytkownika, który awansował.
```
Możesz też użyć domyślnego komunikatu bota, wpisując: `domyślny`.\n
"""

        embed.description = (
            f"{Emojis.REPLY.value} Dobrze, a teraz podaj treść powiadomienia.\n"
            "- **Przykład poniżej:**\n> `Gratulacje {user}! Osiągnąłeś nowy poziom: **{level}**.`\n"
            f"{notify_attributes} Na odpowiedź masz **10** minut. "
            "Inaczej konfiguracja zostanie przerwana. Aby przerwać ją teraz, wpisz `stop`."
        )

        embed.set_footer(text=f"Smiffy v{bot.__version__} | Etap 2/2", icon_url=bot.avatar_url)
        embed.set_author(name=inter.user, icon_url=inter.user_avatar_url)

        embed.description = (
            f"{Emojis.REPLY.value} Podaj treść powiadomienia.\n"
            f"- **Przykład poniżej:**\n{Emojis.REPLY.value} "
            "`Gratulacje {user}! Osiągnąłeś nowy poziom: **{level}**.`\n"
            f"{notify_attributes} `⛔` Na odpowiedź masz **10** minut. "
            "Inaczej konfiguracja zostanie przerwana. Aby przerwać ją teraz, wpisz `stop`."
        )
        await inter.edit_original_message(embed=embed)

        notify_content: Optional[str] = await self.get_notify_content(embed, inter)

        if not notify_content:
            return

        alerts_data: dict[str, str | int] = {
            "type": "channel",
            "notify_content": notify_content,
            "channel_id": notify_channel.id,
        }

        await bot.db.execute_fetchone(
            "UPDATE levels SET alerts_data = ? WHERE guild_id = ?",
            (str(alerts_data), inter.guild.id),
        )

        embed.title = f"Instalacja zakończona {Emojis.GREENBUTTON.value}"
        embed.colour = Color.dark_theme()
        embed.set_thumbnail(url=inter.guild_icon_url)
        embed.description = (
            f"{Emojis.REPLY.value} Na kanale: {notify_channel.mention} będą "
            f"wysyłane powiadomienia o nowych levelach."
        )
        embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

        await inter.edit_original_message(embed=embed)

    async def dm(self, inter: CustomInteraction):
        assert inter.guild

        bot: Smiffy = inter.bot

        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT * FROM levels WHERE guild_id = ?", (inter.guild.id,)
        )

        if not response:
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                color=Color.red(),
                timestamp=utils.utcnow(),
                description=f"{Emojis.REPLY.value} Levelowanie jest wyłączone.",
            )
            embed.set_thumbnail(url=inter.guild_icon_url)
            embed.set_author(name=inter.user, icon_url=inter.user_avatar_url)
            return await inter.send(embed=embed)

        notify_attributes: str = """## Dostępne atrybuty:
```
{level} = Nowy poziom.
{user} = Nick użytkownika, który awansował.
{user.mention} = Oznacznie użytkownika, który awansował.
```
Możesz też użyć domyślnego komunikatu bota, wpisując: `domyślny`.\n
"""

        embed = Embed(
            title="`🛠️` Konfigurowanie powiadomień na kanale",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )
        embed.set_footer(text=f"Smiffy v{bot.__version__} | Etap 1/1", icon_url=bot.avatar_url)
        embed.set_author(name=inter.user, icon_url=inter.user_avatar_url)

        embed.description = (
            f"{Emojis.REPLY.value} Podaj treść powiadomienia.\n"
            f"- **Przykład poniżej:**\n{Emojis.REPLY.value} "
            "`Gratulacje {user}! Osiągnąłeś nowy poziom: **{level}**.`\n"
            f"{notify_attributes} `⛔` Na odpowiedź masz **10** minut. "
            "Inaczej konfiguracja zostanie przerwana. Aby przerwać ją teraz, wpisz `stop`."
        )

        await inter.send(embed=embed)

        notify_content: Optional[str] = await self.get_notify_content(embed, inter)
        if not notify_content:
            return

        alerts_data: dict[str, str] = {"type": "dm", "notify_content": notify_content}

        await bot.db.execute_fetchone(
            "UPDATE levels SET alerts_data = ? WHERE guild_id = ?",
            (str(alerts_data), inter.guild.id),
        )

        embed.title = f"Instalacja zakończona {Emojis.GREENBUTTON.value}"
        embed.colour = Color.dark_theme()
        embed.set_thumbnail(url=inter.guild_icon_url)
        embed.description = (
            f"{Emojis.REPLY.value} Powiadomienia o nowych levelach będą "
            f"wysyłane w prywatnych wiadomościach."
        )

        embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

        await inter.edit_original_message(embed=embed)

    async def both(self, inter: CustomInteraction):
        assert inter.guild and inter.user

        bot: Smiffy = inter.bot

        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT * FROM levels WHERE guild_id = ?", (inter.guild.id,)
        )

        if not response:
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                color=Color.red(),
                timestamp=utils.utcnow(),
                description=f"{Emojis.REPLY.value} Levelowanie jest wyłączone.",
            )
            embed.set_thumbnail(url=inter.guild_icon_url)
            embed.set_author(name=inter.user, icon_url=inter.user_avatar_url)
            return await inter.send(embed=embed)

        embed = Embed(
            title="`🛠️` Konfigurowanie powiadomień na kanale i dm'ach",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
            description=f"{Emojis.REPLY.value} Oznacz lub podaj ID kanału, który chcesz ustawić.\n\n"
            f"Na odpowiedź masz **60** sekund. Inaczej konfiguracja zostanie przerwana. "
            f"Aby przerwać ją teraz, wpisz `stop`.",
        )
        embed.set_footer(text=f"Smiffy v{bot.__version__} | Etap 1/2", icon_url=bot.avatar_url)
        embed.set_thumbnail(url=inter.guild_icon_url)
        embed.set_author(name=inter.user, icon_url=inter.user_avatar_url)
        await inter.send(embed=embed)

        notify_channel: Optional[TextChannel] = await self.get_notify_channel(embed, inter)
        if not notify_channel:
            return

        notify_attributes: str = """## Dostępne atrybuty:
```
{level} = Nowy poziom.
{user} = Nick użytkownika, który awansował.
{user.mention} = Oznacznie użytkownika, który awansował.
```
Możesz też użyć domyślnego komunikatu bota, wpisując: `domyślny`.\n
"""

        embed.set_footer(text=f"Smiffy v{bot.__version__} | Etap 2/2", icon_url=bot.avatar_url)
        embed.set_author(name=inter.user, icon_url=inter.user_avatar_url)

        embed.description = (
            f"{Emojis.REPLY.value} Podaj treść powiadomienia.\n"
            f"- **Przykład poniżej:**\n{Emojis.REPLY.value} "
            "`Gratulacje {user}! Osiągnąłeś nowy poziom: **{level}**.`\n"
            f"{notify_attributes} `⛔` Na odpowiedź masz **10** minut. "
            "Inaczej konfiguracja zostanie przerwana. Aby przerwać ją teraz, wpisz `stop`."
        )

        await inter.edit_original_message(embed=embed)

        notify_content: Optional[str] = await self.get_notify_content(embed, inter)
        if not notify_content:
            return

        embed.title = f"Instalacja zakończona {Emojis.GREENBUTTON.value}"
        embed.colour = Color.dark_theme()
        embed.set_thumbnail(url=inter.guild_icon_url)
        embed.description = (
            f"{Emojis.REPLY.value} Na kanale: {notify_channel.mention} "
            f"oraz w prywatnych wiadomościach będą wysyłane powiadomienia o nowych levelach."
        )

        embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)
        await inter.edit_original_message(embed=embed)

        alerts_data: dict[str, int | str] = {
            "type": "both",
            "channel_id": notify_channel.id,
            "notify_content": notify_content,
        }

        await bot.db.execute_fetchone(
            "UPDATE levels SET alerts_data = ? WHERE guild_id = ?",
            (str(alerts_data), inter.guild.id),
        )


class SelectMultiplierMenus(ui.Select):
    def __init__(self) -> None:
        options = [
            SelectOption(label="Ustaw", description="Przypisz mnożnik expa dla roli", emoji="📌"),
            SelectOption(
                label="Usuń",
                description="Usuń mnożnik expa dla roli",
                emoji="❌",
            ),
            SelectOption(
                label="Aktualny",
                description="Pokaż aktualny mnożnik expa dla roli",
                emoji="✨",
            ),
        ]

        super().__init__(placeholder="Wybierz opcje", options=options)

    async def callback(self, interaction: CustomInteraction):
        assert interaction.guild

        bot: Smiffy = interaction.bot

        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT * FROM levels WHERE guild_id = ?", (interaction.guild.id,)
        )
        if not response:
            return await interaction.send_error_message(description="Levelowanie jest wyłączone na serwerze.")

        option: str = self.values[0]
        if option == "Ustaw":
            return await self.set_multiplier(interaction)
        if option == "Usuń":
            return await self.reset_multiplier(interaction)
        if option == "Aktualny":
            return await self.get_multiplier(interaction)

    @staticmethod
    async def get_multiplier_role(embed: Embed, inter: CustomInteraction) -> Optional[Role]:
        assert isinstance(inter.user, Member) and inter.guild

        bot: Smiffy = inter.bot

        try:
            role_message: Message = await bot.wait_for(
                "message",
                check=lambda message: message.author == inter.user,
                timeout=300,
            )
            await role_message.delete()

        except exceptions.TimeoutError:
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Instalacja przerwana (Upłynął limit czasu).\n\n"
                "Wiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

            await inter.edit_original_message(embed=embed)
            await inter.delete_original_message(delay=20)
            return None

        role: Optional[Role] = await RoleConverter().convert(inter, role_message.content)

        if not role:
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Instalacja przerwana (Nieprawidłowa rola).\n\n"
                "Wiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

            await inter.edit_original_message(embed=embed)
            await inter.delete_original_message(delay=20)

            return

        if role.is_bot_managed():
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Instalacja przerwana (Podana rola nie może zostać użyta)."
                f"\n\nWiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

            await inter.edit_original_message(embed=embed)
            await inter.delete_original_message(delay=20)
            return

        if role.position >= inter.user.top_role.position and inter.guild.owner_id != inter.user.id:
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Rola posiada większe uprawnienie od ciebie."
                "\n\nWiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

            await inter.edit_original_message(embed=embed)
            await inter.delete_original_message(delay=20)
            return

        return role

    async def set_multiplier(self, interaction: CustomInteraction) -> None:
        assert interaction.guild

        bot: Smiffy = interaction.bot

        embed = Embed(
            title="`🛠️` Konfigurowanie mnożnika dla roli",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
            description=f"{Emojis.REPLY.value} Oznacz role lub podaj ID do której chcesz przypisać mnożnik.\n\n"
            "Na odpowiedź masz **5** minut. Inaczej konfiguracja zostanie przerwana. "
            "Aby przerwać ją teraz, wpisz `stop`.",
        )
        embed.set_footer(text="Etap 1/2")
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)

        await interaction.send(embed=embed)

        role: Optional[Role] = await self.get_multiplier_role(embed, interaction)
        if not role:
            return

        embed.description = (
            f"{Emojis.REPLY.value} Podaj mnożnik dla roli: {role.mention}. Domyślny mnożnik to: `5`."
            f"\n\nNa odpowiedź masz **5** minut. Inaczej konfiguracja zostanie przerwana. "
            f"Aby przerwać ją teraz, wpisz `stop`."
        )

        embed.set_footer(text="Etap 2/2")
        await interaction.edit_original_message(embed=embed)

        try:
            multiplier_message: Message = await bot.wait_for(
                "message",
                check=lambda message: message.author == interaction.user,
                timeout=300,
            )
            await multiplier_message.delete()

            multiplier: int = abs(int(multiplier_message.content))

        except exceptions.TimeoutError:
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Instalacja przerwana (Upłynął limit czasu).\n\n"
                "Wiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

            await interaction.edit_original_message(embed=embed)
            return await interaction.delete_original_message(delay=20)

        except ValueError:
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Instalacja przerwana (Nieprawidłowa wartość).\n\n"
                "Wiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

            await interaction.edit_original_message(embed=embed)
            return await interaction.delete_original_message(delay=20)

        if multiplier > 50:
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Instalacja przerwana (Przekroczono limit `50` mnożnika).\n\n"
                "Wiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

            await interaction.edit_original_message(embed=embed)
            return await interaction.delete_original_message(delay=20)

        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT multiplier_data FROM levels WHERE guild_id = ?",
            (interaction.guild.id,),
        )

        if not response:
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Instalacja przerwana (Błąd danych).\n\n"
                "Wiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

            await interaction.edit_original_message(embed=embed)
            return await interaction.delete_original_message(delay=20)

        if not response[0]:
            data: dict[int, int] = {role.id: multiplier}
        else:
            data: dict[int, int] = literal_eval(response[0])

            if role.id in data:
                embed = Embed(
                    title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                    color=Color.red(),
                    timestamp=utils.utcnow(),
                    description=f"{Emojis.REPLY.value} Rola już ma przypisany mnożnik",
                )
                embed.set_thumbnail(url=interaction.guild_icon_url)
                embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
                embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

                await interaction.edit_original_message(embed=embed)
                return

            if len(data) == 25:
                embed = Embed(
                    title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                    color=Color.red(),
                    timestamp=utils.utcnow(),
                    description=f"{Emojis.REPLY.value} Osiągnięto limit `25` przypisanych mnożników do ról.",
                )
                embed.set_thumbnail(url=interaction.guild_icon_url)
                embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
                embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

                await interaction.edit_original_message(embed=embed)
                return

            data[role.id] = multiplier

        await bot.db.execute_fetchone(
            "UPDATE levels SET multiplier_data = ? WHERE guild_id = ?",
            (str(data), interaction.guild.id),
        )

        embed.title = f"Instalacja zakończona {Emojis.GREENBUTTON.value}"
        embed.colour = Color.dark_theme()
        embed.description = (
            f"{Emojis.REPLY.value} Przypisano mnożnik `{multiplier}` dla roli: {role.mention}."
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

        await interaction.edit_original_message(embed=embed)

    async def reset_multiplier(self, interaction: CustomInteraction) -> None:
        assert interaction.guild and interaction.user

        bot: Smiffy = interaction.bot

        embed = Embed(
            title="`❌` Usuwanie mnożnika z roli",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
            description=f"{Emojis.REPLY.value} Oznacz role lub podaj ID z której chcesz się pozybyć mnożnika.\n\n"
            "Na odpowiedź masz **10** minut. Inaczej konfiguracja zostanie przerwana. "
            "Aby przerwać ją teraz, wpisz `stop`.",
        )
        embed.set_footer(text="Etap 1/1")
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)

        await interaction.send(embed=embed)

        role: Optional[Role] = await self.get_multiplier_role(embed, interaction)
        if not role:
            return

        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT multiplier_data FROM levels WHERE guild_id = ?",
            (interaction.guild.id,),
        )

        if not response or not response[0]:
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                color=Color.red(),
                timestamp=utils.utcnow(),
                description=f"{Emojis.REPLY.value} Podana rola nie ma przypisanego mnożniku.",
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)
            embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
            embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

            await interaction.edit_original_message(embed=embed)
            return

        data: dict[int, int] = literal_eval(response[0])
        if data and not data.get(role.id):
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                color=Color.red(),
                timestamp=utils.utcnow(),
                description=f"{Emojis.REPLY.value} Podana rola nie ma przypisanego mnożniku.",
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)
            embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
            embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

            await interaction.edit_original_message(embed=embed)
            return

        del data[role.id]

        data_to_db: Optional[str] = None if not data else str(data)

        await bot.db.execute_fetchone(
            "UPDATE levels SET multiplier_data = ? WHERE guild_id = ?",
            (data_to_db, interaction.guild.id),
        )

        embed.title = f"Instalacja zakończona {Emojis.GREENBUTTON.value}"
        embed.colour = Color.dark_theme()
        embed.description = f"{Emojis.REPLY.value} Usunięto mnożnik dla roli: {role.mention}."

        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

        await interaction.edit_original_message(embed=embed)

    async def get_multiplier(self, interaction: CustomInteraction) -> None:
        assert interaction.guild

        bot: Smiffy = interaction.bot

        embed = Embed(
            title="`📃` Sprawdzanie mnożnika dla roli.",
            color=Color.yellow(),
            timestamp=utils.utcnow(),
            description=f"{Emojis.REPLY.value} Podaj role z której chcesz pozyskać aktualny mnożnik.\n\n"
            "Na odpowiedź masz **10** minut. Inaczej konfiguracja zostanie przerwana. "
            "Aby przerwać ją teraz, wpisz `stop`. ",
        )
        embed.set_footer(text="Etap 1/1")
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        await interaction.send(embed=embed)

        role: Optional[Role] = await self.get_multiplier_role(embed, interaction)
        if not role:
            return

        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT multiplier_data FROM levels WHERE guild_id = ?",
            (interaction.guild.id,),
        )

        if not response or not response[0]:
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                color=Color.red(),
                timestamp=utils.utcnow(),
                description=f"{Emojis.REPLY.value} Podana rola nie ma przypisanego mnożniku.",
            )
            embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
            embed.set_thumbnail(url=interaction.guild_icon_url)
            embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

            await interaction.edit_original_message(embed=embed)
            return

        data: dict[int, int] = literal_eval(response[0])
        multiplier: Optional[int] = data.get(role.id)

        if not multiplier:
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                color=Color.red(),
                timestamp=utils.utcnow(),
                description=f"{Emojis.REPLY.value} Podana rola nie ma przypisanego mnożniku.",
            )
            embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
            embed.set_thumbnail(url=interaction.guild_icon_url)
            embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

            await interaction.edit_original_message(embed=embed)
            return

        embed.title = "`📕` Informacje o mnożniku."
        embed.colour = Color.dark_theme()
        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.description = (
            f"{Emojis.REPLY.value} Rola: {role.mention} posiada przypisany mnożnik: `{multiplier}`."
            f"\n\n- Domyślny: `5`"
        )
        embed.set_footer(text=f"Smiffy v{bot.__version__}", icon_url=bot.avatar_url)

        await interaction.edit_original_message(embed=embed)


class SelectRolesView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(SelectRolesMenus())


class SelectNotifyView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(SelectNotifyMenus())


class SelectMultiplierView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(SelectMultiplierMenus())


class CommandLevels(CustomCog):
    @slash_command(name="levelowanie", dm_permission=False)
    async def levels(self, interaction: CustomInteraction) -> None:
        pass

    @levels.subcommand(name="włącz", description="Włącza levelowanie na serwerze")  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def levels_on(self, interaction: CustomInteraction) -> None:
        assert interaction.guild

        await interaction.response.defer()

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM levels WHERE guild_id = ?", (interaction.guild.id,)
        )
        if response:
            await interaction.send_error_message(description="Levelowanie już jest włączone.")
            return

        await self.bot.db.execute_fetchone("INSERT INTO levels(guild_id) VALUES(?)", (interaction.guild.id,))

        await interaction.send_success_message(
            title=f"Pomyślnie włączono {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Levewalonie zostało włączone.",
        )

    @levels.subcommand(name="wyłącz", description="Wyłącza levelowanie na serwerze")  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def levels_off(self, interaction: CustomInteraction) -> None:
        assert interaction.guild

        await interaction.response.defer()

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM levels WHERE guild_id = ?", (interaction.guild.id,)
        )
        if not response:
            await interaction.send_error_message(description="Levelowanie już jest wyłączone.")
            return

        await self.bot.db.execute_fetchone("DELETE FROM levels WHERE guild_id = ?", (interaction.guild.id,))

        await interaction.send_success_message(
            title=f"Pomyślnie wyłączono {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Levelowanie zostało wyłączone.",
        )

    @levels.subcommand(name="reset", description="Totalny reset levelowania na serwerze")  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def reset(self, interaction: CustomInteraction):
        assert interaction.guild and interaction.user

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM levels WHERE guild_id = ?", (interaction.guild.id,)
        )

        if not response:
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                color=Color.red(),
                timestamp=utils.utcnow(),
                description=f"{Emojis.REPLY.value} Levelowanie jest wyłączone.",
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)
            embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
            return await interaction.send(embed=embed)

        embed = Embed(
            title="`💢` Potwierdź resetowanie levelowania",
            description=f"{Emojis.REPLY.value} Potwierdzenie tego oznacza całkowity reset "
            f"ustawień oraz leveli użytkowników.",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        buttons = ConfirmReset(interaction.user.id)

        await interaction.send(embed=embed, view=buttons)

    @levels.subcommand(  # pyright: ignore
        name="ustawienia", description="Ustawienia dotyczące levelowania na serwerze"
    )
    @PermissionHandler(manage_guild=True)
    async def levels_settings(
        self,
        interaction: CustomInteraction,
        option: str = SlashOption(
            name="opcja",
            description="Wybierz opcje które chcesz zmienić.",
            choices={
                "Rola za level": "roles",
                "Powiadomienia o levelach": "notify",
                "Mnożnik XP za level": "multiplier",
            },
        ),
        status: str = SlashOption(
            name="status",
            description="Wyłącz lub włącz opcje",
            choices={"Włącz": "on", "Wyłącz": "off"},
        ),
    ) -> None:
        assert interaction.guild

        await interaction.response.defer(ephemeral=True)

        if status == "on":
            embed = Embed(
                title="`〽️` Smiffy Levelowanie",
                color=Color.dark_theme(),
                description=f"{Emojis.REPLY.value} Wybierz opcję poniżej, aby przejść do konfiguracji.",
                timestamp=utils.utcnow(),
            )
            embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
            embed.set_thumbnail(url=interaction.guild_icon_url)
            embed.set_footer(text=f"Smiffy v{self.bot.__version__}", icon_url=self.bot.avatar_url)

            if option == "multiplier":
                view = SelectMultiplierView()
                await interaction.send(embed=embed, view=view)

            if option == "roles":
                view = SelectRolesView()
                await interaction.followup.send(embed=embed, view=view)

            if option == "notify":
                embed.description = (
                    f"{Emojis.REPLY.value} Wybierz w jaki sposób bot ma informować o zdobyciu levela."
                )

                view = SelectNotifyView()
                await interaction.followup.send(embed=embed, view=view)

        else:
            response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
                "SELECT * FROM levels WHERE guild_id = ?", (interaction.guild.id,)
            )

            if not response:
                await interaction.send_error_message(description="Levelowanie jest wyłączone.")
                return

            if option == "multiplier":
                if not response[3]:
                    await interaction.send_error_message(
                        description="Aktualnie nie ma żadnych mnożników, więc nie możesz ich wyłączyć."
                    )
                    return

                await self.bot.db.execute_fetchone(
                    "UPDATE levels SET multiplier_data = ? WHERE guild_id = ?",
                    (None, interaction.guild.id),
                )
                await interaction.send_success_message(
                    title=f"Pomyślnie wyłączono ustawienie {Emojis.GREENBUTTON.value}",
                    description=f"{Emojis.REPLY.value} Ustawienie: `Mnożnik`",
                )
                return

            if option == "roles":
                if not response[1]:
                    await interaction.send_error_message(
                        description="Aktualnie nie ma żadnych ustawień role za level, więc nie możesz ich wyłączyć."
                    )
                    return

                await self.bot.db.execute_fetchone(
                    "UPDATE levels SET roles_data = ? WHERE guild_id = ?",
                    (None, interaction.guild.id),
                )

                await interaction.send_success_message(
                    title=f"Pomyślnie wyłączono ustawienie {Emojis.GREENBUTTON.value}",
                    description=f"{Emojis.REPLY.value} Ustawienie: `Rola za level`",
                )
                return

            if option == "notify":
                if not response[2]:
                    await interaction.send_error_message(
                        description="Aktualnie nie ma żadnych ustawień powiadomień, więc nie możesz ich wyłączyć."
                    )
                    return

                await self.bot.db.execute_fetchone(
                    "UPDATE levels SET alerts_data = ? WHERE guild_id = ?",
                    (None, interaction.guild.id),
                )
                await interaction.send_success_message(
                    title=f"Pomyślnie wyłączono ustawienie {Emojis.GREENBUTTON.value}",
                    description=f"{Emojis.REPLY.value} Ustawienie: `Powiadomienia o levelach`",
                )
                return

    @staticmethod
    async def get_card(user_data: UserlevelingData) -> BytesIO:
        background: Editor = Editor(Canvas((900, 300), color="#23272A"))
        profile_image = await load_image_async(user_data["avatar_url"])
        profile: Editor = Editor(profile_image).resize((150, 150)).circle_image()

        poppins = Font.poppins(size=40)
        montserrat = Font.montserrat(variant="bold", size=40)

        if user_data["rank"] >= 1000:
            montserrat.font.size = 33

        poppins_small = Font.poppins(size=30)

        card_right_shape: list[tuple[int, int]] = [
            (600, 0),
            (750, 300),
            (900, 300),
            (900, 0),
        ]

        background.polygon(card_right_shape, "#2C2F33")
        background.paste(profile, (30, 30))

        background.rectangle((30, 220), width=650, height=40, fill="#494b4f", radius=20)

        if user_data["percentage"] > 0:
            if user_data["percentage"] <= 2:
                user_data["percentage"] = 3

            background.bar(
                (30, 220),
                max_width=650,
                height=40,
                percentage=user_data["percentage"],
                fill="#3db374",
                radius=20,
            )
        rank: int = user_data["rank"]

        if 10 <= rank < 100:
            background.text((680, 40), f"Rank: {rank}", font=montserrat, color="white")
        elif rank >= 100:
            background.text((670, 40), f"Rank: {rank}", font=montserrat, color="white")
        else:
            background.text((700, 40), f"Rank: {rank}", font=montserrat, color="white")

        background.text((200, 40), user_data["name"], font=poppins, color="white")
        background.rectangle((200, 100), width=350, height=2, fill="#17F3F6")

        background.text(
            (200, 130),
            f"Level : {user_data['level']}" + f" XP : {user_data['xp']} / {user_data.get('next_level_xp')}",
            font=poppins_small,
            color="white",
        )

        return background.image_bytes

    async def get_leaderboard(self, guild: Guild, first_ten: bool = False) -> Optional[dict[Member, int]]:
        response: Iterable[DB_RESPONSE] = await self.bot.db.execute_fetchall(
            "SELECT * FROM levels_users WHERE guild_id = ?", (guild.id,)
        )

        if not response:
            return None

        total_xp_lb: dict[Member, int] = {}

        for row in response:
            level: int = row[2]
            xp: int = row[3]
            member_id: int = row[1]

            totalxp: int = (level * level * 50) + xp

            member: Optional[Member] = await self.bot.getch_member(guild, member_id)

            if not member:
                continue

            total_xp_lb[member] = totalxp

        sorted_lb: dict = dict(sorted(total_xp_lb.items(), key=lambda item: item[1], reverse=True))
        if first_ten:
            return dict(islice(sorted_lb.items(), 10))

        return sorted_lb

    async def get_rank(self, member: Member) -> int:
        leaderboard: Optional[dict[Member, int]] = await self.get_leaderboard(member.guild)

        if not leaderboard:
            return 1

        for index, user in enumerate(leaderboard.keys()):
            if user.id == member.id:
                return index + 1

        return 0

    @levels.subcommand(name="rank", description="Pokazuje level użytkownika")
    async def rank(
        self,
        interaction: CustomInteraction,
        member: Optional[Member] = SlashOption(
            name="osoba", description="Podaj osobę której chcesz sprawdzić level"
        ),
    ):
        assert isinstance(interaction.user, Member) and interaction.guild

        user = member or interaction.user

        await interaction.response.defer()

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM levels_users WHERE guild_id = ?", (interaction.guild.id,)
        )

        if not response:
            return await interaction.send_error_message(description="Levelowanie na serwerze jest wyłączone.")

        users_response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM levels_users WHERE guild_id = ? AND user_id = ?",
            (interaction.guild.id, user.id),
        )
        if not users_response:
            return await interaction.send_error_message(
                description=f"Nie mogłem odnaleźć {user.mention} w swojej bazie. "
                f"Być może nie napisał jeszcze żadnej wiadomości."
            )

        xp: int = users_response[3]
        next_level_xp: int = users_response[2] * 50

        quotient: float = xp / next_level_xp
        percentage: int = int(quotient * 100)

        user_data: UserlevelingData = UserlevelingData(
            name=user.name,
            avatar_url=interaction.avatars.get_user_avatar(user),
            level=response[2],
            xp=response[3],
            next_level_xp=response[2] * 50,
            percentage=percentage,
            rank=await self.get_rank(user),
        )

        card: File = File(fp=await self.get_card(user_data), filename="rank.png")
        await interaction.send(file=card)

    @levels.subcommand(name="topka", description="Tabela Top 10 użytkowników w levelach")
    async def leaderboard(self, interaction: CustomInteraction):
        assert interaction.guild

        await interaction.response.defer()

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM levels WHERE guild_id = ?", (interaction.guild.id,)
        )

        if not response:
            return await interaction.send_error_message(description="Levelowanie na serwerze jest wyłączone.")

        leaderboard: Optional[dict[Member, int]] = await self.get_leaderboard(
            interaction.guild, first_ten=True
        )
        if not leaderboard or len(leaderboard) == 0:
            return await interaction.send_error_message(description="Brak danych do tabeli levelowania.")

        embed = Embed(
            title="Levelowanie: Top 10",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_thumbnail(url=interaction.guild_icon_url)

        rank = 1
        for user, totalxp in leaderboard.items():
            embed.add_field(
                name=f"Top: #{rank}",
                value=f"{Emojis.REPLY.value} {user.mention} *({totalxp} XP)*",
                inline=False,
            )
            rank += 1

        await interaction.followup.send(embed=embed)


def setup(bot: Smiffy):
    bot.add_cog(CommandLevels(bot))
