import requests
from bs4 import BeautifulSoup
import os, sys, time, json, re, uuid, zipfile, threading, shutil, subprocess, tempfile
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from urllib.parse import urljoin, urlparse

VERSION = "1.3.0"
GITHUB_RAW = "https://raw.githubusercontent.com/huasiyuuuuu/haitang-downloader/main/"
GITHUB_VERSION_URL = GITHUB_RAW + "version.txt"
GITHUB_SCRIPT_URL  = GITHUB_RAW + "%E6%8A%93%E5%B0%8F%E8%AF%B4.py"

def 运行目录():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

HISTORY_FILE = os.path.join(运行目录(), 'history.json')

# ─── 网站适配器 ───────────────────────────────────────────────

class 海棠适配器:
    名称 = "海棠书屋"
    def 匹配(self, url): return "haitang" in url
    def 请求头(self, url): return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.haitang41.com/', 'Accept-Language': 'zh-CN,zh;q=0.9',
    }
    def 获取章节列表(self, soup, 目录url):
        书名 = '未知'
        for tag in soup.find_all(['h1','h2']):
            t = tag.get_text(strip=True)
            if t and len(t) < 40 and '章节' not in t and '目录' not in t:
                书名 = t.split('_')[0].strip(); break
        区 = soup.find('dl', class_='chapterlist')
        if not 区: return 书名, []
        h2 = next((h for h in 区.find_all('h2') if '全部' in h.get_text() or '目录' in h.get_text()), None)
        结果, seen = [], set()
        for tag in (h2.find_next_siblings() if h2 else 区.find_all('dd')):
            if tag.name != 'dd': continue
            a = tag.find('a', href=True)
            if not a or '/read/' not in a['href']: continue
            url = a['href'] if a['href'].startswith('http') else urljoin(目录url, a['href'])
            t = a.get_text(strip=True)
            if url not in seen and t: seen.add(url); 结果.append((url, t))
        return 书名, 结果
    def 提取正文(self, soup): return soup.find(id='rtext')
    def 下一页(self, soup, url):
        for a in soup.find_all('a'):
            if a.get_text(strip=True) == '下一页':
                h = a.get('href','')
                if '_' in h.split('/')[-1]:
                    return h if h.startswith('http') else urljoin(url, h)
        return None

class 第一版主适配器:
    名称 = "第一版主"
    def 匹配(self, url): return "diyibanzhu" in url
    def 请求头(self, url):
        parsed = urlparse(url)
        return {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.210 Mobile Safari/537.36',
            'Referer': f"{parsed.scheme}://{parsed.netloc}/",
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
        }
    def 获取章节列表(self, soup, 目录url):
        书名 = '未知'
        h1 = soup.find('h1')
        if h1: 书名 = h1.get_text(strip=True)
        结果, seen = [], set()
        for ul in soup.find_all('ul', class_='list'):
            for li in ul.find_all('li'):
                a = li.find('a', href=True)
                if not a: continue
                href = a['href']
                url = href if href.startswith('http') else urljoin(目录url, href)
                t = a.get_text(strip=True)
                if url not in seen and t: seen.add(url); 结果.append((url, t))
        return 书名, 结果
    def 提取正文(self, soup): return soup.find(id='nr1')
    def 下一页(self, soup, url):
        for a in soup.find_all('a'):
            t = a.get_text(strip=True)
            if '下一页' in t and '下一章' not in t:
                h = a.get('href','')
                if h and not h.startswith('javascript'):
                    return h if h.startswith('http') else urljoin(url, h)
        return None

class 通用适配器:
    名称 = "通用"
    def 匹配(self, url): return True
    def 请求头(self, url):
        parsed = urlparse(url)
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': f"{parsed.scheme}://{parsed.netloc}/",
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
    def 获取章节列表(self, soup, 目录url):
        书名 = '未知'
        for tag in soup.find_all(['h1','h2']):
            t = tag.get_text(strip=True)
            if t and len(t) < 40: 书名 = t.split('_')[0].strip(); break
        结果, seen = [], set()
        容器计数 = {}
        for a in soup.find_all('a', href=True):
            t = a.get_text(strip=True)
            if not t or len(t) > 60: continue
            p = a.parent
            for _ in range(4):
                if p is None: break
                pid = id(p)
                if pid not in 容器计数: 容器计数[pid] = []
                容器计数[pid].append((a['href'], t))
                p = p.parent
        if 容器计数:
            best = max(容器计数, key=lambda k: len(容器计数[k]))
            for href, t in 容器计数[best]:
                url = href if href.startswith('http') else urljoin(目录url, href)
                if url not in seen and t: seen.add(url); 结果.append((url, t))
        return 书名, 结果
    def 提取正文(self, soup):
        已知 = ['#rtext','#content','#nr1','#chaptercontent','#BookText','#nr',
                '.read-content','.chapter-content','.content','#chapter_content']
        for sel in 已知:
            f = soup.select_one(sel)
            if f and len(f.get_text(strip=True)) > 200: return f
        候选 = [(len(d.get_text(strip=True)), d) for d in soup.find_all(['div','article'])
                if len(d.get_text(strip=True)) > 200]
        return max(候选, key=lambda x: x[0])[1] if 候选 else None
    def 下一页(self, soup, url):
        for a in soup.find_all('a'):
            t = a.get_text(strip=True)
            if '下一页' in t and '下一章' not in t:
                h = a.get('href','')
                if h and not h.startswith('javascript'):
                    return h if h.startswith('http') else urljoin(url, h)
        return None

适配器列表 = [海棠适配器(), 第一版主适配器(), 通用适配器()]

def 获取适配器(url):
    for a in 适配器列表:
        if a.匹配(url): return a
    return 通用适配器()

# ─── 抓取核心 ─────────────────────────────────────────────────

def 抓一页(url, session, 适配器):
    r = session.get(url, headers=适配器.请求头(url), timeout=12)
    r.encoding = r.apparent_encoding if r.encoding in ('ISO-8859-1', None) else r.encoding
    soup = BeautifulSoup(r.text, 'html.parser')
    for tag in soup.find_all(['script','style','nav','header','footer','aside']): tag.decompose()
    content = 适配器.提取正文(soup)
    if not content: return None, None
    for a in content.find_all('a'): a.decompose()
    for br in content.find_all('br'): br.replace_with('\n')
    lines = [l.strip() for l in content.get_text().splitlines()]
    lines = [l for l in lines if l and len(l) > 1]
    return '\n'.join(lines), 适配器.下一页(soup, url)

def 抓一章(url, session, 适配器, 重试=3):
    for attempt in range(重试):
        try:
            parts, cur = [], url
            while cur:
                text, nxt = 抓一页(cur, session, 适配器)
                if text: parts.append(text)
                cur = nxt
                if nxt: time.sleep(0.4)
            result = '\n'.join(parts)
            if result.strip(): return result
        except Exception:
            if attempt < 重试-1: time.sleep(2**attempt)
    return None

def 获取章节列表(目录url, session):
    适配器 = 获取适配器(目录url)
    r = session.get(目录url, headers=适配器.请求头(目录url), timeout=12)
    r.encoding = r.apparent_encoding if r.encoding in ('ISO-8859-1', None) else r.encoding
    soup = BeautifulSoup(r.text, 'html.parser')
    书名, 列表 = 适配器.获取章节列表(soup, 目录url)
    return 书名, 列表, 适配器.名称

# ─── epub ─────────────────────────────────────────────────────

def 生成epub(书名, 章节数据, 保存路径):
    epub_path = re.sub(r'\.txt$', '.epub', 保存路径)
    bid = str(uuid.uuid4())
    container = '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:schemas:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'
    files = []
    for i,(title,body) in enumerate(章节数据):
        fn = f'ch{i+1}.xhtml'
        paras = ''.join(f'<p>{l}</p>' for l in body.splitlines() if l.strip())
        html = (f'<?xml version="1.0" encoding="utf-8"?><!DOCTYPE html>'
                f'<html xmlns="http://www.w3.org/1999/xhtml"><head><meta charset="utf-8"/><title>{title}</title>'
                f'<style>body{{font-family:serif;font-size:1.1em;line-height:1.9;margin:1.8em 2em}}'
                f'h2{{font-size:1.2em;margin-bottom:1em}}p{{text-indent:2em;margin:0.25em 0}}</style>'
                f'</head><body><h2>{title}</h2>{paras}</body></html>')
        files.append((fn,title,html))
    manifest = '\n'.join(f'<item id="c{i+1}" href="{fn}" media-type="application/xhtml+xml"/>' for i,(fn,_,__)in enumerate(files))
    spine = '\n'.join(f'<itemref idref="c{i+1}"/>' for i in range(len(files)))
    nav = '\n'.join(f'<navPoint id="n{i+1}" playOrder="{i+1}"><navLabel><text>{t}</text></navLabel><content src="{fn}"/></navPoint>' for i,(fn,t,_)in enumerate(files))
    opf = (f'<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bid" version="2.0">'
           f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>{书名}</dc:title><dc:language>zh</dc:language>'
           f'<dc:identifier id="bid">{bid}</dc:identifier></metadata>'
           f'<manifest><item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>{manifest}</manifest>'
           f'<spine toc="ncx">{spine}</spine></package>')
    ncx = (f'<?xml version="1.0" encoding="utf-8"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
           f'<head><meta name="dtb:uid" content="{bid}"/></head><docTitle><text>{书名}</text></docTitle>'
           f'<navMap>{nav}</navMap></ncx>')
    with zipfile.ZipFile(epub_path,'w',zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('mimetype','application/epub+zip',compress_type=zipfile.ZIP_STORED)
        zf.writestr('META-INF/container.xml',container)
        zf.writestr('OEBPS/content.opf',opf)
        zf.writestr('OEBPS/toc.ncx',ncx)
        for fn,_,html in files: zf.writestr(f'OEBPS/{fn}',html)
    return epub_path

# ─── 断点 & 历史 ──────────────────────────────────────────────

def 读历史():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE,'r',encoding='utf-8') as f: return json.load(f)
        except: return []
    return []

def 写历史(记录):
    h = 读历史()
    for i,x in enumerate(h):
        if x.get('保存路径') == 记录.get('保存路径'): h[i]=记录; break
    else: h.insert(0,记录)
    with open(HISTORY_FILE,'w',encoding='utf-8') as f: json.dump(h[:30],f,ensure_ascii=False,indent=2)

def 读进度(p): 
    pp = p+'.progress.json'
    if os.path.exists(pp):
        try:
            with open(pp,'r',encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

def 写进度(p,d):
    with open(p+'.progress.json','w',encoding='utf-8') as f: json.dump(d,f,ensure_ascii=False)

# ─── 自动更新 ─────────────────────────────────────────────────

def 检查更新(静默=False):
    try:
        r = requests.get(GITHUB_VERSION_URL, timeout=8)
        latest = r.text.strip()
        if latest != VERSION:
            return latest
    except: pass
    return None

def 执行更新(latest, log_fn):
    try:
        log_fn(f"正在下载 v{latest}...")
        r = requests.get(GITHUB_SCRIPT_URL, timeout=30)
        self_path = os.path.abspath(__file__) if not getattr(sys,'frozen',False) else sys.executable
        tmp = self_path + '.new'
        with open(tmp,'wb') as f: f.write(r.content)
        bak = self_path + '.bak'
        if os.path.exists(bak): os.remove(bak)
        os.rename(self_path, bak)
        os.rename(tmp, self_path)
        if os.path.exists(bak): os.remove(bak)
        log_fn("更新完成！请重新启动程序。")
        return True
    except Exception as e:
        log_fn(f"更新失败：{e}")
        return False

# ─── 卸载 ────────────────────────────────────────────────────

def 执行卸载():
    目录 = 运行目录()
    清理列表 = []
    if os.path.exists(HISTORY_FILE): 清理列表.append(HISTORY_FILE)
    for f in os.listdir(目录):
        if f.endswith('.progress.json'): 清理列表.append(os.path.join(目录,f))
    self_path = sys.executable if getattr(sys,'frozen',False) else os.path.abspath(__file__)
    清理列表.append(self_path)
    msg = "将删除以下文件：\n" + "\n".join(清理列表) + "\n\n下载的小说不会被删除。确认吗？"
    if not messagebox.askyesno("确认卸载", msg): return
    bat = os.path.join(tempfile.gettempdir(), 'uninstall_haitang.bat')
    with open(bat,'w') as f:
        f.write('@echo off\ntimeout /t 2 /nobreak >nul\n')
        for fp in 清理列表:
            f.write(f'del /f /q "{fp}" >nul 2>&1\n')
        f.write(f'del /f /q "{bat}"\n')
    subprocess.Popen(['cmd','/c',bat], creationflags=0x08000000)
    sys.exit(0)

# ─── GUI ──────────────────────────────────────────────────────

BG,CARD,ACCENT = '#111120','#1a1a2e','#e94560'
FG,MUTED,ENTRY = '#e8e8f0','#55556a','#22223a'
GREEN,YELLOW    = '#39d98a','#f5c842'

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"小说下载器  v{VERSION}")
        self.root.geometry("720x680")
        self.root.resizable(True,True)
        self.root.configure(bg=BG)
        self.root.columnconfigure(0,weight=1)
        self.root.rowconfigure(0,weight=1)
        self.session  = requests.Session()
        self.停止标志 = False
        self.章节列表 = []
        self.书名     = ''
        self.适配器名 = ''
        self._running = False
        self._新抓数  = 0
        self._build()
        self._刷新历史()
        self.root.after(2000, lambda: threading.Thread(target=self._启动检查更新, daemon=True).start())

    def _启动检查更新(self):
        latest = 检查更新()
        if latest:
            self._log(f"发现新版本 v{latest}，点「检查更新」按钮可升级", YELLOW)

    def _build(self):
        style = ttk.Style()
        style.theme_use('default')
        style.configure('TProgressbar', troughcolor=ENTRY, background=ACCENT, thickness=5)
        style.configure('TNotebook', background=BG, borderwidth=0)
        style.configure('TNotebook.Tab', background=CARD, foreground=MUTED, font=('微软雅黑',10), padding=(18,7))
        style.map('TNotebook.Tab', background=[('selected',BG)], foreground=[('selected',FG)])
        style.configure('Treeview', background=CARD, foreground=FG, fieldbackground=CARD, rowheight=26, font=('微软雅黑',9))
        style.configure('Treeview.Heading', background=ENTRY, foreground=MUTED, font=('微软雅黑',9,'bold'))
        style.map('Treeview', background=[('selected',ACCENT)])
        nb = ttk.Notebook(self.root)
        nb.grid(row=0,column=0,sticky='nsew')
        t1 = tk.Frame(nb,bg=BG); t1.columnconfigure(0,weight=1); nb.add(t1,text='  下载  ')
        t2 = tk.Frame(nb,bg=BG); t2.columnconfigure(0,weight=1); t2.rowconfigure(1,weight=1); nb.add(t2,text='  历史记录  ')
        t3 = tk.Frame(nb,bg=BG); t3.columnconfigure(0,weight=1); nb.add(t3,text='  设置  ')
        self._build_dl(t1)
        self._build_hist(t2)
        self._build_settings(t3)

    def _lbl(self,p,text,size=9,bold=False,color=MUTED):
        return tk.Label(p,text=text,font=('微软雅黑',size,'bold' if bold else 'normal'),bg=p.cget('bg'),fg=color)

    def _entry_w(self,p,var,width=None):
        kw=dict(textvariable=var,font=('微软雅黑',10),bg=ENTRY,fg=FG,insertbackground=FG,relief='flat',bd=8)
        if width: kw['width']=width
        return tk.Entry(p,**kw)

    def _btn_w(self,p,text,cmd,bg=ACCENT,fg='white',size=10):
        return tk.Button(p,text=text,font=('微软雅黑',size),bg=bg,fg=fg,relief='flat',bd=0,padx=14,
                         activebackground=bg,activeforeground=fg,command=cmd)

    def _build_dl(self,parent):
        hf=tk.Frame(parent,bg=BG); hf.grid(row=0,column=0,sticky='ew',padx=22,pady=(18,4))
        self._lbl(hf,"小说下载器",16,True,FG).pack(side='left')
        self.适配器标签 = tk.StringVar(value="")
        tk.Label(hf,textvariable=self.适配器标签,font=('微软雅黑',9),bg=BG,fg=YELLOW).pack(side='left',padx=10,pady=(5,0))

        c1=tk.Frame(parent,bg=CARD); c1.grid(row=1,column=0,sticky='ew',padx=22,pady=(8,0)); c1.columnconfigure(0,weight=1)
        self._lbl(c1,"书籍目录页网址").grid(row=0,column=0,sticky='w',padx=14,pady=(10,3))
        rf=tk.Frame(c1,bg=CARD); rf.grid(row=1,column=0,sticky='ew',padx=14,pady=(0,6)); rf.columnconfigure(0,weight=1)
        self.url_var=tk.StringVar()
        self._entry_w(rf,self.url_var).grid(row=0,column=0,sticky='ew')
        self._btn_w(rf,"获取章节",self._获取章节).grid(row=0,column=1,padx=(8,0))
        self.书名_var=tk.StringVar(value="请输入网址后点击「获取章节」")
        tk.Label(c1,textvariable=self.书名_var,font=('微软雅黑',10,'bold'),bg=CARD,fg=ACCENT).grid(row=2,column=0,sticky='w',padx=14,pady=(0,10))

        c2=tk.Frame(parent,bg=CARD); c2.grid(row=2,column=0,sticky='ew',padx=22,pady=(6,0))
        self._lbl(c2,"下载范围").grid(row=0,column=0,sticky='w',padx=14,pady=(10,3))
        rf2=tk.Frame(c2,bg=CARD); rf2.grid(row=1,column=0,sticky='w',padx=14,pady=(0,10))
        self._lbl(rf2,"从第",color=FG).pack(side='left')
        self.开始_var=tk.StringVar(value="1")
        self._entry_w(rf2,self.开始_var,6).pack(side='left',padx=6)
        self._lbl(rf2,"章，下载",color=FG).pack(side='left')
        self.数量_var=tk.StringVar(value="999")
        self._entry_w(rf2,self.数量_var,6).pack(side='left',padx=6)
        self._lbl(rf2,"章（999=全部）",color=FG).pack(side='left')

        c3=tk.Frame(parent,bg=CARD); c3.grid(row=3,column=0,sticky='ew',padx=22,pady=(6,0)); c3.columnconfigure(0,weight=1)
        self._lbl(c3,"保存位置").grid(row=0,column=0,sticky='w',padx=14,pady=(10,3))
        rf3=tk.Frame(c3,bg=CARD); rf3.grid(row=1,column=0,sticky='ew',padx=14,pady=(0,10)); rf3.columnconfigure(0,weight=1)
        self.路径_var=tk.StringVar(value=r"D:\缓存文件\小说")
        self._entry_w(rf3,self.路径_var).grid(row=0,column=0,sticky='ew')
        self._btn_w(rf3,"浏览",self._选择路径,bg=ENTRY,fg=FG).grid(row=0,column=1,padx=(8,0))

        pf=tk.Frame(parent,bg=BG); pf.grid(row=4,column=0,sticky='ew',padx=22,pady=(10,0)); pf.columnconfigure(0,weight=1)
        self.进度_var=tk.DoubleVar()
        ttk.Progressbar(pf,variable=self.进度_var,maximum=100).grid(row=0,column=0,columnspan=2,sticky='ew')
        self.进度文字=tk.StringVar(); self.剩余文字=tk.StringVar()
        tk.Label(pf,textvariable=self.进度文字,font=('微软雅黑',9),bg=BG,fg=MUTED).grid(row=1,column=0,sticky='w')
        tk.Label(pf,textvariable=self.剩余文字,font=('微软雅黑',9),bg=BG,fg=YELLOW).grid(row=1,column=1,sticky='e')

        parent.rowconfigure(5,weight=1)
        parent.rowconfigure(6,weight=0)
        lf=tk.Frame(parent,bg=BG); lf.grid(row=5,column=0,sticky='nsew',padx=22,pady=(6,0)); lf.columnconfigure(0,weight=1); lf.rowconfigure(0,weight=1)
        self.日志框=tk.Text(lf,font=('Consolas',9),bg='#0a0a18',fg=GREEN,relief='flat',state='disabled',wrap='word',bd=0)
        self.日志框.grid(row=0,column=0,sticky='nsew')
        sb=tk.Scrollbar(lf,command=self.日志框.yview,bg=BG,troughcolor=BG); sb.grid(row=0,column=1,sticky='ns')
        self.日志框.config(yscrollcommand=sb.set)

        bf=tk.Frame(parent,bg=BG); bf.grid(row=6,column=0,pady=(10,18))
        self.开始按钮=self._btn_w(bf,"▶  开始下载",self._开始下载,size=11)
        self.开始按钮.config(pady=9,padx=28); self.开始按钮.pack(side='left',padx=6)
        self._btn_w(bf,"⏹  暂停",self._停止,bg=ENTRY,fg=FG,size=11).pack(side='left',padx=6)
        self._btn_w(bf,"📂  打开文件夹",self._打开文件夹,bg=ENTRY,fg=FG,size=11).pack(side='left',padx=6)

    def _build_hist(self,parent):
        self._lbl(parent,"下载历史（双击打开文件夹）",11,True,FG).grid(row=0,column=0,sticky='w',padx=22,pady=(16,8))
        hf=tk.Frame(parent,bg=BG); hf.grid(row=1,column=0,sticky='nsew',padx=22,pady=(0,16)); hf.columnconfigure(0,weight=1); hf.rowconfigure(0,weight=1)
        cols=('书名','章数','时间','路径')
        self.历史表=ttk.Treeview(hf,columns=cols,show='headings',height=18)
        for col,w in zip(cols,(180,60,140,290)):
            self.历史表.heading(col,text=col); self.历史表.column(col,width=w,anchor='w')
        sb2=ttk.Scrollbar(hf,orient='vertical',command=self.历史表.yview)
        self.历史表.configure(yscrollcommand=sb2.set)
        self.历史表.grid(row=0,column=0,sticky='nsew'); sb2.grid(row=0,column=1,sticky='ns')
        self.历史表.bind('<Double-1>',self._历史双击)

    def _build_settings(self,parent):
        self._lbl(parent,"程序设置",14,True,FG).grid(row=0,column=0,sticky='w',padx=22,pady=(20,16))
        c=tk.Frame(parent,bg=CARD); c.grid(row=1,column=0,sticky='ew',padx=22); c.columnconfigure(0,weight=1)

        # 当前版本
        rf=tk.Frame(c,bg=CARD); rf.grid(row=0,column=0,sticky='ew',padx=14,pady=(14,0))
        self._lbl(rf,f"当前版本：v{VERSION}",10,False,FG).pack(side='left')
        self.更新状态=tk.StringVar(value="")
        tk.Label(rf,textvariable=self.更新状态,font=('微软雅黑',9),bg=CARD,fg=YELLOW).pack(side='left',padx=12)
        self._btn_w(rf,"检查更新",self._手动检查更新).pack(side='right')

        # 分隔
        tk.Frame(c,bg=ENTRY,height=1).grid(row=1,column=0,sticky='ew',padx=14,pady=12)

        # 卸载
        rf2=tk.Frame(c,bg=CARD); rf2.grid(row=2,column=0,sticky='ew',padx=14,pady=(0,14))
        self._lbl(rf2,"卸载程序（删除程序本身和所有记录文件，下载的小说不受影响）",9,False,MUTED).pack(side='left')
        self._btn_w(rf2,"卸载",执行卸载,bg='#3a1a1a',fg='#ff6666').pack(side='right')

    def _log(self,msg,color=GREEN):
        def _do():
            self.日志框.config(state='normal')
            tag=f't{time.time()}'
            self.日志框.tag_configure(tag,foreground=color)
            self.日志框.insert('end',msg+'\n',tag)
            self.日志框.see('end')
            self.日志框.config(state='disabled')
        self.root.after(0,_do)

    def _选择路径(self):
        p=filedialog.askdirectory()
        if p: self.路径_var.set(p)

    def _打开文件夹(self):
        p=self.路径_var.get().strip()
        if os.path.exists(p): os.startfile(p)
        else: messagebox.showinfo("提示",f"文件夹不存在：{p}")

    def _历史双击(self,_):
        sel=self.历史表.selection()
        if not sel: return
        vals=self.历史表.item(sel[0],'values')
        folder=os.path.dirname(vals[3]) if vals else ''
        if os.path.exists(folder): os.startfile(folder)

    def _刷新历史(self):
        def _do():
            for row in self.历史表.get_children(): self.历史表.delete(row)
            for h in 读历史():
                self.历史表.insert('','end',values=(h.get('书名',''),h.get('章数',''),h.get('时间',''),h.get('保存路径','')))
        self.root.after(0,_do)

    def _格式化剩余(self,秒):
        if 秒<60: return f"约 {int(秒)} 秒后完成"
        if 秒<3600: return f"约 {int(秒//60)} 分钟后完成"
        return f"约 {int(秒//3600)} 小时 {int((秒%3600)//60)} 分后完成"

    def _手动检查更新(self):
        self.更新状态.set("检查中...")
        def 任务():
            latest=检查更新()
            if latest:
                self.root.after(0,lambda: self.更新状态.set(f"发现新版本 v{latest}"))
                if messagebox.askyesno("发现更新",f"发现新版本 v{latest}，当前 v{VERSION}。\n立即更新？"):
                    执行更新(latest,self._log)
            else:
                self.root.after(0,lambda: self.更新状态.set("已是最新版本"))
        threading.Thread(target=任务,daemon=True).start()

    def _获取章节(self):
        url=self.url_var.get().strip()
        if not url: messagebox.showwarning("提示","请输入网址"); return
        self._log("正在获取章节列表...",FG)
        def 任务():
            try:
                书名,lst,适配器名=获取章节列表(url,self.session)
                self.书名=书名; self.章节列表=lst; self.适配器名=适配器名
                first=lst[0][1] if lst else '无'; last=lst[-1][1] if lst else '无'
                self.root.after(0,lambda: self.书名_var.set(f"《{书名}》共 {len(lst)} 章"))
                self.root.after(0,lambda: self.适配器标签.set(f"[{适配器名}]"))
                self._log(f"获取成功：{len(lst)} 章",GREEN)
                self._log(f"  第一章：{first}")
                self._log(f"  最后章：{last}")
            except Exception as e:
                self._log(f"获取失败：{e}",ACCENT)
        threading.Thread(target=任务,daemon=True).start()

    def _停止(self):
        self.停止标志=True; self._log("正在暂停...",YELLOW)

    def _开始下载(self):
        if self._running: return
        if not self.章节列表: messagebox.showwarning("提示","请先获取章节列表"); return
        self.停止标志=False; self._running=True; self._新抓数=0
        self.root.after(0,lambda: self.开始按钮.config(state='disabled'))
        threading.Thread(target=self._下载任务,daemon=True).start()

    def _下载任务(self):
        try: 开始=max(1,int(self.开始_var.get()))
        except: 开始=1
        try: 数量=int(self.数量_var.get())
        except: 数量=999
        目标=self.章节列表[开始-1:开始-1+数量]
        目录=self.路径_var.get().strip()
        os.makedirs(目录,exist_ok=True)
        安全书名=re.sub(r'[\\/:*?"<>|]','',self.书名)
        保存路径=os.path.join(目录,f"{安全书名}.txt")
        进度data=读进度(保存路径)
        已完成=set(进度data.get('已完成',[]))
        失败=[]; epub数据=[]; t0=time.time()
        self._log(f"\n开始下载《{self.书名}》共 {len(目标)} 章",FG)
        if 已完成: self._log(f"断点续传，跳过已完成 {len(已完成)} 章",YELLOW)
        适配器=获取适配器(self.url_var.get().strip())
        with open(保存路径,'a',encoding='utf-8') as f:
            for i,(url,标题) in enumerate(目标):
                if self.停止标志: self._log("已暂停。",YELLOW); break
                pct=round((i+1)/len(目标)*100,1)
                self.root.after(0,lambda p=pct,i=i: (self.进度_var.set(p),self.进度文字.set(f"{i+1}/{len(目标)}  ·  {p}%")))
                if url in 已完成: continue
                self._log(f"[{i+1}/{len(目标)}] {标题}",FG)
                内容=抓一章(url,self.session,适配器)
                if 内容:
                    f.write(f"\n{'─'*32}\n{标题}\n{'─'*32}\n{内容}\n"); f.flush()
                    epub数据.append((标题,内容)); 已完成.add(url)
                    进度data['已完成']=list(已完成); 写进度(保存路径,进度data)
                    self._新抓数+=1; self._log(f"  ✓ {len(内容)} 字",GREEN)
                    if self._新抓数>0:
                        elapsed=time.time()-t0; per=elapsed/self._新抓数
                        self.root.after(0,lambda r=per*(len(目标)-i-1): self.剩余文字.set(self._格式化剩余(r)))
                else:
                    失败.append(标题); self._log(f"  ✗ 失败",ACCENT)
                time.sleep(1)
        if epub数据:
            self._log("生成 epub...",YELLOW)
            threading.Thread(target=lambda: self._生成epub(epub数据,保存路径),daemon=True).start()
        写历史({'书名':self.书名,'章数':self._新抓数,'时间':datetime.now().strftime('%Y-%m-%d %H:%M'),'保存路径':保存路径})
        self._刷新历史()
        self._log(f"\n完成！共 {self._新抓数} 章 → {保存路径}",GREEN)
        if 失败: self._log(f"失败({len(失败)})：" + "、".join(失败[:6])+("…" if len(失败)>6 else ""),ACCENT)
        self.root.after(0,lambda:(self.剩余文字.set(""),self.开始按钮.config(state='normal'),setattr(self,'_running',False)))

    def _生成epub(self,epub数据,保存路径):
        try:
            ep=生成epub(self.书名,epub数据,保存路径)
            self._log(f"epub 已保存：{ep}",GREEN)
        except Exception as e:
            self._log(f"epub 生成失败：{e}",ACCENT)

    def run(self):
        self.root.mainloop()

if __name__=='__main__':
    App().run()
