import requests
from bs4 import BeautifulSoup
import os, sys, time, json, re, uuid, zipfile, threading, shutil, subprocess, tempfile
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from urllib.parse import urljoin, urlparse, quote

VERSION = "1.4.0"
GITHUB_RAW         = "https://raw.githubusercontent.com/huasiyuuuuu/haitang-downloader/main/"
GITHUB_VERSION_URL = GITHUB_RAW + "version.txt"
GITHUB_SCRIPT_URL  = GITHUB_RAW + "%E6%8A%93%E5%B0%8F%E8%AF%B4.py"

def 运行目录():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

HISTORY_FILE  = os.path.join(运行目录(), 'fishhook_history.json')
SITES_FILE    = os.path.join(运行目录(), 'fishhook_sites.json')
SETTINGS_FILE = os.path.join(运行目录(), 'fishhook_settings.json')

# ─── 设置 ─────────────────────────────────────────────────────

DEFAULT_SETTINGS = {
    'save_path':    r'D:\缓存文件\小说',
    'accent_color': '#0078d4',
    'font_family':  'Microsoft YaHei',
    'log_fontsize': 10,
    'corner_radius': 8,
    'auto_open':    True,
    'check_update': True,
    'gen_epub':     True,
    'gen_txt':      True,
}

def 读设置():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                s = json.load(f)
                return {**DEFAULT_SETTINGS, **s}
        except: pass
    return DEFAULT_SETTINGS.copy()

def 写设置(s):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

# ─── 网站历史记忆 ──────────────────────────────────────────────

def 读网站历史():
    if os.path.exists(SITES_FILE):
        try:
            with open(SITES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {}

def 写网站历史(data):
    with open(SITES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def 记录网站访问(url):
    parsed = urlparse(url)
    domain = f"{parsed.scheme}://{parsed.netloc}"
    data = 读网站历史()
    if domain not in data:
        data[domain] = {'name': parsed.netloc, 'count': 0, 'last': '', 'search_url': ''}
    data[domain]['count'] += 1
    data[domain]['last'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    写网站历史(data)

def 获取常用网站():
    data = 读网站历史()
    sites = [(d, info) for d, info in data.items()]
    sites.sort(key=lambda x: x[1]['count'], reverse=True)
    return sites

# ─── 搜索引擎 ─────────────────────────────────────────────────

HEADERS_BROWSER = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

def 搜索Bing(关键词, session):
    results = []
    try:
        q = quote(f'{关键词} 小说 在线阅读')
        url = f'https://www.bing.com/search?q={q}&count=10'
        r = session.get(url, headers=HEADERS_BROWSER, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        for li in soup.select('li.b_algo')[:8]:
            h2 = li.find('h2')
            cite = li.find('cite')
            desc = li.find('p')
            if h2 and h2.find('a'):
                a = h2.find('a')
                results.append({
                    'title': a.get_text(strip=True),
                    'url':   a.get('href', ''),
                    'site':  cite.get_text(strip=True) if cite else '',
                    'desc':  desc.get_text(strip=True)[:80] if desc else '',
                    'source': 'Bing'
                })
    except Exception as e:
        pass
    return results

def 搜索聚合(关键词, session):
    results = []
    # 尝试几个常见聚合小说搜索
    聚合站点 = [
        f'https://www.soshuwu.com/search?q={quote(关键词)}',
        f'https://www.biquge.tv/search.php?keyword={quote(关键词)}',
    ]
    for search_url in 聚合站点:
        try:
            r = session.get(search_url, headers=HEADERS_BROWSER, timeout=8)
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.select('a[href]')[:5]:
                href = a.get('href', '')
                text = a.get_text(strip=True)
                if not text or len(text) < 2 or len(text) > 40: continue
                if 关键词[:2] not in text and 关键词 not in text: continue
                full_url = href if href.startswith('http') else urljoin(search_url, href)
                results.append({
                    'title':  text,
                    'url':    full_url,
                    'site':   urlparse(search_url).netloc,
                    'desc':   '',
                    'source': '聚合搜索'
                })
            if results: break
        except: continue
    return results

def 搜索历史网站(关键词, domain, session):
    results = []
    try:
        data = 读网站历史()
        info = data.get(domain, {})
        search_url = info.get('search_url', '')

        # 尝试常见搜索路径
        if not search_url:
            for path in [
                f'{domain}/search?q={quote(关键词)}',
                f'{domain}/search.php?keyword={quote(关键词)}',
                f'{domain}/modules/article/search.php?searchkey={quote(关键词)}',
                f'{domain}/s/{quote(关键词)}',
            ]:
                try:
                    r = session.get(path, headers=HEADERS_BROWSER, timeout=8)
                    if r.status_code == 200 and 关键词[:2] in r.text:
                        search_url = path
                        data[domain]['search_url'] = path
                        写网站历史(data)
                        break
                except: continue

        if not search_url: return results

        r = session.get(search_url, headers=HEADERS_BROWSER, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True)[:20]:
            text = a.get_text(strip=True)
            href = a['href']
            if not text or len(text) < 2 or len(text) > 50: continue
            if 关键词[:2] not in text: continue
            full_url = href if href.startswith('http') else urljoin(domain, href)
            results.append({
                'title':  text,
                'url':    full_url,
                'site':   urlparse(domain).netloc,
                'desc':   '',
                'source': f'站内搜索'
            })
    except: pass
    return results

# ─── 网站适配器 ───────────────────────────────────────────────

class 海棠适配器:
    名称 = "海棠书屋"
    def 匹配(self, url): return "haitang" in url
    def 请求头(self, url): return {**HEADERS_BROWSER, 'Referer': 'https://www.haitang41.com/'}
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
                h = a.get('href', '')
                if '_' in h.split('/')[-1]:
                    return h if h.startswith('http') else urljoin(url, h)
        return None

class 第一版主适配器:
    名称 = "第一版主"
    def 匹配(self, url): return "diyibanzhu" in url
    def 请求头(self, url):
        parsed = urlparse(url)
        return {**HEADERS_BROWSER,
                'User-Agent': 'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36',
                'Referer': f"{parsed.scheme}://{parsed.netloc}/"}
    def 获取章节列表(self, soup, 目录url):
        书名 = soup.find('h1').get_text(strip=True) if soup.find('h1') else '未知'
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
                h = a.get('href', '')
                if h and not h.startswith('javascript'):
                    return h if h.startswith('http') else urljoin(url, h)
        return None

class 通用适配器:
    名称 = "通用"
    def 匹配(self, url): return True
    def 请求头(self, url):
        parsed = urlparse(url)
        return {**HEADERS_BROWSER, 'Referer': f"{parsed.scheme}://{parsed.netloc}/"}
    def 获取章节列表(self, soup, 目录url):
        书名 = '未知'
        for tag in soup.find_all(['h1','h2']):
            t = tag.get_text(strip=True)
            if t and len(t) < 40: 书名 = t.split('_')[0].strip(); break
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
        结果, seen = [], set()
        if 容器计数:
            best = max(容器计数, key=lambda k: len(容器计数[k]))
            for href, t in 容器计数[best]:
                url = href if href.startswith('http') else urljoin(目录url, href)
                if url not in seen and t: seen.add(url); 结果.append((url, t))
        return 书名, 结果
    def 提取正文(self, soup):
        已知 = ['#rtext','#content','#nr1','#chaptercontent','#BookText',
                '.read-content','.chapter-content','#chapter_content']
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
                h = a.get('href', '')
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
    for tag in soup.find_all(['script','style','nav','header','footer','aside']):
        tag.decompose()
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
    记录网站访问(目录url)
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
    spine    = '\n'.join(f'<itemref idref="c{i+1}"/>' for i in range(len(files)))
    nav      = '\n'.join(f'<navPoint id="n{i+1}" playOrder="{i+1}"><navLabel><text>{t}</text></navLabel><content src="{fn}"/></navPoint>' for i,(fn,t,_)in enumerate(files))
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

# ─── 历史 & 进度 ──────────────────────────────────────────────

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
    with open(HISTORY_FILE,'w',encoding='utf-8') as f: json.dump(h[:50],f,ensure_ascii=False,indent=2)

def 读进度(p):
    pp = p+'.progress.json'
    if os.path.exists(pp):
        try:
            with open(pp,'r',encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

def 写进度(p,d):
    with open(p+'.progress.json','w',encoding='utf-8') as f: json.dump(d,f,ensure_ascii=False)

# ─── 更新 & 卸载 ──────────────────────────────────────────────

def 检查更新():
    try:
        r = requests.get(GITHUB_VERSION_URL, timeout=8)
        latest = r.text.strip()
        if latest != VERSION: return latest
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
        log_fn(f"更新失败：{e}"); return False

def 执行卸载():
    目录 = 运行目录()
    清理 = [f for f in [HISTORY_FILE, SETTINGS_FILE, SITES_FILE] if os.path.exists(f)]
    for f in os.listdir(目录):
        if f.endswith('.progress.json'): 清理.append(os.path.join(目录,f))
    self_path = sys.executable if getattr(sys,'frozen',False) else os.path.abspath(__file__)
    清理.append(self_path)
    msg = "将删除以下文件：\n" + "\n".join(清理) + "\n\n下载的小说不受影响。确认卸载？"
    if not messagebox.askyesno("确认卸载", msg): return
    bat = os.path.join(tempfile.gettempdir(), 'uninstall_fishhook.bat')
    with open(bat,'w') as f:
        f.write('@echo off\ntimeout /t 2 /nobreak >nul\n')
        for fp in 清理: f.write(f'del /f /q "{fp}" >nul 2>&1\n')
        f.write(f'del /f /q "{bat}"\n')
    subprocess.Popen(['cmd','/c',bat], creationflags=0x08000000)
    sys.exit(0)

# ─── 颜色主题 ─────────────────────────────────────────────────

BG    = '#1c1c1c'
BG2   = '#252525'
BG3   = '#2b2b2b'
ENTRY = '#1a1a1a'
BORDER= '#3a3a3a'
FG    = '#e0e0e0'
MUTED = '#888888'
GREEN = '#6ccb5f'
YELLOW= '#ffd700'
RED   = '#ff6b6b'

def get_accent():
    return 读设置().get('accent_color', '#0078d4')

# ─── GUI ──────────────────────────────────────────────────────

class App:
    def __init__(self):
        self.settings  = 读设置()
        self.ACCENT    = self.settings['accent_color']
        self.root = tk.Tk()
        self.root.title(f"FishHook  v{VERSION}")
        self.root.geometry("760x700")
        self.root.resizable(True, True)
        self.root.configure(bg=BG)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.session   = requests.Session()
        self.停止标志  = False
        self.章节列表  = []
        self.书名      = ''
        self._running  = False
        self._新抓数   = 0
        self._search_results = []

        self._build()
        self._刷新历史()
        self._刷新网站历史()
        if self.settings.get('check_update'):
            self.root.after(2000, lambda: threading.Thread(target=self._启动检查更新, daemon=True).start())

    def _启动检查更新(self):
        latest = 检查更新()
        if latest:
            self._log(f"发现新版本 v{latest}，可在「设置」里更新", YELLOW)

    # ── 样式 ───────────────────────────────────────────────────

    def _apply_style(self):
        s = ttk.Style()
        s.theme_use('default')
        s.configure('TProgressbar', troughcolor=ENTRY, background=self.ACCENT, thickness=4)
        s.configure('TNotebook', background=BG, borderwidth=0)
        s.configure('TNotebook.Tab', background=BG3, foreground=MUTED,
                    font=(self.settings['font_family'], 10), padding=(18,7))
        s.map('TNotebook.Tab', background=[('selected',BG)], foreground=[('selected',FG)])
        s.configure('Treeview', background=BG2, foreground=FG, fieldbackground=BG2,
                    rowheight=26, font=(self.settings['font_family'], 9))
        s.configure('Treeview.Heading', background=ENTRY, foreground=MUTED,
                    font=(self.settings['font_family'], 9, 'bold'))
        s.map('Treeview', background=[('selected', self.ACCENT)])

    def _build(self):
        self._apply_style()
        self.nb = ttk.Notebook(self.root)
        self.nb.grid(row=0, column=0, sticky='nsew')

        tabs = [('  下载  ', self._build_dl),
                ('  搜索  ', self._build_search),
                ('  历史  ', self._build_hist),
                ('  设置  ', self._build_settings)]

        for name, builder in tabs:
            t = tk.Frame(self.nb, bg=BG)
            t.columnconfigure(0, weight=1)
            self.nb.add(t, text=name)
            builder(t)

    # ── 通用控件 ────────────────────────────────────────────────

    def _lbl(self, p, text, size=9, bold=False, color=MUTED):
        ff = self.settings.get('font_family','Microsoft YaHei')
        return tk.Label(p, text=text, font=(ff, size, 'bold' if bold else 'normal'),
                        bg=p.cget('bg'), fg=color)

    def _entry_w(self, p, var, width=None):
        ff = self.settings.get('font_family','Microsoft YaHei')
        kw = dict(textvariable=var, font=(ff, 10), bg=ENTRY, fg=FG,
                  insertbackground=FG, relief='flat', bd=8)
        if width: kw['width'] = width
        return tk.Entry(p, **kw)

    def _btn(self, p, text, cmd, bg=None, fg='white', size=10, pady=8, padx=14):
        if bg is None: bg = self.ACCENT
        ff = self.settings.get('font_family','Microsoft YaHei')
        return tk.Button(p, text=text, font=(ff, size), bg=bg, fg=fg,
                         relief='flat', bd=0, padx=padx, pady=pady,
                         activebackground=bg, activeforeground=fg, command=cmd)

    def _section(self, parent, row, label='', pady=(6,0)):
        f = tk.Frame(parent, bg=BG2, bd=0,
                     highlightbackground=BORDER, highlightthickness=1)
        f.grid(row=row, column=0, sticky='ew', padx=20, pady=pady)
        f.columnconfigure(0, weight=1)
        if label:
            tk.Label(f, text=label, font=(self.settings['font_family'],9),
                     bg=BG2, fg=MUTED).grid(row=0, column=0, sticky='w', padx=14, pady=(10,3))
        return f

    # ── 下载 Tab ────────────────────────────────────────────────

    def _build_dl(self, parent):
        # 标题行
        hf = tk.Frame(parent, bg=BG)
        hf.grid(row=0, column=0, sticky='ew', padx=20, pady=(16,4))
        self._lbl(hf, "FishHook", 15, True, FG).pack(side='left')
        self.适配器标签 = tk.StringVar(value="")
        tk.Label(hf, textvariable=self.适配器标签, font=(self.settings['font_family'],9),
                 bg=BG, fg=YELLOW).pack(side='left', padx=10, pady=(4,0))

        # 网址输入
        c1 = self._section(parent, 1, "书籍目录页网址", pady=(8,0))
        rf = tk.Frame(c1, bg=BG2); rf.grid(row=1, column=0, sticky='ew', padx=14, pady=(0,6))
        rf.columnconfigure(0, weight=1)
        self.url_var = tk.StringVar()
        self._entry_w(rf, self.url_var).grid(row=0, column=0, sticky='ew')
        self._btn(rf, "获取章节", self._获取章节).grid(row=0, column=1, padx=(8,0))
        self.书名_var = tk.StringVar(value="输入目录页网址，或切换到「搜索」找书")
        tk.Label(c1, textvariable=self.书名_var, font=(self.settings['font_family'],10,'bold'),
                 bg=BG2, fg=self.ACCENT).grid(row=2, column=0, sticky='w', padx=14, pady=(0,10))

        # 范围
        c2 = self._section(parent, 2, "下载范围")
        rf2 = tk.Frame(c2, bg=BG2); rf2.grid(row=1, column=0, sticky='w', padx=14, pady=(0,10))
        self._lbl(rf2, "从第", color=FG).pack(side='left')
        self.开始_var = tk.StringVar(value="1")
        self._entry_w(rf2, self.开始_var, 6).pack(side='left', padx=6)
        self._lbl(rf2, "章，下载", color=FG).pack(side='left')
        self.数量_var = tk.StringVar(value="999")
        self._entry_w(rf2, self.数量_var, 6).pack(side='left', padx=6)
        self._lbl(rf2, "章（999=全部）", color=FG).pack(side='left')

        # 保存路径
        c3 = self._section(parent, 3, "保存位置")
        rf3 = tk.Frame(c3, bg=BG2); rf3.grid(row=1, column=0, sticky='ew', padx=14, pady=(0,10))
        rf3.columnconfigure(0, weight=1)
        self.路径_var = tk.StringVar(value=self.settings.get('save_path', r'D:\缓存文件\小说'))
        self._entry_w(rf3, self.路径_var).grid(row=0, column=0, sticky='ew')
        self._btn(rf3, "浏览", self._选择路径, bg=BG3, fg=FG).grid(row=0, column=1, padx=(8,0))

        # 进度
        pf = tk.Frame(parent, bg=BG)
        pf.grid(row=4, column=0, sticky='ew', padx=20, pady=(10,0))
        pf.columnconfigure(0, weight=1)
        self.进度_var = tk.DoubleVar()
        ttk.Progressbar(pf, variable=self.进度_var, maximum=100).grid(row=0, column=0, columnspan=2, sticky='ew')
        self.进度文字 = tk.StringVar()
        self.剩余文字 = tk.StringVar()
        tk.Label(pf, textvariable=self.进度文字, font=(self.settings['font_family'],9),
                 bg=BG, fg=MUTED).grid(row=1, column=0, sticky='w')
        tk.Label(pf, textvariable=self.剩余文字, font=(self.settings['font_family'],9),
                 bg=BG, fg=YELLOW).grid(row=1, column=1, sticky='e')

        # 日志
        parent.rowconfigure(5, weight=1)
        parent.rowconfigure(6, weight=0)
        lf = tk.Frame(parent, bg=BG)
        lf.grid(row=5, column=0, sticky='nsew', padx=20, pady=(6,0))
        lf.columnconfigure(0, weight=1); lf.rowconfigure(0, weight=1)
        fs = self.settings.get('log_fontsize', 10)
        self.日志框 = tk.Text(lf, font=('Consolas', fs), bg=ENTRY, fg=GREEN,
                             relief='flat', state='disabled', wrap='word', bd=0,
                             highlightbackground=BORDER, highlightthickness=1)
        self.日志框.grid(row=0, column=0, sticky='nsew')
        sb = tk.Scrollbar(lf, command=self.日志框.yview, bg=BG, troughcolor=BG)
        sb.grid(row=0, column=1, sticky='ns')
        self.日志框.config(yscrollcommand=sb.set)

        # 按钮行
        bf = tk.Frame(parent, bg=BG)
        bf.grid(row=6, column=0, pady=(10,16))
        self.开始按钮 = self._btn(bf, "▶  开始下载", self._开始下载, size=11, pady=9, padx=28)
        self.开始按钮.pack(side='left', padx=6)
        self._btn(bf, "⏹  暂停", self._停止, bg=BG3, fg=FG, size=11, pady=9).pack(side='left', padx=6)
        self._btn(bf, "📂  打开文件夹", self._打开文件夹, bg=BG3, fg=FG, size=11, pady=9).pack(side='left', padx=6)

    # ── 搜索 Tab ────────────────────────────────────────────────

    def _build_search(self, parent):
        parent.rowconfigure(3, weight=1)

        # 搜索框
        sf = self._section(parent, 0, "搜索书名", pady=(16,0))
        rf = tk.Frame(sf, bg=BG2); rf.grid(row=1, column=0, sticky='ew', padx=14, pady=(0,10))
        rf.columnconfigure(0, weight=1)
        self.search_var = tk.StringVar()
        se = self._entry_w(rf, self.search_var)
        se.grid(row=0, column=0, sticky='ew')
        se.bind('<Return>', lambda e: self._执行搜索())
        self._btn(rf, "搜索", self._执行搜索).grid(row=0, column=1, padx=(8,0))

        # 搜索来源选择
        src_f = tk.Frame(sf, bg=BG2)
        src_f.grid(row=2, column=0, sticky='w', padx=14, pady=(0,10))
        self._lbl(src_f, "搜索来源：", color=MUTED).pack(side='left')
        self.src_bing  = tk.BooleanVar(value=True)
        self.src_juhe  = tk.BooleanVar(value=True)
        for var, text in [(self.src_bing,'Bing'), (self.src_juhe,'聚合小说')]:
            tk.Checkbutton(src_f, text=text, variable=var,
                          bg=BG2, fg=FG, selectcolor=ENTRY,
                          activebackground=BG2, activeforeground=FG,
                          font=(self.settings['font_family'],9)).pack(side='left', padx=6)

        # 常用网站快选
        sites_f = self._section(parent, 1, "常用网站（按使用频率排序）")
        self.sites_frame = tk.Frame(sites_f, bg=BG2)
        self.sites_frame.grid(row=1, column=0, sticky='ew', padx=14, pady=(0,10))

        # 搜索状态
        self.search_status = tk.StringVar(value="")
        tk.Label(parent, textvariable=self.search_status,
                 font=(self.settings['font_family'],9), bg=BG, fg=YELLOW
                 ).grid(row=2, column=0, sticky='w', padx=20, pady=(4,0))

        # 结果列表
        res_f = tk.Frame(parent, bg=BG)
        res_f.grid(row=3, column=0, sticky='nsew', padx=20, pady=(4,0))
        res_f.columnconfigure(0, weight=1); res_f.rowconfigure(0, weight=1)

        cols = ('标题', '网站', '来源')
        self.结果表 = ttk.Treeview(res_f, columns=cols, show='headings')
        for col, w in zip(cols, (340, 180, 80)):
            self.结果表.heading(col, text=col)
            self.结果表.column(col, width=w, anchor='w')
        sb2 = ttk.Scrollbar(res_f, orient='vertical', command=self.结果表.yview)
        self.结果表.configure(yscrollcommand=sb2.set)
        self.结果表.grid(row=0, column=0, sticky='nsew')
        sb2.grid(row=0, column=1, sticky='ns')
        self.结果表.bind('<Double-1>', self._结果双击)

        # 底部提示
        tk.Label(parent, text="双击结果自动填入下载页并获取章节",
                 font=(self.settings['font_family'],9), bg=BG, fg=MUTED
                 ).grid(row=4, column=0, pady=(4,12))

    # ── 历史 Tab ────────────────────────────────────────────────

    def _build_hist(self, parent):
        parent.rowconfigure(1, weight=1)
        parent.rowconfigure(3, weight=1)

        self._lbl(parent, "下载历史", 11, True, FG).grid(row=0, column=0, sticky='w', padx=20, pady=(16,6))
        hf = tk.Frame(parent, bg=BG)
        hf.grid(row=1, column=0, sticky='nsew', padx=20)
        hf.columnconfigure(0, weight=1); hf.rowconfigure(0, weight=1)
        cols = ('书名','章数','时间','路径')
        self.历史表 = ttk.Treeview(hf, columns=cols, show='headings', height=8)
        for col, w in zip(cols, (180,60,130,280)):
            self.历史表.heading(col, text=col); self.历史表.column(col, width=w, anchor='w')
        sb = ttk.Scrollbar(hf, orient='vertical', command=self.历史表.yview)
        self.历史表.configure(yscrollcommand=sb.set)
        self.历史表.grid(row=0, column=0, sticky='nsew'); sb.grid(row=0, column=1, sticky='ns')
        self.历史表.bind('<Double-1>', self._历史双击)

        self._lbl(parent, "访问过的网站（常用排前）", 11, True, FG).grid(row=2, column=0, sticky='w', padx=20, pady=(14,6))
        sf = tk.Frame(parent, bg=BG)
        sf.grid(row=3, column=0, sticky='nsew', padx=20, pady=(0,16))
        sf.columnconfigure(0, weight=1); sf.rowconfigure(0, weight=1)
        site_cols = ('网站','访问次数','最后访问')
        self.网站表 = ttk.Treeview(sf, columns=site_cols, show='headings', height=6)
        for col, w in zip(site_cols, (280,80,140)):
            self.网站表.heading(col, text=col); self.网站表.column(col, width=w, anchor='w')
        sb3 = ttk.Scrollbar(sf, orient='vertical', command=self.网站表.yview)
        self.网站表.configure(yscrollcommand=sb3.set)
        self.网站表.grid(row=0, column=0, sticky='nsew'); sb3.grid(row=0, column=1, sticky='ns')

        tk.Label(parent, text="双击历史记录打开文件夹 · 双击网站在搜索页使用",
                 font=(self.settings['font_family'],9), bg=BG, fg=MUTED
                 ).grid(row=4, column=0, pady=(0,8))

    # ── 设置 Tab ────────────────────────────────────────────────

    def _build_settings(self, parent):
        row = 0

        # 外观
        c1 = self._section(parent, row, "外观", pady=(16,0)); row+=1
        # 主题色
        rf = tk.Frame(c1, bg=BG2); rf.grid(row=1, column=0, sticky='ew', padx=14, pady=(4,6))
        self._lbl(rf, "主题色", color=FG).pack(side='left')
        colors = ['#0078d4','#e94560','#1d9e75','#ba7517','#7f77dd','#d85a30']
        for c in colors:
            b = tk.Frame(rf, bg=c, width=20, height=20, cursor='hand2')
            b.pack(side='left', padx=4)
            b.bind('<Button-1>', lambda e, col=c: self._设主题色(col))
        self.custom_color_btn = self._btn(rf, "自定义", self._自定义颜色, bg=BG3, fg=FG, size=9, pady=4, padx=8)
        self.custom_color_btn.pack(side='left', padx=8)

        # 字体
        rf2 = tk.Frame(c1, bg=BG2); rf2.grid(row=2, column=0, sticky='ew', padx=14, pady=(0,6))
        self._lbl(rf2, "字体", color=FG).pack(side='left')
        fonts = ['Microsoft YaHei','Segoe UI','SimHei','SimSun','KaiTi','FangSong','Arial']
        self.font_var = tk.StringVar(value=self.settings.get('font_family','Microsoft YaHei'))
        fm = ttk.Combobox(rf2, textvariable=self.font_var, values=fonts, width=16, state='readonly')
        fm.pack(side='left', padx=8)
        fm.bind('<<ComboboxSelected>>', self._改字体)

        # 日志字号
        rf3 = tk.Frame(c1, bg=BG2); rf3.grid(row=3, column=0, sticky='ew', padx=14, pady=(0,10))
        self._lbl(rf3, "日志字号", color=FG).pack(side='left')
        self.logsize_var = tk.IntVar(value=self.settings.get('log_fontsize',10))
        tk.Spinbox(rf3, from_=8, to=18, textvariable=self.logsize_var, width=4,
                   bg=ENTRY, fg=FG, buttonbackground=BG3, relief='flat').pack(side='left', padx=8)

        # 行为
        c2 = self._section(parent, row, "行为"); row+=1
        toggles = [
            ('auto_open',    '下载完成后自动打开文件夹'),
            ('check_update', '启动时检查更新'),
            ('gen_epub',     '同时生成 epub'),
            ('gen_txt',      '同时生成 txt'),
        ]
        for i,(key,label) in enumerate(toggles):
            rf = tk.Frame(c2, bg=BG2)
            rf.grid(row=i+1, column=0, sticky='ew', padx=14, pady=2)
            rf.columnconfigure(0, weight=1)
            self._lbl(rf, label, color=FG).grid(row=0, column=0, sticky='w')
            var = tk.BooleanVar(value=self.settings.get(key, True))
            setattr(self, f'toggle_{key}', var)
            tk.Checkbutton(rf, variable=var, bg=BG2, activebackground=BG2,
                          selectcolor=ENTRY).grid(row=0, column=1, sticky='e')
        tk.Frame(c2, bg=BG2, height=6).grid(row=len(toggles)+1, column=0)

        # 版本 & 更新 & 卸载
        c3 = self._section(parent, row, "程序管理"); row+=1
        vrf = tk.Frame(c3, bg=BG2); vrf.grid(row=1, column=0, sticky='ew', padx=14, pady=(6,4))
        self._lbl(vrf, f"当前版本：v{VERSION}", 10, False, FG).pack(side='left')
        self.更新状态 = tk.StringVar(value="")
        tk.Label(vrf, textvariable=self.更新状态, font=(self.settings['font_family'],9),
                 bg=BG2, fg=YELLOW).pack(side='left', padx=10)
        self._btn(vrf, "检查更新", self._手动检查更新, size=9, pady=5, padx=10).pack(side='right', padx=4)
        self._btn(vrf, "卸载", 执行卸载, bg='#3a1010', fg='#ff8080', size=9, pady=5, padx=10).pack(side='right', padx=4)

        # 保存按钮
        bf = tk.Frame(parent, bg=BG)
        bf.grid(row=row, column=0, pady=(14,16))
        self._btn(bf, "保存设置", self._保存设置, size=11, pady=9, padx=28).pack(side='left', padx=6)
        self._btn(bf, "重置默认", self._重置设置, bg=BG3, fg=FG, size=11, pady=9).pack(side='left', padx=6)

    # ── 工具方法 ─────────────────────────────────────────────────

    def _log(self, msg, color=None):
        def _do():
            self.日志框.config(state='normal')
            tag = f't{time.time()}'
            self.日志框.tag_configure(tag, foreground=color or GREEN)
            self.日志框.insert('end', msg+'\n', tag)
            self.日志框.see('end')
            self.日志框.config(state='disabled')
        self.root.after(0, _do)

    def _选择路径(self):
        p = filedialog.askdirectory()
        if p: self.路径_var.set(p)

    def _打开文件夹(self):
        p = self.路径_var.get().strip()
        if os.path.exists(p): os.startfile(p)
        else: messagebox.showinfo("提示", f"文件夹不存在：{p}")

    def _格式化剩余(self, 秒):
        if 秒 < 60:   return f"约 {int(秒)} 秒后完成"
        if 秒 < 3600: return f"约 {int(秒//60)} 分钟后完成"
        return f"约 {int(秒//3600)} 小时 {int((秒%3600)//60)} 分后完成"

    def _刷新历史(self):
        def _do():
            for row in self.历史表.get_children(): self.历史表.delete(row)
            for h in 读历史():
                self.历史表.insert('','end',values=(
                    h.get('书名',''), h.get('章数',''),
                    h.get('时间',''), h.get('保存路径','')))
        self.root.after(0, _do)

    def _刷新网站历史(self):
        def _do():
            for row in self.网站表.get_children(): self.网站表.delete(row)
            sites = 获取常用网站()
            for domain, info in sites:
                self.网站表.insert('','end',values=(
                    info.get('name', domain),
                    info.get('count', 0),
                    info.get('last', '')))
            self._刷新常用网站按钮()
        self.root.after(0, _do)

    def _刷新常用网站按钮(self):
        for w in self.sites_frame.winfo_children(): w.destroy()
        sites = 获取常用网站()[:6]
        if not sites:
            self._lbl(self.sites_frame, "暂无记录，搜索或下载后自动记录", color=MUTED).pack(side='left')
            return
        for domain, info in sites:
            name = info.get('name', domain)[:12]
            count = info.get('count', 0)
            b = tk.Button(self.sites_frame, text=f"{name} ({count})",
                         font=(self.settings['font_family'],9),
                         bg=BG3, fg=FG, relief='flat', bd=0, padx=10, pady=4,
                         activebackground=self.ACCENT, activeforeground='white',
                         command=lambda d=domain: self._站内搜索(d))
            b.pack(side='left', padx=4)

    def _历史双击(self, _):
        sel = self.历史表.selection()
        if not sel: return
        vals = self.历史表.item(sel[0], 'values')
        folder = os.path.dirname(vals[3]) if vals else ''
        if os.path.exists(folder): os.startfile(folder)

    # ── 搜索逻辑 ─────────────────────────────────────────────────

    def _执行搜索(self):
        kw = self.search_var.get().strip()
        if not kw: return
        self.search_status.set("搜索中...")
        for row in self.结果表.get_children(): self.结果表.delete(row)
        def 任务():
            results = []
            if self.src_bing.get():
                results += 搜索Bing(kw, self.session)
            if self.src_juhe.get():
                results += 搜索聚合(kw, self.session)
            self._search_results = results
            def _update():
                for row in self.结果表.get_children(): self.结果表.delete(row)
                for r in results:
                    self.结果表.insert('','end', values=(r['title'], r['site'], r['source']))
                self.search_status.set(f"找到 {len(results)} 条结果，双击直接下载")
            self.root.after(0, _update)
        threading.Thread(target=任务, daemon=True).start()

    def _站内搜索(self, domain):
        kw = self.search_var.get().strip()
        if not kw:
            messagebox.showinfo("提示", "请先在搜索框输入书名")
            return
        self.search_status.set(f"正在 {domain} 内搜索...")
        def 任务():
            results = 搜索历史网站(kw, domain, self.session)
            self._search_results = (self._search_results or []) + results
            def _update():
                for r in results:
                    self.结果表.insert('','end', values=(r['title'], r['site'], r['source']))
                self.search_status.set(f"站内搜索完成，新增 {len(results)} 条")
            self.root.after(0, _update)
        threading.Thread(target=任务, daemon=True).start()

    def _结果双击(self, _):
        sel = self.结果表.selection()
        if not sel: return
        idx = self.结果表.index(sel[0])
        if idx >= len(self._search_results): return
        result = self._search_results[idx]
        url = result['url']
        # 切换到下载 Tab，填入网址，自动获取
        self.nb.select(0)
        self.url_var.set(url)
        self._获取章节()

    # ── 下载逻辑 ─────────────────────────────────────────────────

    def _获取章节(self):
        url = self.url_var.get().strip()
        if not url: messagebox.showwarning("提示","请输入网址"); return
        self._log("正在获取章节列表...", FG)
        def 任务():
            try:
                书名, lst, 适配器名 = 获取章节列表(url, self.session)
                self.书名 = 书名; self.章节列表 = lst
                first = lst[0][1] if lst else '无'
                last  = lst[-1][1] if lst else '无'
                self.root.after(0, lambda: self.书名_var.set(f"《{书名}》共 {len(lst)} 章"))
                self.root.after(0, lambda: self.适配器标签.set(f"[{适配器名}]"))
                self._log(f"获取成功：{len(lst)} 章", GREEN)
                self._log(f"  第一章：{first}")
                self._log(f"  最后章：{last}")
                self._刷新网站历史()
            except Exception as e:
                self._log(f"获取失败：{e}", RED)
        threading.Thread(target=任务, daemon=True).start()

    def _停止(self):
        self.停止标志 = True
        self._log("正在暂停，等待当前章节完成...", YELLOW)

    def _开始下载(self):
        if self._running: return
        if not self.章节列表: messagebox.showwarning("提示","请先获取章节列表"); return
        self.停止标志 = False; self._running = True; self._新抓数 = 0
        self.root.after(0, lambda: self.开始按钮.config(state='disabled'))
        threading.Thread(target=self._下载任务, daemon=True).start()

    def _下载任务(self):
        try:    开始 = max(1, int(self.开始_var.get()))
        except: 开始 = 1
        try:    数量 = int(self.数量_var.get())
        except: 数量 = 999
        目标   = self.章节列表[开始-1 : 开始-1+数量]
        目录   = self.路径_var.get().strip()
        os.makedirs(目录, exist_ok=True)
        安全书名 = re.sub(r'[\\/:*?"<>|]', '', self.书名)
        保存路径  = os.path.join(目录, f"{安全书名}.txt")
        进度data  = 读进度(保存路径)
        已完成    = set(进度data.get('已完成', []))
        失败      = []
        epub数据  = []
        t0        = time.time()
        适配器    = 获取适配器(self.url_var.get().strip())

        self._log(f"\n开始下载《{self.书名}》共 {len(目标)} 章", FG)
        if 已完成: self._log(f"断点续传，跳过已完成 {len(已完成)} 章", YELLOW)

        with open(保存路径, 'a', encoding='utf-8') as f:
            for i, (url, 标题) in enumerate(目标):
                if self.停止标志: self._log("已暂停。", YELLOW); break
                pct = round((i+1)/len(目标)*100, 1)
                self.root.after(0, lambda p=pct, i=i: (
                    self.进度_var.set(p),
                    self.进度文字.set(f"{i+1}/{len(目标)}  ·  {p}%")))
                if url in 已完成: continue
                self._log(f"[{i+1}/{len(目标)}] {标题}", FG)
                内容 = 抓一章(url, self.session, 适配器)
                if 内容:
                    if self.settings.get('gen_txt', True):
                        f.write(f"\n{'─'*32}\n{标题}\n{'─'*32}\n{内容}\n")
                        f.flush()
                    epub数据.append((标题, 内容))
                    已完成.add(url)
                    进度data['已完成'] = list(已完成)
                    写进度(保存路径, 进度data)
                    self._新抓数 += 1
                    self._log(f"  ✓ {len(内容)} 字", GREEN)
                    if self._新抓数 > 0:
                        elapsed = time.time() - t0
                        per = elapsed / self._新抓数
                        self.root.after(0, lambda r=per*(len(目标)-i-1):
                                       self.剩余文字.set(self._格式化剩余(r)))
                else:
                    失败.append(标题)
                    self._log(f"  ✗ 失败（已重试3次）", RED)
                time.sleep(1)

        if epub数据 and self.settings.get('gen_epub', True):
            self._log("正在生成 epub...", YELLOW)
            threading.Thread(target=lambda: self._生成epub(epub数据, 保存路径), daemon=True).start()

        写历史({'书名': self.书名, '章数': self._新抓数,
                '时间': datetime.now().strftime('%Y-%m-%d %H:%M'),
                '保存路径': 保存路径})
        self._刷新历史()
        self._log(f"\n完成！共 {self._新抓数} 章 → {保存路径}", GREEN)
        if 失败:
            self._log(f"失败章节({len(失败)})：" + "、".join(失败[:6]) + ("…" if len(失败)>6 else ""), RED)
        if self.settings.get('auto_open') and os.path.exists(目录):
            os.startfile(目录)
        self.root.after(0, lambda: (
            self.剩余文字.set(""),
            self.开始按钮.config(state='normal'),
            setattr(self, '_running', False)))

    def _生成epub(self, epub数据, 保存路径):
        try:
            ep = 生成epub(self.书名, epub数据, 保存路径)
            self._log(f"epub 已保存：{ep}", GREEN)
        except Exception as e:
            self._log(f"epub 生成失败：{e}", RED)

    # ── 设置操作 ─────────────────────────────────────────────────

    def _设主题色(self, color):
        self.ACCENT = color
        self.settings['accent_color'] = color

    def _自定义颜色(self):
        from tkinter.colorchooser import askcolor
        result = askcolor(color=self.ACCENT, title="选择主题色")
        if result[1]:
            self._设主题色(result[1])

    def _改字体(self, _=None):
        self.settings['font_family'] = self.font_var.get()

    def _保存设置(self):
        self.settings['font_family']  = self.font_var.get()
        self.settings['log_fontsize'] = self.logsize_var.get()
        self.settings['save_path']    = self.路径_var.get()
        for key in ['auto_open','check_update','gen_epub','gen_txt']:
            var = getattr(self, f'toggle_{key}', None)
            if var: self.settings[key] = var.get()
        写设置(self.settings)
        messagebox.showinfo("保存成功", "设置已保存，部分更改重启后生效。")

    def _重置设置(self):
        if messagebox.askyesno("确认", "重置所有设置到默认值？"):
            写设置(DEFAULT_SETTINGS)
            messagebox.showinfo("完成", "已重置，请重启程序。")

    def _手动检查更新(self):
        self.更新状态.set("检查中...")
        def 任务():
            latest = 检查更新()
            if latest:
                self.root.after(0, lambda: self.更新状态.set(f"发现新版本 v{latest}"))
                if messagebox.askyesno("发现更新", f"发现新版本 v{latest}，当前 v{VERSION}。立即更新？"):
                    执行更新(latest, self._log)
            else:
                self.root.after(0, lambda: self.更新状态.set("已是最新版本"))
        threading.Thread(target=任务, daemon=True).start()

    def run(self):
        self.root.mainloop()

if __name__ == '__main__':
    App().run()
