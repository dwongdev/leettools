from typing import Optional

import click

from leettools.chat.history_manager import get_history_manager
from leettools.cli.options_common import common_options
from leettools.core.schemas.user import User


@click.command(help="Get answers for a query in the format of a MD file.")
@click.option(
    "-c",
    "--chat_id",
    "chat_id",
    required=True,
    help="The chat id to get the answers for.",
)
@click.option(
    "-q",
    "--query_id",
    "query_id",
    required=True,
    help="The query id to get the answers for.",
)
@click.option(
    "-u",
    "--user",
    "username",
    required=False,
    default=None,
    help="The user to use, default the admin user.",
)
@common_options
def get(
    chat_id: str,
    query_id: str,
    username: Optional[str] = None,
    **kwargs,
):
    """
    Command line interface to get answers for a query in the format of a MD file.
    """

    from leettools.context_manager import Context, ContextManager

    context = ContextManager().get_context()
    chat_manager = get_history_manager(context)

    userstore = context.get_user_store()
    if username is None:
        user = User.get_admin_user()
        username = user.username
    else:
        user = userstore.get_user_by_name(username)
        if user is None:
            click.echo(f"User {username} does not exist.", err=True)
            return

    chat_manager = get_history_manager(context)

    chat_query = chat_manager.get_ch_entry(username=user.username, chat_id=chat_id)
    if chat_query is None:
        click.echo(f"Chat id {chat_id} does not exist.", err=True)
        return

    answers = chat_query.answers
    for answer in answers:
        if answer.query_id == query_id:
            if answer.position_in_answer == "all":
                click.echo(f"{answer.answer_content}\n")
                click.echo(f"# References:\n")
                for _, source_item in answer.answer_source_items.items():
                    click.echo(f"{source_item.answer_source.source_content}\n")
            break
