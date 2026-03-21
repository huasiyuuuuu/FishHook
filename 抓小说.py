import sys, os, time, json, re, uuid, zipfile, threading, shutil, subprocess, tempfile
from datetime import datetime
from urllib.parse import urljoin, urlparse, quote

import requests
from bs4 import BeautifulSoup

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QProgressBar,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QCheckBox, QFrame,
    QMessageBox, QHeaderView, QSpinBox, QSplitter, QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject
from PyQt6.QtGui import QFont, QColor, QTextCursor

VERSION = "2.1.0"
GITHUB_RAW         = "https://raw.githubusercontent.com/huasiyuuuuu/haitang-downloader/main/"
GITHUB_VERSION_URL = GITHUB_RAW + "version.txt"
GITHUB_EXE_URL     = GITHUB_RAW + "FishHook.exe"
LOG_MAX_LINES      = 500

def 运行目录():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

HISTORY_FILE  = os.path.join(运行目录(), 'fishhook_history.json')
SITES_FILE    = os.path.join(运行目录(), 'fishhook_sites.json')
SETTINGS_FILE = os.path.join(运行目录(), 'fishhook_settings.json')

# ── 设置 ──────────────────────────────────────────────────────

DEFAULTS = {
    'save_path':    r'D:\缓存文件\小说',
    'gen_epub':     True,
    'gen_txt':      True,
    'auto_open':    True,
    'check_update': True,
}

def 读设置():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return {**DEFAULTS, **json.load(f)}
        except: pass
    return DEFAULTS.copy()

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
        data[domain] = {'name': parsed.netloc, 'count': 0, 'last': ''}
    data[domain]['count'] += 1
    data[domain]['last'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    写网站(data)

def 常用网站():
    return sorted(读网站().items(), key=lambda x: x[1]['count'], reverse=True)

# ── 下载历史 ──────────────────────────────────────────────────

def 读历史():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return []

def 写历史(r):
    h = 读历史()
    for i, x in enumerate(h):
        if x.get('保存路径') == r.get('保存路径'):
            h[i] = r; break
    else:
        h.insert(0, r)
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
    def 匹配(self, u): return "haitang" in u
    def 头(self, u): return {**HDRS, 'Referer': 'https://www.haitang41.com/'}
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
            u2 = a['href'] if a['href'].startswith('http') else urljoin(base, a['href'])
            t = a.get_text(strip=True)
            if u2 not in seen and t: seen.add(u2); 结果.append((u2, t))
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
            u = href if href.startswith('http') else urljoin(domain, href)
            if u not in [r['url'] for r in results]:
                results.append({'title': t, 'url': u, 'site': domain})
        return results[:15]

class 第一版主适配器:
    名称 = "第一版主"
    def 匹配(self, u): return "diyibanzhu" in u
    def 头(self, u):
        p = urlparse(u)
        return {**HDRS,
                'User-Agent': 'Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36',
                'Referer': f"{p.scheme}://{p.netloc}/"}
    def 章节列表(self, soup, base):
        书名 = soup.find('h1').get_text(strip=True) if soup.find('h1') else '未知'
        结果, seen = [], set()
        for ul in soup.find_all('ul', class_='list'):
            for li in ul.find_all('li'):
                a = li.find('a', href=True)
                if not a: continue
                u = a['href'] if a['href'].startswith('http') else urljoin(base, a['href'])
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
            u = href if href.startswith('http') else urljoin(domain, href)
            if u not in [r['url'] for r in results]:
                results.append({'title': t, 'url': u, 'site': domain})
        return results[:15]

class 通用适配器:
    名称 = "通用"
    def 匹配(self, u): return True
    def 头(self, u):
        p = urlparse(u)
        return {**HDRS, 'Referer': f"{p.scheme}://{p.netloc}/"}
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
        return f"{domain}/search?q={quote(kw)}"
    def 解析搜索(self, soup, domain):
        results = []
        for a in soup.find_all('a', href=True):
            t = a.get_text(strip=True)
            if not t or len(t) > 50 or len(t) < 2: continue
            u = a['href'] if a['href'].startswith('http') else urljoin(domain, a['href'])
            if u not in [r['url'] for r in results]:
                results.append({'title': t, 'url': u, 'site': domain})
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
    adp = 获取适配器(domain + '/')
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

# ── 工作线程（所有 UI 操作全部通过信号发回主线程）────────────

class 获取章节线程(QThread):
    成功  = pyqtSignal(str, list, str)   # 书名, 列表, 适配器名
    失败  = pyqtSignal(str)
    def __init__(self, url, session):
        super().__init__(); self.url = url; self.session = session
    def run(self):
        try:
            书名, lst, adp名 = 获取章节列表(self.url, self.session)
            self.成功.emit(书名, lst, adp名)
        except Exception as e:
            self.失败.emit(str(e))

class 下载线程(QThread):
    日志  = pyqtSignal(str, str)         # msg, color
    进度  = pyqtSignal(int, int)         # cur, total
    完成  = pyqtSignal(int, list, str)   # 已抓数, epub数据, 保存路径
    def __init__(self, 目标, url, 书名, 保存路径, settings, session):
        super().__init__()
        self.目标=目标; self.url=url; self.书名=书名
        self.保存路径=保存路径; self.settings=settings; self.session=session
        self._stop=False
    def stop(self): self._stop=True
    def run(self):
        adp = 获取适配器(self.url)
        进度data = 读进度(self.保存路径)
        已完成   = set(进度data.get('已完成', []))
        失败     = []
        epub数据 = []
        已抓     = 0
        try:
            os.makedirs(os.path.dirname(self.保存路径), exist_ok=True)
        except: pass
        try:
            f = open(self.保存路径, 'a', encoding='utf-8')
        except Exception as e:
            self.日志.emit(f"无法创建文件：{e}", "red")
            self.完成.emit(0, [], self.保存路径)
            return
        try:
            for i, (url, 标题) in enumerate(self.目标):
                if self._stop:
                    self.日志.emit("已暂停。", "yellow"); break
                self.进度.emit(i+1, len(self.目标))
                if url in 已完成: continue
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
                    self.日志.emit(f"  ✗ 失败", "red")
                time.sleep(1)
        finally:
            f.close()
        self.完成.emit(已抓, epub数据, self.保存路径)

class 搜索线程(QThread):
    结果 = pyqtSignal(list)
    def __init__(self, domain, kw, session):
        super().__init__()
        self.domain=domain; self.kw=kw; self.session=session
    def run(self):
        self.结果.emit(站内搜索(self.domain, self.kw, self.session))

class 更新检查线程(QThread):
    有更新  = pyqtSignal(str)    # latest version
    无更新  = pyqtSignal()
    出错    = pyqtSignal(str)
    def run(self):
        try:
            r = requests.get(GITHUB_VERSION_URL, timeout=8)
            latest = r.text.strip()
            if latest and latest != VERSION:
                self.有更新.emit(latest)
            else:
                self.无更新.emit()
        except Exception as e:
            self.出错.emit(str(e))

class 更新下载线程(QThread):
    进度  = pyqtSignal(int)      # percent
    完成  = pyqtSignal(bool, str)
    def __init__(self, exe_url):
        super().__init__(); self.exe_url=exe_url
    def run(self):
        try:
            r = requests.get(self.exe_url, timeout=120, stream=True)
            total = int(r.headers.get('content-length', 0))
            self_path = sys.executable if getattr(sys,'frozen',False) else os.path.abspath(__file__)
            tmp = self_path + '.new'
            done = 0
            with open(tmp, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    done += len(chunk)
                    if total: self.进度.emit(int(done/total*100))
            bak = self_path + '.bak'
            if os.path.exists(bak): os.remove(bak)
            os.rename(self_path, bak)
            os.rename(tmp, self_path)
            if os.path.exists(bak): os.remove(bak)
            self.完成.emit(True, "")
        except Exception as e:
            self.完成.emit(False, str(e))

# ── 样式表 ────────────────────────────────────────────────────

QSS = """
* { font-family: "Microsoft YaHei UI"; }
QMainWindow, QDialog { background: #1c1c1c; }
QWidget { background: #1c1c1c; color: #d4d4d4; font-size: 13px; }
QTabWidget::pane { border: none; background: #1c1c1c; }
QTabBar { background: #242424; }
QTabBar::tab {
    background: transparent; color: #777;
    padding: 9px 22px; border: none;
    border-bottom: 2px solid transparent;
    font-size: 13px; margin-right: 1px;
}
QTabBar::tab:selected { color: #e0e0e0; border-bottom: 2px solid #0078d4; }
QTabBar::tab:hover:!selected { color: #aaa; background: #252525; }
QLineEdit {
    background: #2a2a2a; border: 1px solid #383838;
    border-radius: 6px; padding: 7px 11px;
    color: #e0e0e0; font-size: 13px;
    selection-background-color: #0078d4;
}
QLineEdit:focus { border-color: #0078d4; }
QLineEdit:disabled { color: #555; background: #222; }
QPushButton {
    background: #0078d4; color: #fff; border: none;
    border-radius: 6px; padding: 7px 16px; font-size: 13px;
    min-height: 30px;
}
QPushButton:hover { background: #1084d8; }
QPushButton:pressed { background: #006cbd; }
QPushButton:disabled { background: #2a2a2a; color: #555; }
QPushButton#flat {
    background: #282828; color: #bbb;
    border: 1px solid #383838;
}
QPushButton#flat:hover { background: #303030; color: #ddd; }
QPushButton#danger {
    background: #3a1212; color: #f08080;
    border: 1px solid #5a2020;
}
QPushButton#danger:hover { background: #4a1818; }
QProgressBar {
    background: #282828; border: none;
    border-radius: 3px; height: 4px;
    text-align: center; color: transparent;
}
QProgressBar::chunk { background: #0078d4; border-radius: 3px; }
QTextEdit {
    background: #161616; border: 1px solid #2a2a2a;
    border-radius: 6px; color: #c8c8c8;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 11px; padding: 6px;
    selection-background-color: #0078d4;
}
QTreeWidget {
    background: #1e1e1e; border: 1px solid #2a2a2a;
    border-radius: 6px; color: #d4d4d4;
    alternate-background-color: #212121;
    outline: none;
}
QTreeWidget::item { padding: 4px 0; }
QTreeWidget::item:selected { background: #0078d4; color: #fff; }
QTreeWidget::item:hover:!selected { background: #272727; }
QHeaderView::section {
    background: #222; color: #777;
    border: none; border-right: 1px solid #2a2a2a;
    padding: 5px 10px; font-size: 12px;
}
QScrollBar:vertical {
    background: transparent; width: 6px; margin: 0;
}
QScrollBar::handle:vertical {
    background: #3a3a3a; border-radius: 3px; min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #4a4a4a; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar:horizontal {
    background: transparent; height: 6px;
}
QScrollBar::handle:horizontal {
    background: #3a3a3a; border-radius: 3px;
}
QSpinBox {
    background: #2a2a2a; border: 1px solid #383838;
    border-radius: 6px; padding: 5px 8px; color: #e0e0e0;
}
QCheckBox { color: #d4d4d4; spacing: 8px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #505050; border-radius: 4px;
    background: #2a2a2a;
}
QCheckBox::indicator:checked {
    background: #0078d4; border-color: #0078d4;
    image: none;
}
QLabel { color: #d4d4d4; background: transparent; }
QFrame#card {
    background: #222; border: 1px solid #2e2e2e;
    border-radius: 8px;
}
QSplitter::handle { background: #2a2a2a; height: 1px; }
QMessageBox { background: #1c1c1c; }
QMessageBox QLabel { color: #d4d4d4; }
QMessageBox QPushButton { min-width: 80px; }
"""

# ── 辅助控件 ──────────────────────────────────────────────────

def card(parent=None):
    f = QFrame(parent)
    f.setObjectName("card")
    return f

def small_label(text):
    lbl = QLabel(text)
    lbl.setStyleSheet("color:#666;font-size:11px;letter-spacing:0.3px;")
    return lbl

def hline():
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("border:none;border-top:1px solid #2a2a2a;")
    return f

# ── 主窗口 ────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings     = 读设置()
        self.session      = requests.Session()
        self.章节列表     = []
        self.书名         = ''
        self._dl_thread   = None
        self._fetch_thread= None
        self._search_results = []
        self._selected_domain = ""

        self.setWindowTitle(f"FishHook  v{VERSION}")
        self.resize(820, 720)
        self.setMinimumSize(700, 580)
        self.setStyleSheet(QSS)
        self._build()
        QTimer.singleShot(2000, self._auto_update_check)

    def closeEvent(self, e):
        if self._dl_thread and self._dl_thread.isRunning():
            self._dl_thread.stop()
            self._dl_thread.wait(3000)
        e.accept()

    # ── 构建 ──────────────────────────────────────────────────

    def _build(self):
        cw = QWidget(); self.setCentralWidget(cw)
        ml = QVBoxLayout(cw); ml.setContentsMargins(0,0,0,0); ml.setSpacing(0)
        self.tabs = QTabWidget(); self.tabs.setDocumentMode(True)
        ml.addWidget(self.tabs)
        self.tabs.addTab(self._tab_download(), "  下载  ")
        self.tabs.addTab(self._tab_search(),   "  搜索  ")
        self.tabs.addTab(self._tab_history(),  "  历史  ")
        self.tabs.addTab(self._tab_settings(), "  设置  ")

    def _tab_download(self):
        pg = QWidget(); L = QVBoxLayout(pg)
        L.setContentsMargins(20,16,20,16); L.setSpacing(10)

        # 标题
        hr = QHBoxLayout()
        t = QLabel("FishHook"); t.setStyleSheet("font-size:20px;font-weight:600;color:#e8e8e8;")
        self.adp_lbl = QLabel(""); self.adp_lbl.setStyleSheet(
            "color:#ffd700;font-size:11px;background:#222200;border-radius:4px;padding:2px 8px;")
        hr.addWidget(t); hr.addWidget(self.adp_lbl); hr.addStretch()
        L.addLayout(hr)

        # 网址卡片
        c1 = card(); cl = QVBoxLayout(c1); cl.setContentsMargins(16,12,16,14); cl.setSpacing(8)
        cl.addWidget(small_label("书籍目录页网址"))
        ur = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.haitang41.com/book/10951/")
        self.url_input.returnPressed.connect(self._fetch)
        self.fetch_btn = QPushButton("获取章节"); self.fetch_btn.setFixedWidth(100)
        self.fetch_btn.clicked.connect(self._fetch)
        ur.addWidget(self.url_input); ur.addWidget(self.fetch_btn)
        cl.addLayout(ur)
        self.book_lbl = QLabel("输入目录页网址，或切换到「搜索」标签")
        self.book_lbl.setStyleSheet("color:#0078d4;font-size:13px;font-weight:600;")
        cl.addWidget(self.book_lbl)
        L.addWidget(c1)

        # 范围 + 路径（横排）
        row2 = QHBoxLayout(); row2.setSpacing(10)
        c2 = card(); c2l = QVBoxLayout(c2); c2l.setContentsMargins(16,12,16,14); c2l.setSpacing(8)
        c2l.addWidget(small_label("下载范围"))
        rr = QHBoxLayout()
        rr.addWidget(QLabel("从第"))
        self.start_sp = QSpinBox(); self.start_sp.setRange(1,99999); self.start_sp.setValue(1); self.start_sp.setFixedWidth(68)
        rr.addWidget(self.start_sp)
        rr.addWidget(QLabel("章，下载"))
        self.count_sp = QSpinBox(); self.count_sp.setRange(1,99999); self.count_sp.setValue(9999); self.count_sp.setFixedWidth(68)
        rr.addWidget(self.count_sp)
        rr.addWidget(QLabel("章")); rr.addStretch()
        c2l.addLayout(rr); row2.addWidget(c2)

        c3 = card(); c3l = QVBoxLayout(c3); c3l.setContentsMargins(16,12,16,14); c3l.setSpacing(8)
        c3l.addWidget(small_label("保存位置"))
        pr = QHBoxLayout()
        self.path_input = QLineEdit(self.settings.get('save_path', r'D:\缓存文件\小说'))
        br = QPushButton("浏览"); br.setObjectName("flat"); br.setFixedWidth(64)
        br.clicked.connect(self._browse)
        pr.addWidget(self.path_input); pr.addWidget(br)
        c3l.addLayout(pr); row2.addWidget(c3)
        L.addLayout(row2)

        # 进度
        self.prog = QProgressBar(); self.prog.setFixedHeight(4); self.prog.setTextVisible(False)
        self.prog_lbl = QLabel(""); self.prog_lbl.setStyleSheet("color:#555;font-size:11px;")
        self.prog_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        L.addWidget(self.prog); L.addWidget(self.prog_lbl)

        # 日志
        self.log = QTextEdit(); self.log.setReadOnly(True)
        L.addWidget(self.log, 1)

        # 按钮
        br2 = QHBoxLayout(); br2.setSpacing(8)
        self.start_btn = QPushButton("▶  开始下载"); self.start_btn.setFixedHeight(36)
        self.start_btn.clicked.connect(self._start_dl)
        self.stop_btn = QPushButton("⏹  暂停"); self.stop_btn.setObjectName("flat"); self.stop_btn.setFixedHeight(36)
        self.stop_btn.clicked.connect(self._stop_dl)
        self.open_btn = QPushButton("📂  打开文件夹"); self.open_btn.setObjectName("flat"); self.open_btn.setFixedHeight(36)
        self.open_btn.clicked.connect(self._open_dir)
        br2.addWidget(self.start_btn); br2.addWidget(self.stop_btn); br2.addWidget(self.open_btn)
        L.addLayout(br2)
        return pg

    def _tab_search(self):
        pg = QWidget(); L = QVBoxLayout(pg)
        L.setContentsMargins(20,16,20,16); L.setSpacing(10)

        c1 = card(); c1l = QVBoxLayout(c1); c1l.setContentsMargins(16,12,16,14); c1l.setSpacing(10)
        c1l.addWidget(small_label("常用网站（按使用次数排序）"))
        self.site_btn_layout = QHBoxLayout(); self.site_btn_layout.setSpacing(8)
        self.site_btn_layout.addStretch()
        c1l.addLayout(self.site_btn_layout)
        self.sel_lbl = QLabel("未选择网站 — 请点击上方选择")
        self.sel_lbl.setStyleSheet("color:#555;font-size:12px;")
        c1l.addWidget(self.sel_lbl)
        L.addWidget(c1)

        c2 = card(); c2l = QVBoxLayout(c2); c2l.setContentsMargins(16,12,16,14); c2l.setSpacing(8)
        c2l.addWidget(small_label("书名关键词"))
        sr = QHBoxLayout()
        self.search_input = QLineEdit(); self.search_input.setPlaceholderText("输入书名...")
        self.search_input.returnPressed.connect(self._do_search)
        self.search_btn = QPushButton("搜索"); self.search_btn.setFixedWidth(90)
        self.search_btn.clicked.connect(self._do_search)
        sr.addWidget(self.search_input); sr.addWidget(self.search_btn)
        c2l.addLayout(sr)
        L.addWidget(c2)

        self.search_status = QLabel("")
        self.search_status.setStyleSheet("color:#ffd700;font-size:12px;")
        L.addWidget(self.search_status)

        self.result_tree = QTreeWidget()
        self.result_tree.setHeaderLabels(["书名", "网站"])
        self.result_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.result_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.result_tree.header().resizeSection(1, 200)
        self.result_tree.setAlternatingRowColors(True)
        self.result_tree.itemDoubleClicked.connect(self._result_click)
        L.addWidget(self.result_tree, 1)

        hint = QLabel("双击结果 → 自动跳转下载页并获取章节")
        hint.setStyleSheet("color:#444;font-size:12px;"); hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        L.addWidget(hint)
        self._refresh_site_btns()
        return pg

    def _tab_history(self):
        pg = QWidget(); L = QVBoxLayout(pg)
        L.setContentsMargins(20,16,20,16); L.setSpacing(10)

        L.addWidget(QLabel("下载历史"))
        self.hist_tree = QTreeWidget()
        self.hist_tree.setHeaderLabels(["书名","章数","时间","路径"])
        self.hist_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed); self.hist_tree.header().resizeSection(0, 170)
        self.hist_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed); self.hist_tree.header().resizeSection(1, 55)
        self.hist_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed); self.hist_tree.header().resizeSection(2, 140)
        self.hist_tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.hist_tree.setAlternatingRowColors(True)
        self.hist_tree.itemDoubleClicked.connect(self._hist_click)
        L.addWidget(self.hist_tree)

        L.addWidget(hline())
        L.addWidget(QLabel("访问过的网站"))
        self.site_tree = QTreeWidget()
        self.site_tree.setHeaderLabels(["域名","访问次数","最后访问"])
        self.site_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.site_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed); self.site_tree.header().resizeSection(1, 80)
        self.site_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed); self.site_tree.header().resizeSection(2, 140)
        self.site_tree.setAlternatingRowColors(True)
        L.addWidget(self.site_tree)

        hint = QLabel("双击下载历史 → 打开文件夹")
        hint.setStyleSheet("color:#444;font-size:12px;"); hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        L.addWidget(hint)
        self._refresh_history()
        return pg

    def _tab_settings(self):
        pg = QWidget(); L = QVBoxLayout(pg)
        L.setContentsMargins(20,16,20,16); L.setSpacing(10)

        # 输出格式
        c1 = card(); c1l = QVBoxLayout(c1); c1l.setContentsMargins(16,14,16,14); c1l.setSpacing(10)
        c1l.addWidget(small_label("输出格式"))
        fmt_row = QHBoxLayout()
        self.cb_txt  = QCheckBox("TXT"); self.cb_txt.setChecked(self.settings.get('gen_txt', True))
        self.cb_epub = QCheckBox("EPUB"); self.cb_epub.setChecked(self.settings.get('gen_epub', True))
        fmt_row.addWidget(self.cb_txt); fmt_row.addWidget(self.cb_epub); fmt_row.addStretch()
        c1l.addLayout(fmt_row)
        L.addWidget(c1)

        # 行为
        c2 = card(); c2l = QVBoxLayout(c2); c2l.setContentsMargins(16,14,16,14); c2l.setSpacing(10)
        c2l.addWidget(small_label("行为"))
        self.cb_open = QCheckBox("下载完成后自动打开文件夹")
        self.cb_upd  = QCheckBox("启动时自动检查更新")
        self.cb_open.setChecked(self.settings.get('auto_open', True))
        self.cb_upd.setChecked(self.settings.get('check_update', True))
        c2l.addWidget(self.cb_open); c2l.addWidget(self.cb_upd)
        L.addWidget(c2)

        # 版本管理
        c3 = card(); c3l = QVBoxLayout(c3); c3l.setContentsMargins(16,14,16,14); c3l.setSpacing(10)
        c3l.addWidget(small_label("程序管理"))
        vr = QHBoxLayout()
        vr.addWidget(QLabel(f"当前版本：v{VERSION}"))
        self.upd_lbl = QLabel(""); self.upd_lbl.setStyleSheet("color:#ffd700;font-size:12px;")
        vr.addWidget(self.upd_lbl); vr.addStretch()
        upd_btn = QPushButton("检查更新"); upd_btn.setObjectName("flat"); upd_btn.setFixedWidth(100)
        upd_btn.clicked.connect(self._check_update_manual)
        uninstall = QPushButton("卸载程序"); uninstall.setObjectName("danger"); uninstall.setFixedWidth(100)
        uninstall.clicked.connect(self._uninstall)
        vr.addWidget(upd_btn); vr.addWidget(uninstall)
        c3l.addLayout(vr)
        # 更新进度条（默认隐藏）
        self.upd_prog = QProgressBar(); self.upd_prog.setFixedHeight(4); self.upd_prog.setTextVisible(False)
        self.upd_prog.hide()
        c3l.addWidget(self.upd_prog)
        L.addWidget(c3)

        L.addStretch()

        br = QHBoxLayout(); br.setSpacing(8)
        sv = QPushButton("保存设置"); sv.setFixedHeight(36); sv.clicked.connect(self._save_settings)
        rs = QPushButton("重置默认"); rs.setObjectName("flat"); rs.setFixedHeight(36); rs.clicked.connect(self._reset_settings)
        br.addWidget(sv); br.addWidget(rs)
        L.addLayout(br)
        return pg

    # ── 日志（带行数限制）──────────────────────────────────────

    def _log(self, msg, color='white'):
        c = {'green':'#6ccb5f','red':'#ff6b6b','yellow':'#ffd700','white':'#b8b8b8'}.get(color,'#b8b8b8')
        self.log.append(f'<span style="color:{c};">{msg}</span>')
        # 裁剪日志行数
        doc = self.log.document()
        while doc.blockCount() > LOG_MAX_LINES:
            cur = QTextCursor(doc)
            cur.movePosition(QTextCursor.MoveOperation.Start)
            cur.select(QTextCursor.SelectionType.BlockUnderCursor)
            cur.removeSelectedText()
            cur.deleteChar()
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    # ── 下载 Tab ──────────────────────────────────────────────

    def _browse(self):
        p = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if p: self.path_input.setText(p)

    def _fetch(self):
        url = self.url_input.text().strip()
        if not url: return
        self.fetch_btn.setEnabled(False)
        self.book_lbl.setText("正在获取章节列表...")
        self.book_lbl.setStyleSheet("color:#888;font-size:13px;font-weight:600;")
        self.章节列表 = []
        self._fetch_thread = 获取章节线程(url, self.session)
        self._fetch_thread.成功.connect(self._on_fetched)
        self._fetch_thread.失败.connect(self._on_fetch_fail)
        self._fetch_thread.start()

    def _on_fetched(self, 书名, lst, adp名):
        self.书名 = 书名; self.章节列表 = lst
        self.book_lbl.setText(f"《{书名}》共 {len(lst)} 章")
        self.book_lbl.setStyleSheet("color:#0078d4;font-size:13px;font-weight:600;")
        self.adp_lbl.setText(f" {adp名} "); self.adp_lbl.setVisible(True)
        self._log(f"获取成功：{len(lst)} 章", "green")
        if lst: self._log(f"  第一章：{lst[0][1]}"); self._log(f"  最后章：{lst[-1][1]}")
        self.fetch_btn.setEnabled(True)
        self._refresh_history()

    def _on_fetch_fail(self, err):
        self.book_lbl.setText("获取失败，请检查网址")
        self.book_lbl.setStyleSheet("color:#ff6b6b;font-size:13px;font-weight:600;")
        self._log(f"获取失败：{err}", "red")
        self.fetch_btn.setEnabled(True)

    def _start_dl(self):
        if self._dl_thread and self._dl_thread.isRunning(): return
        if not self.章节列表:
            QMessageBox.warning(self, "提示", "请先获取章节列表"); return
        开始 = self.start_sp.value() - 1
        数量 = self.count_sp.value()
        目标 = self.章节列表[开始 : 开始+数量]
        if not 目标: return
        目录 = self.path_input.text().strip()
        安全书名 = re.sub(r'[\\/:*?"<>|]', '', self.书名)
        保存路径  = os.path.join(目录, f"{安全书名}.txt")
        self.prog.setMaximum(len(目标)); self.prog.setValue(0)
        self.prog_lbl.setText("")
        self.start_btn.setEnabled(False)
        self._log(f"\n开始下载《{self.书名}》共 {len(目标)} 章", "white")
        self._dl_thread = 下载线程(目标, self.url_input.text().strip(),
                                   self.书名, 保存路径, self.settings, self.session)
        self._dl_thread.日志.connect(self._log)
        self._dl_thread.进度.connect(self._on_prog)
        self._dl_thread.完成.connect(self._on_done)
        self._dl_thread.start()

    def _on_prog(self, cur, tot):
        self.prog.setValue(cur)
        self.prog_lbl.setText(f"{cur} / {tot}  ·  {round(cur/tot*100,1)}%")

    def _on_done(self, 已抓, epub数据, 保存路径):
        self._log(f"\n完成！共 {已抓} 章 → {保存路径}", "green")
        self.start_btn.setEnabled(True)
        写历史({'书名':self.书名,'章数':已抓,
                '时间':datetime.now().strftime('%Y-%m-%d %H:%M'),
                '保存路径':保存路径})
        self._refresh_history()
        if epub数据 and self.settings.get('gen_epub'):
            def _gen():
                try:
                    ep = 生成epub(self.书名, epub数据, 保存路径)
                    self._log(f"epub 已保存：{ep}", "green")
                except Exception as e:
                    self._log(f"epub 失败：{e}", "red")
            threading.Thread(target=_gen, daemon=True).start()
        if self.settings.get('auto_open'):
            d = os.path.dirname(保存路径)
            if os.path.exists(d): os.startfile(d)

    def _stop_dl(self):
        if self._dl_thread and self._dl_thread.isRunning():
            self._dl_thread.stop()

    def _open_dir(self):
        p = self.path_input.text().strip()
        if os.path.exists(p): os.startfile(p)
        else: QMessageBox.information(self, "提示", f"文件夹不存在：{p}")

    # ── 搜索 Tab ──────────────────────────────────────────────

    def _refresh_site_btns(self):
        for i in reversed(range(self.site_btn_layout.count())):
            w = self.site_btn_layout.itemAt(i).widget()
            if w: w.deleteLater()
        sites = 常用网站()[:7]
        if not sites:
            lbl = QLabel("暂无记录，下载后自动出现")
            lbl.setStyleSheet("color:#444;font-size:12px;")
            self.site_btn_layout.addWidget(lbl)
        for domain, info in sites:
            name = info.get('name', domain)[:16]
            cnt  = info.get('count', 0)
            btn  = QPushButton(f"{name}  {cnt}")
            btn.setObjectName("flat"); btn.setFixedHeight(28)
            btn.setStyleSheet(btn.styleSheet() + "font-size:12px;")
            btn.clicked.connect(lambda _, d=domain: self._pick_site(d))
            self.site_btn_layout.addWidget(btn)
        self.site_btn_layout.addStretch()

    def _pick_site(self, domain):
        self._selected_domain = domain
        data = 读网站()
        name = data.get(domain, {}).get('name', domain)
        self.sel_lbl.setText(f"已选择：{name}  —  {domain}")
        self.sel_lbl.setStyleSheet("color:#0078d4;font-size:12px;")

    def _do_search(self):
        if not self._selected_domain:
            QMessageBox.information(self, "提示", "请先点击上方选择一个网站"); return
        kw = self.search_input.text().strip()
        if not kw: return
        self.search_status.setText("搜索中...")
        self.search_btn.setEnabled(False)
        self.result_tree.clear(); self._search_results = []
        t = 搜索线程(self._selected_domain, kw, self.session)
        t.结果.connect(self._on_search)
        t.start(); self._s_thread = t

    def _on_search(self, results):
        self._search_results = results
        self.result_tree.clear()
        for r in results:
            QTreeWidgetItem(self.result_tree, [r['title'], r.get('site', self._selected_domain)])
        self.search_status.setText(f"找到 {len(results)} 条结果，双击直接下载")
        self.search_btn.setEnabled(True)

    def _result_click(self, item, _):
        idx = self.result_tree.indexOfTopLevelItem(item)
        if 0 <= idx < len(self._search_results):
            url = self._search_results[idx]['url']
            self.url_input.setText(url)
            self.tabs.setCurrentIndex(0)
            self._fetch()

    # ── 历史 Tab ──────────────────────────────────────────────

    def _refresh_history(self):
        self.hist_tree.clear()
        for h in 读历史():
            QTreeWidgetItem(self.hist_tree, [h.get('书名',''), str(h.get('章数','')),
                                              h.get('时间',''), h.get('保存路径','')])
        self.site_tree.clear()
        for domain, info in 常用网站():
            QTreeWidgetItem(self.site_tree, [info.get('name',domain),
                                              str(info.get('count',0)), info.get('last','')])
        self._refresh_site_btns()

    def _hist_click(self, item, _):
        folder = os.path.dirname(item.text(3))
        if os.path.exists(folder): os.startfile(folder)

    # ── 设置 Tab ──────────────────────────────────────────────

    def _save_settings(self):
        self.settings.update({
            'gen_txt':      self.cb_txt.isChecked(),
            'gen_epub':     self.cb_epub.isChecked(),
            'auto_open':    self.cb_open.isChecked(),
            'check_update': self.cb_upd.isChecked(),
            'save_path':    self.path_input.text(),
        })
        写设置(self.settings)
        QMessageBox.information(self, "已保存", "设置已保存。")

    def _reset_settings(self):
        if QMessageBox.question(self,"确认","重置所有设置？") == QMessageBox.StandardButton.Yes:
            写设置(DEFAULTS); QMessageBox.information(self,"完成","已重置，重启生效。")

    def _uninstall(self):
        目录 = 运行目录()
        清理 = [f for f in [HISTORY_FILE,SETTINGS_FILE,SITES_FILE] if os.path.exists(f)]
        for fn in os.listdir(目录):
            if fn.endswith('.progress.json'): 清理.append(os.path.join(目录,fn))
        self_path = sys.executable if getattr(sys,'frozen',False) else os.path.abspath(__file__)
        清理.append(self_path)
        if QMessageBox.question(self,"确认卸载","将删除程序及记录文件，小说不受影响。确认？") != QMessageBox.StandardButton.Yes: return
        bat = os.path.join(tempfile.gettempdir(), 'uninstall_fishhook.bat')
        with open(bat,'w') as f:
            f.write('@echo off\ntimeout /t 2 /nobreak >nul\n')
            for fp in 清理: f.write(f'del /f /q "{fp}" >nul 2>&1\n')
            f.write(f'del /f /q "{bat}"\n')
        subprocess.Popen(['cmd','/c',bat], creationflags=0x08000000)
        sys.exit(0)

    # ── 更新（全程信号槽，不在子线程操作 UI）─────────────────

    def _auto_update_check(self):
        if not self.settings.get('check_update'): return
        t = 更新检查线程()
        t.有更新.connect(lambda v: self.upd_lbl.setText(f"发现新版本 v{v}"))
        t.有更新.connect(lambda v: self._log(f"发现新版本 v{v}，可在「设置」里更新", "yellow"))
        t.start(); self._chk_thread = t

    def _check_update_manual(self):
        self.upd_lbl.setText("检查中...")
        t = 更新检查线程()
        t.有更新.connect(self._prompt_update)
        t.无更新.connect(lambda: self.upd_lbl.setText("已是最新版本"))
        t.出错.connect(lambda e: self.upd_lbl.setText(f"检查失败"))
        t.start(); self._chk_thread = t

    def _prompt_update(self, latest):
        self.upd_lbl.setText(f"发现新版本 v{latest}")
        reply = QMessageBox.question(self, "发现更新",
            f"发现新版本 v{latest}（当前 v{VERSION}）\n\n"
            "程序将下载新版本并自动重启，继续？")
        if reply == QMessageBox.StandardButton.Yes:
            self._start_update()

    def _start_update(self):
        self.upd_prog.show(); self.upd_prog.setValue(0)
        t = 更新下载线程(GITHUB_EXE_URL)
        t.进度.connect(self.upd_prog.setValue)
        t.完成.connect(self._on_update_done)
        t.start(); self._upd_thread = t

    def _on_update_done(self, ok, err):
        self.upd_prog.hide()
        if ok:
            QMessageBox.information(self, "更新完成", "新版本已就绪，点确定重启。")
            python = sys.executable
            os.execl(python, python, *sys.argv)
        else:
            QMessageBox.warning(self, "更新失败", f"错误：{err}\n请稍后重试。")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
