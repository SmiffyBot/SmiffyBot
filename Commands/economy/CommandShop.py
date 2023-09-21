from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import Color, Embed, Member, SelectOption, ui, utils

from enums import Emojis
from typings import EconomyItemData
from utilities import CustomCog, CustomInteraction

from .__main__ import EconomyCog, EconomyManager

if TYPE_CHECKING:
    from bot import Smiffy


class ItemsList(ui.Select):
    def __init__(self, items_data: list[EconomyItemData]):
        self.items_data: list[EconomyItemData] = items_data

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
                    description=f"Wyświetla sklep na stronie {page}",
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

        for index, item_data in enumerate(self.items_data):
            if index >= min_range:
                item_name: str = item_data["name"]
                item_description: str = item_data["description"]
                item_price: int = item_data["price"]

                embed.add_field(
                    name=f"`🔖` {item_name}",
                    value=f"- `💸` {item_price}$\n- `📄` {item_description}",
                    inline=False,
                )

            if index + 1 == max_range:
                break

        await interaction.message.edit(embed=embed)


class ItemsListView(ui.View):
    def __init__(
        self,
        author_id: int,
        items_data: list[EconomyItemData],
    ):
        super().__init__(timeout=None)

        self.add_item(ItemsList(items_data))
        self.author_id: int = author_id

    async def interaction_check(self, interaction: CustomInteraction):
        assert isinstance(interaction.user, Member)

        if interaction.user.id == self.author_id:
            return True  # Checking if the user who pressed the button has permission manage_messages

        command_mention: str = interaction.get_command_mention(
            command_name="ekonomia",
            sub_command="sklep",
        )
        await interaction.send_error_message(
            description=f"Użyj komendy {command_mention}, aby móc korzystać z stron.",
            ephemeral=True,
        )
        return False


class CommandShop(CustomCog):
    @EconomyCog.main.subcommand(  # pylint: disable=no-member
        name="sklep",
        description="Wyświetla sklep na serwerze",
    )
    async def economy_shop(self, interaction: CustomInteraction):
        assert isinstance(interaction.user, Member) and interaction.guild

        await interaction.response.defer()
        manager: EconomyManager = EconomyManager(bot=self.bot)

        if not await manager.get_guild_economy_status(interaction.guild):
            return await interaction.send_error_message(description="Ekonomia na serwerze jest wyłączona.")

        embed = Embed(
            title=f"`🛒` Sklep serwera {interaction.guild}",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.set_footer(
            text=f"Smiffy v{self.bot.__version__}",
            icon_url=self.bot.avatar_url,
        )

        items: list[EconomyItemData] = await manager.get_guild_shop(interaction.guild)
        if len(items) == 0:
            embed.description = f"{Emojis.REPLY.value} W sklepie aktualnie nie ma żadnych przedmiotów."
            return await interaction.send(embed=embed)

        for index, item_data in enumerate(items):
            item_name: str = item_data["name"]
            item_description: str = item_data["description"]
            item_price: int = item_data["price"]

            embed.add_field(
                name=f"`🔖` {item_name}",
                value=f"- `💸` {item_price}$\n- `📄` {item_description}",
                inline=False,
            )
            if index == 4:
                break

        command_mention: str = interaction.get_command_mention(
            command_name="ekonomia",
            sub_command="kup",
        )
        embed.description = f"> Zakup przedmiot używając {command_mention}"

        pages: ItemsListView = ItemsListView(
            author_id=interaction.user.id,
            items_data=items,
        )
        await interaction.send(embed=embed, view=pages)


def setup(bot: Smiffy):
    bot.add_cog(CommandShop(bot))
