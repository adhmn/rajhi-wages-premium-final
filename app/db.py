from __future__ import annotations
import sqlite3, os, shutil
from datetime import datetime
from .config import get_db_path, load_config, save_config, DEFAULT_SETTINGS, BACKUP_DIR
from .utils import calc_net, to_decimal

SCHEMA = r'''
CREATE TABLE IF NOT EXISTS employees (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  gov_id TEXT NOT NULL UNIQUE,
  iban TEXT NOT NULL,
  nationality TEXT DEFAULT '',
  worker_type TEXT DEFAULT 'غير سعودي',
  basic_salary REAL DEFAULT 0,
  housing_allowance REAL DEFAULT 0,
  other_earnings REAL DEFAULT 0,
  deductions REAL DEFAULT 0,
  active INTEGER DEFAULT 1,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_employees_search ON employees(name, gov_id, iban);
CREATE TABLE IF NOT EXISTS payroll_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  payroll_month TEXT,
  value_date TEXT,
  debit_date TEXT,
  employee_count INTEGER,
  total_amount REAL,
  file_path TEXT,
  csv_path TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS operation_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  action TEXT,
  details TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);
'''

class Database:
    def __init__(self, path: str | None = None):
        self.path = path or get_db_path()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        self.ensure_settings()

    def ensure_settings(self):
        cfg = load_config()
        for k, v in {**DEFAULT_SETTINGS, **cfg}.items():
            self.conn.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)', (k, str(v)))
        self.conn.commit()

    def get_settings(self) -> dict:
        rows = self.conn.execute('SELECT key,value FROM settings').fetchall()
        data = {r['key']: r['value'] for r in rows}
        cfg = load_config()
        return {**DEFAULT_SETTINGS, **cfg, **data}

    def save_settings(self, data: dict):
        for k, v in data.items():
            self.conn.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)', (k, str(v)))
        self.conn.commit()
        merged = {**load_config(), **data}
        save_config(merged)
        self.log('save_settings', 'تم حفظ إعدادات المنشأة والشبكة')

    def log(self, action, details=''):
        self.conn.execute('INSERT INTO operation_logs(action,details) VALUES(?,?)', (action, details))
        self.conn.commit()

    def upsert_employee(self, item: dict):
        net = float(calc_net(item.get('basic_salary'), item.get('housing_allowance'), item.get('other_earnings'), item.get('deductions')))
        vals = {
            'name': item.get('name','').strip(), 'gov_id': str(item.get('gov_id','')).strip(),
            'iban': item.get('iban','').replace(' ', '').strip().upper(), 'nationality': item.get('nationality','').strip(),
            'worker_type': item.get('worker_type','غير سعودي'),
            'basic_salary': float(to_decimal(item.get('basic_salary'))),
            'housing_allowance': float(to_decimal(item.get('housing_allowance'))),
            'other_earnings': float(to_decimal(item.get('other_earnings'))),
            'deductions': float(to_decimal(item.get('deductions'))),
        }
        existing = self.conn.execute('SELECT id FROM employees WHERE gov_id=?', (vals['gov_id'],)).fetchone()
        if existing:
            self.conn.execute('''UPDATE employees SET name=:name, iban=:iban, nationality=:nationality, worker_type=:worker_type,
                basic_salary=:basic_salary, housing_allowance=:housing_allowance, other_earnings=:other_earnings, deductions=:deductions,
                updated_at=CURRENT_TIMESTAMP WHERE gov_id=:gov_id''', vals)
        else:
            self.conn.execute('''INSERT INTO employees(name,gov_id,iban,nationality,worker_type,basic_salary,housing_allowance,other_earnings,deductions)
                VALUES(:name,:gov_id,:iban,:nationality,:worker_type,:basic_salary,:housing_allowance,:other_earnings,:deductions)''', vals)
        self.conn.commit()
        return net

    def bulk_import(self, rows: list[dict]):
        count=0
        for row in rows:
            if row.get('name') and row.get('gov_id') and row.get('iban'):
                self.upsert_employee(row); count += 1
        self.log('import_excel', f'تم استيراد/تحديث {count} عامل')
        return count

    def employees(self, q='', limit=700, offset=0):
        q = (q or '').strip()
        if q:
            like=f'%{q}%'
            sql='''SELECT *, (basic_salary+housing_allowance+other_earnings-deductions) AS net_amount FROM employees
                   WHERE active=1 AND (name LIKE ? OR gov_id LIKE ? OR iban LIKE ?) ORDER BY id DESC LIMIT ? OFFSET ?'''
            return self.conn.execute(sql,(like,like,like,limit,offset)).fetchall()
        return self.conn.execute('''SELECT *, (basic_salary+housing_allowance+other_earnings-deductions) AS net_amount FROM employees
                                    WHERE active=1 ORDER BY id DESC LIMIT ? OFFSET ?''',(limit,offset)).fetchall()

    def all_employees(self):
        return self.conn.execute('''SELECT *, (basic_salary+housing_allowance+other_earnings-deductions) AS net_amount FROM employees WHERE active=1 ORDER BY id ASC''').fetchall()

    def employee(self, emp_id):
        return self.conn.execute('SELECT * FROM employees WHERE id=?',(emp_id,)).fetchone()

    def delete_employee(self, emp_id):
        self.conn.execute('UPDATE employees SET active=0 WHERE id=?',(emp_id,)); self.conn.commit(); self.log('delete_employee', str(emp_id))

    def bulk_update(self, field, mode, value):
        allowed={'basic_salary','housing_allowance','other_earnings','deductions'}
        if field not in allowed: return 0
        value=float(to_decimal(value))
        if mode == 'set':
            sql=f'UPDATE employees SET {field}=?, updated_at=CURRENT_TIMESTAMP WHERE active=1'; args=(value,)
        elif mode == 'add':
            sql=f'UPDATE employees SET {field}={field}+?, updated_at=CURRENT_TIMESTAMP WHERE active=1'; args=(value,)
        elif mode == 'percent':
            sql=f'UPDATE employees SET {field}=ROUND({field}+({field}*?/100.0),2), updated_at=CURRENT_TIMESTAMP WHERE active=1'; args=(value,)
        else: return 0
        cur=self.conn.execute(sql,args); self.conn.commit(); self.log('bulk_update', f'{field} {mode} {value}')
        return cur.rowcount

    def stats(self):
        r=self.conn.execute('SELECT COUNT(*) c, COALESCE(SUM(basic_salary+housing_allowance+other_earnings-deductions),0) s FROM employees WHERE active=1').fetchone()
        return int(r['c']), float(r['s'])

    def add_run(self, month, value_date, debit_date, count, total, file_path, csv_path=''):
        self.conn.execute('''INSERT INTO payroll_runs(payroll_month,value_date,debit_date,employee_count,total_amount,file_path,csv_path)
                             VALUES(?,?,?,?,?,?,?)''',(month,value_date,debit_date,count,float(total),file_path,csv_path))
        self.conn.commit(); self.log('export_txt', file_path)

    def runs(self):
        return self.conn.execute('SELECT * FROM payroll_runs ORDER BY id DESC LIMIT 200').fetchall()

    def backup(self):
        target = BACKUP_DIR / f'rajhi_wages_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        self.conn.commit()
        shutil.copy2(self.path, target)
        self.log('backup', str(target))
        return str(target)
