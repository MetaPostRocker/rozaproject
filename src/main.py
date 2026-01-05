import logging

from telegram import BotCommand
from telegram.ext import Application

from src.bot.handlers import (
    register_common_handlers,
    register_owner_handlers,
    register_tenant_handlers,
    register_payment_handlers,
)
from src.config import settings
from src.services.scheduler import setup_scheduler
from src.services.sheets import sheets_service

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# Commands for regular users (tenants)
TENANT_COMMANDS = [
    BotCommand("start", "Главное меню"),
    BotCommand("help", "Помощь"),
]

# Commands for owner (admin)
OWNER_COMMANDS = [
    BotCommand("start", "Главное меню"),
    BotCommand("help", "Помощь"),
]


async def setup_bot_commands(app: Application) -> None:
    """Set up bot menu commands for different user types."""
    bot = app.bot

    # Set default commands for all users
    await bot.set_my_commands(TENANT_COMMANDS)

    # Set commands for owner
    owner = await sheets_service.get_owner()
    if owner:
        owner_id = owner.get("telegram_id")
        if owner_id:
            from telegram import BotCommandScopeChat
            await bot.set_my_commands(
                OWNER_COMMANDS,
                scope=BotCommandScopeChat(chat_id=owner_id)
            )

    logger.info("Bot commands configured")


async def post_init(app: Application) -> None:
    """Post-initialization hook."""
    await setup_bot_commands(app)


def main() -> None:
    """Start the bot."""
    logger.info("Starting rental bot...")

    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .build()
    )

    # Register handlers
    register_common_handlers(app)
    register_tenant_handlers(app)
    register_payment_handlers(app)
    register_owner_handlers(app)

    # Set up scheduled reminders
    setup_scheduler(app)

    logger.info("Bot is ready, starting polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
