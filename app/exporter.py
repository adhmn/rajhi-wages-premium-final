from __future__ import annotations
import csv
from pathlib import Path
from decimal import Decimal
from .utils import amount_fixed, calc_net, safe_filename, today_yyyymmdd
from .config import EXPORT_DIR


def generate_files(settings: dict, employees, payroll_month: str, value_date: str, debit_date: str) -> tuple[str,str,int,Decimal]:
    EXPORT_DIR.mkdir(exist_ok=True)
    value_date = value_date or today_yyyymmdd()
    debit_date = debit_date or value_date
    prefix = settings.get('file_reference_prefix') or 'WPS'
    filename_base = safe_filename(prefix)
    txt_path = EXPORT_DIR / f'{filename_base}.txt'
    csv_path = EXPORT_DIR / f'{filename_base}.csv'
    total = Decimal('0.00')
    lines=[]
    count=0
    emp_list=list(employees)
    for idx,e in enumerate(emp_list, start=1):
        net=calc_net(e['basic_salary'], e['housing_allowance'], e['other_earnings'], e['deductions'])
        total += net
    # Header compatible with Rajhi/Mudad wage details structure
    header = [
        settings.get('establishment_bank','RJHI').strip() or 'RJHI',
        settings.get('establishment_id','').strip(),
        settings.get('account_number','').strip(),
        settings.get('currency','SAR').strip() or 'SAR',
        value_date,
        amount_fixed(total, 10),
        debit_date,
        f"{prefix}_{value_date}_{payroll_month.replace('-','')}",
        'P000',
        settings.get('mol_establishment_id','').strip(),
    ]
    lines.append('\t'.join(header))
    for idx,e in enumerate(emp_list, start=1):
        net=calc_net(e['basic_salary'], e['housing_allowance'], e['other_earnings'], e['deductions'])
        row = [
            amount_fixed(net, 10),
            str(e['iban']).strip(),
            str(e['name']).strip(),
            settings.get('bank_code','RJHI') or 'RJHI',
            settings.get('payment_description','Payroll') or 'Payroll',
            '',
            amount_fixed(e['basic_salary'], 10),
            amount_fixed(e['housing_allowance'], 10),
            amount_fixed(e['other_earnings'], 10),
            amount_fixed(e['deductions'], 10),
            str(e['gov_id']).strip(),
            f"{value_date}{idx:06d}",
        ]
        lines.append('\t'.join(row))
        count += 1
    encoding = settings.get('export_encoding','utf-8-sig') or 'utf-8-sig'
    txt_path.write_text('\n'.join(lines), encoding=encoding)
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer=csv.writer(f)
        writer.writerow(['Net Amount','IBAN','Name','Bank','Description','Return Code','Basic','Housing','Other','Deductions','Gov ID','Reference'])
        for e in emp_list:
            writer.writerow([
                str(calc_net(e['basic_salary'],e['housing_allowance'],e['other_earnings'],e['deductions'])),
                e['iban'], e['name'], settings.get('bank_code','RJHI'), settings.get('payment_description','Payroll'), '',
                e['basic_salary'], e['housing_allowance'], e['other_earnings'], e['deductions'], e['gov_id'], ''
            ])
    return str(txt_path), str(csv_path), count, total
