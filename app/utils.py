from __future__ import annotations
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime
import re

def today_yyyymmdd() -> str:
    return datetime.now().strftime('%Y%m%d')

def month_key() -> str:
    return datetime.now().strftime('%Y-%m')

def clean_text(v) -> str:
    if v is None:
        return ''
    s = str(v).strip()
    if s.endswith('.0') and s[:-2].isdigit():
        s = s[:-2]
    return s

def to_decimal(v) -> Decimal:
    if v is None or v == '':
        return Decimal('0.00')
    s = str(v).replace(',', '').replace('ريال', '').strip()
    try:
        return Decimal(s).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return Decimal('0.00')

def money(v) -> str:
    return f"{to_decimal(v):,.2f}"

def calc_net(basic, housing, other, deductions) -> Decimal:
    return (to_decimal(basic) + to_decimal(housing) + to_decimal(other) - to_decimal(deductions)).quantize(Decimal('0.01'))

def amount_fixed(v, digits: int = 10) -> str:
    d = to_decimal(v)
    cents = int((d * 100).to_integral_value(rounding=ROUND_HALF_UP))
    whole = cents // 100
    frac = cents % 100
    return f"{whole:0{digits}d},{frac:02d}"

def safe_filename(prefix='WPS') -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

def is_valid_iban(iban: str) -> bool:
    s = clean_text(iban).replace(' ', '').upper()
    return s.startswith('SA') and len(s) == 24 and s[2:].isdigit()

def is_valid_gov_id(gov_id: str) -> bool:
    s = clean_text(gov_id)
    return bool(re.fullmatch(r'\d{7,15}', s))
