import sys, os, time, json, re, uuid, zipfile, threading, shutil, subprocess, tempfile
from datetime import datetime
from urllib.parse import urljoin, urlparse, quote
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QProgressBar,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QCheckBox, QFrame,
    QMessageBox, QHeaderView, QSpinBox, QDialog, QDialogButtonBox,
    QScrollArea, QSplitter, QMenu, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import (Qt, QThread, pyqtSignal, QTimer,
                           QPropertyAnimation, QEasingCurve, QPoint)
from PyQt6.QtGui import QFont, QColor, QIcon, QPixmap, QAction

VERSION = "6.3.0"

GITHUB_RAW            = "https://raw.githubusercontent.com/huasiyuuuuu/FishHook/main/"
GITHUB_MIRROR         = "https://ghfast.top/https://raw.githubusercontent.com/huasiyuuuuu/FishHook/main/"
GITHUB_VERSION_URL    = GITHUB_RAW    + "version.txt"
GITHUB_SCRIPT_URL     = GITHUB_RAW    + "hook.py"
GITHUB_VERSION_MIRROR = GITHUB_MIRROR + "version.txt"
GITHUB_SCRIPT_MIRROR  = GITHUB_MIRROR + "hook.py"

DATA_DIR = Path(os.environ.get('APPDATA', Path.home())) / 'Hook'
DATA_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE  = DATA_DIR / 'history.json'
SITES_FILE    = DATA_DIR / 'sites.json'
SETTINGS_FILE = DATA_DIR / 'settings.json'
ADAPTERS_FILE = DATA_DIR / 'adapters.json'
FIRST_RUN     = DATA_DIR / '.first_run_done'

def app_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

# ── ICO 内嵌（由安装程序替换）────────────────────────────────
ICO_B64 = "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"

# ── 统一网络 Session（带重试）────────────────────────────────

def get_system_proxy():
    """自动读取 Windows 系统代理设置"""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r'Software\Microsoft\Windows\CurrentVersion\Internet Settings')
        enabled, _ = winreg.QueryValueEx(key, 'ProxyEnable')
        if enabled:
            proxy_str, _ = winreg.QueryValueEx(key, 'ProxyServer')
            if proxy_str:
                if '=' not in proxy_str:
                    # 格式: host:port
                    return {'http': f'http://{proxy_str}',
                            'https': f'http://{proxy_str}'}
                else:
                    # 格式: http=host:port;https=host:port
                    proxies = {}
                    for part in proxy_str.split(';'):
                        if '=' in part:
                            k, v = part.split('=', 1)
                            proxies[k.strip()] = f'http://{v.strip()}'
                    return proxies
    except: pass
    return None

def make_session():
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5,
                  status_forcelist=[500,502,503,504])
    adapter = HTTPAdapter(max_retries=retry)
    s.mount('http://', adapter)
    s.mount('https://', adapter)
    # 自动应用系统代理
    proxy = get_system_proxy()
    if proxy:
        s.proxies.update(proxy)
    return s

# ── 设置 ──────────────────────────────────────────────────────

DEFAULTS = {
    'save_path':         r'D:\缓存文件\小说',  # 默认D盘，不改
    'gen_epub':          False,
    'gen_txt':           True,
    'auto_open':         False,
    'auto_check_update': True,
}

def 读设置():
    s = DEFAULTS.copy()
    if SETTINGS_FILE.exists():
        try: s = {**DEFAULTS, **json.loads(SETTINGS_FILE.read_text('utf-8'))}
        except: pass
    # 自动修正 C 盘路径
    p = s.get('save_path', SAVE_PATH_DEFAULT)
    if not p or p.upper().startswith('C:') or 'Desktop' in p or '桌面' in p:
        s['save_path'] = SAVE_PATH_DEFAULT
        写设置(s)
    return s

def 写设置(s):
    SETTINGS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), 'utf-8')

def 读网站():
    if SITES_FILE.exists():
        try: return json.loads(SITES_FILE.read_text('utf-8'))
        except: pass
    return {}

def 写网站(d):
    SITES_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), 'utf-8')

def 记录网站(url):
    p = urlparse(url)
    domain = f"{p.scheme}://{p.netloc}"
    d = 读网站()
    if domain not in d:
        d[domain] = {'name': p.netloc, 'count': 0, 'last': ''}
    d[domain]['count'] += 1
    d[domain]['last'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    写网站(d)

def 常用网站():
    return sorted(读网站().items(), key=lambda x: x[1]['count'], reverse=True)

def 读历史():
    if HISTORY_FILE.exists():
        try: return json.loads(HISTORY_FILE.read_text('utf-8'))
        except: pass
    return []

def 写历史(r):
    h = 读历史()
    for i, x in enumerate(h):
        if x.get('path') == r.get('path'): h[i] = r; break
    else: h.insert(0, r)
    HISTORY_FILE.write_text(json.dumps(h[:50], ensure_ascii=False, indent=2), 'utf-8')

def 删历史(path):
    h = [x for x in 读历史() if x.get('path') != path]
    HISTORY_FILE.write_text(json.dumps(h, ensure_ascii=False, indent=2), 'utf-8')

def 读进度(p):
    pp = Path(str(p) + '.prog.json')
    if pp.exists():
        try: return json.loads(pp.read_text('utf-8'))
        except: pass
    return {}

def 写进度(p, d):
    Path(str(p) + '.prog.json').write_text(
        json.dumps(d, ensure_ascii=False), 'utf-8')

def 删进度(p):
    pp = Path(str(p) + '.prog.json')
    if pp.exists():
        try: pp.unlink()
        except: pass

# ── 适配器配置 ────────────────────────────────────────────────

DEFAULT_ADAPTERS = [
    {
        "name": "海棠书屋",
        "match": ["haitang"],
        "chapter_list": {
            "container": {"tag": "dl", "class": "chapterlist"},
            "section_h2_keywords": ["全部", "目录"],
            "item_tag": "dd",
            "link_must_contain": "/read/"
        },
        "content_selector": "#rtext",
        "next_page_text": "下一页",
        "next_page_must_contain": "_",
        "search": {
            "url_pattern": "{domain}/modules/article/search.php",
            "method": "POST",
            "data": {"searchkey": "{kw}", "action": "login", "searchtype": "all"},
            "result_link_must_contain": "/book/",
            "result_skip": ["/sort/","/top","/quanben","/search","/modules","/read/","#"]
        },
        "headers": {"Referer": "https://www.haitang.com/"}
    },
    {
        "name": "第一版主",
        "match": ["diyibanzhu"],
        "chapter_list": {"container": {"tag": "ul", "class": "list"}, "item_tag": "li"},
        "content_selector": "#nr1",
        "next_page_text": "下一页",
        "user_agent": "mobile",
        "search": {
            "url_pattern": "{domain}/wap.php?action=search&keyword={kw}",
            "method": "GET",
            "result_link_must_contain": ["action=list", "/book/"]
        }
    }
]

def 读适配器配置():
    if ADAPTERS_FILE.exists():
        try: return json.loads(ADAPTERS_FILE.read_text('utf-8'))
        except: pass
    ADAPTERS_FILE.write_text(
        json.dumps(DEFAULT_ADAPTERS, ensure_ascii=False, indent=2), 'utf-8')
    return DEFAULT_ADAPTERS

# ── 动态适配器 ────────────────────────────────────────────────

MOBILE_UA  = ('Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 '
              'Chrome/120.0.0.0 Mobile Safari/537.36')
DESKTOP_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

class DynamicAdapter:
    def __init__(self, cfg):
        self.cfg  = cfg
        self.name = cfg.get('name', '自定义')

    def match(self, url):
        return any(k in url for k in self.cfg.get('match', []))

    def headers(self, url):
        p  = urlparse(url)
        ua = MOBILE_UA if self.cfg.get('user_agent') == 'mobile' else DESKTOP_UA
        h  = {'User-Agent': ua, 'Accept-Language': 'zh-CN,zh;q=0.9',
              'Referer': f"{p.scheme}://{p.netloc}/"}
        h.update(self.cfg.get('headers', {}))
        return h

    def chapters(self, soup, base):
        title = '未知'
        for tag in soup.find_all(['h1','h2']):
            t = tag.get_text(strip=True)
            if t and len(t) < 50 and '章节' not in t and '目录' not in t:
                title = t.split('_')[0].strip(); break
        cl  = self.cfg.get('chapter_list', {})
        con = None
        cc  = cl.get('container', {})
        if cc:
            kw = {}
            if 'class' in cc: kw['class_'] = cc['class']
            con = soup.find(cc.get('tag','div'), **kw)
        if not con:
            return title, self._generic(soup, base)
        kws      = cl.get('section_h2_keywords', [])
        start    = None
        if kws:
            for h2 in con.find_all('h2'):
                if any(k in h2.get_text() for k in kws):
                    start = h2; break
        item_tag = cl.get('item_tag', 'a')
        must     = cl.get('link_must_contain', '')
        result, seen = [], set()
        siblings = start.find_next_siblings() if start else con.find_all(item_tag)
        for tag in siblings:
            if tag.name != item_tag: continue
            a = tag.find('a', href=True) if item_tag != 'a' else tag
            if not a: continue
            href = a.get('href', '')
            if must and must not in href: continue
            u = href if href.startswith('http') else urljoin(base, href)
            t = a.get_text(strip=True)
            if u not in seen and t: seen.add(u); result.append((u, t))
        return title, result

    def _generic(self, soup, base):
        buckets = {}
        for a in soup.find_all('a', href=True):
            t = a.get_text(strip=True)
            if not t or len(t) > 60: continue
            p = a.parent
            for _ in range(4):
                if p is None: break
                pid = id(p)
                if pid not in buckets: buckets[pid] = []
                buckets[pid].append((a['href'], t))
                p = p.parent
        result, seen = [], set()
        if buckets:
            best = max(buckets, key=lambda k: len(buckets[k]))
            for href, t in buckets[best]:
                u = href if href.startswith('http') else urljoin(base, href)
                if u not in seen and t: seen.add(u); result.append((u, t))
        return result

    def content(self, soup):
        sel = self.cfg.get('content_selector', '')
        if sel:
            f = soup.select_one(sel)
            if f and len(f.get_text(strip=True)) > 100: return f
        for s in ['#rtext','#content','#nr1','#chaptercontent',
                  '.read-content','.chapter-content']:
            f = soup.select_one(s)
            if f and len(f.get_text(strip=True)) > 100: return f
        cands = [(len(d.get_text(strip=True)), d)
                 for d in soup.find_all(['div','article'])
                 if len(d.get_text(strip=True)) > 200]
        return max(cands, key=lambda x: x[0])[1] if cands else None

    def next_page(self, soup, url):
        kw   = self.cfg.get('next_page_text', '下一页')
        must = self.cfg.get('next_page_must_contain', '')
        for a in soup.find_all('a'):
            t = a.get_text(strip=True)
            if kw in t and '下一章' not in t:
                h = a.get('href', '')
                if h and not h.startswith('javascript'):
                    if must and must not in h.split('/')[-1]: continue
                    return h if h.startswith('http') else urljoin(url, h)
        return None

    def search_url(self, domain, kw):
        pat = self.cfg.get('search', {}).get('url_pattern', '')
        if not pat: return None
        return pat.replace('{domain}', domain).replace('{kw}', quote(kw))

    def search_method(self): return self.cfg.get('search',{}).get('method','GET')

    def search_data(self, kw):
        data = self.cfg.get('search', {}).get('data', {})
        return {k: v.replace('{kw}', kw) for k, v in data.items()}

    def parse_search(self, soup, domain):
        sc    = self.cfg.get('search', {})
        must  = sc.get('result_link_must_contain', [])
        if isinstance(must, str): must = [must]
        skip  = sc.get('result_skip', [])
        res   = []
        for a in soup.find_all('a', href=True):
            href, t = a['href'], a.get_text(strip=True)
            if not t or len(t) > 60 or len(t) < 1: continue
            if any(s in href for s in skip): continue
            if must and not any(m in href for m in must): continue
            u = href if href.startswith('http') else urljoin(domain, href)
            if u not in [r['url'] for r in res]:
                res.append({'title': t, 'url': u, 'site': domain})
        return res[:20]


class GenericAdapter(DynamicAdapter):
    def __init__(self): super().__init__({'name': '通用'})
    def match(self, url): return True
    def search_url(self, domain, kw):
        return f"{domain}/search?q={quote(kw)}"
    def parse_search(self, soup, domain):
        res = []
        for a in soup.find_all('a', href=True):
            t = a.get_text(strip=True)
            if not t or len(t) > 60 or len(t) < 1: continue
            u = a['href'] if a['href'].startswith('http') else urljoin(domain, a['href'])
            if u not in [r['url'] for r in res]:
                res.append({'title': t, 'url': u, 'site': domain})
        return res[:20]


_ADAPTERS = []

def load_adapters():
    global _ADAPTERS
    _ADAPTERS = [DynamicAdapter(c) for c in 读适配器配置()] + [GenericAdapter()]

def get_adapter(url):
    for a in _ADAPTERS:
        if a.match(url): return a
    return GenericAdapter()

load_adapters()

# ── 自动更新 ──────────────────────────────────────────────────

def get_self_path():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent / 'hook.py'
    return Path(__file__).resolve()

def check_update_available():
    def ver_tuple(v):
        try: return tuple(int(x) for x in v.split('.'))
        except: return (0,)
    for url in [GITHUB_VERSION_MIRROR, GITHUB_VERSION_URL]:
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            latest = r.text.strip()
            if latest and latest != VERSION:
                if ver_tuple(latest) > ver_tuple(VERSION):
                    return latest, True
            return latest, False
        except: continue
    return None, False

def download_update(progress_cb=None):
    self_path = get_self_path()
    tmp_path  = self_path.parent / 'hook.py.new'
    bak_path  = self_path.parent / 'hook.py.bak'
    last_err  = ''
    for url in [GITHUB_SCRIPT_MIRROR, GITHUB_SCRIPT_URL]:
        try:
            r = requests.get(url, timeout=60, stream=True)
            r.raise_for_status()
            total = int(r.headers.get('content-length', 0))
            done  = 0
            with open(tmp_path, 'wb') as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk); done += len(chunk)
                    if total and progress_cb:
                        progress_cb(int(done / total * 100))
            if self_path.exists():
                if bak_path.exists(): bak_path.unlink()
                self_path.rename(bak_path)
            tmp_path.rename(self_path)
            if bak_path.exists(): bak_path.unlink()
            return True, ''
        except Exception as e:
            last_err = str(e)
            if tmp_path.exists(): tmp_path.unlink(missing_ok=True)
            continue
    if bak_path.exists() and not self_path.exists():
        bak_path.rename(self_path)
    return False, last_err

def restart_app():
    if getattr(sys, 'frozen', False):
        os.execl(sys.executable, sys.executable, *sys.argv)
    else:
        os.execl(sys.executable, sys.executable, str(get_self_path()), *sys.argv[1:])

# ── 抓取核心 ──────────────────────────────────────────────────

def safe_get(session, url, headers, timeout=12, **kw):
    try:
        return session.get(url, headers=headers, timeout=timeout, **kw)
    except Exception as e:
        if 'SSL' in str(e) or 'EOF' in str(e):
            import urllib3; urllib3.disable_warnings()
            return session.get(url, headers=headers, timeout=timeout,
                               verify=False, **kw)
        raise

def fetch_page(url, session, adp):
    r = safe_get(session, url, adp.headers(url))
    r.encoding = r.apparent_encoding if r.encoding in ('ISO-8859-1',None) else r.encoding
    soup = BeautifulSoup(r.text, 'html.parser')
    for tag in soup.find_all(['script','style','nav','header','footer','aside']):
        tag.decompose()
    c = adp.content(soup)
    if not c: return None, None
    for a in c.find_all('a'): a.decompose()
    for br in c.find_all('br'): br.replace_with('\n')
    lines = [l.strip() for l in c.get_text().splitlines()]
    lines = [l for l in lines if l and len(l) > 1]
    return '\n'.join(lines), adp.next_page(soup, url)

def fetch_chapter(url, session, adp, retries=3):
    for attempt in range(retries):
        try:
            parts, cur = [], url
            while cur:
                text, nxt = fetch_page(cur, session, adp)
                if text: parts.append(text)
                cur = nxt
                if nxt: time.sleep(0.4)
            result = '\n'.join(parts)
            if result.strip(): return result
        except Exception:
            if attempt < retries-1: time.sleep(2**attempt)
            else: raise
    return None

def fetch_chapter_list(url, session):
    记录网站(url)
    adp = get_adapter(url)
    r   = safe_get(session, url, adp.headers(url))
    r.encoding = r.apparent_encoding if r.encoding in ('ISO-8859-1',None) else r.encoding
    soup = BeautifulSoup(r.text, 'html.parser')
    title, lst = adp.chapters(soup, url)
    return title, lst, adp.name

def smart_resolve_url(url, session):
    """
    三步降级识别目录页：
    1. 找 id="linkIndex" 的链接（海棠书屋标准，最可靠）
    2. 找含"章节目录"/"目录"文字的 <a> 标签（通用）
    3. 字符串推断 /read/{ID}/ → /book/{ID}/（备用）
    """
    adp = get_adapter(url)
    try:
        r = safe_get(session, url, adp.headers(url), timeout=10)
        r.encoding = r.apparent_encoding if r.encoding in ('ISO-8859-1', None) else r.encoding
        soup = BeautifulSoup(r.text, 'html.parser')

        # ── 步骤1：找 id="linkIndex"（海棠书屋专用，最可靠）────
        link_index = soup.find('a', id='linkIndex')
        if link_index and link_index.get('href'):
            full = link_index['href']
            if not full.startswith('http'):
                full = urljoin(url, full)
            return full, '章节页→目录（linkIndex）', None

        # ── 步骤2：找含目录关键词的链接（通用）─────────────────
        keywords = ['章节目录', '目录', '返回目录', '书页', '章节列表']
        for a in soup.find_all('a', href=True):
            t = a.get_text(strip=True)
            href = a['href']
            if not href or href.startswith('javascript'): continue
            if any(k in t for k in keywords):
                full = href if href.startswith('http') else urljoin(url, href)
                if full.rstrip('/') != url.rstrip('/'):
                    return full, f'章节页→目录（{t}）', None

        # ── 步骤3：字符串推断 /read/{ID}/ → /book/{ID}/（备用）─
        parsed = urlparse(url)
        import re as _re
        m = _re.search(r'/read/(\d+)/', parsed.path)
        if m:
            book_id = m.group(1)
            guess = f"{parsed.scheme}://{parsed.netloc}/book/{book_id}/"
            return guess, f'自动推断目录页（书ID={book_id}）', None

        # ── 已经是目录页 ─────────────────────────────────────────
        _, lst = adp.chapters(soup, url)
        if len(lst) >= 3:
            return url, '目录页', None

        return url, '无法识别，直接尝试', None

    except Exception as e:
        err = str(e)
        if 'SSL' in err or 'EOF' in err:
            return url, '网络错误', 'SSL连接失败，请确认梯子已开启后重试'
        elif 'timeout' in err.lower():
            return url, '网络错误', '连接超时，请检查网络'
        elif 'connection' in err.lower():
            return url, '网络错误', '无法连接，请确认网址正确'
        return url, '网络错误', '网络请求失败，请稍后重试'

def do_search(domain, kw, session):
    adp = get_adapter(domain + '/')
    su  = adp.search_url(domain, kw)
    if not su: return [], False
    hdrs = adp.headers(su)
    try:
        if adp.search_method() == 'POST':
            r = session.post(su, data=adp.search_data(kw), headers=hdrs, timeout=10)
        else:
            r = session.get(su, headers=hdrs, timeout=10)
        r.encoding = r.apparent_encoding if r.encoding in ('ISO-8859-1',None) else r.encoding
        return adp.parse_search(BeautifulSoup(r.text,'html.parser'), domain), True
    except:
        return [], False

# ── epub ──────────────────────────────────────────────────────

def make_epub(title, chapters, path):
    epub = re.sub(r'\.txt$', '.epub', str(path))
    bid  = str(uuid.uuid4())
    container = ('<?xml version="1.0"?><container version="1.0" '
                 'xmlns="urn:oasis:schemas:container"><rootfiles>'
                 '<rootfile full-path="OEBPS/content.opf" '
                 'media-type="application/oebps-package+xml"/>'
                 '</rootfiles></container>')
    files = []
    for i, (t, body) in enumerate(chapters):
        fn    = f'ch{i+1}.xhtml'
        paras = ''.join(f'<p>{l}</p>' for l in body.splitlines() if l.strip())
        html  = (f'<?xml version="1.0" encoding="utf-8"?><!DOCTYPE html>'
                 f'<html xmlns="http://www.w3.org/1999/xhtml">'
                 f'<head><meta charset="utf-8"/><title>{t}</title>'
                 f'<style>body{{font-family:serif;font-size:1.1em;line-height:1.9;margin:2em}}'
                 f'p{{text-indent:2em;margin:0.3em 0}}</style>'
                 f'</head><body><h2>{t}</h2>{paras}</body></html>')
        files.append((fn, t, html))
    manifest = '\n'.join(
        f'<item id="c{i+1}" href="{fn}" media-type="application/xhtml+xml"/>'
        for i,(fn,_,__) in enumerate(files))
    spine = '\n'.join(f'<itemref idref="c{i+1}"/>' for i in range(len(files)))
    nav   = '\n'.join(
        f'<navPoint id="n{i+1}" playOrder="{i+1}">'
        f'<navLabel><text>{t}</text></navLabel>'
        f'<content src="{fn}"/></navPoint>'
        for i,(fn,t,_) in enumerate(files))
    opf = (f'<?xml version="1.0" encoding="utf-8"?>'
           f'<package xmlns="http://www.idpf.org/2007/opf" '
           f'unique-identifier="bid" version="2.0">'
           f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
           f'<dc:title>{title}</dc:title><dc:language>zh</dc:language>'
           f'<dc:identifier id="bid">{bid}</dc:identifier></metadata>'
           f'<manifest><item id="ncx" href="toc.ncx" '
           f'media-type="application/x-dtbncx+xml"/>{manifest}</manifest>'
           f'<spine toc="ncx">{spine}</spine></package>')
    ncx = (f'<?xml version="1.0" encoding="utf-8"?>'
           f'<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
           f'<head><meta name="dtb:uid" content="{bid}"/></head>'
           f'<docTitle><text>{title}</text></docTitle>'
           f'<navMap>{nav}</navMap></ncx>')
    with zipfile.ZipFile(epub, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        zf.writestr('META-INF/container.xml', container)
        zf.writestr('OEBPS/content.opf', opf)
        zf.writestr('OEBPS/toc.ncx', ncx)
        for fn,_,html in files:
            zf.writestr(f'OEBPS/{fn}', html)
    return epub

# ── 系统通知 ──────────────────────────────────────────────────

def toast(title, msg):
    """发 Windows 系统通知，三种方式依次尝试"""
    # 方式1：plyer（最稳定）
    try:
        from plyer import notification
        notification.notify(title=title, message=msg,
                            app_name='Hook', timeout=4)
        return
    except: pass
    # 方式2：win10toast
    try:
        from win10toast import ToastNotifier
        ToastNotifier().show_toast(title, msg, duration=4, threaded=True)
        return
    except: pass
    # 方式3：纯 Windows API，无需任何第三方库
    try:
        import ctypes, ctypes.wintypes
        # 用 balloon tip（兼容 Win7+）
        NIF_MESSAGE  = 0x01
        NIF_ICON     = 0x02
        NIF_TIP      = 0x04
        NIF_INFO     = 0x10
        NIIF_INFO    = 0x01
        NIM_ADD      = 0x00
        NIM_MODIFY   = 0x01
        NIM_DELETE   = 0x02
        WM_USER      = 0x0400
        shell32      = ctypes.windll.shell32
        # 简单实现：直接用 MessageBeep 作为有声提示
        ctypes.windll.user32.MessageBeep(0x00000040)
    except: pass

# ── 线程 ──────────────────────────────────────────────────────

class ResolveThread(QThread):
    ok   = pyqtSignal(str, str)
    fail = pyqtSignal(str)
    def __init__(self, url, session):
        super().__init__(); self.url=url; self.session=session
    def run(self):
        try:
            resolved, hint, err = smart_resolve_url(self.url, self.session)
            if err: self.fail.emit(err)
            else:   self.ok.emit(resolved, hint)
        except Exception as e:
            self.fail.emit(str(e))

class FetchThread(QThread):
    ok   = pyqtSignal(str, list, str)
    fail = pyqtSignal(str)
    def __init__(self, url, session):
        super().__init__(); self.url=url; self.session=session
    def run(self):
        try:
            t, lst, name = fetch_chapter_list(self.url, self.session)
            self.ok.emit(t, lst, name)
        except Exception as e:
            self.fail.emit(str(e))

class DownloadThread(QThread):
    log      = pyqtSignal(str, str)
    progress = pyqtSignal(int, int, float, int)
    done     = pyqtSignal(int, list, list, str)
    def __init__(self, target, url, title, path, settings, session):
        super().__init__()
        self.target=target; self.url=url; self.title=title
        self.path=path; self.settings=settings; self.session=session
        self._stop=False; self._paused=False
    def stop(self): self._stop=True
    def run(self):
        adp       = get_adapter(self.url)
        prog      = 读进度(self.path)
        done_urls = set(prog.get('done', []))
        failed=[]; epub_data=[]; count=0
        t0=time.time(); new=0; total_chars=0
        try:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.log.emit(f'无法创建目录：{e}', 'red')
            self.done.emit(0, [], [], self.path); return
        # 用字典按原始索引缓存内容，最后按顺序写入
        content_cache = {}  # {原始索引: (标题, 内容)}
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            CONCURRENCY = 2
            pending = [(i,url,t) for i,(url,t) in enumerate(self.target)
                       if url not in done_urls]
            results_buf = {}
            next_write  = 0

            def dl_one(args):
                idx, url, title = args
                if url.startswith('javascript'):
                    return idx, url, title, None, 'skip_js'
                try:
                    from concurrent.futures import ThreadPoolExecutor as _T
                    with _T(max_workers=1) as ex:
                        fut = ex.submit(fetch_chapter, url, self.session, adp)
                        c   = fut.result(timeout=45)
                    return idx, url, title, c, None
                except Exception as e:
                    return idx, url, title, None, str(e)

            with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
                futs = {ex.submit(dl_one, item): item for item in pending}
                for fut in as_completed(futs):
                    if self._stop:
                        self._paused = True
                        ex.shutdown(wait=False, cancel_futures=True)
                        self.log.emit('已暂停。', 'yellow'); break
                    idx, url, title, content, err = fut.result()
                    results_buf[idx] = (url, title, content, err)
                    elapsed   = time.time()-t0
                    speed     = int(total_chars/elapsed) if elapsed>0 and total_chars>0 else 0
                    done_so_far = len(done_urls)+len(results_buf)
                    eta = elapsed/max(new,1)*(len(self.target)-done_so_far)
                    self.progress.emit(done_so_far, len(self.target), eta, speed)
                    while next_write in results_buf:
                        u,t,c,e = results_buf.pop(next_write)
                        if e == 'skip_js':
                            pass
                        elif c:
                            content_cache[next_write] = (t, c)
                            done_urls.add(u); prog['done'] = list(done_urls)
                            写进度(self.path, prog)
                            count+=1; new+=1; total_chars+=len(c)
                            count+=1; new+=1; total_chars+=len(c)
                            self.log.emit(f'  ✓ [{next_write+1}] {t}  {len(c)}字', 'green')
                        else:
                            failed.append((u, t))
                            self.log.emit(f'  ✗ [{next_write+1}] {t}  {e or "内容为空"}', 'red')
                        next_write += 1
        except Exception as _ex:
            self.log.emit(f'下载过程出错：{_ex}', 'red')
        # ─ 以上为并发下载块 ─
        # 按原始索引顺序写入文件
        try:
            with open(self.path, 'a', encoding='utf-8') as f:
                for idx in sorted(content_cache.keys()):
                    t, c = content_cache[idx]
                    if self.settings.get('gen_txt', True):
                        f.write(f"\n{'─'*32}\n{t}\n{'─'*32}\n{c}\n")
        except Exception as e:
            self.log.emit(f'写入文件失败：{e}', 'red')
        self.done.emit(count, epub_data, failed, self.path)

class SearchThread(QThread):
    result = pyqtSignal(list, bool)
    def __init__(self, domain, kw, session):
        super().__init__()
        self.domain=domain; self.kw=kw; self.session=session
    def run(self):
        results, ok = do_search(self.domain, self.kw, self.session)
        self.result.emit(results, ok)

class EpubThread(QThread):
    done = pyqtSignal(str)
    fail = pyqtSignal(str)
    def __init__(self, title, data, path):
        super().__init__()
        self.title=title; self.data=data; self.path=path
    def run(self):
        try:    self.done.emit(make_epub(self.title, self.data, self.path))
        except Exception as e: self.fail.emit(str(e))

class UpdateCheckThread(QThread):
    result = pyqtSignal(str, bool)
    def run(self):
        ver, newer = check_update_available()
        self.result.emit(ver or '', newer)

class UpdateDownloadThread(QThread):
    progress = pyqtSignal(int)
    done     = pyqtSignal(bool, str)
    def run(self):
        ok, err = download_update(lambda p: self.progress.emit(p))
        self.done.emit(ok, err)


# ── 自定义深色弹窗 ────────────────────────────────────────────

class MsgBox(QDialog):
    """统一深色风格弹窗，替代 QMessageBox"""
    INFO    = 0
    WARNING = 1
    CONFIRM = 2

    def __init__(self, parent, title, text, mode=0):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(280)
        self.setMaximumWidth(400)
        self.setStyleSheet("""
            QDialog { background:#1e1e1e; border:1px solid #2e2e2e;
                      border-radius:10px; }
            QLabel  { color:#d8d8d8; font-size:13px;
                      font-family:"Microsoft YaHei UI"; }
            QPushButton { background:#3b82f6; color:#fff; border:none;
                border-radius:7px; padding:8px 24px; font-size:13px;
                min-width:80px; min-height:32px; }
            QPushButton:hover  { background:#2563eb; }
            QPushButton:pressed{ background:#1d4ed8; }
            QPushButton#cancel { background:#262626; color:#aaa;
                border:1px solid #333; }
            QPushButton#cancel:hover { background:#2e2e2e; color:#ccc; }
            QPushButton#danger { background:#3f1212; color:#f87171;
                border:1px solid #5a2020; }
            QPushButton#danger:hover { background:#4e1818; }
        """)
        L = QVBoxLayout(self)
        L.setContentsMargins(18,14,18,14); L.setSpacing(12)

        # 文字
        msg_lbl = QLabel(text)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet('color:#d8d8d8;font-size:13px;'
                               'font-family:"Microsoft YaHei UI";'
                               'background:transparent;line-height:1.5;')
        L.addWidget(msg_lbl)

        # 按钮（确认在左，取消在右）
        br = QHBoxLayout(); br.setSpacing(8); br.addStretch()
        if mode == self.CONFIRM:
            ok = QPushButton('确认')
            ok.clicked.connect(self.accept)
            cancel = QPushButton('取消'); cancel.setObjectName('cancel')
            cancel.clicked.connect(self.reject)
            br.addWidget(ok); br.addWidget(cancel)
        else:
            ok = QPushButton('确定')
            ok.clicked.connect(self.accept)
            br.addWidget(ok)
        L.addLayout(br)
        self._result = False

    @staticmethod
    def info(parent, title, text):
        d = MsgBox(parent, title, text, MsgBox.INFO)
        d.exec()

    @staticmethod
    def warn(parent, title, text):
        d = MsgBox(parent, title, text, MsgBox.WARNING)
        d.exec()

    @staticmethod
    def confirm(parent, title, text):
        d = MsgBox(parent, title, text, MsgBox.CONFIRM)
        return d.exec() == QDialog.DialogCode.Accepted

# ── 章节勾选对话框 ────────────────────────────────────────────

class DragCheckList(QListWidget):
    """支持拖动批量勾选 + 单点切换的列表"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_start = None
        self._drag_state  = None   # 拖动时统一设置的状态

    def mousePressEvent(self, e):
        item = self.itemAt(e.pos())
        if item and e.button() == Qt.MouseButton.LeftButton:
            # 记录拖动起始 + 起始勾选状态（拖动时反转）
            self._drag_start = self.row(item)
            self._drag_state = (Qt.CheckState.Unchecked
                                if item.checkState() == Qt.CheckState.Checked
                                else Qt.CheckState.Checked)
            self.blockSignals(True)
            item.setCheckState(self._drag_state)
            self.blockSignals(False)
            self.itemChanged.emit(item)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_start is not None:
            item = self.itemAt(e.pos())
            if item:
                end_row = self.row(item)
                r0 = min(self._drag_start, end_row)
                r1 = max(self._drag_start, end_row)
                self.blockSignals(True)
                for r in range(r0, r1+1):
                    self.item(r).setCheckState(self._drag_state)
                self.blockSignals(False)
                self.itemChanged.emit(self.item(r1))

    def mouseReleaseEvent(self, e):
        self._drag_start = None
        self._drag_state  = None
        super().mouseReleaseEvent(e)


class ChapterDialog(QDialog):
    def __init__(self, chapters, parent=None):
        super().__init__(parent)
        self.setWindowTitle('选择章节')
        self.resize(540, 640)
        self.setStyleSheet((parent.styleSheet() if parent else '') + """
            QListWidget {
                background:#1c1c1c; border:1px solid #2a2a2a;
                border-radius:8px; color:#d4d4d4;
                font-size:13px; outline:none;
            }
            QListWidget::item { padding:7px 12px; border-radius:4px; }
            QListWidget::item:hover { background:#242424; }
            QListWidget::item:selected { background:transparent; }
            QListWidget::indicator {
                width:15px; height:15px;
                border:1px solid #444; border-radius:3px;
                background:#1c1c1c;
            }
            QListWidget::indicator:checked {
                background:#3b82f6; border:1px solid #3b82f6;
                image:none;
            }
            QListWidget::indicator:unchecked:hover {
                border:1px solid #3b82f6;
            }
        """)
        self.chapters = chapters
        self.selected = []
        L = QVBoxLayout(self); L.setSpacing(10)

        # 工具栏
        # 搜索框
        search_row = QHBoxLayout()
        self.ch_search = QLineEdit()
        self.ch_search.setPlaceholderText('搜索章节名...')
        self.ch_search.textChanged.connect(self._filter_chapters)
        search_row.addWidget(self.ch_search)
        L.addLayout(search_row)

        tb = QHBoxLayout()
        sa = QPushButton('全选');   sa.setObjectName('flat')
        sn = QPushButton('全不选'); sn.setObjectName('flat')
        sa.clicked.connect(self._select_all)
        sn.clicked.connect(self._select_none)
        self.cnt = QLabel(f'已选 {len(chapters)} / {len(chapters)} 章')
        self.cnt.setStyleSheet('color:#555;font-size:12px;')
        hint = QLabel('点击切换  ·  按住拖动批量选')
        hint.setStyleSheet('color:#333;font-size:11px;')
        tb.addWidget(sa); tb.addWidget(sn)
        tb.addStretch(); tb.addWidget(hint)
        L.addLayout(tb)
        L.addWidget(self.cnt)

        # 搜索过滤
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('搜索章节名…')
        self.search_edit.setStyleSheet(
            'background:#232323;border:1px solid #2e2e2e;border-radius:6px;'
            'padding:6px 10px;color:#e0e0e0;font-size:12px;')
        self.search_edit.textChanged.connect(self._filter)
        L.addWidget(self.search_edit)

        # 拖动勾选列表
        self.lw = DragCheckList()
        self.lw.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.lw.setAlternatingRowColors(True)
        self.lw.setStyleSheet(self.lw.styleSheet() +
                               'QListWidget{alternate-background-color:#1f1f1f;}')
        self._items = []
        for _, title in chapters:
            item = QListWidgetItem(title)
            item.setCheckState(Qt.CheckState.Checked)
            self.lw.addItem(item)
            self._items.append(item)
        self.lw.itemChanged.connect(self._update)
        L.addWidget(self.lw)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._ok)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText('开始下载')
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        L.addWidget(btns)

    def _filter_chapters(self, text):
        for item in self._items:
            item.setHidden(text.lower() not in item.text().lower() if text else False)

    def _select_all(self):
        self.lw.blockSignals(True)
        for i in self._items:
            if not i.isHidden(): i.setCheckState(Qt.CheckState.Checked)
        self.lw.blockSignals(False); self._update()

    def _select_none(self):
        self.lw.blockSignals(True)
        for i in self._items: i.setCheckState(Qt.CheckState.Unchecked)
        self.lw.blockSignals(False); self._update()

    def _update(self):
        n = sum(1 for i in self._items
                if i.checkState() == Qt.CheckState.Checked)
        self.cnt.setText(f'已选 {n} / {len(self._items)} 章')

    def _filter(self, text):
        for i, item in enumerate(self._items):
            item.setHidden(bool(text) and text.lower() not in item.text().lower())

    def _ok(self):
        self.selected = [self.chapters[r]
                         for r, item in enumerate(self._items)
                         if item.checkState() == Qt.CheckState.Checked]
        self.accept()

# ── 样式表 ────────────────────────────────────────────────────

QSS = """
* { font-family:"Microsoft YaHei UI","Segoe UI"; }
QMainWindow,QDialog { background:#181818; }
QWidget { background:#181818; color:#d8d8d8; font-size:13px; }
QTabWidget::pane { border:none; background:#181818; }
QTabBar { background:#1e1e1e; border-bottom:1px solid #252525; }
QTabBar::tab { background:transparent; color:#555; padding:10px 24px;
    border:none; border-bottom:2px solid transparent; font-size:13px; }
QTabBar::tab:selected { color:#e8e8e8; border-bottom:2px solid #3b82f6; }
QTabBar::tab:hover:!selected { color:#999; }
QLineEdit { background:#232323; border:1px solid #2e2e2e; border-radius:7px;
    padding:8px 12px; color:#e0e0e0; font-size:13px;
    selection-background-color:#3b82f6; }
QLineEdit:focus { border-color:#3b82f6; }
QLineEdit:read-only { color:#666; background:#1a1a1a; }
QPushButton { background:#3b82f6; color:#fff; border:none; border-radius:7px;
    padding:8px 18px; font-size:13px; min-height:32px; }
QPushButton:hover { background:#2563eb; }
QPushButton:pressed { background:#1d4ed8; padding:9px 17px 7px 19px; }
QPushButton:disabled { background:#252525; color:#444; }
QPushButton#flat { background:#222; color:#999; border:1px solid #2e2e2e; }
QPushButton#flat:hover { background:#2a2a2a; color:#ccc; }
QPushButton#flat:pressed { padding:9px 17px 7px 19px; }
QPushButton#danger { background:#3f1212; color:#f87171; border:1px solid #5a2020; }
QPushButton#danger:hover { background:#4e1818; }
QProgressBar { background:#222; border:none; border-radius:3px;
    height:6px; color:transparent; }
QProgressBar::chunk { background:#3b82f6; border-radius:3px; }
QTextEdit { background:#111; border:1px solid #222; border-radius:7px;
    color:#bbb; font-family:"Cascadia Code","Consolas",monospace;
    font-size:11px; padding:8px; }
QTreeWidget { background:#1c1c1c; border:1px solid #252525; border-radius:7px;
    color:#d4d4d4; alternate-background-color:#1f1f1f; outline:none; }
QTreeWidget::item { padding:5px 4px; }
QTreeWidget::item:selected { background:#3b82f6; color:#fff; }
QTreeWidget::item:hover:!selected { background:#232323; }
QHeaderView::section { background:#1e1e1e; color:#555; border:none;
    border-right:1px solid #252525; padding:6px 10px; font-size:12px; }
QScrollBar:vertical { background:transparent; width:6px; }
QScrollBar::handle:vertical { background:#2e2e2e; border-radius:3px; min-height:24px; }
QScrollBar::handle:vertical:hover { background:#3a3a3a; }
QScrollBar::add-line,QScrollBar::sub-line { height:0; width:0; }
QScrollBar:horizontal { background:transparent; height:6px; }
QScrollBar::handle:horizontal { background:#2e2e2e; border-radius:3px; }
QSpinBox { background:#232323; border:1px solid #2e2e2e; border-radius:7px;
    padding:6px 10px; color:#e0e0e0; }
QCheckBox { color:#d4d4d4; spacing:8px; }
QCheckBox::indicator { width:17px; height:17px; border:1px solid #3a3a3a;
    border-radius:4px; background:#232323; }
QCheckBox::indicator:checked { background:#3b82f6; border-color:#3b82f6; }
QListWidget::indicator { width:16px; height:16px; border:1px solid #3a3a3a;
    border-radius:3px; background:#232323; }
QListWidget::indicator:checked { background:#3b82f6; border-color:#3b82f6;
    border-radius:3px; }
QListWidget::indicator:unchecked { background:#1e1e1e; border:1px solid #333; }
QLabel { color:#d4d4d4; background:transparent; }
QFrame#card { background:#1e1e1e; border:1px solid #272727; border-radius:8px; }
QDialog { background:#181818; }
QDialogButtonBox QPushButton { min-width:90px; }
QScrollArea { border:none; background:transparent; }
QMenu { background:#1e1e1e; border:1px solid #2e2e2e; border-radius:6px;
    color:#d4d4d4; padding:4px; }
QMenu::item { padding:7px 20px; border-radius:4px; }
QMenu::item:selected { background:#3b82f6; color:#fff; }
"""

def card(p=None):
    f = QFrame(p); f.setObjectName('card'); return f

def sec_label(t):
    l = QLabel(t)
    l.setStyleSheet('color:#444;font-size:11px;letter-spacing:0.5px;')
    return l

def divider():
    f = QFrame(); f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet('border:none;border-top:1px solid #222;')
    return f

# ── 主窗口 ────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings  = 读设置()
        self.session   = make_session()
        self.chapters  = []
        self.book_name = ''
        self._dl_thread  = None
        self._failed     = []
        self._search_results = []
        self._sel_domain = ''

        self.setWindowTitle(f'Hook  v{VERSION}')
        self.resize(860, 740)
        self.setMinimumSize(720, 580)
        self.setStyleSheet(QSS)

        # 任务栏图标
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('HookApp.v6')
        except: pass
        self._set_icon()
        self._build()

        # 首次运行引导
        if not FIRST_RUN.exists():
            QTimer.singleShot(500, self._show_guide)

        # 自动更新检查
        if self.settings.get('auto_check_update', True):
            QTimer.singleShot(3000, self._auto_check_update)

    def _set_icon(self):
        try:
            import base64 as _b64, tempfile as _tmp
            if not ICO_B64: return
            ico_bytes = _b64.b64decode(ICO_B64)
            _ico_path = os.path.join(_tmp.gettempdir(), 'hook_app.ico')
            with open(_ico_path, 'wb') as f: f.write(ico_bytes)
            icon = QIcon(_ico_path)
            self.setWindowIcon(icon)
            QApplication.instance().setWindowIcon(icon)
        except: pass

    def closeEvent(self, e):
        if self._dl_thread and self._dl_thread.isRunning():
            if not MsgBox.confirm(self, '下载进行中',
                '下载正在进行，关闭将暂停（已下内容不丢失）。确认关闭？'):
                e.ignore(); return
            self._dl_thread.stop()
            self._dl_thread.wait(3000)
        if self._settings_dirty():
            if not MsgBox.confirm(self, '设置未保存', '有设置改动未保存，确认放弃？'):
                e.ignore(); return
        e.accept()

    def _show_guide(self):
        FIRST_RUN.touch()
        MsgBox.info(self, '欢迎使用 Hook',
            '三步开始下载\n\n'
            '① 粘贴小说网址（目录页或章节页均可）\n'
            '② 点「识别并获取」\n'
            '③ 点「开始下载」\n\n'
            '历史页右键可继续下载或删除记录')

    # ── 构建 ──────────────────────────────────────────────────

    def _build(self):
        cw = QWidget(); self.setCentralWidget(cw)
        ml = QVBoxLayout(cw); ml.setContentsMargins(0,0,0,0)
        self.tabs = QTabWidget(); self.tabs.setDocumentMode(True)
        ml.addWidget(self.tabs)
        self.tabs.addTab(self._tab_dl(),       '  下载  ')
        self.tabs.addTab(self._tab_search(),   '  搜索  ')
        self.tabs.addTab(self._tab_history(),  '  历史  ')
        self.tabs.addTab(self._tab_settings(), '  设置  ')

    # ── 下载 Tab ──────────────────────────────────────────────

    def _tab_dl(self):
        pg = QWidget(); L = QVBoxLayout(pg)
        L.setContentsMargins(20,16,20,16); L.setSpacing(12)

        # 标题行
        hr = QHBoxLayout()
        t  = QLabel('Hook')
        t.setStyleSheet('font-size:20px;font-weight:700;color:#ececec;')
        self.adp_lbl = QLabel('')
        self.adp_lbl.setStyleSheet(
            'color:#86efac;background:#0f2318;border-radius:4px;'
            'padding:2px 8px;font-size:11px;')
        hist = 读历史()
        stats = QLabel(f'已下载 {len(hist)} 本  ·  '
                       f'{sum(h.get("count",0) for h in hist)} 章')
        stats.setStyleSheet('color:#2a2a2a;font-size:11px;')
        self.stats_lbl = stats
        hr.addWidget(t); hr.addWidget(self.adp_lbl)
        hr.addStretch(); hr.addWidget(stats)
        L.addLayout(hr)

        # URL 卡片
        c1 = card(); c1l = QVBoxLayout(c1)
        c1l.setContentsMargins(16,12,16,14); c1l.setSpacing(8)
        c1l.addWidget(sec_label('小说目录页网址（粘贴任意页面均可自动识别）'))
        ur = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText('粘贴网址，支持目录页、章节页…')
        self.url_input.returnPressed.connect(self._auto_fetch)
        self.fetch_btn = QPushButton('识别并获取')
        self.fetch_btn.setFixedWidth(110)
        self.fetch_btn.clicked.connect(self._auto_fetch)
        ur.addWidget(self.url_input); ur.addWidget(self.fetch_btn)
        c1l.addLayout(ur)
        self.book_lbl = QLabel('输入目录页网址，或切换到「搜索」标签找书')
        self.book_lbl.setStyleSheet('color:#3b82f6;font-size:13px;font-weight:600;')
        c1l.addWidget(self.book_lbl)
        L.addWidget(c1)

        # 范围 + 路径
        row2 = QHBoxLayout(); row2.setSpacing(12)
        c2 = card(); c2l = QVBoxLayout(c2)
        c2l.setContentsMargins(16,12,16,14); c2l.setSpacing(8)
        c2l.addWidget(sec_label('下载范围'))
        rr = QHBoxLayout()
        rr.addWidget(QLabel('从第'))
        self.start_sp = QSpinBox()
        self.start_sp.setRange(1,99999); self.start_sp.setValue(1)
        self.start_sp.setFixedWidth(70)
        rr.addWidget(self.start_sp); rr.addWidget(QLabel('章  到第'))
        self.end_sp = QSpinBox()
        self.end_sp.setRange(1,99999); self.end_sp.setValue(1)
        self.end_sp.setFixedWidth(70)
        rr.addWidget(self.end_sp)
        self.end_lbl = QLabel('章')
        self.end_lbl.setStyleSheet('color:#444;font-size:11px;')
        rr.addWidget(self.end_lbl); rr.addStretch()
        c2l.addLayout(rr); row2.addWidget(c2)

        c3 = card(); c3l = QVBoxLayout(c3)
        c3l.setContentsMargins(16,12,16,14); c3l.setSpacing(8)
        c3l.addWidget(sec_label('保存位置'))
        pr = QHBoxLayout()
        save_path = self.settings.get('save_path', r'D:\缓存文件\小说')
        # 最终保险：如果是 C 盘或桌面路径，强制改回 D 盘
        if not save_path or save_path.upper().startswith('C:') or 'Desktop' in save_path or '桌面' in save_path:
            save_path = r'D:\缓存文件\小说'
        self.path_input = QLineEdit(save_path)
        self.path_input.setReadOnly(True)
        br = QPushButton('更改'); br.setObjectName('flat'); br.setFixedWidth(64)
        br.clicked.connect(self._browse)
        pr.addWidget(self.path_input); pr.addWidget(br)
        c3l.addLayout(pr); row2.addWidget(c3, 2)
        L.addLayout(row2)

        # 进度
        self.prog = QProgressBar(); self.prog.setFixedHeight(6)
        self.prog.setTextVisible(False)
        prow = QHBoxLayout()
        self.prog_lbl = QLabel('')
        self.prog_lbl.setStyleSheet('color:#444;font-size:11px;')
        self.eta_lbl = QLabel('')
        self.eta_lbl.setStyleSheet('color:#fbbf24;font-size:11px;')
        prow.addWidget(self.prog_lbl); prow.addStretch(); prow.addWidget(self.eta_lbl)
        L.addWidget(self.prog); L.addLayout(prow)

        # 日志
        self.log_box = QTextEdit(); self.log_box.setReadOnly(True)
        L.addWidget(self.log_box, 1)

        # 按钮行
        bf = QHBoxLayout(); bf.setSpacing(8)
        self.start_btn = QPushButton('▶  开始下载')
        self.start_btn.setFixedHeight(36)
        self.start_btn.clicked.connect(self._start)
        self.sel_btn = QPushButton('📋  选择章节')
        self.sel_btn.setObjectName('flat'); self.sel_btn.setFixedHeight(36)
        self.sel_btn.clicked.connect(self._select_chapters)
        self.sel_btn.setEnabled(False)
        self.stop_btn = QPushButton('⏹  暂停')
        self.stop_btn.setObjectName('flat'); self.stop_btn.setFixedHeight(36)
        self.stop_btn.clicked.connect(self._stop)
        self.retry_btn = QPushButton('🔄  重试失败')
        self.retry_btn.setObjectName('flat'); self.retry_btn.setFixedHeight(36)
        self.retry_btn.clicked.connect(self._retry)
        self.retry_btn.setEnabled(False)
        self.open_btn = QPushButton('📂  打开文件夹')
        self.open_btn.setObjectName('flat'); self.open_btn.setFixedHeight(36)
        self.open_btn.clicked.connect(self._open)
        for b in [self.start_btn,self.sel_btn,self.stop_btn,
                  self.retry_btn,self.open_btn]:
            bf.addWidget(b)
        L.addLayout(bf)
        return pg

    # ── 搜索 Tab ──────────────────────────────────────────────

    def _tab_search(self):
        pg = QWidget(); L = QVBoxLayout(pg)
        L.setContentsMargins(20,16,20,16); L.setSpacing(12)

        c1 = card(); c1l = QVBoxLayout(c1)
        c1l.setContentsMargins(16,12,16,14); c1l.setSpacing(8)
        c1l.addWidget(sec_label('常用网站（下载后自动记录，按使用次数排序）'))
        self.site_row = QHBoxLayout(); self.site_row.setSpacing(8)
        self.site_row.addStretch()
        c1l.addLayout(self.site_row)
        self.sel_lbl = QLabel('未选择网站 — 点击上方选择')
        self.sel_lbl.setStyleSheet('color:#444;font-size:12px;')
        c1l.addWidget(self.sel_lbl)
        L.addWidget(c1)

        c2 = card(); c2l = QVBoxLayout(c2)
        c2l.setContentsMargins(16,12,16,14); c2l.setSpacing(8)
        c2l.addWidget(sec_label('搜索关键词'))
        sr = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('输入书名...')
        self.search_input.returnPressed.connect(self._search)
        self.search_btn = QPushButton('搜索'); self.search_btn.setFixedWidth(90)
        self.search_btn.clicked.connect(self._search)
        sr.addWidget(self.search_input); sr.addWidget(self.search_btn)
        c2l.addLayout(sr)
        L.addWidget(c2)

        self.search_status = QLabel('')
        self.search_status.setStyleSheet('color:#fbbf24;font-size:12px;')
        L.addWidget(self.search_status)

        self.result_tree = QTreeWidget()
        self.result_tree.setHeaderLabels(['书名', '网站'])
        self.result_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.result_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.result_tree.header().resizeSection(1, 200)
        self.result_tree.setAlternatingRowColors(True)
        self.result_tree.itemDoubleClicked.connect(self._result_click)
        L.addWidget(self.result_tree, 1)

        hint = QLabel('双击结果 → 自动识别目录页并获取章节')
        hint.setStyleSheet('color:#333;font-size:12px;')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        L.addWidget(hint)
        self._refresh_site_btns()
        return pg

    # ── 历史 Tab ──────────────────────────────────────────────

    def _tab_history(self):
        pg = QWidget(); L = QVBoxLayout(pg)
        L.setContentsMargins(20,16,20,16); L.setSpacing(12)
        L.addWidget(QLabel('下载历史'))

        self.hist_tree = QTreeWidget()
        self.hist_tree.setHeaderLabels(['书名','章数','时间','路径'])
        for i,(w,s) in enumerate([(170,False),(55,False),(140,False),(1,True)]):
            self.hist_tree.header().setSectionResizeMode(
                i, QHeaderView.ResizeMode.Stretch if s else QHeaderView.ResizeMode.Fixed)
            if not s: self.hist_tree.header().resizeSection(i, w)
        self.hist_tree.setAlternatingRowColors(True)
        self.hist_tree.itemDoubleClicked.connect(self._hist_click)
        # 右键菜单
        self.hist_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.hist_tree.customContextMenuRequested.connect(self._hist_context_menu)
        L.addWidget(self.hist_tree)

        L.addWidget(divider())
        L.addWidget(QLabel('访问过的网站'))
        self.site_tree = QTreeWidget()
        self.site_tree.setHeaderLabels(['域名','次数','最后访问'])
        self.site_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i,w in [(1,70),(2,140)]:
            self.site_tree.header().setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            self.site_tree.header().resizeSection(i, w)
        self.site_tree.setAlternatingRowColors(True)
        L.addWidget(self.site_tree)

        hint = QLabel('双击历史 → 打开文件夹  ·  右键 → 更多操作')
        hint.setStyleSheet('color:#333;font-size:12px;')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        L.addWidget(hint)
        self._refresh_history()
        return pg

    # ── 设置 Tab ──────────────────────────────────────────────

    def _tab_settings(self):
        pg = QWidget(); L = QVBoxLayout(pg)
        L.setContentsMargins(20,16,20,16); L.setSpacing(12)

        # 输出格式
        c1 = card(); c1l = QVBoxLayout(c1)
        c1l.setContentsMargins(16,14,16,14); c1l.setSpacing(10)
        c1l.addWidget(sec_label('输出格式'))
        fr = QHBoxLayout()
        self.cb_txt  = QCheckBox('TXT 文本')
        self.cb_epub = QCheckBox('EPUB 电子书')
        self.cb_txt.setChecked(self.settings.get('gen_txt', True))
        self.cb_epub.setChecked(self.settings.get('gen_epub', False))
        fr.addWidget(self.cb_txt); fr.addWidget(self.cb_epub); fr.addStretch()
        c1l.addLayout(fr)
        L.addWidget(c1)

        # 行为
        c2 = card(); c2l = QVBoxLayout(c2)
        c2l.setContentsMargins(16,14,16,14); c2l.setSpacing(10)
        c2l.addWidget(sec_label('行为'))
        self.cb_open     = QCheckBox('下载完成后自动打开文件夹')
        self.cb_auto_upd = QCheckBox('启动时自动检查更新')
        self.cb_open.setChecked(self.settings.get('auto_open', False))
        self.cb_auto_upd.setChecked(self.settings.get('auto_check_update', True))
        c2l.addWidget(self.cb_open); c2l.addWidget(self.cb_auto_upd)
        L.addWidget(c2)

        # 适配器
        c3 = card(); c3l = QVBoxLayout(c3)
        c3l.setContentsMargins(16,14,16,14); c3l.setSpacing(8)
        c3l.addWidget(sec_label('网站适配器'))
        hint = QLabel(f'配置文件：{ADAPTERS_FILE}')
        hint.setStyleSheet('color:#333;font-size:11px;')
        c3l.addWidget(hint)
        br2 = QHBoxLayout()
        open_cfg = QPushButton('打开配置文件')
        open_cfg.setObjectName('flat'); open_cfg.setFixedWidth(130)
        open_cfg.clicked.connect(lambda: os.startfile(str(ADAPTERS_FILE)))
        reload_cfg = QPushButton('重新加载')
        reload_cfg.setObjectName('flat'); reload_cfg.setFixedWidth(90)
        reload_cfg.clicked.connect(self._reload_adapters)
        br2.addWidget(open_cfg); br2.addWidget(reload_cfg); br2.addStretch()
        c3l.addLayout(br2)
        L.addWidget(c3)

        # 程序管理
        c4 = card(); c4l = QVBoxLayout(c4)
        c4l.setContentsMargins(16,14,16,14); c4l.setSpacing(8)
        c4l.addWidget(sec_label('程序管理'))
        vr = QHBoxLayout()
        vr.addWidget(QLabel(f'版本：v{VERSION}'))
        self.upd_status = QLabel('')
        self.upd_status.setStyleSheet('color:#fbbf24;font-size:12px;')
        vr.addWidget(self.upd_status); vr.addStretch()
        upd_btn = QPushButton('检查更新')
        upd_btn.setObjectName('flat'); upd_btn.setFixedWidth(100)
        upd_btn.clicked.connect(self._check_update)
        uninstall = QPushButton('卸载')
        uninstall.setObjectName('danger'); uninstall.setFixedWidth(80)
        uninstall.clicked.connect(self._uninstall)
        vr.addWidget(upd_btn); vr.addWidget(uninstall)
        c4l.addLayout(vr)
        self.upd_prog = QProgressBar()
        self.upd_prog.setFixedHeight(4); self.upd_prog.setTextVisible(False)
        self.upd_prog.hide()
        c4l.addWidget(self.upd_prog)
        L.addWidget(c4)

        L.addStretch()
        br = QHBoxLayout(); br.setSpacing(8)
        sv = QPushButton('保存设置'); sv.setFixedHeight(36); sv.clicked.connect(self._save)
        rs = QPushButton('重置默认'); rs.setObjectName('flat')
        rs.setFixedHeight(36); rs.clicked.connect(self._reset)
        br.addWidget(sv); br.addWidget(rs)
        L.addLayout(br)
        return pg

    # ── 日志 ──────────────────────────────────────────────────

    def _log(self, msg, color='white'):
        c = {'green':'#4ade80','red':'#f87171','yellow':'#fbbf24',
             'white':'#aaa','blue':'#93c5fd'}.get(color, '#aaa')
        self.log_box.append(f'<span style="color:{c};">{msg}</span>')
        doc = self.log_box.document()
        while doc.blockCount() > 500:
            cur = self.log_box.textCursor()
            cur.movePosition(cur.MoveOperation.Start)
            cur.select(cur.SelectionType.BlockUnderCursor)
            cur.removeSelectedText(); cur.deleteChar()
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum())

    # ── 下载 Tab 逻辑 ─────────────────────────────────────────

    def _browse(self):
        p = QFileDialog.getExistingDirectory(self, '选择保存目录',
                                              self.path_input.text())
        if p:
            self.path_input.setText(p)
            self.settings['save_path'] = p
            写设置(self.settings)

    def _auto_fetch(self):
        url = self.url_input.text().strip()
        if not url: return
        self.fetch_btn.setEnabled(False)
        self.sel_btn.setEnabled(False)
        self.chapters = []
        self.book_lbl.setText('正在识别网页类型…')
        self.book_lbl.setStyleSheet('color:#555;font-size:13px;font-weight:600;')
        self._log(f'识别网址：{url}', 'blue')
        t = ResolveThread(url, self.session)
        t.ok.connect(self._on_resolved)
        t.fail.connect(self._on_fetch_fail)
        t.start(); self._resolve_thread = t

    def _on_resolved(self, resolved, hint):
        self._log(f'识别结果：{hint}  →  {resolved}', 'blue')
        if resolved != self.url_input.text().strip():
            self.url_input.setText(resolved)
        self.book_lbl.setText('正在获取章节列表…')
        t = FetchThread(resolved, self.session)
        t.ok.connect(self._on_fetched)
        t.fail.connect(self._on_fetch_fail)
        t.start(); self._fetch_thread = t

    def _on_fetched(self, title, lst, adp_name):
        self.book_name = title; self.chapters = lst
        self.book_lbl.setText(f'《{title}》  共 {len(lst)} 章  ✓ 可以下载')
        self.book_lbl.setStyleSheet('color:#4ade80;font-size:13px;font-weight:600;')
        self.adp_lbl.setText(f' {adp_name} '); self.adp_lbl.setVisible(True)
        self._log(f'获取成功：{len(lst)} 章', 'green')
        if lst:
            self._log(f'  第一章：{lst[0][1]}')
            self._log(f'  最后章：{lst[-1][1]}')
            self._log(f'  → 点「开始下载」或「选择章节」继续', 'blue')
        if lst:
            self.end_sp.setRange(1, len(lst))
            self.end_sp.setValue(len(lst))
            self.end_lbl.setText(f'章（共 {len(lst)} 章）')
        self.fetch_btn.setEnabled(True)
        self.sel_btn.setEnabled(True)
        self._refresh_history()

    def _on_fetch_fail(self, err):
        self.book_lbl.setText('获取失败 — 请检查网址')
        self.book_lbl.setStyleSheet('color:#f87171;font-size:13px;font-weight:600;')
        # 过滤技术错误，显示用户能看懂的提示
        if 'SSL连接失败' in err or 'SSL' in err or 'EOF' in err:
            msg = 'SSL 连接失败，请确认梯子已开启后重试'
        elif '连接超时' in err or 'timeout' in err.lower():
            msg = '连接超时，请检查网络后重试'
        elif '无法连接' in err or 'connection' in err.lower():
            msg = '无法连接，请确认网址正确且网站可访问'
        elif '网络请求失败' in err:
            msg = '网络请求失败，请稍后重试'
        else:
            msg = '获取失败，请确认粘贴的是小说目录页或章节页'
        self._log(f'✗ {msg}', 'red')
        self.fetch_btn.setEnabled(True)

    def _select_chapters(self):
        if not self.chapters: return
        dlg = ChapterDialog(self.chapters, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected:
            self._start_with(dlg.selected)

    def _start(self):
        if self._dl_thread and self._dl_thread.isRunning(): return
        if not self.chapters:
            MsgBox.warn(self, '提示', '请先获取章节列表'); return
        start  = self.start_sp.value() - 1
        end    = self.end_sp.value()
        target = self.chapters[start:end]
        if not target: return
        self._start_with(target)

    def _start_with(self, target):
        if self._dl_thread and self._dl_thread.isRunning(): return
        save_dir = self.path_input.text().strip()
        if not save_dir:
            MsgBox.warn(self, '提示', '请设置保存位置'); return
        # 磁盘空间检查
        try:
            free = shutil.disk_usage(save_dir).free
            need = len(target) * 5 * 1024
            if free < need:
                mf = free//1024//1024; mn = need//1024//1024
                if not MsgBox.confirm(self, '磁盘空间不足',
                    f'预估需要约 {mn}MB，当前剩余 {mf}MB。继续？'):
                    return
        except: pass
        safe      = re.sub(r'[\\/:*?"<>|]', '', self.book_name)
        save_path = str(Path(save_dir) / f'{safe}.txt')
        self.prog.setMaximum(len(target)); self.prog.setValue(0)
        self.prog_lbl.setText(''); self.eta_lbl.setText('')
        self.start_btn.setEnabled(False); self.retry_btn.setEnabled(False)
        self._failed = []
        self._log(f'\n开始下载《{self.book_name}》共 {len(target)} 章', 'blue')
        self._dl_thread = DownloadThread(
            target, self.url_input.text().strip(),
            self.book_name, save_path, self.settings, self.session)
        self._dl_thread.log.connect(self._log)
        self._dl_thread.progress.connect(self._on_prog)
        self._dl_thread.done.connect(self._on_done)
        self._dl_thread.start()

    def _on_prog(self, cur, total, eta, speed=0):
        self.prog.setValue(cur)
        pct = round(cur/total*100, 1) if total else 0
        spd = (f'  ·  {speed//1000}k字/秒' if speed >= 1000
               else (f'  ·  {speed}字/秒' if speed > 0 else ''))
        self.prog_lbl.setText(f'{cur} / {total}  ·  {pct}%{spd}')
        if eta > 0:
            if eta >= 3600:   s = f'{int(eta//3600)}h {int((eta%3600)//60)}m'
            elif eta >= 60:   s = f'{int(eta//60)}m {int(eta%60)}s'
            else:             s = f'{int(eta)}s'
            self.eta_lbl.setText(f'剩余约 {s}')

    def _on_done(self, count, epub_data, failed, save_path):
        self._log(f'\n完成！共 {count} 章 → {save_path}', 'green')
        self._failed = failed
        if failed:
            self._log(f'失败 {len(failed)} 章：' +
                      '、'.join(t for _,t in failed[:4]) +
                      ('…' if len(failed)>4 else ''), 'red')
            self.retry_btn.setEnabled(True)
        self.start_btn.setEnabled(True)
        写历史({'name': self.book_name, 'count': count,
                'time': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'path': save_path,
                'url':  self.url_input.text().strip()})
        删进度(save_path)
        self._refresh_history()
        self._update_stats()
        # 系统通知
        if not getattr(self._dl_thread, '_paused', False):
            toast('Hook 下载完成', f'《{self.book_name}》共 {count} 章')
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except: pass
            tip = QDialog(self)
            tip.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                               Qt.WindowType.WindowStaysOnTopHint)
            tip.setStyleSheet('QDialog{background:#14532d;border:1px solid #166534;'
                              'border-radius:8px;}QLabel{color:#4ade80;font-size:13px;'
                              'font-family:"Microsoft YaHei UI";padding:12px 20px;}')
            QLabel(f'✓  《{self.book_name}》下载完成，共 {count} 章', tip).show()
            tip.adjustSize()
            try:
                screen = QApplication.primaryScreen().geometry()
                tip.move(screen.width()-tip.width()-20, screen.height()-tip.height()-60)
            except: pass
            tip.show()
            QTimer.singleShot(2500, tip.close)
        if epub_data and self.settings.get('gen_epub'):
            self._log('正在生成 EPUB…', 'yellow')
            et = EpubThread(self.book_name, epub_data, save_path)
            et.done.connect(lambda p: self._log(f'EPUB 已保存：{p}', 'green'))
            et.fail.connect(lambda e: self._log(f'EPUB 失败：{e}', 'red'))
            et.start(); self._epub_thread = et
        if (self.settings.get('auto_open') and
                not getattr(self._dl_thread, '_paused', False)):
            d = str(Path(save_path).parent)
            if Path(d).exists(): os.startfile(d)

    def _retry(self):
        if not self._failed: return
        self._log(f'\n重试 {len(self._failed)} 个失败章节…', 'yellow')
        self._start_with(self._failed)

    def _stop(self):
        if self._dl_thread and self._dl_thread.isRunning():
            self._dl_thread.stop()

    def _open(self):
        p = self.path_input.text().strip()
        if Path(p).exists(): os.startfile(p)
        else: MsgBox.info(self, '提示', '文件夹不存在：{p}')

    def _update_stats(self):
        hist = 读历史()
        self.stats_lbl.setText(
            f'已下载 {len(hist)} 本  ·  '
            f'{sum(h.get("count",0) for h in hist)} 章')
        self.stats_lbl.setStyleSheet('color:#333;font-size:11px;')

    # ── 搜索 Tab 逻辑 ─────────────────────────────────────────

    def _refresh_site_btns(self):
        for i in reversed(range(self.site_row.count())):
            w = self.site_row.itemAt(i).widget()
            if w: w.deleteLater()
        sites = 常用网站()[:8]
        if not sites:
            l = QLabel('暂无记录，下载后自动出现')
            l.setStyleSheet('color:#333;font-size:12px;')
            self.site_row.addWidget(l)
        for domain, info in sites:
            name = info.get('name', domain)[:16]
            cnt  = info.get('count', 0)
            btn  = QPushButton(f'{name}  {cnt}')
            btn.setObjectName('flat'); btn.setFixedHeight(28)
            btn.clicked.connect(lambda _, d=domain: self._pick_site(d))
            self.site_row.addWidget(btn)
        self.site_row.addStretch()

    def _pick_site(self, domain):
        self._sel_domain = domain
        name = 读网站().get(domain, {}).get('name', domain)
        self.sel_lbl.setText(f'已选择：{name}  —  {domain}')
        self.sel_lbl.setStyleSheet('color:#3b82f6;font-size:12px;')

    def _search(self):
        if not self._sel_domain:
            MsgBox.info(self, '提示', '请先点击上方选择一个网站'); return
        kw = self.search_input.text().strip()
        if not kw: return
        self.search_status.setText('搜索中…')
        self.search_status.setStyleSheet('color:#fbbf24;font-size:12px;')
        self.search_btn.setEnabled(False)
        self.result_tree.clear(); self._search_results = []
        t = SearchThread(self._sel_domain, kw, self.session)
        t.result.connect(self._on_search)
        t.start(); self._s_thread = t

    def _on_search(self, results, ok):
        self._search_results = results
        self.result_tree.clear()
        for r in results:
            QTreeWidgetItem(self.result_tree,
                            [r['title'], r.get('site', self._sel_domain)])
        if results:
            self.search_status.setText(f'找到 {len(results)} 条结果，双击直接下载')
            self.search_status.setStyleSheet('color:#4ade80;font-size:12px;')
        elif ok:
            self.search_status.setText('未找到相关结果')
            self.search_status.setStyleSheet('color:#888;font-size:12px;')
        else:
            self.search_status.setText('搜索出错（网络问题或该网站不支持搜索）')
            self.search_status.setStyleSheet('color:#f87171;font-size:12px;')
        self.search_btn.setEnabled(True)

    def _result_click(self, item, _):
        idx = self.result_tree.indexOfTopLevelItem(item)
        if 0 <= idx < len(self._search_results):
            self.url_input.setText(self._search_results[idx]['url'])
            self.tabs.setCurrentIndex(0)
            self._auto_fetch()

    # ── 历史 Tab 逻辑 ─────────────────────────────────────────

    def _refresh_history(self):
        def _do():
            self.hist_tree.clear()
            for h in 读历史():
                item = QTreeWidgetItem(self.hist_tree, [
                    h.get('name',''), str(h.get('count','')),
                    h.get('time',''), h.get('path','')])
                # 把 URL 存在 UserRole 供右键继续下载使用
                item.setData(0, Qt.ItemDataRole.UserRole, h.get('url',''))
            self.site_tree.clear()
            for domain, info in 常用网站():
                QTreeWidgetItem(self.site_tree, [
                    info.get('name', domain),
                    str(info.get('count', 0)),
                    info.get('last', '')])
            self._refresh_site_btns()
        QTimer.singleShot(0, _do)

    def _hist_click(self, item, _):
        folder = str(Path(item.text(3)).parent)
        if Path(folder).exists(): os.startfile(folder)
        else: MsgBox.info(self, '提示', '文件夹不存在：{folder}')

    def _hist_context_menu(self, pos):
        item = self.hist_tree.itemAt(pos)
        if not item: return
        menu  = QMenu(self)
        path  = item.text(3)
        name  = item.text(0)
        a_open   = menu.addAction('📂  打开文件夹')
        a_retry  = menu.addAction('⬇️  继续下载（重新获取）')
        menu.addSeparator()
        a_delete = menu.addAction('🗑  删除记录')
        action = menu.exec(self.hist_tree.viewport().mapToGlobal(pos))
        if action == a_open:
            folder = str(Path(path).parent)
            if Path(folder).exists(): os.startfile(folder)
        elif action == a_retry:
            hist_url = next((h.get('url','') for h in 读历史() if h.get('path')==path), '')
            if hist_url:
                self.url_input.setText(hist_url)
                self.tabs.setCurrentIndex(0)
                self._auto_fetch()
            else:
                MsgBox.info(self,'提示','未找到网址记录，请手动输入网址。')
                self.tabs.setCurrentIndex(0)
        elif action == a_delete:
            if MsgBox.confirm(self,'确认',
                f'删除《{name}》的下载记录？（文件不受影响）'):
                删历史(path)
                self._refresh_history()
                self._update_stats()

    # ── 设置 Tab 逻辑 ─────────────────────────────────────────

    def _settings_dirty(self):
        try:
            return (self.cb_txt.isChecked()     != self.settings.get('gen_txt',True)   or
                    self.cb_epub.isChecked()    != self.settings.get('gen_epub',False) or
                    self.cb_open.isChecked()    != self.settings.get('auto_open',False) or
                    self.cb_auto_upd.isChecked()!= self.settings.get('auto_check_update',True))
        except: return False

    def _reload_adapters(self):
        load_adapters()
        MsgBox.info(self, '完成', '已重新加载 {len(_ADAPTERS)-1} 个适配器。')

    def _save(self):
        self.settings.update({
            'gen_txt':           self.cb_txt.isChecked(),
            'gen_epub':          self.cb_epub.isChecked(),
            'auto_open':         self.cb_open.isChecked(),
            'auto_check_update': self.cb_auto_upd.isChecked(),
            'save_path':         self.path_input.text(),
        })
        写设置(self.settings)
        MsgBox.info(self, '已保存', '设置已保存。')

    def _reset(self):
        if MsgBox.confirm(self, '确认', '重置所有设置？'):
            写设置(DEFAULTS)
            MsgBox.info(self, '完成', '已重置，重启生效。')

    def _uninstall(self):
        if not MsgBox.confirm(self,'确认卸载',
            '将删除程序及所有数据，下载的小说不受影响。确认？'): return
        self_path = Path(sys.executable) if getattr(sys,'frozen',False) else Path(__file__)
        bat = Path(tempfile.gettempdir()) / 'uninstall_hook.bat'
        with open(bat,'w') as f:
            f.write('@echo off\ntimeout /t 2 /nobreak >nul\n')
            f.write(f'del /f /q "{self_path}" >nul 2>&1\n')
            f.write(f'rd /s /q "{DATA_DIR}" >nul 2>&1\n')
            f.write(f'del /f /q "{bat}"\n')
        subprocess.Popen(['cmd','/c',str(bat)], creationflags=0x08000000)
        sys.exit(0)

    # ── 更新逻辑 ──────────────────────────────────────────────

    def _auto_check_update(self):
        t = UpdateCheckThread()
        t.result.connect(self._on_auto_check)
        t.start(); self._upd_chk = t

    def _on_auto_check(self, ver, newer):
        if newer:
            self.upd_status.setText(f'发现新版本 v{ver}')
            self._log(f'发现新版本 v{ver}，可在「设置」里更新', 'yellow')

    def _check_update(self):
        self.upd_status.setText('检查中…')
        t = UpdateCheckThread()
        t.result.connect(self._on_check_result)
        t.start(); self._upd_chk = t

    def _on_check_result(self, ver, newer):
        if not ver:
            self.upd_status.setText('检查失败，请稍后重试')
            return
        if newer:
            self.upd_status.setText(f'发现新版本 v{ver}')
            msg = f'发现新版本 v{ver}（当前 v{VERSION}）\n\n更新只需几秒，完成后自动重启。继续？'
            if MsgBox.confirm(self,'发现更新',msg):
                self._do_update()
        else:
            self.upd_status.setText('已是最新版本')

    def _do_update(self):
        self.upd_prog.show(); self.upd_prog.setValue(0)
        self.upd_status.setText('正在下载更新…')
        t = UpdateDownloadThread()
        t.progress.connect(self.upd_prog.setValue)
        t.done.connect(self._on_update_done)
        t.start(); self._upd_dl = t

    def _on_update_done(self, ok, err):
        self.upd_prog.hide()
        if ok:
            MsgBox.info(self, '更新完成', '新版本已下载，点确定后自动重启。')
            restart_app()
        else:
            self.upd_status.setText('更新失败')
            MsgBox.warn(self, '更新失败', '错误：{err}\n\n请检查网络后重试。')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
