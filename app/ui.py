from __future__ import annotations
import os, shutil, subprocess, sys
from decimal import Decimal
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
try:
    import customtkinter as ctk
except Exception as e:
    raise RuntimeError('customtkinter is required') from e

from .config import APP_NAME, APP_VERSION, load_config, save_config, EXPORT_DIR
from .db import Database
from .importer import parse_excel
from .exporter import generate_files
from .utils import money, month_key, today_yyyymmdd, is_valid_iban, is_valid_gov_id

ctk.set_appearance_mode('dark')
ctk.set_default_color_theme('blue')

BG = '#08111f'
CARD = '#101d32'
CARD2 = '#13233b'
TEXT = '#f8fafc'
MUTED = '#94a3b8'
GOLD = '#f5c542'
GREEN = '#16a34a'
BLUE = '#2563eb'
RED = '#dc2626'
PURPLE = '#9333ea'
BORDER = '#24344d'

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f'{APP_NAME} Premium v{APP_VERSION}')
        self.geometry('1480x850')
        self.minsize(1160, 720)
        self.configure(fg_color=BG)
        self.db = Database()
        self.selected_id = None
        self.page = 0
        self.page_size = 700
        self.fields = {}
        self._setup_tree_style()
        self._layout()
        self.refresh_all()

    def _setup_tree_style(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Treeview', background='#ffffff', foreground='#0f172a', fieldbackground='#ffffff', rowheight=32, font=('Segoe UI', 10))
        style.configure('Treeview.Heading', background='#e7edf5', foreground='#0f172a', font=('Segoe UI', 10, 'bold'), padding=8)
        style.map('Treeview', background=[('selected', '#dbeafe')], foreground=[('selected', '#0f172a')])
        style.configure('Vertical.TScrollbar', background='#cbd5e1', troughcolor='#f1f5f9')

    def _layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.sidebar = ctk.CTkFrame(self, width=250, fg_color='#0b1628', corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky='nsew')
        self.main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.main.grid(row=0, column=1, sticky='nsew')
        self.main.grid_rowconfigure(2, weight=1)
        self.main.grid_columnconfigure(0, weight=1)
        self._build_sidebar()
        self._build_header()
        self._build_pages()

    def _build_sidebar(self):
        ctk.CTkLabel(self.sidebar, text='برنامج أجور\nالراجحي', font=('Segoe UI', 26, 'bold'), text_color=TEXT, justify='right').pack(anchor='e', padx=22, pady=(26, 8))
        ctk.CTkLabel(self.sidebar, text='حماية الأجور • TXT / CSV', font=('Segoe UI', 13, 'bold'), text_color=GOLD).pack(anchor='e', padx=22, pady=(0, 24))
        self.nav_buttons = {}
        for key, title in [
            ('workers','إدارة العمال والرواتب'), ('export','توليد ملف الأجور'), ('settings','إعدادات المنشأة والشبكة'),
            ('runs','المسيرات السابقة'), ('help','دليل التشغيل')]:
            b = ctk.CTkButton(self.sidebar, text=title, height=46, corner_radius=12, fg_color=CARD2, hover_color='#1f3658', anchor='e', font=('Segoe UI', 14, 'bold'), command=lambda k=key: self.show_page(k))
            b.pack(fill='x', padx=14, pady=6)
            self.nav_buttons[key]=b
        ctk.CTkLabel(self.sidebar, text=f'v{APP_VERSION}\nقاعدة بيانات محلية أو شبكة مشتركة', font=('Segoe UI', 11), text_color=MUTED, justify='right').pack(side='bottom', anchor='e', padx=18, pady=22)

    def _build_header(self):
        top = ctk.CTkFrame(self.main, height=92, fg_color=BG, corner_radius=0)
        top.grid(row=0, column=0, sticky='ew', padx=22, pady=(18, 6))
        top.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(top, text='لوحة تشغيل حماية الأجور', font=('Segoe UI', 26, 'bold'), text_color=TEXT).grid(row=0, column=1, sticky='e')
        ctk.CTkLabel(top, text='استيراد العمال، تعديل الرواتب والبدلات، ثم توليد ملف TXT جاهز للراجحي', font=('Segoe UI', 13), text_color=MUTED).grid(row=1, column=1, sticky='e', pady=(4,0))
        self.stats_text = ctk.CTkLabel(top, text='', font=('Segoe UI', 16, 'bold'), text_color=GOLD)
        self.stats_text.grid(row=0, column=0, rowspan=2, sticky='w')

    def _build_pages(self):
        self.pages = ctk.CTkFrame(self.main, fg_color=BG, corner_radius=0)
        self.pages.grid(row=2, column=0, sticky='nsew', padx=22, pady=12)
        self.pages.grid_rowconfigure(0, weight=1)
        self.pages.grid_columnconfigure(0, weight=1)
        self.frames = {}
        for key in ['workers','export','settings','runs','help']:
            f = ctk.CTkFrame(self.pages, fg_color=BG, corner_radius=0)
            f.grid(row=0, column=0, sticky='nsew')
            self.frames[key]=f
        self._workers_page(self.frames['workers'])
        self._export_page(self.frames['export'])
        self._settings_page(self.frames['settings'])
        self._runs_page(self.frames['runs'])
        self._help_page(self.frames['help'])
        self.show_page('workers')

    def show_page(self, key):
        self.frames[key].tkraise()
        for k,b in self.nav_buttons.items():
            b.configure(fg_color=GOLD if k==key else CARD2, text_color='#111827' if k==key else TEXT)
        if key=='runs': self.refresh_runs()

    def card(self, parent, title=''):
        c = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=18, border_width=1, border_color=BORDER)
        if title:
            ctk.CTkLabel(c, text=title, font=('Segoe UI', 16, 'bold'), text_color=TEXT).pack(anchor='e', padx=16, pady=(14, 8))
        return c

    def _workers_page(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)
        actions = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=18, border_width=1, border_color=BORDER)
        actions.grid(row=0, column=0, sticky='ew', pady=(0,10))
        actions.grid_columnconfigure(0, weight=1)
        self.search = ctk.CTkEntry(actions, placeholder_text='بحث بالاسم أو الهوية أو الآيبان...', height=42, font=('Segoe UI', 13), justify='right')
        self.search.grid(row=0, column=0, sticky='ew', padx=14, pady=14)
        self.search.bind('<KeyRelease>', lambda e: self.refresh_workers(reset_page=True))
        ctk.CTkButton(actions, text='تحديث', width=100, height=42, fg_color='#475569', command=self.refresh_all).grid(row=0,column=1,padx=6)
        ctk.CTkButton(actions, text='تعديل جماعي', width=125, height=42, fg_color=PURPLE, command=self.bulk_dialog).grid(row=0,column=2,padx=6)
        ctk.CTkButton(actions, text='استيراد Excel', width=135, height=42, fg_color=GREEN, command=self.import_excel).grid(row=0,column=3,padx=14)

        form = self.card(parent, 'بيانات العامل')
        form.grid(row=1, column=0, sticky='ew', pady=(0,10))
        form.grid_columnconfigure((0,2,4), weight=1)
        labels = [
            ('name','اسم العامل'),('gov_id','رقم الهوية / الإقامة'),('iban','الآيبان'),
            ('worker_type','سعودي / غير سعودي'),('basic_salary','الراتب'),('housing_allowance','بدل السكن'),
            ('other_earnings','بدلات أخرى'),('deductions','خصومات'),('nationality','الجنسية')]
        body=ctk.CTkFrame(form, fg_color='transparent')
        body.pack(fill='x', padx=14, pady=(0,14))
        for i,(key,label) in enumerate(labels):
            r=i//3; c=(i%3)*2
            ctk.CTkLabel(body, text=label, text_color=TEXT, font=('Segoe UI', 12, 'bold')).grid(row=r,column=c+1,sticky='e',padx=8,pady=7)
            if key=='worker_type':
                w=ctk.CTkOptionMenu(body, values=['غير سعودي','سعودي'], height=38, anchor='e')
                w.set('غير سعودي')
            else:
                w=ctk.CTkEntry(body, height=38, justify='right')
            w.grid(row=r,column=c,sticky='ew',padx=8,pady=7)
            self.fields[key]=w
        for i in range(6): body.grid_columnconfigure(i, weight=1)
        btns=ctk.CTkFrame(form, fg_color='transparent')
        btns.pack(anchor='w', padx=14, pady=(0,14))
        ctk.CTkButton(btns, text='حفظ / تحديث العامل', width=160, height=40, fg_color=BLUE, command=self.save_worker).pack(side='right', padx=5)
        ctk.CTkButton(btns, text='جديد', width=90, height=40, fg_color='#64748b', command=self.clear_form).pack(side='right', padx=5)
        ctk.CTkButton(btns, text='حذف المحدد', width=110, height=40, fg_color=RED, command=self.delete_worker).pack(side='right', padx=5)

        table_card=self.card(parent)
        table_card.grid(row=2,column=0,sticky='nsew')
        table_card.grid_rowconfigure(0, weight=1); table_card.grid_columnconfigure(0, weight=1)
        cols=('id','name','gov_id','iban','worker_type','basic_salary','housing_allowance','other_earnings','deductions','net_amount')
        headings={'id':'#','name':'الاسم','gov_id':'الهوية/الإقامة','iban':'الآيبان','worker_type':'النوع','basic_salary':'الراتب','housing_allowance':'السكن','other_earnings':'بدلات','deductions':'خصومات','net_amount':'الصافي'}
        self.tree=ttk.Treeview(table_card,columns=cols,show='headings')
        for col in cols:
            self.tree.heading(col,text=headings[col])
            self.tree.column(col,anchor='center',width=110 if col not in ('name','iban') else 220)
        self.tree.grid(row=0,column=0,sticky='nsew', padx=8, pady=8)
        sb=ttk.Scrollbar(table_card, orient='vertical', command=self.tree.yview); self.tree.configure(yscrollcommand=sb.set); sb.grid(row=0,column=1,sticky='ns',pady=8)
        self.tree.bind('<<TreeviewSelect>>', self.select_worker)

    def _export_page(self, parent):
        c=self.card(parent, 'توليد ملف الأجور TXT / CSV')
        c.pack(fill='x', pady=(0,12))
        grid=ctk.CTkFrame(c, fg_color='transparent'); grid.pack(fill='x', padx=20, pady=14)
        self.payroll_month=ctk.CTkEntry(grid, height=42, justify='right'); self.payroll_month.insert(0, month_key())
        self.value_date=ctk.CTkEntry(grid, height=42, justify='right'); self.value_date.insert(0, today_yyyymmdd())
        self.debit_date=ctk.CTkEntry(grid, height=42, justify='right'); self.debit_date.insert(0, today_yyyymmdd())
        for i,(w,l) in enumerate([(self.payroll_month,'شهر المسير'),(self.value_date,'تاريخ القيمة YYYYMMDD'),(self.debit_date,'تاريخ الخصم YYYYMMDD')]):
            ctk.CTkLabel(grid,text=l,text_color=TEXT,font=('Segoe UI',13,'bold')).grid(row=0,column=i*2+1,sticky='e',padx=8,pady=8)
            w.grid(row=0,column=i*2,sticky='ew',padx=8,pady=8)
        for i in range(6): grid.grid_columnconfigure(i, weight=1)
        ctk.CTkButton(c, text='توليد ملف الأجور الآن', height=52, width=260, fg_color=GOLD, text_color='#111827', font=('Segoe UI',15,'bold'), command=self.export_files).pack(anchor='e', padx=20, pady=(2,20))
        self.export_msg=ctk.CTkTextbox(parent, height=250, fg_color=CARD, border_width=1, border_color=BORDER, text_color=TEXT, font=('Consolas', 13))
        self.export_msg.pack(fill='both', expand=True)
        self.export_msg.insert('1.0','جاهز لتوليد ملف الراجحي. سيتم إنشاء TXT و CSV وحفظ المسير في السجل.\n')

    def _settings_page(self, parent):
        c=self.card(parent, 'إعدادات المنشأة والشبكة')
        c.pack(fill='x')
        self.setting_fields={}
        cfg=self.db.get_settings()
        labels=[('establishment_name','اسم المنشأة'),('establishment_bank','بنك المنشأة'),('establishment_id','رقم المنشأة'),('account_number','حساب المنشأة / الآيبان'),('currency','العملة'),('mol_establishment_id','رقم منشأة وزارة العمل'),('file_reference_prefix','بادئة مرجع الملف'),('payment_description','وصف الدفع'),('bank_code','كود بنك العمال'),('db_path','مسار قاعدة البيانات المشتركة')]
        grid=ctk.CTkFrame(c, fg_color='transparent'); grid.pack(fill='x', padx=20, pady=14)
        for i,(key,label) in enumerate(labels):
            r=i//2; col=(i%2)*2
            ctk.CTkLabel(grid,text=label,text_color=TEXT,font=('Segoe UI',12,'bold')).grid(row=r,column=col+1,sticky='e',padx=8,pady=7)
            e=ctk.CTkEntry(grid,height=38,justify='right')
            e.insert(0,cfg.get(key,''))
            e.grid(row=r,column=col,sticky='ew',padx=8,pady=7)
            self.setting_fields[key]=e
        for i in range(4): grid.grid_columnconfigure(i, weight=1)
        btns=ctk.CTkFrame(c, fg_color='transparent'); btns.pack(anchor='w', padx=20, pady=(0,18))
        ctk.CTkButton(btns,text='حفظ الإعدادات',fg_color=GREEN,height=42,command=self.save_settings).pack(side='right',padx=5)
        ctk.CTkButton(btns,text='اختيار قاعدة مشتركة',fg_color=BLUE,height=42,command=self.choose_db).pack(side='right',padx=5)
        ctk.CTkButton(btns,text='نسخة احتياطية',fg_color=GOLD,text_color='#111827',height=42,command=self.backup).pack(side='right',padx=5)
        ctk.CTkLabel(parent,text='للعمل على 3 أجهزة: ضع قاعدة البيانات في مجلد Shared على الجهاز الرئيسي، ثم اختر نفس المسار من كل جهاز.',text_color=GOLD,font=('Segoe UI',14,'bold'),wraplength=1000,justify='right').pack(anchor='e',pady=18)

    def _runs_page(self, parent):
        bar=ctk.CTkFrame(parent, fg_color=CARD, corner_radius=14); bar.pack(fill='x', pady=(0,10))
        ctk.CTkButton(bar,text='تحديث السجل',fg_color=BLUE,command=self.refresh_runs).pack(side='right',padx=10,pady=10)
        ctk.CTkButton(bar,text='فتح مجلد التصدير',fg_color=GREEN,command=self.open_exports).pack(side='right',padx=10,pady=10)
        cols=('id','payroll_month','value_date','employee_count','total_amount','file_path','created_at')
        self.runs_tree=ttk.Treeview(parent,columns=cols,show='headings')
        for col,h in zip(cols,['#','الشهر','تاريخ القيمة','عدد العمال','الإجمالي','مسار الملف','وقت الإنشاء']):
            self.runs_tree.heading(col,text=h); self.runs_tree.column(col,anchor='center',width=140 if col!='file_path' else 460)
        self.runs_tree.pack(fill='both',expand=True)

    def _help_page(self, parent):
        t=ctk.CTkTextbox(parent, fg_color=CARD, border_color=BORDER, border_width=1, text_color=TEXT, font=('Segoe UI', 15), wrap='word')
        t.pack(fill='both', expand=True)
        t.insert('1.0', '''طريقة التشغيل المختصرة:\n\n1) افتح البرنامج على الجهاز الرئيسي.\n2) من إعدادات المنشأة والشبكة تأكد من بيانات المنشأة والحساب.\n3) من العمال والرواتب اضغط استيراد Excel واختر ملف العمال.\n4) عدّل راتب أي عامل أو بدلاته من نفس الشاشة.\n5) استخدم التعديل الجماعي عند الحاجة لزيادة أو تثبيت مبلغ للرواتب/البدلات.\n6) من توليد ملف الأجور أدخل شهر المسير وتاريخ القيمة واضغط توليد ملف الأجور.\n7) سيخرج TXT و CSV ويحفظ المسير في السجل.\n\nتشغيل أكثر من جهاز:\n- ضع قاعدة البيانات في مجلد مشترك داخل شبكة المكتب.\n- من كل جهاز اختر نفس ملف قاعدة البيانات من إعدادات المنشأة والشبكة.\n''')
        t.configure(state='disabled')

    def refresh_all(self):
        self.refresh_workers(reset_page=True); self.refresh_stats(); self.refresh_runs()

    def refresh_stats(self):
        c,total=self.db.stats(); self.stats_text.configure(text=f'عدد العمال: {c:,}  |  صافي الرواتب: {money(total)} ريال')

    def refresh_workers(self, reset_page=False):
        if reset_page: self.page=0
        q=self.search.get() if hasattr(self,'search') else ''
        rows=self.db.employees(q=q, limit=self.page_size, offset=self.page*self.page_size)
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            self.tree.insert('', 'end', values=(r['id'],r['name'],r['gov_id'],r['iban'],r['worker_type'],money(r['basic_salary']),money(r['housing_allowance']),money(r['other_earnings']),money(r['deductions']),money(r['net_amount'])))
        self.refresh_stats()

    def collect_form(self):
        data={}
        for k,w in self.fields.items():
            data[k]=w.get() if hasattr(w,'get') else ''
        return data

    def save_worker(self):
        data=self.collect_form()
        if not data.get('name') or not data.get('gov_id') or not data.get('iban'):
            messagebox.showwarning('تنبيه','الاسم والهوية والآيبان مطلوبة'); return
        if not is_valid_iban(data['iban']):
            if not messagebox.askyesno('تحذير','الآيبان لا يبدو صحيحًا، هل تريد الحفظ؟'): return
        self.db.upsert_employee(data)
        self.clear_form(); self.refresh_workers(); messagebox.showinfo('تم','تم حفظ العامل')

    def clear_form(self):
        self.selected_id=None
        for k,w in self.fields.items():
            if k=='worker_type': w.set('غير سعودي')
            else: w.delete(0,'end')

    def select_worker(self, event=None):
        sel=self.tree.selection()
        if not sel: return
        vals=self.tree.item(sel[0],'values')
        if not vals: return
        emp=self.db.employee(vals[0])
        if not emp: return
        self.selected_id=emp['id']
        mapping=['name','gov_id','iban','worker_type','basic_salary','housing_allowance','other_earnings','deductions','nationality']
        for k,w in self.fields.items():
            if k=='worker_type': w.set(emp[k] or 'غير سعودي')
            else:
                w.delete(0,'end'); w.insert(0, str(emp[k] if emp[k] is not None else ''))

    def delete_worker(self):
        if not self.selected_id:
            messagebox.showwarning('تنبيه','اختر عامل أولًا'); return
        if messagebox.askyesno('تأكيد','حذف العامل المحدد؟'):
            self.db.delete_employee(self.selected_id); self.clear_form(); self.refresh_workers()

    def import_excel(self):
        path=filedialog.askopenfilename(title='اختر ملف العمال', filetypes=[('Excel files','*.xls *.xlsx *.xlsm')])
        if not path: return
        try:
            settings, rows=parse_excel(path)
            if settings: self.db.save_settings(settings)
            count=self.db.bulk_import(rows)
            self.refresh_all()
            messagebox.showinfo('تم الاستيراد', f'تم استيراد/تحديث {count} عامل')
        except Exception as e:
            messagebox.showerror('خطأ في الاستيراد', str(e))

    def bulk_dialog(self):
        d=ctk.CTkToplevel(self); d.title('تعديل جماعي'); d.geometry('480x330'); d.configure(fg_color=BG); d.grab_set()
        ctk.CTkLabel(d,text='تعديل جماعي للرواتب والبدلات',font=('Segoe UI',20,'bold'),text_color=TEXT).pack(pady=20)
        field=ctk.CTkOptionMenu(d, values=['basic_salary','housing_allowance','other_earnings','deductions']); field.set('basic_salary'); field.pack(fill='x', padx=30, pady=8)
        mode=ctk.CTkOptionMenu(d, values=['set','add','percent']); mode.set('add'); mode.pack(fill='x', padx=30, pady=8)
        val=ctk.CTkEntry(d, placeholder_text='القيمة', justify='right'); val.pack(fill='x', padx=30, pady=8)
        def run():
            n=self.db.bulk_update(field.get(), mode.get(), val.get()); self.refresh_all(); d.destroy(); messagebox.showinfo('تم', f'تم تعديل {n} سجل')
        ctk.CTkButton(d,text='تنفيذ التعديل',fg_color=PURPLE,command=run).pack(pady=20)

    def export_files(self):
        employees=self.db.all_employees()
        if not employees:
            messagebox.showwarning('تنبيه','لا يوجد عمال للتصدير'); return
        try:
            txt,csv_path,count,total=generate_files(self.db.get_settings(), employees, self.payroll_month.get(), self.value_date.get(), self.debit_date.get())
            self.db.add_run(self.payroll_month.get(), self.value_date.get(), self.debit_date.get(), count, total, txt, csv_path)
            self.export_msg.configure(state='normal'); self.export_msg.delete('1.0','end')
            self.export_msg.insert('1.0', f'تم توليد الملف بنجاح\n\nعدد العمال: {count}\nالإجمالي: {money(total)} ريال\n\nTXT:\n{txt}\n\nCSV:\n{csv_path}\n')
            self.refresh_all(); messagebox.showinfo('تم', 'تم توليد ملف الأجور')
        except Exception as e:
            messagebox.showerror('خطأ في التصدير', str(e))

    def save_settings(self):
        data={k:w.get() for k,w in self.setting_fields.items()}
        self.db.save_settings(data); messagebox.showinfo('تم','تم حفظ الإعدادات')

    def choose_db(self):
        path=filedialog.asksaveasfilename(title='اختر/أنشئ قاعدة البيانات المشتركة', defaultextension='.db', filetypes=[('SQLite DB','*.db')])
        if not path: return
        if not os.path.exists(path):
            try: shutil.copy2(self.db.path, path)
            except Exception: pass
        cfg=load_config(); cfg['db_path']=path; save_config(cfg); self.db.save_settings({'db_path':path})
        self.setting_fields['db_path'].delete(0,'end'); self.setting_fields['db_path'].insert(0,path)
        messagebox.showinfo('تم','تم حفظ مسار قاعدة البيانات. أغلق البرنامج وافتحه من جديد لاستخدامها.')

    def backup(self):
        p=self.db.backup(); messagebox.showinfo('تم النسخ الاحتياطي', p)

    def refresh_runs(self):
        if not hasattr(self,'runs_tree'): return
        self.runs_tree.delete(*self.runs_tree.get_children())
        for r in self.db.runs():
            self.runs_tree.insert('', 'end', values=(r['id'],r['payroll_month'],r['value_date'],r['employee_count'],money(r['total_amount']),r['file_path'],r['created_at']))

    def open_exports(self):
        path=str(EXPORT_DIR)
        if sys.platform.startswith('win'):
            os.startfile(path)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', path])
        else:
            subprocess.Popen(['xdg-open', path])
