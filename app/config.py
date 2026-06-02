from __future__ import annotations
import os, json
from pathlib import Path

APP_NAME = 'برنامج أجور الراجحي'
APP_VERSION = '4.0.0'
COMPANY = 'Ethar Web'

BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
USER_DIR = Path(os.getenv('APPDATA') or Path.home()) / 'RajhiWagesPremium'
USER_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = USER_DIR / 'config.json'
DEFAULT_DB_PATH = USER_DIR / 'rajhi_wages.db'
EXPORT_DIR = USER_DIR / 'exports'
BACKUP_DIR = USER_DIR / 'backups'
EXPORT_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)

DEFAULT_SETTINGS = {
    'establishment_name': 'شركة ساحل التميز للمقاولات شركة شخص واحد',
    'establishment_bank': 'RJHI',
    'establishment_id': '00079259',
    'account_number': 'SA3880000129608016910669',
    'currency': 'SAR',
    'mol_establishment_id': '2515736',
    'file_reference_prefix': 'WPS',
    'payment_description': 'Payroll',
    'bank_code': 'RJHI',
    'export_encoding': 'utf-8-sig',
    'db_path': str(DEFAULT_DB_PATH),
}

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
            return {**DEFAULT_SETTINGS, **data}
        except Exception:
            pass
    save_config(DEFAULT_SETTINGS)
    return DEFAULT_SETTINGS.copy()

def save_config(data: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def get_db_path() -> str:
    cfg = load_config()
    return cfg.get('db_path') or str(DEFAULT_DB_PATH)
