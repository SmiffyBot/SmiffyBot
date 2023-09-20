from __future__ import annotations
from typing import TYPE_CHECKING

from nextcord import SlashOption, Color

from utilities import CustomInteraction, CustomCog, PermissionHandler
from typings import EconomyItemData
from enums import Emojis

from .__main__ import EconomyCog, EconomyManager

if TYPE_CHECKING:
    from bot import Smiffy


class CommandCreateItem(CustomCog):
    @EconomyCog.main.subcommand(  # pylint: disable=no-member   # pyright: ignore
        name="stwórz_przedmiot", description="Tworzy nowy przedmiot do sklepu"
    )
    @PermissionHandler(manage_guild=True)
    async def economy_createitem(
        self,
        interaction: CustomInteraction,
        item_name: str = SlashOption(
            name="nazwa_predmiotu", description="Podaj nazwę przedmiotu", max_length=32
        ),
        item_description: str = SlashOption(name="opis", description="Podaj opis przedmiotu", max_length=64),
        item_price: int = SlashOption(name="cena", description="Podaj cenę przedmiotu"),
    ):
        assert interaction.guild

        await interaction.response.defer()
        manager: EconomyManager = EconomyManager(bot=self.bot)

        if not await manager.get_guild_economy_status(interaction.guild):
            return await interaction.send_error_message(description="Ekonomia na serwerze jest wyłączona.")

        if await manager.get_guild_item(guild=interaction.guild, item_name=item_name):
            return await interaction.send_error_message(description="Podany przedmiot już istnieje.")

        if len(await manager.get_guild_shop(guild=interaction.guild)) >= 25:
            return await interaction.send_error_message(
                description="Osiągnięto limit `25` przedmiotów w sklepie."
            )
        if item_price <= 0:
            return await interaction.send_error_message(description="Minimalna cena przedmiotu to `1$`")

        item_id: str = await manager.generate_item_id(guild=interaction.guild)

        item_data: EconomyItemData = EconomyItemData(
            guild_id=interaction.guild.id,
            name=item_name,
            description=item_description,
            price=item_price,
            reply_message=None,
            required_role=None,
            given_role=None,
            item_id=item_id,
        )

        await manager.create_guild_item(item_data=item_data)

        command_mention: str = interaction.get_command_mention(
            command_name="ekonomia", sub_command="edytuj_przedmiot"
        )

        await interaction.send_success_message(
            title=f"Pomyślnie stworzono przedmiot {Emojis.GREENBUTTON.value}",
            color=Color.green(),
            description=f"{Emojis.REPLY.value} Aby ustawić więcej opcji przedmiotu, wpisz {command_mention}",
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandCreateItem(bot))
