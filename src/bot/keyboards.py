from typing import List, Dict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton


# === Reply Keyboards (постоянные кнопки внизу) ===

def get_tenant_reply_keyboard() -> ReplyKeyboardMarkup:
    """Persistent reply keyboard for tenant."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📊 Сдать показания"), KeyboardButton("💳 Мои счета")],
            [KeyboardButton("🔧 Мои счетчики")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def get_owner_reply_keyboard() -> ReplyKeyboardMarkup:
    """Persistent reply keyboard for owner."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📊 Статус показаний"), KeyboardButton("💰 Неоплаченные")],
            [KeyboardButton("📨 Выставить счёт"), KeyboardButton("🔔 Напоминания")],
            [KeyboardButton("⚙️ Управление")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# === Главное меню (Inline) ===

def get_tenant_main_menu(has_readings: bool = True, has_invoices: bool = True) -> InlineKeyboardMarkup:
    """Inline main menu for tenant."""
    buttons = []
    if has_readings:
        buttons.append([InlineKeyboardButton("📊 Сдать показания", callback_data="menu_readings")])
    if has_invoices:
        buttons.append([InlineKeyboardButton("💳 Мои счета", callback_data="menu_invoices")])
    buttons.append([InlineKeyboardButton("🔧 Мои счетчики", callback_data="menu_my_meters")])
    return InlineKeyboardMarkup(buttons)


def get_owner_main_menu() -> InlineKeyboardMarkup:
    """Inline main menu for owner."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Статус показаний", callback_data="owner_readings_status")],
        [InlineKeyboardButton("💰 Неоплаченные счета", callback_data="owner_unpaid")],
        [InlineKeyboardButton("📨 Выставить счёт", callback_data="owner_issue_invoice")],
        [InlineKeyboardButton("🔔 Напоминания", callback_data="owner_reminders")],
        [InlineKeyboardButton("⚙️ Управление", callback_data="owner_management")],
    ])


def get_owner_management_menu() -> InlineKeyboardMarkup:
    """Management submenu for owner."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Добавить помещение", callback_data="mgmt_add_premise")],
        [InlineKeyboardButton("📟 Добавить счетчик", callback_data="mgmt_add_meter")],
        [InlineKeyboardButton("📋 Список помещений", callback_data="mgmt_list_premises")],
        [InlineKeyboardButton("📋 Список счетчиков", callback_data="mgmt_list_meters")],
        [InlineKeyboardButton("💰 Тарифы", callback_data="mgmt_tariffs")],
        [InlineKeyboardButton("« Назад", callback_data="owner_back_main")],
    ])


def get_tariffs_keyboard(tariffs: List[Dict]) -> InlineKeyboardMarkup:
    """Keyboard with tariff buttons for editing."""
    buttons = []
    for t in tariffs:
        tariff_type = t.get("Тип", "")
        tariff_value = t.get("Тариф", 0)
        label = f"💰 {tariff_type}: {tariff_value:.2f} руб."
        buttons.append([InlineKeyboardButton(label, callback_data=f"edit_tariff_{tariff_type}")])
    buttons.append([InlineKeyboardButton("« Назад", callback_data="owner_management")])
    return InlineKeyboardMarkup(buttons)


def get_owner_reminders_menu() -> InlineKeyboardMarkup:
    """Reminders submenu for owner."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Напомнить о показаниях", callback_data="remind_readings")],
        [InlineKeyboardButton("💳 Напомнить об оплате", callback_data="remind_payments")],
        [InlineKeyboardButton("« Назад", callback_data="owner_back_main")],
    ])


# === Выбор счетчика для показаний ===

def get_meters_keyboard(meters: List[Dict]) -> InlineKeyboardMarkup:
    """Keyboard with meter buttons for readings submission."""
    buttons = []
    for meter in meters:
        meter_id = meter.get("id")
        name = meter.get("Название", "Unknown")
        premise = meter.get("Помещение", "")
        label = f"{name} ({premise})" if premise else name
        buttons.append([InlineKeyboardButton(label, callback_data=f"meter_{meter_id}")])
    buttons.append([InlineKeyboardButton("« Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


# === Выбор счета для оплаты ===

def get_invoices_keyboard(invoices: List[Dict]) -> InlineKeyboardMarkup:
    """Keyboard with invoice buttons for payment."""
    buttons = []
    for inv in invoices:
        inv_id = inv.get("id")
        amount = inv.get("Сумма", 0)
        desc = inv.get("Описание", "")[:20]
        label = f"{amount} руб - {desc}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"pay_invoice_{inv_id}")])
    buttons.append([InlineKeyboardButton("« Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


# === Выбор помещения ===

def get_premises_keyboard(premises: List[Dict], callback_prefix: str = "premise") -> InlineKeyboardMarkup:
    """Keyboard with premise buttons."""
    buttons = []
    for p in premises:
        p_id = p.get("id")
        name = p.get("Название", "Unknown")
        buttons.append([InlineKeyboardButton(name, callback_data=f"{callback_prefix}_{p_id}")])
    buttons.append([InlineKeyboardButton("« Назад", callback_data="owner_back_main")])
    return InlineKeyboardMarkup(buttons)


# === Выбор арендатора ===

def get_tenants_keyboard(tenants: List[Dict], callback_prefix: str = "tenant") -> InlineKeyboardMarkup:
    """Keyboard with tenant buttons."""
    buttons = []
    for t in tenants:
        tid = t.get("telegram_id")
        name = t.get("Имя", "Unknown")
        buttons.append([InlineKeyboardButton(name, callback_data=f"{callback_prefix}_{tid}")])
    buttons.append([InlineKeyboardButton("« Назад", callback_data="owner_back_main")])
    return InlineKeyboardMarkup(buttons)


# === Кнопки действий ===

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Cancel button."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ])


def get_back_keyboard(callback_data: str = "back_main") -> InlineKeyboardMarkup:
    """Back button."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("« Назад", callback_data=callback_data)]
    ])


def get_confirm_keyboard(confirm_data: str, cancel_data: str = "cancel") -> InlineKeyboardMarkup:
    """Confirm/Cancel buttons."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=confirm_data),
            InlineKeyboardButton("✏️ Изменить", callback_data=cancel_data),
        ]
    ])


def get_edit_confirm_keyboard(edit_data: str, confirm_data: str) -> InlineKeyboardMarkup:
    """Edit/Confirm buttons for data confirmation step."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Изменить", callback_data=edit_data),
            InlineKeyboardButton("✅ Подтвердить", callback_data=confirm_data),
        ]
    ])


def get_upload_receipt_keyboard(invoice_id: int) -> InlineKeyboardMarkup:
    """Button to upload receipt for specific invoice."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Отправить чек об оплате", callback_data=f"upload_receipt_{invoice_id}")]
    ])


# === Выставление счетов ===

def get_draft_invoices_keyboard(invoices: List[Dict]) -> InlineKeyboardMarkup:
    """Keyboard with draft invoices to issue."""
    buttons = []
    for inv in invoices:
        premise_id = inv.get("помещение_id")
        premise_name = inv.get("Помещение", "")
        amount = inv.get("Сумма", 0) or 0
        responsible = inv.get("Имя_оплата", "")
        label = f"{premise_name}: {amount:.0f} руб ({responsible})"
        buttons.append([InlineKeyboardButton(label, callback_data=f"issue_invoice_{premise_id}")])
    buttons.append([InlineKeyboardButton("« Назад", callback_data="owner_back_main")])
    return InlineKeyboardMarkup(buttons)


# === Напоминания ===

def get_tenants_to_remind_keyboard(tenants: List[Dict], remind_type: str) -> InlineKeyboardMarkup:
    """Keyboard with tenants to send reminders."""
    buttons = []
    for t in tenants:
        tid = t.get("telegram_id")
        name = t.get("name", t.get("Имя", "Unknown"))
        buttons.append([InlineKeyboardButton(name, callback_data=f"remind_{remind_type}_{tid}")])
    buttons.append([InlineKeyboardButton("Напомнить всем", callback_data=f"remind_{remind_type}_all")])
    buttons.append([InlineKeyboardButton("« Назад", callback_data="owner_reminders")])
    return InlineKeyboardMarkup(buttons)
