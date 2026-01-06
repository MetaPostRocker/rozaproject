from __future__ import annotations

import asyncio
import time
from datetime import datetime
from functools import partial
from typing import Optional, List, Dict, Any

import gspread
from google.oauth2.service_account import Credentials

from src.config import settings


class SheetsService:
    """Service for interacting with Google Sheets.

    Includes in-memory cache with TTL to reduce API calls.
    """

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    # Cache TTL in seconds (2 minutes for reads)
    CACHE_TTL = 120

    def __init__(self):
        self._client: Optional[gspread.Client] = None
        self._spreadsheet: Optional[gspread.Spreadsheet] = None
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _get_cached(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry["time"] < self.CACHE_TTL:
                return entry["data"]
            del self._cache[key]
        return None

    def _set_cached(self, key: str, data: Any) -> None:
        """Set value in cache with current timestamp."""
        self._cache[key] = {"data": data, "time": time.time()}

    def invalidate_cache(self, pattern: Optional[str] = None) -> None:
        """Invalidate cache entries.

        If pattern is provided, only keys containing the pattern are removed.
        Otherwise, all cache is cleared.
        """
        if pattern is None:
            self._cache.clear()
        else:
            keys_to_delete = [k for k in self._cache if pattern in k]
            for k in keys_to_delete:
                del self._cache[k]

    def _get_client(self) -> gspread.Client:
        if self._client is None:
            creds = Credentials.from_service_account_info(
                settings.google_credentials, scopes=self.SCOPES
            )
            self._client = gspread.authorize(creds)
        return self._client

    def _get_spreadsheet(self) -> gspread.Spreadsheet:
        if self._spreadsheet is None:
            client = self._get_client()
            self._spreadsheet = client.open_by_key(settings.google_sheets_id)
        return self._spreadsheet

    async def _run_sync(self, func, *args, **kwargs):
        """Run synchronous gspread calls in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    def _is_true(self, value) -> bool:
        """Check if value is truthy (TRUE, True, true, 1, etc)."""
        if value is True:
            return True
        if isinstance(value, str):
            return value.upper() == "TRUE"
        return False

    # ============================================================
    # Помещения
    # Columns: id, Название, Адрес
    # ============================================================

    async def get_all_premises(self) -> List[Dict]:
        """Get all premises (cached)."""
        cached = self._get_cached("premises")
        if cached is not None:
            return cached

        def _get():
            sheet = self._get_spreadsheet().worksheet("Помещения")
            return sheet.get_all_records()

        result = await self._run_sync(_get)
        self._set_cached("premises", result)
        return result

    async def get_premise(self, premise_id: int) -> Optional[Dict]:
        """Get premise by id (uses cached premises)."""
        premises = await self.get_all_premises()
        for record in premises:
            if str(record.get("id")) == str(premise_id):
                return record
        return None

    async def add_premise(self, name: str, address: str = "") -> int:
        """Add new premise. Returns new id."""
        def _add():
            sheet = self._get_spreadsheet().worksheet("Помещения")
            records = sheet.get_all_records()
            new_id = max([r.get("id", 0) for r in records], default=0) + 1
            sheet.append_row([new_id, name, address])
            return new_id

        result = await self._run_sync(_add)
        self.invalidate_cache("premises")
        return result

    # ============================================================
    # Арендаторы
    # Columns: telegram_id, Имя, Телефон, is_owner
    # ============================================================

    async def _get_all_tenants_raw(self) -> List[Dict]:
        """Get all tenants including owner (cached)."""
        cached = self._get_cached("tenants_raw")
        if cached is not None:
            return cached

        def _get():
            sheet = self._get_spreadsheet().worksheet("Арендаторы")
            return sheet.get_all_records()

        result = await self._run_sync(_get)
        self._set_cached("tenants_raw", result)
        return result

    async def get_tenant(self, telegram_id: int) -> Optional[Dict]:
        """Get tenant by telegram_id (uses cached tenants)."""
        tenants = await self._get_all_tenants_raw()
        for record in tenants:
            if str(record.get("telegram_id")) == str(telegram_id):
                return record
        return None

    async def get_all_tenants(self) -> List[Dict]:
        """Get all tenants excluding owner (uses cached tenants)."""
        tenants = await self._get_all_tenants_raw()
        return [r for r in tenants if not self._is_true(r.get("is_owner"))]

    async def get_owner(self) -> Optional[Dict]:
        """Get owner record (uses cached tenants)."""
        tenants = await self._get_all_tenants_raw()
        for record in tenants:
            if self._is_true(record.get("is_owner")):
                return record
        return None

    async def add_tenant(self, telegram_id: int, name: str, phone: str = "") -> None:
        """Add new tenant."""
        def _add():
            sheet = self._get_spreadsheet().worksheet("Арендаторы")
            sheet.append_row([telegram_id, name, phone, "FALSE"])

        await self._run_sync(_add)
        self.invalidate_cache("tenants")

    # ============================================================
    # Счетчики
    # Columns: id, помещение_id, Помещение, Название, Тип, Единица, Тариф,
    #          ответственный_показания, Имя_показания,
    #          ответственный_оплата, Имя_оплата,
    #          Последнее показание, Дата посл. показания,
    #          Оплаченное показание, Дата посл. оплаты,
    #          Расход к оплате, Сумма к оплате
    # ============================================================

    async def get_all_meters(self) -> List[Dict]:
        """Get all meters (cached)."""
        cached = self._get_cached("meters")
        if cached is not None:
            return cached

        def _get():
            sheet = self._get_spreadsheet().worksheet("Счетчики")
            return sheet.get_all_records()

        result = await self._run_sync(_get)
        self._set_cached("meters", result)
        return result

    async def get_meter(self, meter_id: int) -> Optional[Dict]:
        """Get meter by id (uses cached meters)."""
        meters = await self.get_all_meters()
        for record in meters:
            if str(record.get("id")) == str(meter_id):
                return record
        return None

    async def get_meters_for_readings(self, telegram_id: int) -> List[Dict]:
        """Get meters where user is responsible for readings (uses cached meters)."""
        meters = await self.get_all_meters()
        return [
            r for r in meters
            if str(r.get("ответственный_показания")) == str(telegram_id)
        ]

    async def get_meters_for_payment(self, telegram_id: int) -> List[Dict]:
        """Get meters where user is responsible for payment (uses cached meters)."""
        meters = await self.get_all_meters()
        return [
            r for r in meters
            if str(r.get("ответственный_оплата")) == str(telegram_id)
        ]

    async def get_meters_by_premise(self, premise_id: int) -> List[Dict]:
        """Get all meters for a premise (uses cached meters)."""
        meters = await self.get_all_meters()
        return [r for r in meters if str(r.get("помещение_id")) == str(premise_id)]

    async def add_meter(
        self,
        premise_id: int,
        premise_name: str,
        name: str,
        meter_type: str,
        unit: str,
        responsible_readings: int,
        responsible_readings_name: str,
        responsible_payment: int,
        responsible_payment_name: str,
    ) -> int:
        """Add new meter. Returns new id.

        Note: Columns Тариф, Расход к оплате, Сумма к оплате are formula-based
        in Google Sheets and should NOT be written by the bot.
        """
        def _add():
            sheet = self._get_spreadsheet().worksheet("Счетчики")
            records = sheet.get_all_records()
            new_id = max([r.get("id", 0) for r in records], default=0) + 1
            # Columns: id, помещение_id, Помещение, Название, Тип, Единица, Тариф (формула),
            #          ответственный_показания, Имя_показания,
            #          ответственный_оплата, Имя_оплата,
            #          Последнее показание, Дата посл. показания,
            #          Оплаченное показание, Дата посл. оплаты,
            #          Расход к оплате (формула), Сумма к оплате (формула)
            #
            # We only write up to column 15 (Дата посл. оплаты).
            # Columns 7 (Тариф), 16 (Расход к оплате), 17 (Сумма к оплате)
            # are calculated by formulas in Google Sheets.
            sheet.append_row([
                new_id,
                premise_id,
                premise_name,
                name,
                meter_type,
                unit,
                "",  # Тариф - will be filled by formula from Настройки
                responsible_readings,
                responsible_readings_name,
                responsible_payment,
                responsible_payment_name,
                0,   # Последнее показание
                "",  # Дата посл. показания
                0,   # Оплаченное показание
                "",  # Дата посл. оплаты
                # Columns 16-17 (Расход к оплате, Сумма к оплате) - formulas will auto-fill
            ])
            return new_id

        result = await self._run_sync(_add)
        self.invalidate_cache("meters")
        return result

    async def update_meter_last_reading(self, meter_id: int, reading: float) -> None:
        """Update last reading and date for a meter.

        Note: Columns Расход к оплате (16) and Сумма к оплате (17) are formula-based
        in Google Sheets and recalculate automatically.
        """
        def _update():
            sheet = self._get_spreadsheet().worksheet("Счетчики")
            records = sheet.get_all_records()
            for i, record in enumerate(records, start=2):
                if str(record.get("id")) == str(meter_id):
                    # Column L = Последнее показание (12)
                    # Column M = Дата посл. показания (13)
                    # Batch update (1 API call instead of 2)
                    sheet.update(f"L{i}:M{i}", [[reading, datetime.now().strftime("%Y-%m-%d")]])
                    break

        await self._run_sync(_update)
        self.invalidate_cache("meters")

    async def update_meter_paid_reading(self, meter_id: int) -> Dict:
        """Mark current reading as paid. Returns meter info with payment amount.

        Note: Columns Расход к оплате (16) and Сумма к оплате (17) are formula-based
        in Google Sheets. When Оплаченное показание is updated, formulas will
        automatically recalculate to show 0 (or new consumption).
        """
        def _update():
            sheet = self._get_spreadsheet().worksheet("Счетчики")
            records = sheet.get_all_records()
            for i, record in enumerate(records, start=2):
                if str(record.get("id")) == str(meter_id):
                    last_reading = record.get("Последнее показание", 0) or 0

                    # Read current values from formula columns (for return info)
                    consumption = record.get("Расход к оплате", 0) or 0
                    amount = record.get("Сумма к оплате", 0) or 0

                    # Column N = Оплаченное показание (14)
                    # Column O = Дата посл. оплаты (15)
                    # Batch update (1 API call instead of 2)
                    sheet.update(f"N{i}:O{i}", [[last_reading, datetime.now().strftime("%Y-%m-%d")]])

                    return {
                        "meter": record,
                        "consumption": consumption,
                        "amount": amount,
                    }
            return None

        result = await self._run_sync(_update)
        self.invalidate_cache("meters")
        return result

    # ============================================================
    # Показания
    # Columns: Дата, счетчик_id, Счетчик, помещение_id, Помещение,
    #          telegram_id, Имя, Показание
    # ============================================================

    async def _get_all_readings(self) -> List[Dict]:
        """Get all readings (cached)."""
        cached = self._get_cached("readings")
        if cached is not None:
            return cached

        def _get():
            sheet = self._get_spreadsheet().worksheet("Показания")
            return sheet.get_all_records()

        result = await self._run_sync(_get)
        self._set_cached("readings", result)
        return result

    async def get_last_reading_for_meter(self, meter_id: int) -> Optional[Dict]:
        """Get last reading for a specific meter (uses cached readings)."""
        all_readings = await self._get_all_readings()
        matching = [
            r for r in all_readings
            if str(r.get("счетчик_id")) == str(meter_id)
        ]
        if matching:
            return matching[-1]
        return None

    async def save_reading(
        self,
        meter_id: int,
        meter_name: str,
        premise_id: int,
        premise_name: str,
        telegram_id: int,
        tenant_name: str,
        reading: float,
    ) -> int:
        """Save a new reading and update meter's last reading."""
        def _save():
            sheet = self._get_spreadsheet().worksheet("Показания")
            row = [
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                meter_id,
                meter_name,
                premise_id,
                premise_name,
                telegram_id,
                tenant_name,
                reading,
            ]
            sheet.append_row(row)
            return sheet.row_count

        # Save to log
        result = await self._run_sync(_save)

        # Invalidate readings cache
        self.invalidate_cache("readings")

        # Update meter's last reading
        await self.update_meter_last_reading(meter_id, reading)

        return result

    async def get_readings_for_meter(self, meter_id: int) -> List[Dict]:
        """Get all readings for a meter (uses cached readings)."""
        all_readings = await self._get_all_readings()
        return [r for r in all_readings if str(r.get("счетчик_id")) == str(meter_id)]

    async def get_current_month_readings_for_meter(self, meter_id: int) -> List[Dict]:
        """Get readings for current month for a meter (uses cached readings)."""
        readings_map = await self._get_current_month_meter_readings_map()
        return readings_map.get(str(meter_id), [])

    # ============================================================
    # Счета (актуальный долг по помещению)
    # Columns: A=помещение_id, B=Помещение, C=ответственный_оплата, D=Имя_оплата,
    #          E=Сумма (формула), F=Выставленная сумма, G=Статус (формула),
    #          H=need_push, I=Дата последней оплаты, J=Выставить (чекбокс)
    # ============================================================

    async def _get_all_invoices(self) -> List[Dict]:
        """Get all invoices with row numbers (cached)."""
        cached = self._get_cached("invoices")
        if cached is not None:
            return cached

        def _get():
            sheet = self._get_spreadsheet().worksheet("Счета")
            records = sheet.get_all_records()
            result = []
            for i, record in enumerate(records, start=2):
                record["_row"] = i
                result.append(record)
            return result

        result = await self._run_sync(_get)
        self._set_cached("invoices", result)
        return result

    async def get_invoice_for_premise(self, premise_id: int) -> Optional[Dict]:
        """Get current invoice for a premise (uses cached invoices)."""
        invoices = await self._get_all_invoices()
        for record in invoices:
            if str(record.get("помещение_id")) == str(premise_id):
                return record
        return None

    async def get_invoices_for_tenant(self, telegram_id: int) -> List[Dict]:
        """Get all invoices where tenant is responsible for payment (uses cached invoices)."""
        invoices = await self._get_all_invoices()
        return [
            r for r in invoices
            if str(r.get("ответственный_оплата")) == str(telegram_id)
        ]

    async def get_unpaid_invoices_for_tenant(self, telegram_id: int) -> List[Dict]:
        """Get unpaid invoices for a tenant (only with status 'Не оплачен')."""
        invoices = await self.get_invoices_for_tenant(telegram_id)
        return [
            inv for inv in invoices
            if inv.get("Статус") == "Не оплачен" and (inv.get("Сумма", 0) or 0) > 0
        ]

    async def get_all_unpaid_invoices(self) -> List[Dict]:
        """Get all invoices with status 'Не оплачен' (uses cached invoices)."""
        invoices = await self._get_all_invoices()
        return [
            r for r in invoices
            if r.get("Статус") == "Не оплачен" and (r.get("Сумма", 0) or 0) > 0
        ]

    async def get_draft_invoices(self) -> List[Dict]:
        """Get all invoices with status 'Черновик' (uses cached invoices)."""
        invoices = await self._get_all_invoices()
        return [
            r for r in invoices
            if r.get("Статус") == "Черновик" and (r.get("Сумма", 0) or 0) > 0
        ]

    async def issue_invoice(self, premise_id: int) -> bool:
        """Issue invoice: copy Сумма to Выставленная сумма.

        Note: Does NOT set need_push flag because notification is sent
        immediately by the bot in issue_invoice_callback.
        """
        def _issue():
            sheet = self._get_spreadsheet().worksheet("Счета")
            records = sheet.get_all_records()
            for i, record in enumerate(records, start=2):
                if str(record.get("помещение_id")) == str(premise_id):
                    current_amount = record.get("Сумма", 0) or 0
                    sheet.update_cell(i, 6, current_amount)
                    return True
            return False

        result = await self._run_sync(_issue)
        if result:
            self.invalidate_cache("invoices")
        return result

    async def update_invoice_amount(self, premise_id: int) -> None:
        """Recalculate invoice amount from meters for a premise."""
        def _update():
            # Get all meters for this premise
            meters_sheet = self._get_spreadsheet().worksheet("Счетчики")
            meters = meters_sheet.get_all_records()

            total = 0
            responsible_id = None
            responsible_name = ""
            premise_name = ""

            for meter in meters:
                if str(meter.get("помещение_id")) == str(premise_id):
                    total += meter.get("Сумма к оплате", 0) or 0
                    if not responsible_id:
                        responsible_id = meter.get("ответственный_оплата")
                        responsible_name = meter.get("Имя_оплата", "")
                        premise_name = meter.get("Помещение", "")

            # Update or create invoice
            invoices_sheet = self._get_spreadsheet().worksheet("Счета")
            records = invoices_sheet.get_all_records()

            found = False
            for i, record in enumerate(records, start=2):
                if str(record.get("помещение_id")) == str(premise_id):
                    invoices_sheet.update_cell(i, 5, total)
                    found = True
                    break

            if not found and total > 0:
                invoices_sheet.append_row([
                    premise_id,
                    premise_name,
                    responsible_id,
                    responsible_name,
                    total,
                    "Не оплачен",
                    "",
                ])

        await self._run_sync(_update)
        self.invalidate_cache("invoices")

    async def mark_invoice_paid(self, premise_id: int) -> None:
        """Mark invoice as paid: zero out Выставленная сумма, update date."""
        def _mark():
            sheet = self._get_spreadsheet().worksheet("Счета")
            records = sheet.get_all_records()
            for i, record in enumerate(records, start=2):
                if str(record.get("помещение_id")) == str(premise_id):
                    # Column F = Выставленная сумма (6) - set to 0
                    # Column I = Дата последней оплаты (9)
                    # Batch update (1 API call instead of 2)
                    sheet.update(f"F{i}", [[0]])
                    sheet.update(f"I{i}", [[datetime.now().strftime("%Y-%m-%d")]])
                    break

        await self._run_sync(_mark)
        self.invalidate_cache("invoices")

    async def get_invoices_needing_push(self) -> List[Dict]:
        """Get all invoices where need_push = 1 (uses cached invoices)."""
        invoices = await self._get_all_invoices()
        result = []
        for record in invoices:
            need_push = record.get("need_push", 0)
            if need_push == 1 or need_push == "1" or need_push is True:
                result.append(record)
        return result

    async def clear_need_push(self, premise_id: int) -> None:
        """Clear need_push flag after sending notification."""
        def _clear():
            sheet = self._get_spreadsheet().worksheet("Счета")
            records = sheet.get_all_records()
            for i, record in enumerate(records, start=2):
                if str(record.get("помещение_id")) == str(premise_id):
                    sheet.update_cell(i, 8, 0)
                    break

        await self._run_sync(_clear)
        self.invalidate_cache("invoices")

    # ============================================================
    # Оплаты (лог)
    # Columns: Дата, помещение_id, Помещение, ответственный_оплата,
    #          Имя_оплата, Сумма, Ссылка на чек
    # ============================================================

    async def save_payment(
        self,
        premise_id: int,
        premise_name: str,
        telegram_id: int,
        tenant_name: str,
        amount: float,
        receipt_url: str,
    ) -> None:
        """Save payment record to log."""
        def _save():
            sheet = self._get_spreadsheet().worksheet("Оплаты")
            sheet.append_row([
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                premise_id,
                premise_name,
                telegram_id,
                tenant_name,
                amount,
                receipt_url,
            ])
        return await self._run_sync(_save)

    async def process_payment(
        self,
        premise_id: int,
        premise_name: str,
        telegram_id: int,
        tenant_name: str,
        amount: float,
        receipt_url: str,
    ) -> None:
        """
        Process payment for a premise:
        1. Mark each meter as paid (update Оплаченное показание in Счетчики)
        2. Save payment log
        3. Update invoice status (NOT the amount - it's a formula)

        Optimized: batch updates all meters in single API call instead of N calls.
        """
        def _mark_meters_paid():
            sheet = self._get_spreadsheet().worksheet("Счетчики")
            records = sheet.get_all_records()
            today = datetime.now().strftime("%Y-%m-%d")

            # Collect all updates for this premise
            updates = []
            for i, record in enumerate(records, start=2):
                if str(record.get("помещение_id")) == str(premise_id):
                    last_reading = record.get("Последнее показание", 0) or 0
                    # Column N = Оплаченное показание (14), Column O = Дата посл. оплаты (15)
                    updates.append({
                        "range": f"N{i}:O{i}",
                        "values": [[last_reading, today]]
                    })

            # Batch update all meters at once
            if updates:
                sheet.batch_update(updates)

        await self._run_sync(_mark_meters_paid)
        self.invalidate_cache("meters")

        # Save payment log
        await self.save_payment(
            premise_id=premise_id,
            premise_name=premise_name,
            telegram_id=telegram_id,
            tenant_name=tenant_name,
            amount=amount,
            receipt_url=receipt_url,
        )

        # Update invoice status only (don't touch Сумма - it's a formula)
        await self.mark_invoice_paid(premise_id)

    # ============================================================
    # Настройки
    # Columns: Ключ, Значение
    # ============================================================

    async def _get_all_settings(self) -> Dict[str, str]:
        """Get all settings as a dict (cached)."""
        cached = self._get_cached("settings")
        if cached is not None:
            return cached

        def _get():
            sheet = self._get_spreadsheet().worksheet("Настройки")
            records = sheet.get_all_records()
            return {r.get("Ключ"): r.get("Значение") for r in records if r.get("Ключ")}

        result = await self._run_sync(_get)
        self._set_cached("settings", result)
        return result

    async def get_setting(self, key: str) -> Optional[str]:
        """Get setting value by key (uses cached settings)."""
        settings_dict = await self._get_all_settings()
        return settings_dict.get(key)

    async def get_payment_details(self) -> str:
        """Get payment details from settings (uses cached settings)."""
        details = await self.get_setting("payment_details")
        return details or "Реквизиты не указаны"

    async def get_readings_period(self) -> tuple:
        """Get readings reminder period (start_day, end_day). Uses cached settings."""
        settings_dict = await self._get_all_settings()
        start = settings_dict.get("readings_start_day")
        end = settings_dict.get("readings_end_day")
        return (int(start) if start else 15, int(end) if end else 20)

    # ============================================================
    # Тарифы
    # Columns: Тип, Тариф
    # ============================================================

    async def get_tariffs(self) -> List[Dict]:
        """Get all tariffs from Тарифы sheet (cached)."""
        cached = self._get_cached("tariffs")
        if cached is not None:
            return cached

        def _get():
            sheet = self._get_spreadsheet().worksheet("Тарифы")
            records = sheet.get_all_records()
            result = []
            for i, record in enumerate(records, start=2):
                result.append({
                    "_row": i,
                    "Тип": record.get("Тип", ""),
                    "Тариф": record.get("Тариф", 0) or 0,
                })
            return result

        result = await self._run_sync(_get)
        self._set_cached("tariffs", result)
        return result

    async def get_tariff_by_type(self, tariff_type: str) -> Optional[Dict]:
        """Get tariff by type name (uses cached tariffs)."""
        tariffs = await self.get_tariffs()
        for t in tariffs:
            if t.get("Тип") == tariff_type:
                return t
        return None

    async def update_tariff(self, tariff_type: str, new_value: float) -> bool:
        """Update tariff value by type name."""
        def _update():
            sheet = self._get_spreadsheet().worksheet("Тарифы")
            records = sheet.get_all_records()
            for i, record in enumerate(records, start=2):
                if record.get("Тип") == tariff_type:
                    sheet.update_cell(i, 2, new_value)
                    return True
            return False

        result = await self._run_sync(_update)
        if result:
            self.invalidate_cache("tariffs")
        return result

    # ============================================================
    # Агрегация для статусов
    # ============================================================

    async def _get_current_month_meter_readings_map(self) -> Dict[str, List[Dict]]:
        """Get map of meter_id -> readings for current month (cached).

        Used by both get_readings_status and get_tenants_without_readings
        to avoid duplicate API calls.
        """
        cache_key = f"readings_map_{datetime.now().strftime('%Y-%m')}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        all_readings = await self._get_all_readings()
        current_month = datetime.now().strftime("%Y-%m")

        # Group readings by meter_id for current month
        readings_by_meter: Dict[str, List[Dict]] = {}
        for r in all_readings:
            if str(r.get("Дата", "")).startswith(current_month):
                meter_id = str(r.get("счетчик_id", ""))
                if meter_id not in readings_by_meter:
                    readings_by_meter[meter_id] = []
                readings_by_meter[meter_id].append(r)

        self._set_cached(cache_key, readings_by_meter)
        return readings_by_meter

    async def get_readings_status(self) -> List[Dict]:
        """Get readings status for all meters (who submitted this month).

        Fully cached: uses cached meters and cached readings map.
        """
        meters = await self.get_all_meters()
        readings_by_meter = await self._get_current_month_meter_readings_map()

        result = []
        for meter in meters:
            meter_id = str(meter.get("id", ""))
            meter_readings = readings_by_meter.get(meter_id, [])
            result.append({
                "meter": meter,
                "has_readings": len(meter_readings) > 0,
                "readings_count": len(meter_readings),
            })
        return result

    async def get_tenants_without_readings(self) -> List[Dict]:
        """Get list of tenants who haven't submitted readings this month.

        Fully cached: uses cached meters and cached readings map.
        """
        meters = await self.get_all_meters()
        readings_by_meter = await self._get_current_month_meter_readings_map()

        # Find tenants with meters without readings
        tenants_to_remind = {}
        for meter in meters:
            meter_id = str(meter.get("id", ""))
            if meter_id not in readings_by_meter:
                tid = meter.get("ответственный_показания")
                if tid and tid not in tenants_to_remind:
                    tenants_to_remind[tid] = {
                        "telegram_id": tid,
                        "name": meter.get("Имя_показания", ""),
                        "meters": []
                    }
                if tid:
                    tenants_to_remind[tid]["meters"].append(meter.get("Название", ""))

        return list(tenants_to_remind.values())

    async def get_tenants_with_unpaid(self) -> List[Dict]:
        """Get list of tenants with unpaid invoices."""
        invoices = await self.get_all_unpaid_invoices()

        tenants_map = {}
        for inv in invoices:
            tid = inv.get("ответственный_оплата")
            if tid and tid not in tenants_map:
                tenants_map[tid] = {
                    "telegram_id": tid,
                    "name": inv.get("Имя_оплата", ""),
                    "total": 0,
                    "premises": []
                }
            if tid:
                tenants_map[tid]["total"] += inv.get("Сумма", 0) or 0
                tenants_map[tid]["premises"].append(inv.get("Помещение", ""))

        return list(tenants_map.values())


sheets_service = SheetsService()
