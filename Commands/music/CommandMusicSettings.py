from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import ButtonStyle, Color, Embed, Member, SlashOption, ui, utils

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

from .__main__ import MusicCog

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import DB_RESPONSE, Optional


class NotifyStatusView(ui.View):
    def __init__(self, author_id: int, org_inter: CustomInteraction):
        super().__init__(timeout=None)

        self.author_id: int = author_id
        self.org_inter: CustomInteraction = org_inter

    async def interaction_check(self, interaction: CustomInteraction) -> bool:
        assert interaction.user

        if interaction.user.id != self.author_id:
            await interaction.send_error_message(
                description="Tylko autor tej wiadomości może tego użyć.", ephemeral=True
            )

            return False
        return True

    @ui.button(  # pyright: ignore[reportGeneralTypeIssues]
        label="Włącz", style=ButtonStyle.green, row=2, emoji=Emojis.GREENBUTTON.value
    )
    async def button_on(
        self, button: ui.Button, interaction: CustomInteraction
    ):  # pylint: disable=unused-argument
        assert interaction.guild

        await interaction.response.defer()

        bot: Smiffy = interaction.bot
        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT * FROM music_settings WHERE guild_id = ?", (interaction.guild.id,)
        )

        if not response:
            await bot.db.execute_fetchone(
                "INSERT INTO music_settings(guild_id, permission_roles, notify) VALUES(?,?,?)",
                (interaction.guild.id, None, None),
            )
        else:
            await bot.db.execute_fetchone(
                "UPDATE music_settings SET notify = ? WHERE guild_id = ?",
                (None, interaction.guild.id),
            )

        await interaction.send_success_message(
            title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Pomyślnie włączono powiadomienia.",
        )

        await self.org_inter.delete_original_message()

    @ui.button(  # pyright: ignore[reportGeneralTypeIssues]
        label="Wyłącz", style=ButtonStyle.red, row=2, emoji=Emojis.REDBUTTON.value
    )
    async def button_off(
        self, button: ui.Button, interaction: CustomInteraction
    ):  # pylint: disable=unused-argument
        assert interaction.guild

        await interaction.response.defer()

        bot: Smiffy = interaction.bot
        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT * FROM music_settings WHERE guild_id = ?", (interaction.guild.id,)
        )

        if not response:
            await bot.db.execute_fetchone(
                "INSERT INTO music_settings(guild_id, permission_roles, notify) VALUES(?,?,?)",
                (interaction.guild.id, None, "off"),
            )
        else:
            await bot.db.execute_fetchone(
                "UPDATE music_settings SET notify = ? WHERE guild_id = ?",
                ("off", interaction.guild.id),
            )

        await interaction.send_success_message(
            title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Pomyślnie wyłączono powiadomienia.",
        )
        await self.org_inter.delete_original_message()


class SelectView(ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=None)

        self.author_id: int = author_id

        self.roles_select: ui.RoleSelect = ui.RoleSelect(
            placeholder="Wybierz role z uprawnieniami", max_values=5, min_values=0
        )

        self.add_item(self.roles_select)

    async def interaction_check(self, interaction: CustomInteraction) -> bool:
        assert interaction.user

        if interaction.user.id != self.author_id:
            await interaction.send_error_message(
                description="Tylko autor tej wiadomości może tego użyć.", ephemeral=True
            )

            return False
        return True

    @ui.button(  # pyright: ignore[reportGeneralTypeIssues]
        label="Ustaw", style=ButtonStyle.green, row=2, emoji=Emojis.GREENBUTTON.value
    )
    async def button_callback(
        self, button: ui.Button, interaction: CustomInteraction
    ):  # pylint: disable=unused-argument
        assert interaction.guild

        await interaction.response.defer()

        bot: Smiffy = interaction.bot
        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT * FROM music_settings WHERE guild_id = ?", (interaction.guild.id,)
        )
        if len(self.roles_select.values) != 0:
            for role in self.roles_select.values:
                if role.is_bot_managed():
                    return await interaction.send_error_message(
                        description=f"Rola: {role.mention} nie może zostać użyta.",
                    )

            data: Optional[str] = str([role.id for role in self.roles_select.values])
        else:
            data: Optional[str] = None

        if not response:
            await bot.db.execute_fetchone(
                "INSERT INTO music_settings(guild_id, permission_roles, notify) VALUES(?,?,?)",
                (interaction.guild.id, data, None),
            )
        else:
            await bot.db.execute_fetchone(
                "UPDATE music_settings SET permission_roles = ? WHERE guild_id = ?",
                (data, interaction.guild.id),
            )

        if interaction.message:
            await interaction.message.delete()

        await interaction.send_success_message(
            title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Pomyślnie zaktualizowano uprawnienia.",
        )


class CommandMusicSettings(CustomCog):
    @MusicCog.main.subcommand(  # pylint: disable=no-member  # pyright: ignore
        name="ustawienia", description="Zmień ustawienia muzyki na serwerze"
    )
    @PermissionHandler(manage_guild=True)
    async def music_settings(
        self,
        interaction: CustomInteraction,
        option: str = SlashOption(
            name="opcja",
            description="Wybierz opcję do ustawienia",
            choices={"Uprawnienia komend": "permissions", "Powiadomienia": "alerts"},
        ),
    ):
        assert isinstance(interaction.user, Member)

        if option == "permissions":
            embed = Embed(
                title="`⚙️` Ustawienia muzyka",
                colour=Color.dark_theme(),
                timestamp=utils.utcnow(),
                description=f"{Emojis.REPLY.value} Wybierz rolę, które mają mieć uprawnienia do "
                f"używania muzycznych komend. **Jeśli chcesz, "
                f"aby każdy mógł używać komend, zostaw listę pustą.**",
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)
            embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
            embed.set_footer(text=f"Smiffy v{self.bot.__version__}", icon_url=self.bot.avatar_url)
            roleselect = SelectView(interaction.user.id)

            await interaction.send(embed=embed, view=roleselect)

        else:
            embed = Embed(
                title="`⚙️` Ustawienia powiadomienia",
                colour=Color.dark_theme(),
                timestamp=utils.utcnow(),
                description=f"{Emojis.REPLY.value} Włącz lub wyłącz powiadomienia bota dotyczące muzyki. "
                f"Przykład poniżej.",
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)
            embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
            embed.set_footer(text=f"Smiffy v{self.bot.__version__}", icon_url=self.bot.avatar_url)
            embed.set_image(
                url="https://cdn.discordapp.com/attachments/1015919889720037396/1143255193492922428/Bez_tytuu.png"
            )

            buttons = NotifyStatusView(interaction.user.id, interaction)

            await interaction.send(embed=embed, view=buttons)


def setup(bot: Smiffy):
    bot.add_cog(CommandMusicSettings(bot))
