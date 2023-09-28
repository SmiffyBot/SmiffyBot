from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from nextcord import ForumChannel, errors
from utilities import CustomCog, bot_utils
from enums import Emojis

if TYPE_CHECKING:
    from nextcord import Thread, TextChannel, ForumTag

    from bot import Smiffy


class ThreadCreate(CustomCog):

    @staticmethod
    def get_bugs_forum_channel() -> Optional[int]:
        return bot_utils.get_value_from_config(
            "BUGS_FORUM_CHANNEL_ID",
        )

    @staticmethod
    def get_bug_tag() -> Optional[int]:
        return bot_utils.get_value_from_config(
            "BUGS_FORUM_TAG_ID"
        )

    @staticmethod
    def get_help_forum_channel() -> Optional[int]:
        return bot_utils.get_value_from_config(
            "HELP_FORUM_CHANNEL_ID",
        )

    @staticmethod
    def get_help_tag() -> Optional[int]:
        return bot_utils.get_value_from_config(
            "HELP_FORUM_TAG_ID"
        )

    @CustomCog.listener()
    async def on_thread_create(self, thread: Thread):
        parent_channel: ForumChannel | TextChannel = thread.parent

        if not isinstance(parent_channel, ForumChannel):
            return

        help_channel: Optional[int] = self.get_help_forum_channel()
        help_tag_id: Optional[int] = self.get_help_tag()

        bugs_channel: Optional[int] = self.get_bugs_forum_channel()
        bugs_tag_id: Optional[int] = self.get_bug_tag()

        if parent_channel.id == help_channel:
            help_tag: Optional[ForumTag] = parent_channel.get_tag(help_tag_id)
            tags: list[ForumTag] | None = thread.applied_tags
            if help_tag is not None and tags is not None:

                tags.append(help_tag)
                await thread.edit(applied_tags=tags)

                try:
                    await thread.send(f"- Pomyślnie nadano tag: `{help_tag.name}` {Emojis.GREENBUTTON.value}")
                except (errors.Forbidden, errors.HTTPException):
                    pass

        elif parent_channel.id == bugs_channel:
            bug_tag: Optional[ForumTag] = parent_channel.get_tag(bugs_tag_id)
            tags: list[ForumTag] | None = thread.applied_tags

            if bug_tag is not None and tags is not None:

                tags.append(bug_tag)
                await thread.edit(applied_tags=tags)

                try:
                    await thread.send(f"- Pomyślnie nadano tag: `{bug_tag.name}` {Emojis.GREENBUTTON.value}")
                except (errors.Forbidden, errors.HTTPException):
                    pass


def setup(bot: Smiffy):
    bot.add_cog(ThreadCreate(bot))
