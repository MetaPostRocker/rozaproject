from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from src.bot.keyboards import (
    get_tenant_main_menu,
    get_owner_main_menu,
    get_meters_keyboard,
    get_back_keyboard,
    get_tenant_reply_keyboard,
    get_owner_reply_keyboard,
)
from src.services.sheets import sheets_service


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command - show welcome message and main menu."""
    await show_main_menu(update, context)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False) -> None:
    """Show main menu based on user role."""
    user = update.effective_user
    telegram_id = user.id

    tenant = await sheets_service.get_tenant(telegram_id)

    if tenant:
        is_owner = sheets_service._is_true(tenant.get("is_owner"))

        if is_owner:
            text = (
                f"👋 Здравствуйте, {tenant['Имя']}!\n\n"
                "🏠 Вы вошли как владелец.\n\n"
                "Выберите нужный раздел в меню ниже:"
            )
            keyboard = get_owner_main_menu()
            reply_keyboard = get_owner_reply_keyboard()
        else:
            # Check what features are available for this tenant
            meters = await sheets_service.get_meters_for_readings(telegram_id)
            invoices = await sheets_service.get_unpaid_invoices_for_tenant(telegram_id)

            text = f"👋 Здравствуйте, {tenant['Имя']}!"
            if invoices:
                total = sum(inv.get("Сумма", 0) or 0 for inv in invoices)
                text += f"\n\n💳 У Вас есть неоплаченные счета на сумму: {total:.0f} руб."
            else:
                text += "\n\n✨ У Вас нет задолженностей."

            text += "\n\nВыберите нужный раздел:"

            keyboard = get_tenant_main_menu(
                has_readings=len(meters) > 0,
                has_invoices=len(invoices) > 0
            )
            reply_keyboard = get_tenant_reply_keyboard()
    else:
        text = (
            f"👋 Здравствуйте!\n\n"
            f"🆔 Ваш Telegram ID:\n<code>{telegram_id}</code>\n\n"
            "📝 Вы ещё не зарегистрированы в системе.\n\n"
            "Пожалуйста, сообщите этот ID Вашему арендодателю, "
            "чтобы он добавил Вас в систему."
        )
        keyboard = None
        reply_keyboard = None

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        message = update.message or update.callback_query.message
        await message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")
        # Send reply keyboard separately if needed
        if reply_keyboard and update.message:
            await update.message.reply_text(
                "⬇️ Используйте кнопки ниже для быстрого доступа:",
                reply_markup=reply_keyboard
            )


async def back_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle back to main menu."""
    query = update.callback_query
    await query.answer()
    await show_main_menu(update, context, edit=True)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    await update.message.reply_text(
        "🏠 *Бот для учёта показаний счётчиков и оплаты аренды*\n\n"
        "📊 *Сдать показания* — отправить текущие показания счётчиков\n"
        "💳 *Мои счета* — посмотреть и оплатить счета\n"
        "🔧 *Мои счетчики* — информация о Ваших счётчиках\n\n"
        "Нажмите кнопку в меню ниже или используйте /start",
        parse_mode="Markdown"
    )


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle cancel button."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Операция отменена.")
    context.user_data.clear()


# === Reply keyboard handlers ===

async def reply_keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle reply keyboard button presses."""
    text = update.message.text

    if "Сдать показания" in text:
        await handle_readings_menu(update, context)
    elif "Неоплаченные" in text:
        # Owner button - show ALL unpaid invoices
        await handle_owner_unpaid(update, context)
    elif "Мои счета" in text:
        # Tenant button - show user's unpaid invoices
        await handle_invoices_menu(update, context)
    elif "Мои счетчики" in text:
        await handle_my_meters_menu(update, context)
    elif "Статус показаний" in text:
        await handle_owner_readings_status(update, context)
    elif "Выставить счёт" in text:
        await handle_owner_issue_invoice(update, context)
    elif "Напоминания" in text:
        await handle_owner_reminders(update, context)
    elif "Управление" in text:
        await handle_owner_management(update, context)


async def handle_readings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show meters list for readings submission (from reply keyboard)."""
    user_id = update.effective_user.id
    meters = await sheets_service.get_meters_for_readings(user_id)

    if not meters:
        await update.message.reply_text(
            "📊 У Вас нет счётчиков для сдачи показаний.",
            reply_markup=get_tenant_main_menu(has_readings=False)
        )
        return

    await update.message.reply_text(
        "📊 *Сдача показаний*\n\n"
        "Выберите счётчик, для которого хотите сдать показания:",
        reply_markup=get_meters_keyboard(meters),
        parse_mode="Markdown"
    )


async def handle_invoices_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show invoices (from reply keyboard)."""
    from src.bot.handlers.payments import get_premises_to_pay_keyboard
    user_id = update.effective_user.id
    invoices = await sheets_service.get_unpaid_invoices_for_tenant(user_id)

    if not invoices:
        await update.message.reply_text(
            "✨ У Вас нет неоплаченных счетов. Всё оплачено!",
            reply_markup=get_back_keyboard()
        )
        return

    total = sum(inv.get("Сумма", 0) for inv in invoices)
    lines = ["💳 *Ваши неоплаченные счета:*\n"]

    for inv in invoices:
        premise = inv.get("Помещение", "")
        amount = inv.get("Сумма", 0)
        lines.append(f"• {premise}: {amount:.0f} руб.")

    lines.append(f"\n📋 *Итого к оплате: {total:.0f} руб.*")
    lines.append("\nВыберите помещение для оплаты:")

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=get_premises_to_pay_keyboard(invoices),
        parse_mode="Markdown"
    )


async def handle_my_meters_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's meters info (from reply keyboard)."""
    user_id = update.effective_user.id
    meters = await sheets_service.get_meters_for_readings(user_id)

    if not meters:
        await update.message.reply_text(
            "🔧 У Вас нет закреплённых счётчиков.",
            reply_markup=get_tenant_main_menu(has_readings=False)
        )
        return

    lines = ["🔧 *Ваши счётчики:*\n"]
    for meter in meters:
        name = meter.get("Название", "")
        premise = meter.get("Помещение", "")
        last_reading = meter.get("Последнее показание", 0) or 0
        last_date = meter.get("Дата посл. показания", "") or "-"
        unit = meter.get("Единица", "")
        to_pay = meter.get("Сумма к оплате", 0) or 0

        lines.append(f"📟 *{name}* ({premise})")
        lines.append(f"   Последнее показание: {last_reading} {unit}")
        lines.append(f"   Дата: {last_date}")
        if to_pay > 0:
            lines.append(f"   💰 К оплате: {to_pay:.0f} руб.")
        lines.append("")

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=get_back_keyboard(),
        parse_mode="Markdown"
    )


async def handle_owner_readings_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show readings status (from reply keyboard)."""
    from src.bot.handlers.owner import owner_readings_status_callback
    # Create a fake callback query context
    status_list = await sheets_service.get_readings_status()

    if not status_list:
        await update.message.reply_text(
            "📊 Нет счётчиков в системе.",
            reply_markup=get_back_keyboard("owner_back_main")
        )
        return

    lines = ["📊 *Статус показаний за текущий месяц:*\n"]

    submitted = 0
    total = len(status_list)

    for item in status_list:
        meter = item["meter"]
        name = meter.get("Название", "")
        premise = meter.get("Помещение", "")
        responsible = meter.get("Имя_показания", "")

        if item["has_readings"]:
            emoji = "✅"
            submitted += 1
        else:
            emoji = "⏳"

        lines.append(f"{emoji} {name} ({premise}) — {responsible}")

    lines.append(f"\n📈 *Сдано: {submitted} из {total}*")

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=get_back_keyboard("owner_back_main"),
        parse_mode="Markdown"
    )


async def handle_owner_issue_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show draft invoices (from reply keyboard)."""
    from src.bot.keyboards import get_draft_invoices_keyboard
    invoices = await sheets_service.get_draft_invoices()

    if not invoices:
        await update.message.reply_text(
            "📨 Нет черновиков счетов для выставления.\n\n"
            "ℹ️ Убедитесь, что в таблице есть записи со статусом «Черновик» и суммой > 0.",
            reply_markup=get_back_keyboard("owner_back_main")
        )
        return

    lines = ["📨 *Черновики счетов (готовы к выставлению):*\n"]
    total = 0

    for inv in invoices:
        premise = inv.get("Помещение", "")
        name = inv.get("Имя_оплата", "")
        amount = inv.get("Сумма", 0) or 0
        total += amount
        lines.append(f"• {premise} ({name}): {amount:.0f} руб.")

    lines.append(f"\n💰 *Всего: {total:.0f} руб.*")
    lines.append("\nВыберите счёт для выставления:")

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=get_draft_invoices_keyboard(invoices),
        parse_mode="Markdown"
    )


async def handle_owner_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show reminders menu (from reply keyboard)."""
    from src.bot.keyboards import get_owner_reminders_menu
    await update.message.reply_text(
        "🔔 *Напоминания*\n\n"
        "Выберите тип напоминания:",
        reply_markup=get_owner_reminders_menu(),
        parse_mode="Markdown"
    )


async def handle_owner_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show management menu (from reply keyboard)."""
    from src.bot.keyboards import get_owner_management_menu
    await update.message.reply_text(
        "⚙️ *Управление*\n\n"
        "Выберите действие:",
        reply_markup=get_owner_management_menu(),
        parse_mode="Markdown"
    )


async def handle_owner_unpaid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all unpaid invoices for owner (from reply keyboard)."""
    invoices = await sheets_service.get_all_unpaid_invoices()

    if not invoices:
        await update.message.reply_text(
            "✨ Нет неоплаченных счетов. Все арендаторы оплатили!",
            reply_markup=get_back_keyboard("owner_back_main")
        )
        return

    lines = ["💰 *Неоплаченные счета:*\n"]
    total = 0

    for inv in invoices:
        premise = inv.get("Помещение", "")
        name = inv.get("Имя_оплата", "")
        amount = inv.get("Сумма", 0) or 0
        total += amount
        lines.append(f"• {premise} ({name}): {amount:.0f} руб.")

    lines.append(f"\n💰 *Всего к оплате: {total:.0f} руб.*")

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=get_back_keyboard("owner_back_main"),
        parse_mode="Markdown"
    )


# === Tenant menu handlers (Inline) ===

async def menu_readings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show meters list for readings submission."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    meters = await sheets_service.get_meters_for_readings(user_id)

    if not meters:
        await query.edit_message_text(
            "📊 У Вас нет счётчиков для сдачи показаний.",
            reply_markup=get_tenant_main_menu(has_readings=False)
        )
        return

    await query.edit_message_text(
        "📊 *Сдача показаний*\n\n"
        "Выберите счётчик, для которого хотите сдать показания:",
        reply_markup=get_meters_keyboard(meters),
        parse_mode="Markdown"
    )


async def menu_invoices_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show unpaid invoices list (by premise)."""
    query = update.callback_query
    await query.answer()

    # Import here to avoid circular import
    from src.bot.handlers.payments import menu_invoices_callback as show_invoices
    await show_invoices(update, context)


async def menu_my_meters_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's meters info."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    meters = await sheets_service.get_meters_for_readings(user_id)

    if not meters:
        await query.edit_message_text(
            "🔧 У Вас нет закреплённых счётчиков.",
            reply_markup=get_tenant_main_menu(has_readings=False)
        )
        return

    lines = ["🔧 *Ваши счётчики:*\n"]
    for meter in meters:
        name = meter.get("Название", "")
        premise = meter.get("Помещение", "")
        last_reading = meter.get("Последнее показание", 0) or 0
        last_date = meter.get("Дата посл. показания", "") or "-"
        unit = meter.get("Единица", "")
        to_pay = meter.get("Сумма к оплате", 0) or 0

        lines.append(f"📟 *{name}* ({premise})")
        lines.append(f"   Последнее показание: {last_reading} {unit}")
        lines.append(f"   Дата: {last_date}")
        if to_pay > 0:
            lines.append(f"   💰 К оплате: {to_pay:.0f} руб.")
        lines.append("")

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=get_back_keyboard(),
        parse_mode="Markdown"
    )


def register_common_handlers(app: Application) -> None:
    """Register common command handlers."""
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))

    # Reply keyboard handler (for persistent bottom buttons)
    reply_keyboard_filter = filters.Regex(
        r"^(📊 Сдать показания|💳 Мои счета|🔧 Мои счетчики|"
        r"📊 Статус показаний|💰 Неоплаченные|📨 Выставить счёт|"
        r"🔔 Напоминания|⚙️ Управление)$"
    )
    app.add_handler(MessageHandler(reply_keyboard_filter, reply_keyboard_handler))

    # Menu navigation
    app.add_handler(CallbackQueryHandler(back_main_callback, pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(cancel_callback, pattern="^cancel$"))

    # Tenant menu
    app.add_handler(CallbackQueryHandler(menu_readings_callback, pattern="^menu_readings$"))
    app.add_handler(CallbackQueryHandler(menu_invoices_callback, pattern="^menu_invoices$"))
    app.add_handler(CallbackQueryHandler(menu_my_meters_callback, pattern="^menu_my_meters$"))
