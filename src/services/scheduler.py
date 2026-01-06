import logging
from datetime import datetime, time

from telegram.ext import Application

from src.services.sheets import sheets_service

logger = logging.getLogger(__name__)


async def send_readings_reminders(app: Application) -> None:
    """Send reminders to tenants who haven't submitted readings this month."""
    logger.info("Running scheduled readings reminder")

    # Check if we're in the reminder period (15-20)
    today = datetime.now().day
    start_day, end_day = await sheets_service.get_readings_period()

    if not (start_day <= today <= end_day):
        logger.info(f"Today ({today}) is not in reminder period ({start_day}-{end_day})")
        return

    tenants = await sheets_service.get_tenants_without_readings()

    if not tenants:
        logger.info("All tenants have submitted readings")
        return

    for tenant in tenants:
        tid = tenant.get("telegram_id")
        meters = tenant.get("meters", [])

        try:
            meters_text = ", ".join(meters) if meters else "Ваши счётчики"

            await app.bot.send_message(
                chat_id=tid,
                text=(
                    f"📊 *Напоминание о показаниях*\n\n"
                    f"Пожалуйста, не забудьте сдать показания счётчиков.\n\n"
                    f"📟 Ожидаем показания: {meters_text}\n\n"
                    "Нажмите кнопку «📊 Сдать показания» в меню бота."
                ),
                parse_mode="Markdown"
            )
            logger.info(f"Sent readings reminder to {tid}")

        except Exception as e:
            logger.error(f"Failed to send readings reminder to {tid}: {e}")


async def process_invoice_push_notifications(app: Application) -> None:
    """Check for invoices needing push notification and send them."""
    logger.debug("Checking for invoice push notifications")

    invoices = await sheets_service.get_invoices_needing_push()

    if not invoices:
        return

    payment_details = await sheets_service.get_payment_details()

    for invoice in invoices:
        premise_id = invoice.get("помещение_id")
        premise_name = invoice.get("Помещение", "")
        responsible_id = invoice.get("ответственный_оплата")
        amount = invoice.get("Сумма", 0) or 0

        if not responsible_id:
            logger.warning(f"No responsible_id for premise {premise_id}")
            await sheets_service.clear_need_push(premise_id)
            continue

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
            await app.bot.send_message(
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
            logger.info(f"Sent invoice notification to {responsible_id} for premise {premise_id}")

        except Exception as e:
            logger.error(f"Failed to send invoice notification to {responsible_id}: {e}")

        # Clear the flag regardless of success (to avoid spam on errors)
        await sheets_service.clear_need_push(premise_id)


async def send_payment_reminders(app: Application) -> None:
    """Send reminders to tenants with unpaid invoices."""
    logger.info("Running scheduled payment reminder")

    tenants = await sheets_service.get_tenants_with_unpaid()

    if not tenants:
        logger.info("No unpaid invoices")
        return

    payment_details = await sheets_service.get_payment_details()

    for tenant in tenants:
        tid = tenant.get("telegram_id")
        total = tenant.get("total", 0)
        premises = tenant.get("premises", [])

        try:
            premises_text = ", ".join(premises) if premises else ""

            await app.bot.send_message(
                chat_id=tid,
                text=(
                    f"💳 *Напоминание об оплате*\n\n"
                    f"💰 К оплате: *{total:.0f} руб.*"
                    + (f"\n🏠 Помещения: {premises_text}" if premises_text else "") + "\n\n"
                    f"🏦 *Реквизиты:*\n`{payment_details}`\n\n"
                    "📸 После оплаты, пожалуйста, отправьте фото чека через бот.\n\n"
                    "Нажмите кнопку «💳 Мои счета» в меню."
                ),
                parse_mode="Markdown"
            )
            logger.info(f"Sent payment reminder to {tid}")

        except Exception as e:
            logger.error(f"Failed to send payment reminder to {tid}: {e}")


def setup_scheduler(app: Application) -> None:
    """Set up scheduled jobs."""
    job_queue = app.job_queue

    if job_queue is None:
        logger.warning("Job queue not available, skipping scheduler setup")
        return

    # Check for invoice push notifications every 5 minutes
    job_queue.run_repeating(
        lambda ctx: process_invoice_push_notifications(app),
        interval=300,  # every 5 minutes
        first=30,  # start after 30 seconds
        name="invoice_push_check",
    )

    # Send readings reminders daily at 10:00 (during the period 15-20)
    job_queue.run_daily(
        lambda ctx: send_readings_reminders(app),
        time=time(hour=10, minute=0),
        name="readings_reminder",
    )

    # Send payment reminders on 1st and 5th of each month at 10:00
    job_queue.run_monthly(
        lambda ctx: send_payment_reminders(app),
        when=time(hour=10, minute=0),
        day=1,
        name="payment_reminder_1",
    )

    job_queue.run_monthly(
        lambda ctx: send_payment_reminders(app),
        when=time(hour=10, minute=0),
        day=5,
        name="payment_reminder_5",
    )

    logger.info("Scheduler jobs configured")
