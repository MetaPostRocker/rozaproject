from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src.bot.keyboards import get_cancel_keyboard, get_back_keyboard, get_edit_confirm_keyboard
from src.services.sheets import sheets_service
from src.services.storage import storage_service

# Conversation states
UPLOADING_RECEIPT = 1
CONFIRMING_PAYMENT = 2


def get_premises_to_pay_keyboard(invoices):
    """Generate keyboard with premises that have unpaid amounts."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    buttons = []
    for inv in invoices:
        premise_id = inv.get("помещение_id")
        premise_name = inv.get("Помещение", "")
        amount = inv.get("Сумма", 0)
        label = f"💳 {premise_name}: {amount:.0f} руб."
        buttons.append([InlineKeyboardButton(label, callback_data=f"pay_premise_{premise_id}")])

    buttons.append([InlineKeyboardButton("« Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


async def menu_invoices_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show unpaid invoices for tenant."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    invoices = await sheets_service.get_unpaid_invoices_for_tenant(user_id)

    if not invoices:
        await query.edit_message_text(
            "✨ У Вас нет неоплаченных счетов. Всё оплачено!",
            reply_markup=get_back_keyboard()
        )
        return

    # Build summary
    total = sum(inv.get("Сумма", 0) for inv in invoices)
    lines = ["💳 *Ваши неоплаченные счета:*\n"]

    for inv in invoices:
        premise = inv.get("Помещение", "")
        amount = inv.get("Сумма", 0)
        lines.append(f"• {premise}: {amount:.0f} руб.")

    lines.append(f"\n📋 *Итого к оплате: {total:.0f} руб.*")
    lines.append("\nВыберите помещение для оплаты:")

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=get_premises_to_pay_keyboard(invoices),
        parse_mode="Markdown"
    )


async def pay_premise_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle premise selection for payment."""
    query = update.callback_query
    await query.answer()

    # Extract premise_id from callback_data: "pay_premise_123"
    premise_id = int(query.data.split("_")[2])
    invoice = await sheets_service.get_invoice_for_premise(premise_id)

    if not invoice:
        await query.edit_message_text("❌ Счёт не найден.")
        return ConversationHandler.END

    amount = invoice.get("Сумма", 0)
    if amount <= 0:
        await query.edit_message_text("✨ Этот счёт уже оплачен.")
        return ConversationHandler.END

    # Store premise info in context
    context.user_data["selected_premise_id"] = premise_id
    context.user_data["selected_invoice"] = invoice

    premise_name = invoice.get("Помещение", "")

    # Get payment details
    payment_details = await sheets_service.get_payment_details()

    # Get meters breakdown - only meters where user is responsible for payment
    user_id = update.effective_user.id
    meters = await sheets_service.get_meters_by_premise(premise_id)
    breakdown_lines = []
    for meter in meters:
        # Only show meters where this user is responsible for payment
        if str(meter.get("ответственный_оплата")) != str(user_id):
            continue
        meter_name = meter.get("Название", "")
        consumption = meter.get("Расход к оплате", 0) or 0
        unit = meter.get("Единица", "")
        tariff = meter.get("Тариф", 0) or 0
        if consumption > 0:
            breakdown_lines.append(f"   📟 {meter_name}: {consumption:.2f} {unit} × {tariff:.2f} руб.")

    breakdown = "\n".join(breakdown_lines) if breakdown_lines else "   (нет данных)"

    await query.edit_message_text(
        f"💳 *Оплата счёта*\n\n"
        f"🏠 Помещение: *{premise_name}*\n"
        f"💰 Сумма к оплате: *{amount:.0f} руб.*\n\n"
        f"📊 *Детализация:*\n{breakdown}\n\n"
        f"🏦 *Реквизиты для оплаты:*\n`{payment_details}`\n\n"
        "📸 После оплаты, пожалуйста, *отправьте фото чека*:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

    return UPLOADING_RECEIPT


async def receive_receipt_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process uploaded receipt photo."""
    user = update.effective_user

    if not update.message.photo:
        await update.message.reply_text(
            "⚠️ Пожалуйста, отправьте *фотографию* чека.\n\n"
            "Можете сделать фото прямо сейчас или выбрать из галереи.",
            reply_markup=get_cancel_keyboard(),
            parse_mode="Markdown"
        )
        return UPLOADING_RECEIPT

    premise_id = context.user_data.get("selected_premise_id")
    invoice = context.user_data.get("selected_invoice")

    if not premise_id or not invoice:
        await update.message.reply_text("❌ Ошибка: данные потеряны. Пожалуйста, начните сначала.")
        return ConversationHandler.END

    # Store photo for confirmation
    context.user_data["receipt_photo"] = update.message.photo[-1]

    premise_name = invoice.get("Помещение", "")
    amount = invoice.get("Сумма", 0) or 0

    await update.message.reply_text(
        f"📋 *Проверьте данные:*\n\n"
        f"🏠 Помещение: *{premise_name}*\n"
        f"💰 Сумма: *{amount:.0f} руб.*\n"
        f"📸 Чек: получен\n\n"
        "Подтвердить оплату?",
        reply_markup=get_edit_confirm_keyboard("payment_new_photo", "payment_confirm"),
        parse_mode="Markdown"
    )

    return CONFIRMING_PAYMENT


async def confirm_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirm and process payment."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    premise_id = context.user_data.get("selected_premise_id")
    invoice = context.user_data.get("selected_invoice")
    photo = context.user_data.get("receipt_photo")

    if not premise_id or not invoice or not photo:
        await query.edit_message_text("❌ Ошибка: данные потеряны. Пожалуйста, начните сначала.")
        return ConversationHandler.END

    # Show loading message
    await query.edit_message_text("⏳ Обрабатываем Вашу оплату...")

    # Get file and download
    file = await photo.get_file()
    photo_bytes = await file.download_as_bytearray()

    # Upload to R2
    receipt_url = await storage_service.upload_receipt(
        file_bytes=bytes(photo_bytes),
        telegram_id=user.id,
        file_id=photo.file_id,
    )

    # Get tenant info
    tenant = await sheets_service.get_tenant(user.id)
    tenant_name = tenant.get("Имя", "") if tenant else ""
    premise_name = invoice.get("Помещение", "")
    amount = invoice.get("Сумма", 0) or 0

    # Process payment (updates meters, saves log, updates invoice status)
    await sheets_service.process_payment(
        premise_id=premise_id,
        premise_name=premise_name,
        telegram_id=user.id,
        tenant_name=tenant_name,
        amount=amount,
        receipt_url=receipt_url,
    )

    # Notify tenant
    await query.edit_message_text(
        f"✅ *Оплата успешно зафиксирована!*\n\n"
        f"🏠 Помещение: {premise_name}\n"
        f"💰 Сумма: *{amount:.0f} руб.*\n"
        f"📸 Чек сохранён\n\n"
        "Спасибо за своевременную оплату! 🙏",
        reply_markup=get_back_keyboard(),
        parse_mode="Markdown"
    )

    # Notify owner
    owner = await sheets_service.get_owner()
    if owner and tenant:
        try:
            await context.bot.send_message(
                chat_id=owner["telegram_id"],
                text=(
                    f"💰 *Получена оплата!*\n\n"
                    f"👤 Арендатор: {tenant_name}\n"
                    f"🏠 Помещение: {premise_name}\n"
                    f"💵 Сумма: *{amount:.0f} руб.*\n"
                    f"📸 [Чек]({receipt_url})"
                ),
                parse_mode="Markdown"
            )
        except Exception:
            pass  # Owner might have blocked the bot

    # Clear user data
    context.user_data.clear()

    return ConversationHandler.END


async def new_photo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Request new photo."""
    query = update.callback_query
    await query.answer()

    invoice = context.user_data.get("selected_invoice")
    if not invoice:
        await query.edit_message_text("❌ Ошибка: данные потеряны. Пожалуйста, начните сначала.")
        return ConversationHandler.END

    await query.edit_message_text(
        "📸 Пожалуйста, отправьте новое фото чека:",
        reply_markup=get_cancel_keyboard()
    )

    return UPLOADING_RECEIPT


async def cancel_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel payment."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "❌ Оплата отменена.\n\n"
        "Вы можете вернуться к оплате в любое время через меню.",
        reply_markup=get_back_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END


def register_payment_handlers(app: Application) -> None:
    """Register payment handlers."""
    # Conversation handler for payment with receipt upload
    payment_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pay_premise_callback, pattern=r"^pay_premise_\d+$")
        ],
        states={
            UPLOADING_RECEIPT: [
                MessageHandler(filters.PHOTO, receive_receipt_photo),
                CallbackQueryHandler(cancel_payment_callback, pattern="^cancel$"),
            ],
            CONFIRMING_PAYMENT: [
                CallbackQueryHandler(confirm_payment_callback, pattern="^payment_confirm$"),
                CallbackQueryHandler(new_photo_callback, pattern="^payment_new_photo$"),
                CallbackQueryHandler(cancel_payment_callback, pattern="^cancel$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_payment_callback, pattern="^cancel$"),
        ],
        allow_reentry=True,
    )

    app.add_handler(payment_conv)
