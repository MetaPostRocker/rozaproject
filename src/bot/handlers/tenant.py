from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src.bot.keyboards import get_cancel_keyboard, get_back_keyboard, get_meters_keyboard, get_edit_confirm_keyboard
from src.services.sheets import sheets_service

# Conversation states
ENTERING_READING = 1
CONFIRMING_READING = 2


async def meter_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle meter selection for readings."""
    query = update.callback_query
    await query.answer()

    # Extract meter_id from callback_data: "meter_123"
    meter_id = int(query.data.split("_")[1])
    meter = await sheets_service.get_meter(meter_id)

    if not meter:
        await query.edit_message_text("❌ Счётчик не найден.")
        return ConversationHandler.END

    # Store meter info in context
    context.user_data["selected_meter"] = meter

    # Get last reading
    last_reading = await sheets_service.get_last_reading_for_meter(meter_id)
    prev_value = last_reading.get("Показание", 0) if last_reading else 0
    context.user_data["prev_value"] = prev_value

    name = meter.get("Название", "")
    premise = meter.get("Помещение", "")
    unit = meter.get("Единица", "")

    await query.edit_message_text(
        f"📟 *Сдача показаний*\n\n"
        f"Счётчик: *{name}*\n"
        f"Помещение: {premise}\n"
        f"Предыдущее показание: *{prev_value} {unit}*\n\n"
        f"📝 Введите текущее показание:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

    return ENTERING_READING


async def receive_reading(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process meter reading input."""
    text = update.message.text.strip()

    try:
        value = float(text.replace(",", "."))
    except ValueError:
        await update.message.reply_text(
            "⚠️ Пожалуйста, введите число.\n\n"
            "Например: `12345` или `123.45`",
            reply_markup=get_cancel_keyboard(),
            parse_mode="Markdown"
        )
        return ENTERING_READING

    meter = context.user_data.get("selected_meter")
    if not meter:
        await update.message.reply_text("❌ Ошибка: счётчик не выбран. Пожалуйста, начните сначала.")
        return ConversationHandler.END

    prev_value = context.user_data.get("prev_value", 0)

    # Validate: current should be >= previous
    if value < prev_value:
        await update.message.reply_text(
            f"⚠️ Введённое показание (*{value}*) меньше предыдущего (*{prev_value}*).\n\n"
            "Пожалуйста, проверьте данные и введите корректное значение:",
            reply_markup=get_cancel_keyboard(),
            parse_mode="Markdown"
        )
        return ENTERING_READING

    # Store value for confirmation
    context.user_data["reading_value"] = value

    # Show confirmation
    unit = meter.get("Единица", "")
    consumption = value - prev_value

    await update.message.reply_text(
        f"📋 *Проверьте данные:*\n\n"
        f"📟 Счётчик: *{meter.get('Название', '')}*\n"
        f"🏠 Помещение: {meter.get('Помещение', '')}\n\n"
        f"📊 Предыдущее показание: {prev_value} {unit}\n"
        f"📊 Новое показание: *{value} {unit}*\n"
        f"📈 Расход: *{consumption:.2f} {unit}*\n\n"
        "Всё верно?",
        reply_markup=get_edit_confirm_keyboard("reading_edit", "reading_confirm"),
        parse_mode="Markdown"
    )

    return CONFIRMING_READING


async def confirm_reading_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirm and save reading."""
    query = update.callback_query
    await query.answer()

    meter = context.user_data.get("selected_meter")
    value = context.user_data.get("reading_value")
    prev_value = context.user_data.get("prev_value", 0)

    if not meter or value is None:
        await query.edit_message_text("❌ Ошибка: данные потеряны. Пожалуйста, начните сначала.")
        return ConversationHandler.END

    # Get tenant info
    user = update.effective_user
    tenant = await sheets_service.get_tenant(user.id)
    tenant_name = tenant.get("Имя", "") if tenant else ""

    # Save reading
    await sheets_service.save_reading(
        meter_id=meter.get("id"),
        meter_name=meter.get("Название", ""),
        premise_id=meter.get("помещение_id", 0),
        premise_name=meter.get("Помещение", ""),
        telegram_id=user.id,
        tenant_name=tenant_name,
        reading=value,
    )

    unit = meter.get("Единица", "")
    consumption = value - prev_value

    await query.edit_message_text(
        f"✅ *Показание успешно сохранено!*\n\n"
        f"📟 Счётчик: {meter.get('Название', '')}\n"
        f"📊 Показание: *{value} {unit}*\n"
        f"📈 Расход: *{consumption:.2f} {unit}*\n\n"
        "Спасибо! Если нужно сдать ещё показания, нажмите кнопку ниже.",
        reply_markup=get_back_keyboard(),
        parse_mode="Markdown"
    )

    # Clear user data
    context.user_data.clear()

    return ConversationHandler.END


async def edit_reading_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Go back to edit reading."""
    query = update.callback_query
    await query.answer()

    meter = context.user_data.get("selected_meter")
    if not meter:
        await query.edit_message_text("❌ Ошибка: данные потеряны. Пожалуйста, начните сначала.")
        return ConversationHandler.END

    prev_value = context.user_data.get("prev_value", 0)
    name = meter.get("Название", "")
    premise = meter.get("Помещение", "")
    unit = meter.get("Единица", "")

    await query.edit_message_text(
        f"📟 *Сдача показаний*\n\n"
        f"Счётчик: *{name}*\n"
        f"Помещение: {premise}\n"
        f"Предыдущее показание: *{prev_value} {unit}*\n\n"
        f"📝 Введите текущее показание:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

    return ENTERING_READING


async def cancel_reading_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel reading submission."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "❌ Сдача показаний отменена.\n\n"
        "Вы можете вернуться в меню, нажав кнопку ниже.",
        reply_markup=get_back_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END


def register_tenant_handlers(app: Application) -> None:
    """Register tenant command handlers."""
    # Conversation handler for meter readings
    readings_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(meter_selected_callback, pattern=r"^meter_\d+$")
        ],
        states={
            ENTERING_READING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_reading),
                CallbackQueryHandler(cancel_reading_callback, pattern="^cancel$"),
            ],
            CONFIRMING_READING: [
                CallbackQueryHandler(confirm_reading_callback, pattern="^reading_confirm$"),
                CallbackQueryHandler(edit_reading_callback, pattern="^reading_edit$"),
                CallbackQueryHandler(cancel_reading_callback, pattern="^cancel$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_reading_callback, pattern="^cancel$"),
            CallbackQueryHandler(cancel_reading_callback, pattern="^back_main$"),
        ],
        allow_reentry=True,  # Allow starting new conversation even if previous wasn't finished
    )

    app.add_handler(readings_conv)
