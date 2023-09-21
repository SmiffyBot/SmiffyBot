from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from nextcord import Color, SlashOption

from enums import Emojis
from typings import EconomyItemData
from utilities import CustomCog, CustomInteraction, PermissionHandler

from .__main__ import EconomyCog, EconomyManager

if TYPE_CHECKING:
    from bot import Smiffy


class CommandDeleteItem(CustomCog):
    @EconomyCog.main.subcommand(  # pylint: disable=no-member   # pyright: ignore
        name="usuń_przedmiot",
        description="Usuwa wybrany przedmiot",
    )
    @PermissionHandler(manage_guild=True)
    async def economy_deleteitem(
        self,
        interaction: CustomInteraction,
        item_name: str = SlashOption(
            name="nazwa_predmiotu",
            description="Podaj nazwę przedmiotu",
            max_length=32,
        ),
    ):
        assert interaction.guild

        await interaction.response.defer()
        manager: EconomyManager = EconomyManager(bot=self.bot)

        if not await manager.get_guild_economy_status(interaction.guild):
            return await interaction.send_error_message(description="Ekonomia na serwerze jest wyłączona.")

        if not await manager.get_guild_item(
            guild=interaction.guild,
            item_name=item_name,
        ):
            return await interaction.send_error_message(description="Podany przedmiot nie istnieje.")

        await manager.delete_guild_item(
            guild=interaction.guild,
            item_name=item_name,
        )
        await interaction.send_success_message(
            title=f"Pomyślnie usunięto {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Pomyślnie usunięto przedmiot o nazwie: `{item_name}`",
            color=Color.dark_theme(),
        )

    @economy_deleteitem.on_autocomplete("item_name")
    async def deleteitem_autocomplete(
        self,
        interaction: CustomInteraction,
        query: Optional[str],
    ) -> Optional[list[str]]:
        assert interaction.guild

        manager: EconomyManager = EconomyManager(bot=self.bot)

        items: list[EconomyItemData] = await manager.get_guild_shop(guild=interaction.guild)
        if not items:
            return None

        items_name: list[str] = [data["name"] for data in items]
        if not query:
            return items_name

        get_near_item: list[str] = [item for item in items_name if item.lower().startswith(query.lower())]
        return get_near_item


def setup(bot: Smiffy):
    bot.add_cog(CommandDeleteItem(bot))
