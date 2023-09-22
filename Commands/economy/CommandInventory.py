from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from nextcord import Color, Embed, Member, SelectOption, ui, utils

from enums import Emojis
from typings import EconomyItemData, EconomyUserData
from utilities import CustomCog, CustomInteraction

from .__main__ import EconomyCog, EconomyManager

if TYPE_CHECKING:
    from bot import Smiffy


class ItemsList(ui.Select):
    def __init__(self, items_data: dict[str, int]):
        self.items_data: dict[str, int] = items_data

        amount_of_items: int = len(items_data)
        if amount_of_items != 5:
            pages: int = round((amount_of_items / 5) + 0.5)
        else:
            pages: int = 1
        pages_list: list[SelectOption] = []

        for page in range(1, pages + 1):
            pages_list.append(
                SelectOption(
                    label=f"Strona: {page}",
                    description=f"Wyświetla ekwipunek na stronie {page}",
                    value=str(page),
                    emoji="📖",
                )
            )

        super().__init__(
            placeholder="Wybierz następną stronę przedmiotów",
            options=pages_list,
        )

    async def callback(self, interaction: CustomInteraction) -> None:
        if not interaction.message:
            await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd.")
            return

        selected_page: int = int(self.values[0]) - 1
        min_range: int = selected_page * 5
        max_range: int = (selected_page * 5) + 5

        embed: Embed = interaction.message.embeds[0]
        embed.clear_fields()

        for index, item_name in enumerate(self.items_data):
            if index >= min_range:
                embed.add_field(
                    name=f"`🧷` {item_name}",
                    value=f"{Emojis.REPLY.value} **Ilość:** `{self.items_data[item_name]}`",
                    inline=False,
                )

            if index + 1 == max_range:
                break

        await interaction.message.edit(embed=embed)


class ItemsListView(ui.View):
    def __init__(self, items_data: dict[str, int]):
        super().__init__(timeout=None)

        self.add_item(ItemsList(items_data))


class CommandInventory(CustomCog):
    @EconomyCog.main.subcommand(  # pylint: disable=no-member
        name="ekwipunek",
        description="Wyświetla Twój ekwipunek.",
    )
    async def economy_inventory(self, interaction: CustomInteraction):
        await interaction.response.defer()

        assert isinstance(interaction.user, Member) and interaction.guild

        manager: EconomyManager = EconomyManager(bot=self.bot)

        if not await manager.get_guild_economy_status(interaction.guild):
            return await interaction.send_error_message(description="Ekonomia na serwerze jest wyłączona.")

        user_data: EconomyUserData = await manager.get_user_data(interaction.user)
        user_items: list[str] = user_data["items"]
        if len(user_items) == 0:
            return await interaction.send_error_message(
                description="Nie posiadasz aktualnie żadnych przedmiotów."
            )

        items: dict[str, int] = {}
        for item_id in user_items:
            item: Optional[EconomyItemData] = await manager.get_guild_item(interaction.guild, item_id=item_id)
            if item:
                amount: int = items.get(item["name"], 0)
                amount += 1
                items[item["name"]] = amount

        embed = Embed(
            title=f"`📂` Ekwipunek {interaction.user}",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)

        index = 0
        for item_name, amount in items.items():
            if index == 5:
                break

            embed.add_field(
                name=f"`🔖` {item_name}",
                value=f"{Emojis.REPLY.value} **Ilość:** `{amount}`",
                inline=False,
            )
            index += 1

        selectpage = ItemsListView(items)
        await interaction.send(embed=embed, view=selectpage)


def setup(bot: Smiffy):
    bot.add_cog(CommandInventory(bot))
