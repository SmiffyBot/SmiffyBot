from __future__ import annotations
from typing import TYPE_CHECKING

from nextcord import (
    Embed,
    Color,
    utils,
    slash_command,
    SlashOption,
    TextChannel,
    Thread,
)

from utilities import (
    CustomInteraction,
    CustomCog,
    PermissionHandler,
)
from enums import Emojis

if TYPE_CHECKING:
    from bot import Smiffy
    from nextcord import Message


class CommandPoll(CustomCog):
    def __init__(self, bot: Smiffy) -> None:
        super().__init__(bot=bot)

        self._emojis: list = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]

    @slash_command(
        name="ankieta", description="Bot tworzy nową ankiete!", dm_permission=False
    )  # pyright: ignore
    @PermissionHandler(manage_messages=True, user_role_has_permission="poll")
    async def poll(
        self,
        interaction: CustomInteraction,
        topic: str = SlashOption(name="temat", description="Podaj temat ankiety", max_length=96),
        option_1: str = SlashOption(name="opcja_1", description="Podaj opcję nr. 1", max_length=256),
        option_2: str = SlashOption(name="opcja_2", description="Podaj opcję nr. 2", max_length=256),
        option_3: str = SlashOption(
            name="opcja_3",
            description="Podaj opcję nr. 3",
            max_length=256,
            required=False,
        ),
        option_4: str = SlashOption(
            name="opcja_4",
            description="Podaj opcję nr. 4",
            max_length=256,
            required=False,
        ),
        option_5: str = SlashOption(
            name="opcja_5",
            description="Podaj opcję nr. 5",
            max_length=256,
            required=False,
        ),
        option_6: str = SlashOption(
            name="opcja_6",
            description="Podaj opcję nr. 6",
            max_length=256,
            required=False,
        ),
        option_7: str = SlashOption(
            name="opcja_7",
            description="Podaj opcję nr. 7",
            max_length=256,
            required=False,
        ),
        option_8: str = SlashOption(
            name="opcja_8",
            description="Podaj opcję nr. 8",
            max_length=256,
            required=False,
        ),
    ):
        await interaction.response.defer(ephemeral=True)

        reply_emoji: str = Emojis.REPLY.value

        _emojis: list[str] = [
            "<:number_1:1135650530379710494>",
            "<:number_2:1135650529003974759>",
        ]
        size: str = "##"
        if len(topic) >= 64:
            size: str = "###"

        _description: str = f"{size} {topic}\n"
        _description += (
            f"**1. {option_1}**{reply_emoji} {_emojis[0]}\n" f"**2. {option_2}**{reply_emoji} {_emojis[1]}\n"
        )

        # i need to rewrite this. But currently I have no idea.

        if option_3:
            _description += f"**3. {option_3}**{reply_emoji} <:number_3:1135650526390915154>\n"
            _emojis.append("<:number_3:1135650526390915154>")

        if option_4:
            _description += f"**4. {option_4}**{reply_emoji} <:number_4:1135650512990122024>\n"
            _emojis.append("<:number_4:1135650512990122024>")

        if option_5:
            _description += f"**5. {option_5}**{reply_emoji} <:number_5:1135650515380875336>\n"
            _emojis.append("<:number_5:1135650515380875336>")

        if option_6:
            _description += f"**6. {option_6}**{reply_emoji} `<:number_6:1135650521580052491>`\n"
            _emojis.append("<:number_6:1135650521580052491>")

        if option_7:
            _description += f"**7. {option_7}**{reply_emoji} <:number_7:1135650524436365504>\n"
            _emojis.append("<:number_7:1135650524436365504>")

        if option_8:
            _description += f"**8. {option_8}**{reply_emoji} <:number_8:1135650519961055262>\n"
            _emojis.append("<:number_8:1135650519961055262>")

        embed = Embed(
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
            description=_description,
        )
        embed.set_footer(text=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_author(name="✨ Smiffy Ankieta")
        embed.set_thumbnail(url=interaction.guild_icon_url)

        if isinstance(interaction.channel, (TextChannel, Thread)):
            await interaction.send_success_message(
                title=f"Pomyślnie utworzono ankiete {Emojis.GREENBUTTON.value}",
                ephemeral=True,
            )

            message: Message = await interaction.channel.send(embed=embed)
            for emoji in _emojis:
                await message.add_reaction(emoji)


def setup(bot: Smiffy):
    bot.add_cog(CommandPoll(bot))
