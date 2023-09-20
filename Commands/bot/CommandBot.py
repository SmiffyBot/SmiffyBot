from __future__ import annotations
from typing import TYPE_CHECKING

from nextcord import Embed, Color, slash_command, SlashOption, TextChannel, Member

from utilities import CustomInteraction, CustomCog, bot_utils, PermissionHandler
from errors import InvalidServerData
from enums import Emojis

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import Optional, DB_RESPONSE
    from nextcord.abc import GuildChannel


class CommandBot(CustomCog):
    async def get_channel(self, interaction: CustomInteraction) -> Optional[TextChannel]:
        channel_id: Optional[str] = bot_utils.get_value_from_config("CHANNEL_NOTIFY")

        if not isinstance(channel_id, int):
            await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd.", ephemeral=True)
            raise InvalidServerData

        channel: Optional[GuildChannel] = await self.bot.getch_channel(channel_id)

        if not channel or not isinstance(channel, TextChannel):
            await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd.", ephemeral=True)
            return

        return channel

    @slash_command(name="bot", guild_ids=[983442350963576863], dm_permission=False)
    async def bot_command(self, interaction: CustomInteraction):
        pass

    @bot_command.subcommand(name="propozycja", description="Zgłoś propozycje dotyczącą bota!")
    async def bot_proposition(
        self,
        interaction: CustomInteraction,
        text: str = SlashOption(name="propozycja", description="Wpisz swoją propozycje.", max_length=1024),
    ):
        assert isinstance(interaction.user, Member) and interaction.guild

        await interaction.response.defer()

        channel: Optional[TextChannel] = await self.get_channel(interaction)
        if not channel:
            return

        embed = Embed(
            title="Zgłoszono nową propozycje!",
            color=Color.green(),
            description=f"```{text}```",
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_thumbnail(url=interaction.guild_icon_url)

        embed.add_field(
            name="`🛰️` Serwer",
            value=f"{Emojis.REPLY.value} **{interaction.guild}** (`{interaction.guild.id}`)",
        )

        embed.add_field(
            name="`👤` Osoba",
            value=f"{Emojis.REPLY.value} **{interaction.user}** (`{interaction.user.id}`)",
            inline=False,
        )

        await channel.send(embed=embed)

        await interaction.send_success_message(
            title=f"Pomyślnie przesłano {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Twoja propozycja została przesłana.",
            ephemeral=True,
        )

    @bot_command.subcommand(name="bląd", description="Zgłoś błąd bota")
    async def bot_error(
        self,
        interaction: CustomInteraction,
        text: str = SlashOption(name="błąd", description="Opisz dokładnie błąd", max_length=1024),
    ):
        assert isinstance(interaction.user, Member) and interaction.guild

        await interaction.response.defer()

        channel: Optional[TextChannel] = await self.get_channel(interaction)
        if not channel:
            return

        embed = Embed(
            title="Zgłoszono nowy błąd :(",
            color=Color.red(),
            description=f"```{text}```",
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_thumbnail(url=interaction.guild_icon_url)

        embed.add_field(
            name="`🛰️` Serwer",
            value=f"{Emojis.REPLY.value} **{interaction.guild}** (`{interaction.guild.id}`)",
        )

        embed.add_field(
            name="`👤` Osoba",
            value=f"{Emojis.REPLY.value} **{interaction.user}** (`{interaction.user.id}`)",
            inline=False,
        )

        await channel.send(embed=embed)

        await interaction.send_success_message(
            title=f"Pomyślnie przesłano {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Twoj błąd został zgłoszony.",
            ephemeral=True,
        )

    @bot_command.subcommand(  # pyright: ignore
        name="powiadomienia", description="Ustaw kanał z powiadomieniami dotyczące bota"
    )
    @PermissionHandler(manage_guild=True)
    async def notifications(
        self,
        interaction: CustomInteraction,
        channel: TextChannel = SlashOption(name="kanał", description="Wybierz kanał z powiadomieniami"),
    ):
        assert interaction.guild

        await interaction.response.defer()

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM bot_utils WHERE guild_id = ?", (interaction.guild.id,)
        )

        if not response:
            await self.bot.db.execute_fetchone(
                "INSERT INTO bot_utils(guild_id, alerts_channel_id) VALUES(?,?)",
                (interaction.guild.id, channel.id),
            )
        else:
            await self.bot.db.execute_fetchone(
                "UPDATE bot_utils SET alerts_channel_id = ? WHERE guild_id = ?",
                (channel.id, interaction.guild.id),
            )

        return await interaction.send_success_message(
            title=f"Pomyślnie ustawiono powiadomienia {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Na podanym kanale będą pojawiać się powiadomienia "
            f"o najważniejszych zmianach bota",
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandBot(bot))
