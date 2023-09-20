from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from nextcord import (
    Embed,
    Color,
    utils,
    slash_command,
    SlashOption,
    AutoModerationEventType,
    AutoModerationAction,
    AutoModerationActionType,
    AutoModerationTriggerType,
    AutoModerationTriggerMetadata,
    AutoModerationRule,
)

from utilities import CustomInteraction, CustomCog, PermissionHandler
from enums import Emojis

if TYPE_CHECKING:
    from bot import Smiffy


class CommandBlockWord(CustomCog):
    @slash_command(name="zablokujsłowo", dm_permission=False)
    async def blockword(self, interaction: CustomInteraction):  # pylint: disable=unused-argument
        ...

    @blockword.subcommand(name="dodaj", description="Dodaj słowo do zablokowania")  # pyright: ignore
    @PermissionHandler(manage_messages=True)
    async def blockword_add(
        self,
        interaction: CustomInteraction,
        word: str = SlashOption(
            name="słowo",
            description="Podaj słowo, które chcesz zablokować",
            max_length=128,
        ),
    ):
        assert self.bot.user and interaction.guild

        await interaction.response.defer()

        actions: list[AutoModerationAction] = [
            AutoModerationAction(type=AutoModerationActionType.block_message)
        ]
        block_words_rule: Optional[AutoModerationRule] = None

        for rule in await interaction.guild.auto_moderation_rules():
            if rule.creator_id == self.bot.user.id and rule.trigger_type == AutoModerationTriggerType.keyword:
                block_words_rule = rule

        if not block_words_rule:
            await interaction.guild.create_auto_moderation_rule(
                name="SmiffyBot - Blokowanie Słów",
                event_type=AutoModerationEventType.message_send,
                actions=actions,
                trigger_type=AutoModerationTriggerType.keyword,
                trigger_metadata=AutoModerationTriggerMetadata(keyword_filter=[word]),
                enabled=True,
            )
        else:
            blocked_words: Optional[list[str]] = block_words_rule.trigger_metadata.keyword_filter

            if not blocked_words:
                blocked_words = []

            elif word in blocked_words:
                return await interaction.send_error_message(description="Podane słowo już jest zablokowane.")
            blocked_words.append(word)
            await block_words_rule.edit(
                trigger_metadata=AutoModerationTriggerMetadata(keyword_filter=blocked_words)
            )

        await interaction.send_success_message(
            title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Dodano słowo do zablokowanych słów.",
            color=Color.green(),
        )

    @blockword.subcommand(name="usuń", description="Usuwa słowo z zablokowanych słów")  # pyright: ignore
    @PermissionHandler(manage_messages=True)
    async def blockword_remove(
        self,
        interaction: CustomInteraction,
        word: str = SlashOption(name="słowo", description="Podaj słowo, które chcesz usunąć", max_length=128),
    ):
        assert self.bot.user and interaction.guild

        await interaction.response.defer()

        block_words_rule: Optional[AutoModerationRule] = None

        for rule in await interaction.guild.auto_moderation_rules():
            if rule.creator_id == self.bot.user.id and rule.trigger_type == AutoModerationTriggerType.keyword:
                block_words_rule = rule

        if not block_words_rule:
            return await interaction.send_error_message(description="Podane słowo nie jest zablokowane.")

        blocked_words: Optional[list[str]] = block_words_rule.trigger_metadata.keyword_filter

        if not blocked_words:
            return await interaction.send_error_message(description="Podane słowo nie jest zablokowane.")

        if word not in blocked_words:
            return await interaction.send_error_message(description="Podane słowo nie jest zablokowane.")
        blocked_words.remove(word)
        await block_words_rule.edit(
            trigger_metadata=AutoModerationTriggerMetadata(keyword_filter=blocked_words)
        )

        await interaction.send_success_message(
            title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Usunięto podane słowo z zablokowanych słów.",
            color=Color.green(),
        )

    @blockword.subcommand(name="lista", description="Wyświetla listę zablokowanych słów")  # pyright: ignore
    @PermissionHandler(manage_messages=True)
    async def blockword_list(self, interaction: CustomInteraction):
        assert self.bot.user and interaction.guild

        await interaction.response.defer()

        block_words_rule: Optional[AutoModerationRule] = None

        for rule in await interaction.guild.auto_moderation_rules():
            if rule.creator_id == self.bot.user.id and rule.trigger_type == AutoModerationTriggerType.keyword:
                block_words_rule = rule

        if not block_words_rule:
            return await interaction.send_error_message(
                description="Na serwerze nie ma żadnych zablokowanych słów."
            )

        blocked_words: Optional[list[str]] = block_words_rule.trigger_metadata.keyword_filter

        if not blocked_words:
            return await interaction.send_error_message(
                description="Aktualnie nie ma żadnych zablokowanych słów."
            )

        automod_link: str = "https://support.discord.com/hc/pl/articles/4421269296535-AutoMod-FAQ"

        blocked_words_text: str = ""
        for word in blocked_words:
            blocked_words_text += f"`{word}`, "
            if len(blocked_words_text) >= 3800:
                break

        embed = Embed(
            title="`📃` Lista zablokowanych słów",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
            description=f"{Emojis.REPLY.value} System blokowania słów Smiffiego bazuje na "
            f"[Discord AutoMod]({automod_link})\n\n{blocked_words_text[0:-2]}",
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_thumbnail(url=interaction.guild_icon_url)

        await interaction.send(embed=embed)


def setup(bot: Smiffy):
    bot.add_cog(CommandBlockWord(bot))
