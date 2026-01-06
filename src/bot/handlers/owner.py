from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src.bot.keyboards import (
    get_owner_main_menu,
    get_owner_management_menu,
    get_owner_reminders_menu,
    get_premises_keyboard,
    get_tenants_keyboard,
    get_tenants_to_remind_keyboard,
    get_draft_invoices_keyboard,
    get_tariffs_keyboard,
    get_back_keyboard,
    get_cancel_keyboard,
    get_edit_confirm_keyboard,
)
from src.services.sheets import sheets_service

# Conversation states
ADDING_PREMISE_NAME = 1
ADDING_PREMISE_ADDRESS = 2
CONFIRMING_PREMISE = 3
ADDING_METER_NAME = 4
ADDING_METER_TYPE = 5
ADDING_METER_UNIT = 6
SELECTING_METER_RESPONSIBLE_READINGS = 7
SELECTING_METER_RESPONSIBLE_PAYMENT = 8
CONFIRMING_METER = 9
EDITING_TARIFF = 10


# === Owner menu navigation ===

async def owner_back_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return to owner main menu."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    tenant = await sheets_service.get_tenant(user.id)
    name = tenant.get("Имя", "") if tenant else ""

    await query.edit_message_text(
        f"👋 Здравствуйте, {name}!\n\n"
        "🏠 Вы вошли как владелец.\n\n"
        "Выберите нужный раздел:",
        reply_markup=get_owner_main_menu()
    )


# === Readings status ===

READINGS_STATUS_PAGE_SIZE = 10


async def owner_readings_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show readings status for all meters (first page)."""
    query = update.callback_query
    await query.answer()

    await show_readings_status_page(query, context, page=0)


async def readings_status_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show readings status for a specific page."""
    query = update.callback_query
    await query.answer()

    # Extract page number from callback_data: readings_status_page_N
    page = int(query.data.split("_")[-1])
    await show_readings_status_page(query, context, page)


async def show_readings_status_page(query, context: ContextTypes.DEFAULT_TYPE, page: int) -> None:
    """Display a specific page of readings status."""
    status_list = await sheets_service.get_readings_status()

    if not status_list:
        await query.edit_message_text(
            "📊 Нет счётчиков в системе.",
            reply_markup=get_back_keyboard("owner_back_main")
        )
        return

    total = len(status_list)
    submitted = sum(1 for item in status_list if item["has_readings"])

    # Pagination
    total_pages = (total + READINGS_STATUS_PAGE_SIZE - 1) // READINGS_STATUS_PAGE_SIZE
    page = max(0, min(page, total_pages - 1))

    start_idx = page * READINGS_STATUS_PAGE_SIZE
    end_idx = min(start_idx + READINGS_STATUS_PAGE_SIZE, total)
    page_items = status_list[start_idx:end_idx]

    lines = [f"📊 *Статус показаний за текущий месяц:*\n"]

    for item in page_items:
        meter = item["meter"]
        name = meter.get("Название", "")
        premise = meter.get("Помещение", "")
        responsible = meter.get("Имя_показания", "")

        if item["has_readings"]:
            emoji = "✅"
        else:
            emoji = "⏳"

        lines.append(f"{emoji} {name} ({premise}) — {responsible}")

    lines.append(f"\n📈 *Сдано: {submitted} из {total}*")

    if total_pages > 1:
        lines.append(f"📄 Страница {page + 1} из {total_pages}")

    # Build pagination keyboard
    buttons = []
    nav_row = []

    if page > 0:
        nav_row.append(InlineKeyboardButton("« Назад", callback_data=f"readings_status_page_{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Вперёд »", callback_data=f"readings_status_page_{page + 1}"))

    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton("« В меню", callback_data="owner_back_main")])

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


# === Unpaid invoices ===

async def owner_unpaid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all unpaid invoices."""
    query = update.callback_query
    await query.answer()

    invoices = await sheets_service.get_all_unpaid_invoices()

    if not invoices:
        await query.edit_message_text(
            "✨ Нет неоплаченных счетов! Все арендаторы оплатили.",
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

    lines.append(f"\n💵 *Итого: {total:.0f} руб.*")

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=get_back_keyboard("owner_back_main"),
        parse_mode="Markdown"
    )


# === Issue invoices ===

async def owner_issue_invoice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show draft invoices to issue."""
    query = update.callback_query
    await query.answer()

    invoices = await sheets_service.get_draft_invoices()

    if not invoices:
        await query.edit_message_text(
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

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=get_draft_invoices_keyboard(invoices),
        parse_mode="Markdown"
    )


async def issue_invoice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Issue specific invoice (change status from 'Черновик' to 'Не оплачен')."""
    query = update.callback_query
    await query.answer()

    # Extract premise_id from callback_data: "issue_invoice_123"
    premise_id = int(query.data.split("_")[2])

    # Get invoice info before issuing
    invoice = await sheets_service.get_invoice_for_premise(premise_id)
    if not invoice:
        await query.edit_message_text(
            "❌ Счёт не найден.",
            reply_markup=get_back_keyboard("owner_back_main")
        )
        return

    premise_name = invoice.get("Помещение", "")
    amount = invoice.get("Сумма", 0) or 0
    responsible_id = invoice.get("ответственный_оплата")
    responsible_name = invoice.get("Имя_оплата", "")

    # Issue the invoice
    success = await sheets_service.issue_invoice(premise_id)

    if success:
        await query.edit_message_text(
            f"✅ *Счёт успешно выставлен!*\n\n"
            f"🏠 Помещение: {premise_name}\n"
            f"💰 Сумма: *{amount:.0f} руб.*\n"
            f"👤 Ответственный: {responsible_name}\n\n"
            "Арендатору отправлено уведомление.",
            reply_markup=get_back_keyboard("owner_back_main"),
            parse_mode="Markdown"
        )

        # Notify tenant about the invoice
        if responsible_id:
            payment_details = await sheets_service.get_payment_details()

            # Get meters breakdown for this user
            meters = await sheets_service.get_meters_by_premise(premise_id)
            breakdown_lines = []
            for meter in meters:
                if str(meter.get("ответственный_оплата")) != str(responsible_id):
                    continue
                meter_name = meter.get("Название", "")
                consumption = meter.get("Расход к оплате", 0) or 0
                unit = meter.get("Единица", "")
                tariff = meter.get("Тариф", 0) or 0
                if consumption > 0:
                    breakdown_lines.append(f"   📟 {meter_name}: {consumption:.2f} {unit} × {tariff:.2f} руб.")

            breakdown = "\n".join(breakdown_lines) if breakdown_lines else ""
            breakdown_section = f"\n📊 *Детализация:*\n{breakdown}\n" if breakdown else ""

            try:
                await context.bot.send_message(
                    chat_id=responsible_id,
                    text=(
                        f"📨 *Вам выставлен счёт на оплату!*\n\n"
                        f"🏠 Помещение: {premise_name}\n"
                        f"💰 Сумма: *{amount:.0f} руб.*\n"
                        f"{breakdown_section}\n"
                        f"🏦 *Реквизиты для оплаты:*\n`{payment_details}`\n\n"
                        "📸 После оплаты, пожалуйста, отправьте фото чека через бот.\n\n"
                        "Нажмите кнопку «💳 Мои счета» в меню."
                    ),
                    parse_mode="Markdown"
                )
            except Exception:
                pass  # Tenant might have blocked the bot
    else:
        await query.edit_message_text(
            "❌ Не удалось выставить счёт. Попробуйте позже.",
            reply_markup=get_back_keyboard("owner_back_main")
        )


# === Reminders ===

async def owner_reminders_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show reminders submenu."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "🔔 *Напоминания*\n\n"
        "Выберите тип напоминания:",
        reply_markup=get_owner_reminders_menu(),
        parse_mode="Markdown"
    )


async def remind_readings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show tenants who haven't submitted readings."""
    query = update.callback_query
    await query.answer()

    tenants = await sheets_service.get_tenants_without_readings()

    if not tenants:
        await query.edit_message_text(
            "✨ Все арендаторы сдали показания в этом месяце!",
            reply_markup=get_back_keyboard("owner_reminders")
        )
        return

    await query.edit_message_text(
        f"📊 *Не сдали показания ({len(tenants)} чел.):*\n\n"
        "Выберите, кому отправить напоминание:",
        reply_markup=get_tenants_to_remind_keyboard(tenants, "readings"),
        parse_mode="Markdown"
    )


async def remind_payments_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show tenants with unpaid invoices."""
    query = update.callback_query
    await query.answer()

    tenants = await sheets_service.get_tenants_with_unpaid()

    if not tenants:
        await query.edit_message_text(
            "✨ Нет неоплаченных счетов!",
            reply_markup=get_back_keyboard("owner_reminders")
        )
        return

    await query.edit_message_text(
        f"💳 *Не оплатили ({len(tenants)} чел.):*\n\n"
        "Выберите, кому отправить напоминание:",
        reply_markup=get_tenants_to_remind_keyboard(tenants, "payment"),
        parse_mode="Markdown"
    )


async def send_reminder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send reminder to selected tenant or all."""
    query = update.callback_query
    await query.answer()

    # Parse callback: "remind_readings_123456" or "remind_payment_all"
    parts = query.data.split("_")
    remind_type = parts[1]  # "readings" or "payment"
    target = parts[2]  # telegram_id or "all"

    if target == "all":
        await send_reminder_to_all(update, context, remind_type)
    else:
        await send_reminder_to_one(update, context, remind_type, int(target))


async def send_reminder_to_one(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    remind_type: str,
    tenant_id: int
) -> None:
    """Send reminder to one tenant."""
    query = update.callback_query

    if remind_type == "readings":
        message = (
            "📊 *Напоминание о показаниях*\n\n"
            "Пожалуйста, не забудьте сдать показания счётчиков.\n\n"
            "Нажмите кнопку «📊 Сдать показания» в меню бота."
        )
    else:
        # Payment reminder
        invoices = await sheets_service.get_unpaid_invoices_for_tenant(tenant_id)
        total = sum(inv.get("Сумма", 0) or 0 for inv in invoices)
        payment_details = await sheets_service.get_payment_details()

        message = (
            f"💳 *Напоминание об оплате*\n\n"
            f"💰 К оплате: *{total:.0f} руб.*\n\n"
            f"🏦 *Реквизиты:*\n`{payment_details}`\n\n"
            "📸 После оплаты, пожалуйста, отправьте фото чека через бот."
        )

    try:
        await context.bot.send_message(chat_id=tenant_id, text=message, parse_mode="Markdown")
        await query.edit_message_text(
            "✅ Напоминание успешно отправлено!",
            reply_markup=get_back_keyboard("owner_reminders")
        )
    except Exception as e:
        error_str = str(e).lower()
        if "chat not found" in error_str or "bot was blocked" in error_str:
            error_msg = "Пользователь не запустил бота или заблокировал его."
        elif "user is deactivated" in error_str:
            error_msg = "Аккаунт пользователя удалён."
        else:
            error_msg = str(e)

        await query.edit_message_text(
            f"❌ Не удалось отправить напоминание.\n\n{error_msg}",
            reply_markup=get_back_keyboard("owner_reminders")
        )


async def send_reminder_to_all(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    remind_type: str
) -> None:
    """Send reminders to all relevant tenants."""
    query = update.callback_query

    sent = 0
    failed = 0

    if remind_type == "readings":
        tenants = await sheets_service.get_tenants_without_readings()
        message = (
            "📊 *Напоминание о показаниях*\n\n"
            "Пожалуйста, не забудьте сдать показания счётчиков.\n\n"
            "Нажмите кнопку «📊 Сдать показания» в меню бота."
        )

        for tenant in tenants:
            try:
                await context.bot.send_message(
                    chat_id=tenant["telegram_id"],
                    text=message,
                    parse_mode="Markdown"
                )
                sent += 1
            except Exception:
                failed += 1
    else:
        # Payment reminders
        tenants = await sheets_service.get_tenants_with_unpaid()
        payment_details = await sheets_service.get_payment_details()

        for tenant in tenants:
            total = tenant.get("total", 0)
            message = (
                f"💳 *Напоминание об оплате*\n\n"
                f"💰 К оплате: *{total:.0f} руб.*\n\n"
                f"🏦 *Реквизиты:*\n`{payment_details}`\n\n"
                "📸 После оплаты, пожалуйста, отправьте фото чека через бот."
            )

            try:
                await context.bot.send_message(
                    chat_id=tenant["telegram_id"],
                    text=message,
                    parse_mode="Markdown"
                )
                sent += 1
            except Exception:
                failed += 1

    await query.edit_message_text(
        f"📤 *Рассылка завершена*\n\n"
        f"✅ Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}",
        reply_markup=get_back_keyboard("owner_reminders"),
        parse_mode="Markdown"
    )


# === Management ===

async def owner_management_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show management submenu."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "⚙️ *Управление*\n\n"
        "Выберите действие:",
        reply_markup=get_owner_management_menu(),
        parse_mode="Markdown"
    )


# --- Add premise ---

async def mgmt_add_premise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start adding a new premise."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "🏠 *Добавление помещения*\n\n"
        "📝 Введите название помещения\n"
        "(например: «Офис 1» или «Склад»):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

    return ADDING_PREMISE_NAME


async def receive_premise_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process premise name input."""
    name = update.message.text.strip()

    if not name:
        await update.message.reply_text(
            "⚠️ Название не может быть пустым.\n\n"
            "Пожалуйста, введите название помещения:",
            reply_markup=get_cancel_keyboard(),
        )
        return ADDING_PREMISE_NAME

    context.user_data["premise_name"] = name

    await update.message.reply_text(
        f"✅ Название: *{name}*\n\n"
        "📍 Теперь введите адрес помещения\n"
        "(или отправьте «-» чтобы пропустить):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

    return ADDING_PREMISE_ADDRESS


async def receive_premise_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process premise address and show confirmation."""
    address = update.message.text.strip()
    if address == "-":
        address = ""

    context.user_data["premise_address"] = address
    name = context.user_data.get("premise_name", "")

    await update.message.reply_text(
        f"📋 *Проверьте данные:*\n\n"
        f"🏠 Название: *{name}*\n"
        f"📍 Адрес: {address or '(не указан)'}\n\n"
        "Всё верно?",
        reply_markup=get_edit_confirm_keyboard("premise_edit", "premise_confirm"),
        parse_mode="Markdown"
    )

    return CONFIRMING_PREMISE


async def confirm_premise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirm and save premise."""
    query = update.callback_query
    await query.answer()

    name = context.user_data.get("premise_name", "")
    address = context.user_data.get("premise_address", "")

    premise_id = await sheets_service.add_premise(name, address)

    await query.edit_message_text(
        f"✅ *Помещение успешно добавлено!*\n\n"
        f"🆔 ID: {premise_id}\n"
        f"🏠 Название: *{name}*\n"
        f"📍 Адрес: {address or '(не указан)'}",
        reply_markup=get_back_keyboard("owner_management"),
        parse_mode="Markdown"
    )

    context.user_data.clear()
    return ConversationHandler.END


async def edit_premise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Go back to edit premise."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "🏠 *Добавление помещения*\n\n"
        "📝 Введите название помещения:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

    return ADDING_PREMISE_NAME


# --- Add meter ---

async def mgmt_add_meter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start adding a new meter - select premise."""
    query = update.callback_query
    await query.answer()

    premises = await sheets_service.get_all_premises()

    if not premises:
        await query.edit_message_text(
            "⚠️ Сначала добавьте хотя бы одно помещение.",
            reply_markup=get_back_keyboard("owner_management")
        )
        return ConversationHandler.END

    await query.edit_message_text(
        "📟 *Добавление счётчика*\n\n"
        "🏠 Выберите помещение:",
        reply_markup=get_premises_keyboard(premises, callback_prefix="meter_premise"),
        parse_mode="Markdown"
    )

    return ConversationHandler.END


async def meter_premise_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle premise selection for new meter."""
    query = update.callback_query
    await query.answer()

    premise_id = int(query.data.split("_")[2])
    premise = await sheets_service.get_premise(premise_id)

    if not premise:
        await query.edit_message_text("❌ Помещение не найдено.")
        return ConversationHandler.END

    context.user_data["meter_premise"] = premise

    await query.edit_message_text(
        f"📟 *Добавление счётчика*\n\n"
        f"🏠 Помещение: *{premise.get('Название', '')}*\n\n"
        "📝 Введите название счётчика\n"
        "(например: «Электро-1», «Вода ХВС»):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

    return ADDING_METER_NAME


async def receive_meter_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process meter name."""
    name = update.message.text.strip()

    if not name:
        await update.message.reply_text(
            "⚠️ Название не может быть пустым.\n\n"
            "Введите название счётчика:",
            reply_markup=get_cancel_keyboard(),
        )
        return ADDING_METER_NAME

    context.user_data["meter_name"] = name

    await update.message.reply_text(
        f"✅ Название: *{name}*\n\n"
        "📊 Введите тип счётчика\n"
        "(например: «электр», «вода», «газ»):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

    return ADDING_METER_TYPE


async def receive_meter_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process meter type."""
    meter_type = update.message.text.strip()
    context.user_data["meter_type"] = meter_type

    await update.message.reply_text(
        f"✅ Тип: *{meter_type}*\n\n"
        "📏 Введите единицу измерения\n"
        "(например: «кВт·ч», «м³»):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

    return ADDING_METER_UNIT


async def receive_meter_unit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process meter unit and select responsible for readings."""
    unit = update.message.text.strip()
    context.user_data["meter_unit"] = unit

    # Тариф now comes from Настройки sheet via formula - no need to ask user
    # Proceed directly to selecting responsible person for readings
    tenants = await sheets_service.get_all_tenants()

    if not tenants:
        await update.message.reply_text(
            "⚠️ Нет арендаторов в системе.\n\n"
            "Сначала добавьте арендаторов в таблицу."
        )
        context.user_data.clear()
        return ConversationHandler.END

    await update.message.reply_text(
        f"✅ Единица: *{unit}*\n\n"
        "👤 Выберите ответственного за *ПОКАЗАНИЯ*:",
        reply_markup=get_tenants_keyboard(tenants, callback_prefix="meter_resp_read"),
        parse_mode="Markdown"
    )

    return SELECTING_METER_RESPONSIBLE_READINGS


async def meter_responsible_readings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle responsible person for readings selection."""
    query = update.callback_query
    await query.answer()

    responsible_id = int(query.data.split("_")[3])
    tenant = await sheets_service.get_tenant(responsible_id)

    if not tenant:
        await query.edit_message_text("❌ Арендатор не найден.")
        return ConversationHandler.END

    context.user_data["responsible_readings_id"] = responsible_id
    context.user_data["responsible_readings_name"] = tenant.get("Имя", "")

    # Now select responsible for payment
    tenants = await sheets_service.get_all_tenants()

    await query.edit_message_text(
        f"✅ За показания: *{tenant.get('Имя', '')}*\n\n"
        "👤 Выберите ответственного за *ОПЛАТУ*:",
        reply_markup=get_tenants_keyboard(tenants, callback_prefix="meter_resp_pay"),
        parse_mode="Markdown"
    )

    return SELECTING_METER_RESPONSIBLE_PAYMENT


async def meter_responsible_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle responsible person for payment selection - show confirmation."""
    query = update.callback_query
    await query.answer()

    responsible_id = int(query.data.split("_")[3])
    tenant = await sheets_service.get_tenant(responsible_id)

    if not tenant:
        await query.edit_message_text("❌ Арендатор не найден.")
        return ConversationHandler.END

    context.user_data["responsible_payment_id"] = responsible_id
    context.user_data["responsible_payment_name"] = tenant.get("Имя", "")

    premise = context.user_data.get("meter_premise", {})

    await query.edit_message_text(
        f"📋 *Проверьте данные:*\n\n"
        f"🏠 Помещение: *{premise.get('Название', '')}*\n"
        f"📟 Название: *{context.user_data.get('meter_name', '')}*\n"
        f"📊 Тип: {context.user_data.get('meter_type', '')}\n"
        f"📏 Единица: {context.user_data.get('meter_unit', '')}\n"
        f"👤 За показания: {context.user_data.get('responsible_readings_name', '')}\n"
        f"👤 За оплату: {tenant.get('Имя', '')}\n\n"
        "ℹ️ _Тариф будет взят из листа Настройки._\n\n"
        "Всё верно?",
        reply_markup=get_edit_confirm_keyboard("meter_edit", "meter_confirm"),
        parse_mode="Markdown"
    )

    return CONFIRMING_METER


async def confirm_meter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirm and save meter."""
    query = update.callback_query
    await query.answer()

    premise = context.user_data.get("meter_premise", {})

    # Save meter (tariff is formula-based in Google Sheets, not passed here)
    meter_id = await sheets_service.add_meter(
        premise_id=premise.get("id", 0),
        premise_name=premise.get("Название", ""),
        name=context.user_data.get("meter_name", ""),
        meter_type=context.user_data.get("meter_type", ""),
        unit=context.user_data.get("meter_unit", ""),
        responsible_readings=context.user_data.get("responsible_readings_id", 0),
        responsible_readings_name=context.user_data.get("responsible_readings_name", ""),
        responsible_payment=context.user_data.get("responsible_payment_id", 0),
        responsible_payment_name=context.user_data.get("responsible_payment_name", ""),
    )

    await query.edit_message_text(
        f"✅ *Счётчик успешно добавлен!*\n\n"
        f"🆔 ID: {meter_id}\n"
        f"🏠 Помещение: *{premise.get('Название', '')}*\n"
        f"📟 Название: *{context.user_data.get('meter_name', '')}*\n"
        f"📊 Тип: {context.user_data.get('meter_type', '')}\n"
        f"📏 Единица: {context.user_data.get('meter_unit', '')}\n"
        f"👤 За показания: {context.user_data.get('responsible_readings_name', '')}\n"
        f"👤 За оплату: {context.user_data.get('responsible_payment_name', '')}\n\n"
        "ℹ️ _Тариф будет подтянут из листа Настройки._",
        reply_markup=get_back_keyboard("owner_management"),
        parse_mode="Markdown"
    )

    context.user_data.clear()
    return ConversationHandler.END


async def edit_meter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Go back to edit meter - restart from premise selection."""
    query = update.callback_query
    await query.answer()

    premises = await sheets_service.get_all_premises()

    await query.edit_message_text(
        "📟 *Добавление счётчика*\n\n"
        "🏠 Выберите помещение:",
        reply_markup=get_premises_keyboard(premises, callback_prefix="meter_premise"),
        parse_mode="Markdown"
    )

    context.user_data.clear()
    return ConversationHandler.END


# --- List premises ---

PREMISES_PAGE_SIZE = 10


async def mgmt_list_premises_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all premises (first page)."""
    query = update.callback_query
    await query.answer()

    await show_premises_page(query, context, page=0)


async def premises_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show premises for a specific page."""
    query = update.callback_query
    await query.answer()

    page = int(query.data.split("_")[-1])
    await show_premises_page(query, context, page)


async def show_premises_page(query, context: ContextTypes.DEFAULT_TYPE, page: int) -> None:
    """Display a specific page of premises."""
    premises = await sheets_service.get_all_premises()

    if not premises:
        await query.edit_message_text(
            "📋 Нет помещений в системе.",
            reply_markup=get_back_keyboard("owner_management")
        )
        return

    total = len(premises)
    total_pages = (total + PREMISES_PAGE_SIZE - 1) // PREMISES_PAGE_SIZE
    page = max(0, min(page, total_pages - 1))

    start_idx = page * PREMISES_PAGE_SIZE
    end_idx = min(start_idx + PREMISES_PAGE_SIZE, total)
    page_items = premises[start_idx:end_idx]

    lines = ["📋 *Помещения:*\n"]
    for p in page_items:
        pid = p.get("id", "")
        name = p.get("Название", "")
        address = p.get("Адрес", "")
        lines.append(f"🏠 *#{pid}* {name}" + (f"\n   📍 {address}" if address else ""))

    if total_pages > 1:
        lines.append(f"\n📄 Страница {page + 1} из {total_pages} (всего: {total})")

    # Build pagination keyboard
    buttons = []
    nav_row = []

    if page > 0:
        nav_row.append(InlineKeyboardButton("« Назад", callback_data=f"premises_page_{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Вперёд »", callback_data=f"premises_page_{page + 1}"))

    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton("« В управление", callback_data="owner_management")])

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


# --- List meters ---

METERS_PAGE_SIZE = 5  # Meters have more info, so fewer per page


async def mgmt_list_meters_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all meters (first page)."""
    query = update.callback_query
    await query.answer()

    await show_meters_page(query, context, page=0)


async def meters_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show meters for a specific page."""
    query = update.callback_query
    await query.answer()

    page = int(query.data.split("_")[-1])
    await show_meters_page(query, context, page)


async def show_meters_page(query, context: ContextTypes.DEFAULT_TYPE, page: int) -> None:
    """Display a specific page of meters."""
    meters = await sheets_service.get_all_meters()

    if not meters:
        await query.edit_message_text(
            "📋 Нет счётчиков в системе.",
            reply_markup=get_back_keyboard("owner_management")
        )
        return

    total = len(meters)
    total_pages = (total + METERS_PAGE_SIZE - 1) // METERS_PAGE_SIZE
    page = max(0, min(page, total_pages - 1))

    start_idx = page * METERS_PAGE_SIZE
    end_idx = min(start_idx + METERS_PAGE_SIZE, total)
    page_items = meters[start_idx:end_idx]

    lines = ["📋 *Счётчики:*\n"]
    for m in page_items:
        mid = m.get("id", "")
        name = m.get("Название", "")
        premise = m.get("Помещение", "")
        resp_readings = m.get("Имя_показания", "")
        resp_payment = m.get("Имя_оплата", "")
        to_pay = m.get("Сумма к оплате", 0) or 0

        lines.append(f"📟 *#{mid} {name}* ({premise})")
        lines.append(f"   👤 Показания: {resp_readings}")
        lines.append(f"   👤 Оплата: {resp_payment}")
        if to_pay > 0:
            lines.append(f"   💰 К оплате: {to_pay:.0f} руб.")
        lines.append("")

    if total_pages > 1:
        lines.append(f"📄 Страница {page + 1} из {total_pages} (всего: {total})")

    # Build pagination keyboard
    buttons = []
    nav_row = []

    if page > 0:
        nav_row.append(InlineKeyboardButton("« Назад", callback_data=f"meters_page_{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Вперёд »", callback_data=f"meters_page_{page + 1}"))

    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton("« В управление", callback_data="owner_management")])

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


# --- Tariffs management ---

async def mgmt_tariffs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all tariffs."""
    query = update.callback_query
    await query.answer()

    tariffs = await sheets_service.get_tariffs()

    if not tariffs:
        await query.edit_message_text(
            "💰 Нет тарифов в системе.\n\n"
            "Добавьте тарифы в лист «Тарифы» в Google Sheets.",
            reply_markup=get_back_keyboard("owner_management")
        )
        return

    lines = ["💰 *Тарифы:*\n"]
    for t in tariffs:
        tariff_type = t.get("Тип", "")
        tariff_value = t.get("Тариф", 0)
        lines.append(f"• {tariff_type}: *{tariff_value:.2f}* руб.")

    lines.append("\n_Нажмите на тариф для изменения:_")

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=get_tariffs_keyboard(tariffs),
        parse_mode="Markdown"
    )


async def edit_tariff_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start editing a tariff."""
    query = update.callback_query
    await query.answer()

    # Extract tariff type from callback_data: "edit_tariff_электр"
    tariff_type = query.data.replace("edit_tariff_", "")
    tariff = await sheets_service.get_tariff_by_type(tariff_type)

    if not tariff:
        await query.edit_message_text(
            "❌ Тариф не найден.",
            reply_markup=get_back_keyboard("mgmt_tariffs")
        )
        return ConversationHandler.END

    context.user_data["editing_tariff_type"] = tariff_type
    context.user_data["editing_tariff_old"] = tariff.get("Тариф", 0)

    await query.edit_message_text(
        f"💰 *Изменение тарифа*\n\n"
        f"Тип: *{tariff_type}*\n"
        f"Текущее значение: *{tariff.get('Тариф', 0):.2f}* руб.\n\n"
        f"📝 Введите новое значение тарифа:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

    return EDITING_TARIFF


async def receive_tariff_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process new tariff value."""
    text = update.message.text.strip()

    try:
        new_value = float(text.replace(",", "."))
    except ValueError:
        await update.message.reply_text(
            "⚠️ Пожалуйста, введите число.\n\n"
            "Например: `5.50` или `45`",
            reply_markup=get_cancel_keyboard(),
            parse_mode="Markdown"
        )
        return EDITING_TARIFF

    if new_value < 0:
        await update.message.reply_text(
            "⚠️ Тариф не может быть отрицательным.\n\n"
            "Введите корректное значение:",
            reply_markup=get_cancel_keyboard()
        )
        return EDITING_TARIFF

    tariff_type = context.user_data.get("editing_tariff_type", "")
    old_value = context.user_data.get("editing_tariff_old", 0)

    # Update tariff in Google Sheets
    success = await sheets_service.update_tariff(tariff_type, new_value)

    if success:
        await update.message.reply_text(
            f"✅ *Тариф успешно изменён!*\n\n"
            f"Тип: *{tariff_type}*\n"
            f"Было: {old_value:.2f} руб.\n"
            f"Стало: *{new_value:.2f}* руб.",
            reply_markup=get_back_keyboard("mgmt_tariffs"),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "❌ Не удалось обновить тариф. Попробуйте позже.",
            reply_markup=get_back_keyboard("mgmt_tariffs")
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_tariff_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel tariff editing."""
    query = update.callback_query
    await query.answer()

    # Return to tariffs list
    tariffs = await sheets_service.get_tariffs()

    lines = ["💰 *Тарифы:*\n"]
    for t in tariffs:
        tariff_type = t.get("Тип", "")
        tariff_value = t.get("Тариф", 0)
        lines.append(f"• {tariff_type}: *{tariff_value:.2f}* руб.")

    lines.append("\n_Нажмите на тариф для изменения:_")

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=get_tariffs_keyboard(tariffs),
        parse_mode="Markdown"
    )

    context.user_data.clear()
    return ConversationHandler.END


# --- Cancel management operations ---

async def cancel_management_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel management operation."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "❌ Операция отменена.",
        reply_markup=get_owner_management_menu()
    )
    context.user_data.clear()
    return ConversationHandler.END


def register_owner_handlers(app: Application) -> None:
    """Register owner handlers."""
    # Main menu navigation
    app.add_handler(CallbackQueryHandler(owner_back_main_callback, pattern="^owner_back_main$"))

    # Status and info
    app.add_handler(CallbackQueryHandler(owner_readings_status_callback, pattern="^owner_readings_status$"))
    app.add_handler(CallbackQueryHandler(readings_status_page_callback, pattern=r"^readings_status_page_\d+$"))
    app.add_handler(CallbackQueryHandler(owner_unpaid_callback, pattern="^owner_unpaid$"))

    # Issue invoices
    app.add_handler(CallbackQueryHandler(owner_issue_invoice_callback, pattern="^owner_issue_invoice$"))
    app.add_handler(CallbackQueryHandler(issue_invoice_callback, pattern=r"^issue_invoice_\d+$"))

    # Reminders submenu
    app.add_handler(CallbackQueryHandler(owner_reminders_callback, pattern="^owner_reminders$"))
    app.add_handler(CallbackQueryHandler(remind_readings_callback, pattern="^remind_readings$"))
    app.add_handler(CallbackQueryHandler(remind_payments_callback, pattern="^remind_payments$"))
    app.add_handler(CallbackQueryHandler(send_reminder_callback, pattern=r"^remind_(readings|payment)_"))

    # Management submenu
    app.add_handler(CallbackQueryHandler(owner_management_callback, pattern="^owner_management$"))
    app.add_handler(CallbackQueryHandler(mgmt_list_premises_callback, pattern="^mgmt_list_premises$"))
    app.add_handler(CallbackQueryHandler(premises_page_callback, pattern=r"^premises_page_\d+$"))
    app.add_handler(CallbackQueryHandler(mgmt_list_meters_callback, pattern="^mgmt_list_meters$"))
    app.add_handler(CallbackQueryHandler(meters_page_callback, pattern=r"^meters_page_\d+$"))

    # Add premise conversation
    add_premise_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(mgmt_add_premise_callback, pattern="^mgmt_add_premise$")
        ],
        states={
            ADDING_PREMISE_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_premise_name),
                CallbackQueryHandler(cancel_management_callback, pattern="^cancel$"),
            ],
            ADDING_PREMISE_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_premise_address),
                CallbackQueryHandler(cancel_management_callback, pattern="^cancel$"),
            ],
            CONFIRMING_PREMISE: [
                CallbackQueryHandler(confirm_premise_callback, pattern="^premise_confirm$"),
                CallbackQueryHandler(edit_premise_callback, pattern="^premise_edit$"),
                CallbackQueryHandler(cancel_management_callback, pattern="^cancel$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_management_callback, pattern="^cancel$"),
            CallbackQueryHandler(cancel_management_callback, pattern="^owner_back_main$"),
        ],
        allow_reentry=True,
    )
    app.add_handler(add_premise_conv)

    # Add meter conversation (tariff is formula-based in Google Sheets, not asked here)
    add_meter_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(mgmt_add_meter_callback, pattern="^mgmt_add_meter$")
        ],
        states={
            ADDING_METER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_meter_name),
                CallbackQueryHandler(cancel_management_callback, pattern="^cancel$"),
            ],
            ADDING_METER_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_meter_type),
                CallbackQueryHandler(cancel_management_callback, pattern="^cancel$"),
            ],
            ADDING_METER_UNIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_meter_unit),
                CallbackQueryHandler(cancel_management_callback, pattern="^cancel$"),
            ],
            SELECTING_METER_RESPONSIBLE_READINGS: [
                CallbackQueryHandler(meter_responsible_readings_callback, pattern=r"^meter_resp_read_\d+$"),
                CallbackQueryHandler(cancel_management_callback, pattern="^cancel$"),
            ],
            SELECTING_METER_RESPONSIBLE_PAYMENT: [
                CallbackQueryHandler(meter_responsible_payment_callback, pattern=r"^meter_resp_pay_\d+$"),
                CallbackQueryHandler(cancel_management_callback, pattern="^cancel$"),
            ],
            CONFIRMING_METER: [
                CallbackQueryHandler(confirm_meter_callback, pattern="^meter_confirm$"),
                CallbackQueryHandler(edit_meter_callback, pattern="^meter_edit$"),
                CallbackQueryHandler(cancel_management_callback, pattern="^cancel$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_management_callback, pattern="^cancel$"),
            CallbackQueryHandler(cancel_management_callback, pattern="^owner_back_main$"),
        ],
        allow_reentry=True,
    )
    app.add_handler(add_meter_conv)

    # Meter premise selection (intermediate step)
    app.add_handler(CallbackQueryHandler(meter_premise_selected_callback, pattern=r"^meter_premise_\d+$"))

    # Tariffs management
    app.add_handler(CallbackQueryHandler(mgmt_tariffs_callback, pattern="^mgmt_tariffs$"))

    # Edit tariff conversation
    edit_tariff_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(edit_tariff_callback, pattern=r"^edit_tariff_.+$")
        ],
        states={
            EDITING_TARIFF: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_tariff_value),
                CallbackQueryHandler(cancel_tariff_edit_callback, pattern="^cancel$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_tariff_edit_callback, pattern="^cancel$"),
            CallbackQueryHandler(cancel_tariff_edit_callback, pattern="^mgmt_tariffs$"),
        ],
        allow_reentry=True,
    )
    app.add_handler(edit_tariff_conv)
