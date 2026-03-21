import sys, os, time, json, re, uuid, zipfile, threading, shutil, subprocess, tempfile
from datetime import datetime
from urllib.parse import urljoin, urlparse, quote

import requests
from bs4 import BeautifulSoup

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QProgressBar,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QCheckBox, QComboBox,
    QSpinBox, QFrame, QScrollArea, QMessageBox, QColorDialog,
    QSplitter, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon

VERSION = "2.0.0"
GITHUB_RAW         = "https://raw.githubusercontent.com/huasiyuuuuu/haitang-downloader/main/"
GITHUB_VERSION_URL = GITHUB_RAW + "version.txt"
GITHUB_EXE_URL     = GITHUB_RAW + "FishHook.exe"

def 运行目录():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

HISTORY_FILE  = os.path.join(运行目录(), 'fishhook_history.json')
SITES_FILE    = os.path.join(运行目录(), 'fishhook_sites.json')
SETTINGS_FILE = os.path.join(运行目录(), 'fishhook_settings.json')

# ── 设置 ──────────────────────────────────────────────────────

DEFAULT_SETTINGS = {
    'save_path':    r'D:\缓存文件\小说',
    'accent':       '#0078d4',
    'font_size':    10,
    'log_size':     10,
    'gen_epub':     True,
    'gen_txt':      True,
    'auto_open':    True,
    'check_update': True,
}

def 读设置():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return {**DEFAULT_SETTINGS, **json.load(f)}
        except: pass
    return DEFAULT_SETTINGS.copy()

def 写设置(s):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

# ── 网站历史 ──────────────────────────────────────────────────

def 读网站():
    if os.path.exists(SITES_FILE):
        try:
            with open(SITES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {}

def 写网站(data):
    with open(SITES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def 记录网站(url):
    parsed = urlparse(url)
    domain = f"{parsed.scheme}://{parsed.netloc}"
    data = 读网站()
    if domain not in data:
        data[domain] = {'name': parsed.netloc, 'count': 0, 'last': '', 'search_url': ''}
    data[domain]['count'] += 1
    data[domain]['last'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    写网站(data)

def 常用网站():
    data = 读网站()
    return sorted(data.items(), key=lambda x: x[1]['count'], reverse=True)

# ── 下载历史 ──────────────────────────────────────────────────

def 读历史():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return []

def 写历史(记录):
    h = 读历史()
    for i, x in enumerate(h):
        if x.get('保存路径') == 记录.get('保存路径'):
            h[i] = 记录; break
    else:
        h.insert(0, 记录)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(h[:50], f, ensure_ascii=False, indent=2)

def 读进度(p):
    pp = p + '.progress.json'
    if os.path.exists(pp):
        try:
            with open(pp, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {}

def 写进度(p, d):
    with open(p + '.progress.json', 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False)

# ── 适配器 ────────────────────────────────────────────────────

HDRS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

class 海棠适配器:
    名称 = "海棠书屋"
    def 匹配(self, url): return "haitang" in url
    def 头(self, url): return {**HDRS, 'Referer': 'https://www.haitang41.com/'}
    def 章节列表(self, soup, base):
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
            u = a['href'] if a['href'].startswith('http') else urljoin(base, a['href'])
            t = a.get_text(strip=True)
            if u not in seen and t: seen.add(u); 结果.append((u, t))
        return 书名, 结果
    def 正文(self, soup): return soup.find(id='rtext')
    def 下一页(self, soup, url):
        for a in soup.find_all('a'):
            if a.get_text(strip=True) == '下一页':
                h = a.get('href','')
                if '_' in h.split('/')[-1]:
                    return h if h.startswith('http') else urljoin(url, h)
        return None
    def 搜索url(self, domain, kw):
        return f"{domain}/modules/article/search.php?searchkey={quote(kw)}"
    def 解析搜索(self, soup, domain):
        results = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/book/' not in href: continue
            t = a.get_text(strip=True)
            if not t or len(t) > 50: continue
            url = href if href.startswith('http') else urljoin(domain, href)
            if url not in [r['url'] for r in results]:
                results.append({'title': t, 'url': url})
        return results[:15]

class 第一版主适配器:
    名称 = "第一版主"
    def 匹配(self, url): return "diyibanzhu" in url
    def 头(self, url):
        parsed = urlparse(url)
        return {**HDRS,
                'User-Agent': 'Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36',
                'Referer': f"{parsed.scheme}://{parsed.netloc}/"}
    def 章节列表(self, soup, base):
        书名 = soup.find('h1').get_text(strip=True) if soup.find('h1') else '未知'
        结果, seen = [], set()
        for ul in soup.find_all('ul', class_='list'):
            for li in ul.find_all('li'):
                a = li.find('a', href=True)
                if not a: continue
                href = a['href']
                u = href if href.startswith('http') else urljoin(base, href)
                t = a.get_text(strip=True)
                if u not in seen and t: seen.add(u); 结果.append((u, t))
        return 书名, 结果
    def 正文(self, soup): return soup.find(id='nr1')
    def 下一页(self, soup, url):
        for a in soup.find_all('a'):
            t = a.get_text(strip=True)
            if '下一页' in t and '下一章' not in t:
                h = a.get('href','')
                if h and not h.startswith('javascript'):
                    return h if h.startswith('http') else urljoin(url, h)
        return None
    def 搜索url(self, domain, kw):
        return f"{domain}/wap.php?action=search&keyword={quote(kw)}"
    def 解析搜索(self, soup, domain):
        results = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            t = a.get_text(strip=True)
            if not t or len(t) > 50 or len(t) < 2: continue
            if 'action=list' not in href and '/book/' not in href: continue
            url = href if href.startswith('http') else urljoin(domain, href)
            if url not in [r['url'] for r in results]:
                results.append({'title': t, 'url': url})
        return results[:15]

class 通用适配器:
    名称 = "通用"
    def 匹配(self, url): return True
    def 头(self, url):
        parsed = urlparse(url)
        return {**HDRS, 'Referer': f"{parsed.scheme}://{parsed.netloc}/"}
    def 章节列表(self, soup, base):
        书名 = '未知'
        for tag in soup.find_all(['h1','h2']):
            t = tag.get_text(strip=True)
            if t and len(t) < 40: 书名 = t.split('_')[0].strip(); break
        容器 = {}
        for a in soup.find_all('a', href=True):
            t = a.get_text(strip=True)
            if not t or len(t) > 60: continue
            p = a.parent
            for _ in range(4):
                if p is None: break
                pid = id(p)
                if pid not in 容器: 容器[pid] = []
                容器[pid].append((a['href'], t))
                p = p.parent
        结果, seen = [], set()
        if 容器:
            best = max(容器, key=lambda k: len(容器[k]))
            for href, t in 容器[best]:
                u = href if href.startswith('http') else urljoin(base, href)
                if u not in seen and t: seen.add(u); 结果.append((u, t))
        return 书名, 结果
    def 正文(self, soup):
        for sel in ['#rtext','#content','#nr1','#chaptercontent','.read-content','.chapter-content']:
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
    def 搜索url(self, domain, kw):
        for path in [f'/search?q={quote(kw)}', f'/search.php?keyword={quote(kw)}',
                     f'/modules/article/search.php?searchkey={quote(kw)}']:
            return domain + path
    def 解析搜索(self, soup, domain):
        results = []
        for a in soup.find_all('a', href=True):
            t = a.get_text(strip=True)
            if not t or len(t) > 50 or len(t) < 2: continue
            url = a['href'] if a['href'].startswith('http') else urljoin(domain, a['href'])
            if url not in [r['url'] for r in results]:
                results.append({'title': t, 'url': url})
        return results[:15]

适配器列表 = [海棠适配器(), 第一版主适配器(), 通用适配器()]

def 获取适配器(url):
    for a in 适配器列表:
        if a.匹配(url): return a
    return 通用适配器()

# ── 抓取 ──────────────────────────────────────────────────────

def 抓一页(url, session, adp):
    r = session.get(url, headers=adp.头(url), timeout=12)
    r.encoding = r.apparent_encoding if r.encoding in ('ISO-8859-1', None) else r.encoding
    soup = BeautifulSoup(r.text, 'html.parser')
    for tag in soup.find_all(['script','style','nav','header','footer','aside']):
        tag.decompose()
    content = adp.正文(soup)
    if not content: return None, None
    for a in content.find_all('a'): a.decompose()
    for br in content.find_all('br'): br.replace_with('\n')
    lines = [l.strip() for l in content.get_text().splitlines()]
    lines = [l for l in lines if l and len(l) > 1]
    return '\n'.join(lines), adp.下一页(soup, url)

def 抓一章(url, session, adp, 重试=3):
    for attempt in range(重试):
        try:
            parts, cur = [], url
            while cur:
                text, nxt = 抓一页(cur, session, adp)
                if text: parts.append(text)
                cur = nxt
                if nxt: time.sleep(0.4)
            result = '\n'.join(parts)
            if result.strip(): return result
        except Exception:
            if attempt < 重试-1: time.sleep(2**attempt)
    return None

def 获取章节列表(目录url, session):
    记录网站(目录url)
    adp = 获取适配器(目录url)
    r = session.get(目录url, headers=adp.头(目录url), timeout=12)
    r.encoding = r.apparent_encoding if r.encoding in ('ISO-8859-1', None) else r.encoding
    soup = BeautifulSoup(r.text, 'html.parser')
    书名, lst = adp.章节列表(soup, 目录url)
    return 书名, lst, adp.名称

def 站内搜索(domain, kw, session):
    adp = 获取适配器(domain)
    search_url = adp.搜索url(domain, kw)
    try:
        r = session.get(search_url, headers=adp.头(search_url), timeout=10)
        r.encoding = r.apparent_encoding if r.encoding in ('ISO-8859-1', None) else r.encoding
        soup = BeautifulSoup(r.text, 'html.parser')
        return adp.解析搜索(soup, domain)
    except:
        return []

# ── epub ──────────────────────────────────────────────────────

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

# ── 工作线程 ──────────────────────────────────────────────────

class 获取章节线程(QThread):
    完成 = pyqtSignal(str, list, str)
    失败 = pyqtSignal(str)
    def __init__(self, url, session):
        super().__init__()
        self.url = url
        self.session = session
    def run(self):
        try:
            书名, lst, adp名 = 获取章节列表(self.url, self.session)
            self.完成.emit(书名, lst, adp名)
        except Exception as e:
            self.失败.emit(str(e))

class 下载线程(QThread):
    日志 = pyqtSignal(str, str)
    进度 = pyqtSignal(int, int)
    完成 = pyqtSignal(int, list, str)
    def __init__(self, 目标, url, 书名, 保存路径, settings, session):
        super().__init__()
        self.目标 = 目标
        self.url  = url
        self.书名 = 书名
        self.保存路径 = 保存路径
        self.settings = settings
        self.session  = session
        self._stop = False
    def stop(self): self._stop = True
    def run(self):
        adp = 获取适配器(self.url)
        进度data = 读进度(self.保存路径)
        已完成   = set(进度data.get('已完成', []))
        失败     = []
        epub数据 = []
        已抓     = 0
        os.makedirs(os.path.dirname(self.保存路径), exist_ok=True)
        with open(self.保存路径, 'a', encoding='utf-8') as f:
            for i, (url, 标题) in enumerate(self.目标):
                if self._stop:
                    self.日志.emit("已暂停。", "yellow"); break
                self.进度.emit(i+1, len(self.目标))
                if url in 已完成:
                    continue
                self.日志.emit(f"[{i+1}/{len(self.目标)}] {标题}", "white")
                内容 = 抓一章(url, self.session, adp)
                if 内容:
                    if self.settings.get('gen_txt', True):
                        f.write(f"\n{'─'*32}\n{标题}\n{'─'*32}\n{内容}\n")
                        f.flush()
                    epub数据.append((标题, 内容))
                    已完成.add(url)
                    进度data['已完成'] = list(已完成)
                    写进度(self.保存路径, 进度data)
                    已抓 += 1
                    self.日志.emit(f"  ✓ {len(内容)} 字", "green")
                else:
                    失败.append(标题)
                    self.日志.emit(f"  ✗ 失败（已重试3次）", "red")
                time.sleep(1)
        self.完成.emit(已抓, epub数据, self.保存路径)

class 搜索线程(QThread):
    结果 = pyqtSignal(list)
    def __init__(self, domain, kw, session):
        super().__init__()
        self.domain  = domain
        self.kw      = kw
        self.session = session
    def run(self):
        results = 站内搜索(self.domain, self.kw, self.session)
        self.结果.emit(results)

class 更新线程(QThread):
    日志    = pyqtSignal(str)
    完成    = pyqtSignal(bool)
    def __init__(self, exe_url):
        super().__init__()
        self.exe_url = exe_url
    def run(self):
        try:
            self.日志.emit("正在下载新版本...")
            r = requests.get(self.exe_url, timeout=60, stream=True)
            self_path = sys.executable if getattr(sys,'frozen',False) else os.path.abspath(__file__)
            tmp = self_path + '.new'
            with open(tmp, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            bak = self_path + '.bak'
            if os.path.exists(bak): os.remove(bak)
            os.rename(self_path, bak)
            os.rename(tmp, self_path)
            if os.path.exists(bak): os.remove(bak)
            self.日志.emit("下载完成！点确定重启程序。")
            self.完成.emit(True)
        except Exception as e:
            self.日志.emit(f"更新失败：{e}")
            self.完成.emit(False)

# ── 样式表 ────────────────────────────────────────────────────

def build_stylesheet(accent='#0078d4'):
    a  = accent
    ah = QColor(accent).darker(115).name()
    return f"""
QMainWindow, QWidget {{ background: #1c1c1c; color: #e0e0e0; font-family: "Microsoft YaHei UI"; }}
QTabWidget::pane {{ border: none; background: #1c1c1c; }}
QTabBar::tab {{ background: #2b2b2b; color: #888; padding: 10px 22px; border: none;
                border-radius: 6px 6px 0 0; margin-right: 2px; font-size: 13px; }}
QTabBar::tab:selected {{ background: #1c1c1c; color: #e0e0e0; border-bottom: 2px solid {a}; }}
QTabBar::tab:hover:!selected {{ background: #333; color: #ccc; }}
QLineEdit {{ background: #2a2a2a; border: 1px solid #3a3a3a; border-radius: 6px;
             padding: 8px 12px; color: #e0e0e0; font-size: 13px; selection-background-color: {a}; }}
QLineEdit:focus {{ border: 1px solid {a}; }}
QPushButton {{ background: {a}; color: white; border: none; border-radius: 6px;
               padding: 8px 18px; font-size: 13px; }}
QPushButton:hover {{ background: {ah}; }}
QPushButton:pressed {{ background: {ah}; padding: 9px 17px 7px 19px; }}
QPushButton:disabled {{ background: #3a3a3a; color: #666; }}
QPushButton[flat=true] {{ background: #2b2b2b; color: #ccc; border: 1px solid #3a3a3a; }}
QPushButton[flat=true]:hover {{ background: #333; }}
QProgressBar {{ background: #2a2a2a; border: none; border-radius: 3px; height: 5px; }}
QProgressBar::chunk {{ background: {a}; border-radius: 3px; }}
QTextEdit {{ background: #141414; border: 1px solid #2a2a2a; border-radius: 6px;
             color: #e0e0e0; font-family: "Cascadia Code","Consolas"; font-size: 10px; padding: 4px; }}
QTreeWidget {{ background: #1e1e1e; border: 1px solid #2a2a2a; border-radius: 6px;
               alternate-background-color: #222; color: #e0e0e0; }}
QTreeWidget::item:selected {{ background: {a}; color: white; }}
QTreeWidget::item:hover:!selected {{ background: #2a2a2a; }}
QHeaderView::section {{ background: #252525; color: #888; border: none;
                         border-right: 1px solid #333; padding: 6px 10px; font-size: 12px; }}
QScrollBar:vertical {{ background: #1c1c1c; width: 8px; border-radius: 4px; }}
QScrollBar::handle:vertical {{ background: #3a3a3a; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #4a4a4a; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: #1c1c1c; height: 8px; border-radius: 4px; }}
QScrollBar::handle:horizontal {{ background: #3a3a3a; border-radius: 4px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QComboBox {{ background: #2a2a2a; border: 1px solid #3a3a3a; border-radius: 6px;
              padding: 6px 12px; color: #e0e0e0; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{ background: #2a2a2a; border: 1px solid #3a3a3a; color: #e0e0e0; }}
QSpinBox {{ background: #2a2a2a; border: 1px solid #3a3a3a; border-radius: 6px;
             padding: 6px 8px; color: #e0e0e0; }}
QCheckBox {{ color: #e0e0e0; spacing: 8px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid #3a3a3a;
                         border-radius: 4px; background: #2a2a2a; }}
QCheckBox::indicator:checked {{ background: {a}; border: 1px solid {a}; }}
QLabel {{ color: #e0e0e0; }}
QLabel[muted=true] {{ color: #888; font-size: 12px; }}
QFrame[card=true] {{ background: #242424; border: 1px solid #303030; border-radius: 8px; }}
QSplitter::handle {{ background: #2a2a2a; }}
"""

# ── 卡片容器 ──────────────────────────────────────────────────

def card_widget(parent=None):
    w = QFrame(parent)
    w.setProperty('card', True)
    w.setStyleSheet("QFrame[card=true]{background:#242424;border:1px solid #303030;border-radius:8px;}")
    return w

def section_label(text):
    lbl = QLabel(text)
    lbl.setStyleSheet("color:#888;font-size:11px;padding:2px 0;")
    return lbl

# ── 主窗口 ────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = 读设置()
        self.session  = requests.Session()
        self.章节列表 = []
        self.书名     = ''
        self.adp_名   = ''
        self._dl_thread = None
        self._search_results = []

        self.setWindowTitle(f"FishHook  v{VERSION}")
        self.resize(800, 700)
        self.setMinimumSize(680, 560)
        self.setStyleSheet(build_stylesheet(self.settings.get('accent','#0078d4')))

        self._build_ui()

        if self.settings.get('check_update'):
            QTimer.singleShot(3000, self._auto_check_update)

    # ── UI 构建 ───────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        main_layout.addWidget(self.tabs)

        self.tabs.addTab(self._build_download(), "  下载  ")
        self.tabs.addTab(self._build_search(),   "  搜索  ")
        self.tabs.addTab(self._build_history(),  "  历史  ")
        self.tabs.addTab(self._build_settings(), "  设置  ")

    def _build_download(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20,16,20,16)
        layout.setSpacing(12)

        # 标题行
        title_row = QHBoxLayout()
        title = QLabel("FishHook")
        title.setStyleSheet("font-size:18px;font-weight:600;color:#e0e0e0;")
        self.adp_badge = QLabel("")
        self.adp_badge.setStyleSheet("color:#ffd700;font-size:12px;padding:3px 8px;"
                                      "background:#2a2200;border-radius:4px;")
        title_row.addWidget(title)
        title_row.addWidget(self.adp_badge)
        title_row.addStretch()
        layout.addLayout(title_row)

        # 网址卡片
        c1 = card_widget()
        c1l = QVBoxLayout(c1)
        c1l.setContentsMargins(16,12,16,14)
        c1l.setSpacing(8)
        c1l.addWidget(section_label("书籍目录页网址"))
        url_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.haitang41.com/book/10951/")
        self.url_input.returnPressed.connect(self._get_chapters)
        self.get_btn = QPushButton("获取章节")
        self.get_btn.setFixedWidth(100)
        self.get_btn.clicked.connect(self._get_chapters)
        url_row.addWidget(self.url_input)
        url_row.addWidget(self.get_btn)
        c1l.addLayout(url_row)
        self.book_label = QLabel("输入目录页网址，或切换到「搜索」找书")
        self.book_label.setStyleSheet(f"color:{self.settings.get('accent','#0078d4')};font-size:13px;font-weight:600;")
        c1l.addWidget(self.book_label)
        layout.addWidget(c1)

        # 范围卡片
        c2 = card_widget()
        c2l = QVBoxLayout(c2)
        c2l.setContentsMargins(16,12,16,14)
        c2l.setSpacing(8)
        c2l.addWidget(section_label("下载范围"))
        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("从第"))
        self.start_spin = QSpinBox()
        self.start_spin.setRange(1, 99999)
        self.start_spin.setValue(1)
        self.start_spin.setFixedWidth(70)
        range_row.addWidget(self.start_spin)
        range_row.addWidget(QLabel("章，下载"))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 99999)
        self.count_spin.setValue(9999)
        self.count_spin.setFixedWidth(70)
        range_row.addWidget(self.count_spin)
        range_row.addWidget(QLabel("章"))
        range_row.addStretch()
        c2l.addLayout(range_row)
        layout.addWidget(c2)

        # 路径卡片
        c3 = card_widget()
        c3l = QVBoxLayout(c3)
        c3l.setContentsMargins(16,12,16,14)
        c3l.setSpacing(8)
        c3l.addWidget(section_label("保存位置"))
        path_row = QHBoxLayout()
        self.path_input = QLineEdit(self.settings.get('save_path', r'D:\缓存文件\小说'))
        browse_btn = QPushButton("浏览")
        browse_btn.setProperty('flat', True)
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(self._browse_path)
        path_row.addWidget(self.path_input)
        path_row.addWidget(browse_btn)
        c3l.addLayout(path_row)
        layout.addWidget(c3)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        self.progress_label = QLabel("")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.progress_label.setStyleSheet("color:#888;font-size:11px;")
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_label)

        # 日志
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(120)
        layout.addWidget(self.log_box)

        # 按钮行
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("▶  开始下载")
        self.start_btn.setFixedHeight(38)
        self.start_btn.clicked.connect(self._start_download)
        self.stop_btn = QPushButton("⏹  暂停")
        self.stop_btn.setProperty('flat', True)
        self.stop_btn.setFixedHeight(38)
        self.stop_btn.clicked.connect(self._stop_download)
        self.open_btn = QPushButton("📂  打开文件夹")
        self.open_btn.setProperty('flat', True)
        self.open_btn.setFixedHeight(38)
        self.open_btn.clicked.connect(self._open_folder)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addWidget(self.open_btn)
        layout.addLayout(btn_row)

        return page

    def _build_search(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20,16,20,16)
        layout.setSpacing(12)

        layout.addWidget(QLabel("选择网站，输入书名，站内搜索"))

        # 常用网站
        sites_card = card_widget()
        sites_cl = QVBoxLayout(sites_card)
        sites_cl.setContentsMargins(16,12,16,14)
        sites_cl.setSpacing(8)
        sites_cl.addWidget(section_label("常用网站（按使用次数排序，点击选择）"))
        self.sites_btn_row = QHBoxLayout()
        self.sites_btn_row.setSpacing(8)
        self.sites_btn_row.addStretch()
        sites_cl.addLayout(self.sites_btn_row)
        layout.addWidget(sites_card)
        self._refresh_site_btns()

        # 当前选中网站
        self.selected_domain = ""
        self.selected_label = QLabel("未选择网站")
        self.selected_label.setStyleSheet("color:#888;font-size:12px;")
        layout.addWidget(self.selected_label)

        # 搜索框
        search_card = card_widget()
        search_cl = QVBoxLayout(search_card)
        search_cl.setContentsMargins(16,12,16,14)
        search_cl.setSpacing(8)
        search_cl.addWidget(section_label("搜索书名"))
        s_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入书名或关键词...")
        self.search_input.returnPressed.connect(self._do_search)
        self.search_btn = QPushButton("搜索")
        self.search_btn.setFixedWidth(90)
        self.search_btn.clicked.connect(self._do_search)
        s_row.addWidget(self.search_input)
        s_row.addWidget(self.search_btn)
        search_cl.addLayout(s_row)
        layout.addWidget(search_card)

        self.search_status = QLabel("")
        self.search_status.setStyleSheet("color:#ffd700;font-size:12px;")
        layout.addWidget(self.search_status)

        # 结果列表
        self.result_tree = QTreeWidget()
        self.result_tree.setHeaderLabels(["书名", "网站"])
        self.result_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.result_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.result_tree.header().resizeSection(1, 200)
        self.result_tree.setAlternatingRowColors(True)
        self.result_tree.itemDoubleClicked.connect(self._result_dblclick)
        layout.addWidget(self.result_tree)

        hint = QLabel("双击结果自动跳到下载页并获取章节")
        hint.setProperty('muted', True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        return page

    def _build_history(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20,16,20,16)
        layout.setSpacing(12)

        layout.addWidget(QLabel("下载历史"))

        self.hist_tree = QTreeWidget()
        self.hist_tree.setHeaderLabels(["书名","章数","时间","保存路径"])
        self.hist_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.hist_tree.header().resizeSection(0, 180)
        self.hist_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.hist_tree.header().resizeSection(1, 60)
        self.hist_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.hist_tree.header().resizeSection(2, 140)
        self.hist_tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.hist_tree.setAlternatingRowColors(True)
        self.hist_tree.itemDoubleClicked.connect(self._hist_dblclick)
        layout.addWidget(self.hist_tree)

        layout.addWidget(QLabel("访问过的网站"))

        self.site_tree = QTreeWidget()
        self.site_tree.setHeaderLabels(["域名","次数","最后访问"])
        self.site_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.site_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.site_tree.header().resizeSection(1, 60)
        self.site_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.site_tree.header().resizeSection(2, 140)
        self.site_tree.setAlternatingRowColors(True)
        layout.addWidget(self.site_tree)

        hint = QLabel("双击历史记录打开文件夹")
        hint.setProperty('muted', True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        self._refresh_history()
        return page

    def _build_settings(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20,16,20,16)
        layout.setSpacing(12)

        # 外观
        c1 = card_widget()
        c1l = QVBoxLayout(c1)
        c1l.setContentsMargins(16,12,16,14)
        c1l.setSpacing(10)
        c1l.addWidget(section_label("外观"))

        acc_row = QHBoxLayout()
        acc_row.addWidget(QLabel("主题色"))
        self.accent_preview = QLabel("  ")
        self.accent_preview.setFixedSize(28,28)
        accent = self.settings.get('accent','#0078d4')
        self.accent_preview.setStyleSheet(f"background:{accent};border-radius:6px;")
        acc_btn = QPushButton("更改颜色")
        acc_btn.setProperty('flat', True)
        acc_btn.setFixedWidth(100)
        acc_btn.clicked.connect(self._pick_color)
        preset_colors = ['#0078d4','#e94560','#1d9e75','#7f77dd','#ba7517','#d85a30']
        acc_row.addWidget(self.accent_preview)
        for c in preset_colors:
            btn = QPushButton()
            btn.setFixedSize(22,22)
            btn.setStyleSheet(f"background:{c};border-radius:5px;border:none;")
            btn.clicked.connect(lambda _, col=c: self._set_accent(col))
            acc_row.addWidget(btn)
        acc_row.addWidget(acc_btn)
        acc_row.addStretch()
        c1l.addLayout(acc_row)
        layout.addWidget(c1)

        # 行为
        c2 = card_widget()
        c2l = QVBoxLayout(c2)
        c2l.setContentsMargins(16,12,16,14)
        c2l.setSpacing(8)
        c2l.addWidget(section_label("行为"))
        self.toggle_txt   = QCheckBox("同时生成 txt")
        self.toggle_epub  = QCheckBox("同时生成 epub")
        self.toggle_open  = QCheckBox("下载完成后自动打开文件夹")
        self.toggle_upd   = QCheckBox("启动时检查更新")
        for cb, key in [(self.toggle_txt,'gen_txt'),(self.toggle_epub,'gen_epub'),
                        (self.toggle_open,'auto_open'),(self.toggle_upd,'check_update')]:
            cb.setChecked(self.settings.get(key, True))
            c2l.addWidget(cb)
        layout.addWidget(c2)

        # 版本管理
        c3 = card_widget()
        c3l = QVBoxLayout(c3)
        c3l.setContentsMargins(16,12,16,14)
        c3l.setSpacing(8)
        c3l.addWidget(section_label("程序管理"))
        ver_row = QHBoxLayout()
        ver_row.addWidget(QLabel(f"当前版本：v{VERSION}"))
        self.update_label = QLabel("")
        self.update_label.setStyleSheet("color:#ffd700;font-size:12px;")
        ver_row.addWidget(self.update_label)
        ver_row.addStretch()
        upd_btn = QPushButton("检查更新")
        upd_btn.setProperty('flat', True)
        upd_btn.setFixedWidth(100)
        upd_btn.clicked.connect(self._manual_check_update)
        uninstall_btn = QPushButton("卸载")
        uninstall_btn.setStyleSheet("background:#3a1010;color:#ff8080;border:none;border-radius:6px;padding:6px 14px;")
        uninstall_btn.clicked.connect(self._uninstall)
        ver_row.addWidget(upd_btn)
        ver_row.addWidget(uninstall_btn)
        c3l.addLayout(ver_row)
        layout.addWidget(c3)

        layout.addStretch()

        # 保存
        save_row = QHBoxLayout()
        save_btn = QPushButton("保存设置")
        save_btn.setFixedHeight(38)
        save_btn.clicked.connect(self._save_settings)
        reset_btn = QPushButton("重置默认")
        reset_btn.setProperty('flat', True)
        reset_btn.setFixedHeight(38)
        reset_btn.clicked.connect(self._reset_settings)
        save_row.addWidget(save_btn)
        save_row.addWidget(reset_btn)
        layout.addLayout(save_row)

        return page

    # ── 日志 ──────────────────────────────────────────────────

    def _log(self, msg, color='white'):
        colors = {'green':'#6ccb5f','red':'#ff6b6b','yellow':'#ffd700','white':'#cccccc'}
        c = colors.get(color, '#cccccc')
        self.log_box.append(f'<span style="color:{c};">{msg}</span>')
        self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())

    # ── 下载 Tab 操作 ─────────────────────────────────────────

    def _browse_path(self):
        p = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if p: self.path_input.setText(p)

    def _get_chapters(self):
        url = self.url_input.text().strip()
        if not url: return
        self._log("正在获取章节列表...", 'white')
        self.get_btn.setEnabled(False)
        self._fetch_thread = 获取章节线程(url, self.session)
        self._fetch_thread.完成.connect(self._on_chapters_fetched)
        self._fetch_thread.失败.connect(lambda e: (self._log(f"获取失败：{e}", 'red'), self.get_btn.setEnabled(True)))
        self._fetch_thread.start()

    def _on_chapters_fetched(self, 书名, lst, adp名):
        self.书名 = 书名
        self.章节列表 = lst
        self.adp_名 = adp名
        self.book_label.setText(f"《{书名}》共 {len(lst)} 章")
        self.adp_badge.setText(f" {adp名} ")
        self.adp_badge.setVisible(bool(adp名))
        first = lst[0][1] if lst else '无'
        last  = lst[-1][1] if lst else '无'
        self._log(f"获取成功：{len(lst)} 章", 'green')
        self._log(f"  第一章：{first}")
        self._log(f"  最后章：{last}")
        self.get_btn.setEnabled(True)
        self._refresh_history()

    def _start_download(self):
        if self._dl_thread and self._dl_thread.isRunning(): return
        if not self.章节列表:
            QMessageBox.warning(self, "提示", "请先获取章节列表")
            return
        开始 = self.start_spin.value() - 1
        数量 = self.count_spin.value()
        目标 = self.章节列表[开始 : 开始+数量]
        目录 = self.path_input.text().strip()
        安全书名 = re.sub(r'[\\/:*?"<>|]', '', self.书名)
        保存路径  = os.path.join(目录, f"{安全书名}.txt")
        self.progress_bar.setMaximum(len(目标))
        self.progress_bar.setValue(0)
        self.start_btn.setEnabled(False)
        self._log(f"\n开始下载《{self.书名}》共 {len(目标)} 章", 'white')
        self._dl_thread = 下载线程(目标, self.url_input.text().strip(),
                                  self.书名, 保存路径, self.settings, self.session)
        self._dl_thread.日志.connect(self._log)
        self._dl_thread.进度.connect(lambda cur, tot: (
            self.progress_bar.setValue(cur),
            self.progress_label.setText(f"{cur}/{tot}  ·  {round(cur/tot*100,1)}%")))
        self._dl_thread.完成.connect(self._on_download_done)
        self._dl_thread.start()

    def _on_download_done(self, 已抓, epub数据, 保存路径):
        self._log(f"\n完成！共 {已抓} 章 → {保存路径}", 'green')
        写历史({'书名': self.书名, '章数': 已抓,
                '时间': datetime.now().strftime('%Y-%m-%d %H:%M'),
                '保存路径': 保存路径})
        self._refresh_history()
        self.start_btn.setEnabled(True)
        if epub数据 and self.settings.get('gen_epub'):
            def _gen():
                try:
                    ep = 生成epub(self.书名, epub数据, 保存路径)
                    self._log(f"epub 已保存：{ep}", 'green')
                except Exception as e:
                    self._log(f"epub 失败：{e}", 'red')
            threading.Thread(target=_gen, daemon=True).start()
        if self.settings.get('auto_open') and os.path.exists(os.path.dirname(保存路径)):
            os.startfile(os.path.dirname(保存路径))

    def _stop_download(self):
        if self._dl_thread and self._dl_thread.isRunning():
            self._dl_thread.stop()

    def _open_folder(self):
        p = self.path_input.text().strip()
        if os.path.exists(p): os.startfile(p)

    # ── 搜索 Tab 操作 ─────────────────────────────────────────

    def _refresh_site_btns(self):
        for i in reversed(range(self.sites_btn_row.count())):
            w = self.sites_btn_row.itemAt(i).widget()
            if w: w.deleteLater()
        sites = 常用网站()[:8]
        if not sites:
            lbl = QLabel("暂无记录，下载后自动记录")
            lbl.setStyleSheet("color:#666;font-size:12px;")
            self.sites_btn_row.addWidget(lbl)
        for domain, info in sites:
            name = info.get('name', domain)[:14]
            count = info.get('count', 0)
            btn = QPushButton(f"{name}  ({count}次)")
            btn.setProperty('flat', True)
            btn.setFixedHeight(30)
            btn.clicked.connect(lambda _, d=domain: self._select_site(d))
            self.sites_btn_row.addWidget(btn)
        self.sites_btn_row.addStretch()

    def _select_site(self, domain):
        self.selected_domain = domain
        data = 读网站()
        name = data.get(domain, {}).get('name', domain)
        self.selected_label.setText(f"已选择：{name}  ({domain})")
        self.selected_label.setStyleSheet(f"color:{self.settings.get('accent','#0078d4')};font-size:12px;")

    def _do_search(self):
        if not self.selected_domain:
            QMessageBox.information(self, "提示", "请先点击上方选择一个网站")
            return
        kw = self.search_input.text().strip()
        if not kw: return
        self.search_status.setText("搜索中...")
        self.search_btn.setEnabled(False)
        self.result_tree.clear()
        self._search_results = []
        self._s_thread = 搜索线程(self.selected_domain, kw, self.session)
        self._s_thread.结果.connect(self._on_search_done)
        self._s_thread.start()

    def _on_search_done(self, results):
        self._search_results = results
        self.result_tree.clear()
        for r in results:
            item = QTreeWidgetItem([r['title'], r.get('site', self.selected_domain)])
            self.result_tree.addTopLevelItem(item)
        self.search_status.setText(f"找到 {len(results)} 条结果，双击直接下载")
        self.search_btn.setEnabled(True)

    def _result_dblclick(self, item, _):
        idx = self.result_tree.indexOfTopLevelItem(item)
        if idx < 0 or idx >= len(self._search_results): return
        url = self._search_results[idx]['url']
        self.url_input.setText(url)
        self.tabs.setCurrentIndex(0)
        self._get_chapters()

    # ── 历史 Tab 操作 ─────────────────────────────────────────

    def _refresh_history(self):
        self.hist_tree.clear()
        for h in 读历史():
            item = QTreeWidgetItem([h.get('书名',''), str(h.get('章数','')),
                                     h.get('时间',''), h.get('保存路径','')])
            self.hist_tree.addTopLevelItem(item)
        self.site_tree.clear()
        for domain, info in 常用网站():
            item = QTreeWidgetItem([info.get('name', domain),
                                     str(info.get('count',0)),
                                     info.get('last','')])
            self.site_tree.addTopLevelItem(item)

    def _hist_dblclick(self, item, _):
        path = item.text(3)
        folder = os.path.dirname(path)
        if os.path.exists(folder): os.startfile(folder)

    # ── 设置 Tab 操作 ─────────────────────────────────────────

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self.settings.get('accent','#0078d4')), self)
        if c.isValid(): self._set_accent(c.name())

    def _set_accent(self, color):
        self.settings['accent'] = color
        self.accent_preview.setStyleSheet(f"background:{color};border-radius:6px;")
        self.setStyleSheet(build_stylesheet(color))
        self.book_label.setStyleSheet(f"color:{color};font-size:13px;font-weight:600;")

    def _save_settings(self):
        self.settings['gen_txt']      = self.toggle_txt.isChecked()
        self.settings['gen_epub']     = self.toggle_epub.isChecked()
        self.settings['auto_open']    = self.toggle_open.isChecked()
        self.settings['check_update'] = self.toggle_upd.isChecked()
        self.settings['save_path']    = self.path_input.text()
        写设置(self.settings)
        QMessageBox.information(self, "保存成功", "设置已保存。")

    def _reset_settings(self):
        if QMessageBox.question(self, "确认", "重置所有设置？") == QMessageBox.StandardButton.Yes:
            写设置(DEFAULT_SETTINGS)
            QMessageBox.information(self, "完成", "已重置，请重启程序。")

    def _uninstall(self):
        目录 = 运行目录()
        清理 = [f for f in [HISTORY_FILE, SETTINGS_FILE, SITES_FILE] if os.path.exists(f)]
        for fn in os.listdir(目录):
            if fn.endswith('.progress.json'): 清理.append(os.path.join(目录,fn))
        self_path = sys.executable if getattr(sys,'frozen',False) else os.path.abspath(__file__)
        清理.append(self_path)
        msg = "将删除：\n" + "\n".join(清理) + "\n\n下载的小说不受影响。确认？"
        if QMessageBox.question(self, "确认卸载", msg) != QMessageBox.StandardButton.Yes: return
        bat = os.path.join(tempfile.gettempdir(), 'uninstall_fishhook.bat')
        with open(bat,'w') as f:
            f.write('@echo off\ntimeout /t 2 /nobreak >nul\n')
            for fp in 清理: f.write(f'del /f /q "{fp}" >nul 2>&1\n')
            f.write(f'del /f /q "{bat}"\n')
        subprocess.Popen(['cmd','/c',bat], creationflags=0x08000000)
        sys.exit(0)

    # ── 更新 ──────────────────────────────────────────────────

    def _auto_check_update(self):
        def _check():
            try:
                r = requests.get(GITHUB_VERSION_URL, timeout=8)
                latest = r.text.strip()
                if latest != VERSION:
                    self.update_label.setText(f"发现新版本 v{latest}")
                    self._log(f"发现新版本 v{latest}，可在「设置」里更新", 'yellow')
            except: pass
        threading.Thread(target=_check, daemon=True).start()

    def _manual_check_update(self):
        self.update_label.setText("检查中...")
        def _check():
            try:
                r = requests.get(GITHUB_VERSION_URL, timeout=8)
                latest = r.text.strip()
                if latest != VERSION:
                    self.update_label.setText(f"发现新版本 v{latest}")
                    reply = QMessageBox.question(self, "发现更新",
                        f"发现新版本 v{latest}（当前 v{VERSION}）\n\n"
                        f"更新将下载新的 exe 替换当前程序，完成后需要重启。\n继续？")
                    if reply == QMessageBox.StandardButton.Yes:
                        self._do_update(GITHUB_EXE_URL)
                else:
                    self.update_label.setText("已是最新版本")
            except Exception as e:
                self.update_label.setText(f"检查失败：{e}")
        threading.Thread(target=_check, daemon=True).start()

    def _do_update(self, exe_url):
        self._upd_thread = 更新线程(exe_url)
        self._upd_thread.日志.connect(lambda m: self._log(m, 'yellow'))
        self._upd_thread.完成.connect(self._on_update_done)
        self._upd_thread.start()

    def _on_update_done(self, ok):
        if ok:
            QMessageBox.information(self, "更新完成", "新版本已就绪，点确定重启程序。")
            python = sys.executable
            os.execl(python, python, *sys.argv)
        else:
            QMessageBox.warning(self, "更新失败", "请稍后重试，或手动下载最新版本。")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
