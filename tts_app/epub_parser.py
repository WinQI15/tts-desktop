"""
统一书籍解析模块
支持 EPUB / PDF / MOBI 三种格式，统一返回章节列表
"""
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

# 延迟导入各格式依赖
_ebooklib_available = False
try:
    import ebooklib
    from ebooklib import epub
    _ebooklib_available = True
except ImportError:
    pass

_bs4_available = False
try:
    from bs4 import BeautifulSoup
    _bs4_available = True
except ImportError:
    pass

_fitz_available = False
try:
    import fitz  # PyMuPDF
    _fitz_available = True
except ImportError:
    pass

_mobi_available = False
try:
    import mobi
    _mobi_available = True
except ImportError:
    pass


class BookParser:
    """统一书籍解析器 — 支持 EPUB/PDF/MOBI

    用法:
        parser = BookParser("book.epub")  # 或 .pdf / .mobi
        metadata = parser.get_metadata()
        chapters = parser.extract_chapters()
        toc = parser.get_toc_tree()  # 3级目录树
    """

    FORMATS = {
        ".epub": "EPUB 电子书",
        ".pdf":  "PDF 文档",
        ".mobi": "MOBI/Kindle 电子书",
    }

    def __init__(self, file_path: str):
        self.file_path = file_path
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".epub":
            self._parser = _EpubBackend(file_path)
        elif ext == ".pdf":
            self._parser = _PdfBackend(file_path)
        elif ext == ".mobi":
            self._parser = _MobiBackend(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {ext}")

    def get_metadata(self) -> dict:
        return self._parser.get_metadata()

    def extract_chapters(self) -> list[dict]:
        return self._parser.extract_chapters()

    def get_toc_tree(self) -> list[dict]:
        return self._parser.get_toc_tree()

    def get_full_text(self) -> str:
        return "\n\n".join(ch["content"] for ch in self.extract_chapters())

    @staticmethod
    def is_valid_book(file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        return ext in BookParser.FORMATS


# ============================================================
# EPUB 后端
# ============================================================

class _EpubBackend:
    """EPUB 解析（复用现有逻辑）"""

    def __init__(self, file_path: str):
        if not _ebooklib_available:
            raise ImportError("ebooklib 未安装")
        if not _bs4_available:
            raise ImportError("beautifulsoup4 未安装")

        self.file_path = file_path
        self.book = epub.read_epub(file_path)
        self._chapters: list[dict] = []

    def get_metadata(self) -> dict:
        meta = {"title": "未知标题", "author": "未知作者", "language": "未知语言"}
        try:
            dc = self.book.get_metadata("DC", "title")
            if dc: meta["title"] = str(dc[0][0])
        except (AttributeError, TypeError, IndexError):
            pass
        try:
            dc = self.book.get_metadata("DC", "creator")
            if dc: meta["author"] = str(dc[0][0])
        except (AttributeError, TypeError, IndexError):
            pass
        try:
            dc = self.book.get_metadata("DC", "language")
            if dc: meta["language"] = str(dc[0][0])
        except (AttributeError, TypeError, IndexError):
            pass
        return meta

    def extract_chapters(self) -> list[dict]:
        if self._chapters:
            return self._chapters
        chapters = []
        try:
            spine_items = self._get_spine_items()
            idx = 0
            for item in spine_items:
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    try:
                        content = item.get_content()
                        soup = BeautifulSoup(content, "html.parser")
                        title = self._extract_title(soup, item)
                        text = self._clean_text(soup.get_text())
                        if text.strip():
                            chapters.append({
                                "title": title, "content": text,
                                "index": idx, "file_name": item.get_name(),
                                "char_count": len(text),
                                "item_id": getattr(item, 'id', ''),
                            })
                            idx += 1
                    except Exception:
                        continue
            self._chapters = chapters
        except Exception as e:
            logger.error(f"EPUB 提取失败: {e}")
        return chapters

    def get_toc_tree(self) -> list[dict]:
        chapters = self.extract_chapters()
        href_to_idx: dict[str, int] = {}
        for ch in chapters:
            fname = ch.get("file_name", "")
            if fname:
                href_to_idx[fname] = ch["index"]
                base = fname.split("/")[-1] if "/" in fname else fname
                href_to_idx[base] = ch["index"]

        toc = self._extract_toc(href_to_idx)
        if toc:
            return toc
        return self._build_heading_tree()

    def _get_spine_items(self):
        try:
            spine = self.book.spine
            if not spine:
                return [item for item in self.book.get_items()
                        if item.get_type() == ebooklib.ITEM_DOCUMENT]
            item_map = {item.id: item for item in self.book.get_items()}
            ordered = []
            for item_id, _linear in spine:
                if item_id in item_map:
                    item = item_map[item_id]
                    if item.get_type() == ebooklib.ITEM_DOCUMENT:
                        ordered.append(item)
            return ordered
        except (AttributeError, TypeError, ValueError) as e:
            logger.debug(f"Spine解析失败，回退到manifest: {e}")
            return [item for item in self.book.get_items()
                    if item.get_type() == ebooklib.ITEM_DOCUMENT]
        except Exception as e:
            logger.debug(f"Spine解析异常: {e}")
            # 回退：尝试从 manifest 获取文档
            try:
                return [item for item in self.book.get_items()
                        if item.get_type() == ebooklib.ITEM_DOCUMENT]
            except Exception:
                return []

    def _extract_toc(self, href_to_idx: dict[str, int]) -> list[dict]:
        from ebooklib.epub import Section, Link
        try:
            raw = self.book.toc
            if not raw:
                return []
            tree = self._parse_toc(raw, href_to_idx, 0)
            # MOBI 转 EPUB 常产生扁平 TOC → 用文本模式重建层级
            if tree and self._is_toc_flat(tree):
                logger.info("EPUB TOC 扁平，基于文本模式重建层级")
                tree = self._hierarchize_toc(tree)
            return tree
        except (AttributeError, TypeError) as e:
            logger.debug(f"TOC解析失败（EPUB结构问题）: {e}")
            return []
        except Exception as e:
            logger.debug(f"TOC解析异常: {e}")
            return []

    def _is_toc_flat(self, tree: list[dict]) -> bool:
        """判断 TOC 树是否是扁平结构（大部分根节点无子节点）"""
        if len(tree) <= 1:
            return False
        flat_count = sum(1 for n in tree if not n.get("children"))
        return flat_count > len(tree) / 2

    def _hierarchize_toc(self, tree: list[dict]) -> list[dict]:
        """扁平 TOC → 按文本模式重建层级结构"""
        # 1. 展平所有节点
        flat = []
        def _flatten(nodes):
            for n in nodes:
                flat.append(n)
                if n.get("children"):
                    _flatten(n["children"])
        _flatten(tree)

        # 2. 按文本检测层级
        new_tree = []
        stack = []
        for n in flat:
            level = self._detect_level(n["title"])
            if level == 0:
                level = 2  # 未识别的归为"章"级
            node = {"title": n["title"], "level": level,
                    "index": n["index"], "children": [],
                    "href": n.get("href", "")}
            if level == 1:
                new_tree.append(node)
                stack = [node]
            else:
                while stack and stack[-1]["level"] >= level:
                    stack.pop()
                if stack:
                    stack[-1]["children"].append(node)
                else:
                    new_tree.append(node)
                stack.append(node)

        return new_tree

    def _parse_toc(self, items, href_to_idx: dict, level: int) -> list[dict]:
        from ebooklib.epub import Section, Link
        result = []
        for item in items:
            title = ""; href = ""; children_raw = []
            if isinstance(item, tuple):
                head = item[0]
                children_raw = list(item[1]) if len(item) > 1 and isinstance(item[1], list) else []
                if isinstance(head, (Section, Link)):
                    title = getattr(head, 'title', '') or ''
                    href = getattr(head, 'href', '') or ''
                elif isinstance(head, str):
                    title = head
                else:
                    continue
            elif isinstance(item, (Section, Link)):
                title = getattr(item, 'title', '') or ''
                href = getattr(item, 'href', '') or ''
            elif isinstance(item, str):
                title = item
            else:
                continue
            title = title.strip()
            if not title or title.startswith("<") or "object at" in title:
                continue
            idx = self._resolve_href(href, href_to_idx)
            children = self._parse_toc(children_raw, href_to_idx, level + 1)
            result.append({"title": title, "level": min(level + 1, 3), "index": idx, "children": children, "href": href})

        # ★ 子节点若无法映射到独立章节 → 继承父节点的 index
        # （子节通常和父章共享同一个 spine item）
        self._propagate_index(result, -1)
        return result

    def _propagate_index(self, nodes: list[dict], parent_idx: int):
        """子节点 index=-1 时继承父节点 index"""
        for node in nodes:
            if node["index"] < 0 and parent_idx >= 0:
                node["index"] = parent_idx
            if node.get("children"):
                self._propagate_index(node["children"], node["index"])

    @staticmethod
    def _resolve_href(href: str, href_to_idx: dict) -> int:
        if not href:
            return -1
        path = href.split("#")[0] if "#" in href else href
        path = path.lstrip("./\\")
        for key, idx in href_to_idx.items():
            if path == key or path.endswith("/" + key) or key.endswith(path):
                return idx
            if path.replace("_", "").replace("-", "") == key.replace("_", "").replace("-", ""):
                return idx
        return -1

    def _build_heading_tree(self) -> list[dict]:
        chapters = self.extract_chapters()
        tree = []
        stack = []
        for ch in chapters:
            level = self._detect_level(ch.get("title", ""))
            if level == 0:
                continue
            node = {"title": ch["title"], "level": level, "index": ch["index"], "children": []}
            if level == 1:
                tree.append(node)
                stack = [node]
            else:
                while stack and stack[-1]["level"] >= level:
                    stack.pop()
                if stack:
                    stack[-1]["children"].append(node)
                else:
                    tree.append(node)
                stack.append(node)
        return tree

    @staticmethod
    def _detect_level(title: str) -> int:
        """从标题文字猜测层级：1=卷/部, 2=章, 3=节/小节, 0=非标题"""
        if re.match(r'^(第[一二三四五六七八九十\d]+[部卷篇集]|Part\s+\d+)', title):
            return 1
        if re.match(r'^(第[一二三四五六七八九十\d]+章|Chapter\s+\d+)', title):
            return 2
        if re.match(r'^(第[一二三四五六七八九十\d]+[节条]|Section\s+\d+)', title):
            return 3
        if re.match(r'^\d+\.\d+\.\d+', title):
            return 3
        if re.match(r'^\d+\.\d+', title):
            return 2
        if re.match(r'^\d+[.、．]\s*', title):
            return 3
        if re.match(r'^[\(（]\d+[\)）]', title):   #  (1) / （1）
            return 3
        if re.match(r'^(序言|前言|目录|附录|后记|尾声|楔子|卷首|番外|导读)', title):
            return 1
        return 0

    def _extract_title(self, soup, item) -> str:
        for tag in ["h1", "h2", "h3", "h4"]:
            heading = soup.find(tag)
            if heading and heading.get_text().strip():
                return heading.get_text().strip()
        title_tag = soup.find("title")
        if title_tag and title_tag.get_text().strip():
            return title_tag.get_text().strip()
        name = item.get_name()
        name = re.sub(r"[\\/]", " - ", name)
        name = re.sub(r"\.(x?html?|xml)$", "", name, flags=re.IGNORECASE)
        return name

    @staticmethod
    def _clean_text(text: str) -> str:
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = "\n".join(line.strip() for line in text.split("\n"))
        text = re.sub(r" {2,}", " ", text)
        return text.strip()


# ============================================================
# PDF 后端（PyMuPDF）
# ============================================================

class _PdfBackend:
    """PDF 解析 — 按页分章，按大纲（书签）建目录树"""

    def __init__(self, file_path: str):
        if not _fitz_available:
            raise ImportError("PyMuPDF (fitz) 未安装，请运行: pip install PyMuPDF")
        self.file_path = file_path
        self.doc = fitz.open(file_path)
        self._chapters: list[dict] = []

    def get_metadata(self) -> dict:
        meta = {"title": "未知标题", "author": "未知作者", "language": "中文"}
        try:
            md = self.doc.metadata
            if md:
                meta["title"] = md.get("title", meta["title"]) or meta["title"]
                meta["author"] = md.get("author", meta["author"]) or meta["author"]
        except Exception:
            pass
        return meta

    def extract_chapters(self) -> list[dict]:
        if self._chapters:
            return self._chapters
        chapters = []
        for page_num in range(self.doc.page_count):
            page = self.doc[page_num]
            text = page.get_text("text").strip()
            if not text:
                continue
            # 从页面首行文字提取标题
            lines = text.split("\n")
            title = lines[0].strip()[:80] if lines else f"第{page_num+1}页"
            chapters.append({
                "title": title,
                "content": text,
                "index": page_num,
                "file_name": f"page_{page_num+1}",
                "char_count": len(text),
                "item_id": f"p{page_num}",
            })
        self._chapters = chapters
        logger.info(f"PDF 提取到 {len(chapters)} 个页面")
        return chapters

    def get_toc_tree(self) -> list[dict]:
        """使用 PDF 书签/大纲构建目录树"""
        toc_raw = self.doc.get_toc()  # [(level, title, page), ...]
        if not toc_raw:
            # 无书签 → 按页当一章
            chapters = self.extract_chapters()
            return [{"title": f"第{i+1}页 " + (c["title"][:30] if c["title"] else ""),
                      "level": 1, "index": i, "children": []}
                    for i, c in enumerate(chapters)]

        # 构建树
        tree = []
        stack = []
        chapters = self.extract_chapters()

        # page_num → index 映射（PDF页码从1开始）
        page_to_idx = {i: i for i in range(len(chapters))}

        for level, title, page in toc_raw:
            idx = page_to_idx.get(page - 1, -1)
            node = {"title": title, "level": min(level, 3), "index": idx, "children": []}
            if level == 1:
                tree.append(node)
                stack = [node]
            else:
                while stack and len(stack) >= level:
                    stack.pop()
                if stack:
                    stack[-1]["children"].append(node)
                else:
                    tree.append(node)
                stack.append(node)
        return tree


# ============================================================
# MOBI 后端（基于 BeautifulSoup 的 HTML 解析）
# ============================================================

class _MobiBackend:
    """MOBI/Kindle 解析 — 优先使用提取的 EPUB 目录，否则回退到 HTML 标签分析"""

    def __init__(self, file_path: str):
        if not _mobi_available:
            raise ImportError("mobi 未安装，请运行: pip install mobi")

        self.file_path = file_path
        self._chapters: list[dict] = []
        self._toc_tree: list[dict] | None = None
        self._temp_dir = None
        self._epub_backend: _EpubBackend | None = None
        self._soup = None

        try:
            self._temp_dir, ext_path = mobi.extract(file_path)
            if not ext_path:
                return

            ext = os.path.splitext(ext_path)[1].lower()

            if ext == ".epub" and _ebooklib_available:
                # ★ KF8 格式 → 提取为 EPUB，用 _EpubBackend 获取完整目录树
                logger.info("MOBI 以 KF8 格式提取为 EPUB，使用 EPUB 目录解析")
                self._epub_backend = _EpubBackend(ext_path)

            elif _bs4_available:
                # ★ 旧格式 → 提取为 HTML，用 BeautifulSoup 分析
                logger.info("MOBI 以 mobi7 格式提取为 HTML，使用标签分析")
                with open(ext_path, "r", encoding="utf-8", errors="replace") as f:
                    html = f.read()
                self._soup = BeautifulSoup(html, "html.parser")

        except Exception as e:
            logger.error(f"MOBI 提取失败: {e}")

    def __del__(self):
        if self._temp_dir and os.path.exists(self._temp_dir):
            import shutil
            shutil.rmtree(self._temp_dir, ignore_errors=True)

    def get_metadata(self) -> dict:
        # 优先使用 EPUB 后端的元数据
        if self._epub_backend:
            return self._epub_backend.get_metadata()
        title = os.path.splitext(os.path.basename(self.file_path))[0]
        if self._soup and self._soup.title:
            t = self._soup.title.get_text(strip=True)
            if t:
                title = t
        return {"title": title, "author": "未知作者", "language": "中文"}

    def extract_chapters(self) -> list[dict]:
        # 优先使用 EPUB 后端
        if self._epub_backend:
            return self._epub_backend.extract_chapters()
        return self._extract_chapters_html()

    def get_toc_tree(self) -> list[dict]:
        # 优先使用 EPUB 后端的 TOC 树（包含真实的书籍目录结构）
        if self._epub_backend:
            return self._epub_backend.get_toc_tree()
        return self._get_toc_tree_html()

    # ==================== HTML 回退方案（旧格式 MOBI） ====================

    def _extract_chapters_html(self) -> list[dict]:
        """回退：从 HTML 正文提取章节（旧格式 mobi7）"""
        if self._chapters:
            return self._chapters
        if not self._soup:
            return []

        chapters = []
        idx = 0
        body = self._soup.body or self._soup

        headings = self._find_heading_tags(body)

        if not headings:
            text = body.get_text(separator="\n", strip=True)
            if self._is_content(text):
                chapters.append(self._make_chapter(
                    os.path.splitext(os.path.basename(self.file_path))[0],
                    text, idx))
            self._chapters = chapters
            return chapters

        # 同步构建目录树
        tree = []
        stack = []
        self._toc_tree = tree

        for i, (tag, level, title) in enumerate(headings):
            content_parts = []
            cursor = tag.find_next_sibling()
            next_tag = headings[i + 1][0] if i + 1 < len(headings) else None

            while cursor and cursor != next_tag:
                if cursor.name and cursor.name.startswith("h"):
                    break
                txt = cursor.get_text(separator="\n", strip=True)
                if txt:
                    content_parts.append(txt)
                cursor = cursor.find_next_sibling()

            content = "\n\n".join(content_parts)
            if not self._is_content(content):
                continue

            chapters.append(self._make_chapter(title, content, idx))

            node = {"title": title, "level": level, "index": idx, "children": []}
            if level == 1:
                tree.append(node)
                stack = [node]
            else:
                # 弹出同级或更低层的节点（同层为兄弟，不是父子）
                while stack and stack[-1]["level"] >= level:
                    stack.pop()
                if stack:
                    stack[-1]["children"].append(node)
                else:
                    tree.append(node)
                stack.append(node)

            idx += 1

        if not chapters:
            text = body.get_text(separator="\n", strip=True)
            if self._is_content(text):
                chapters.append(self._make_chapter(
                    os.path.splitext(os.path.basename(self.file_path))[0],
                    text, 0))
                self._toc_tree = None

        self._chapters = chapters
        logger.info(f"MOBI(HTML) 提取到 {len(chapters)} 个章节")
        return chapters

    def _get_toc_tree_html(self) -> list[dict]:
        """回退：返回 HTML 分析中构建的扁平目录树"""
        chapters = self.extract_chapters()
        if self._toc_tree:
            return self._toc_tree
        return [{"title": ch["title"], "level": 1, "index": i, "children": []}
                for i, ch in enumerate(chapters)]

    # ==================== HTML 标题检测辅助方法 ====================

    @staticmethod
    def _detect_level(title: str) -> int:
        """从标题文字猜测层级：1=卷/部, 2=章, 3=节/小节, 0=非标题"""
        if re.match(r'^(第[一二三四五六七八九十\d]+[部卷篇集]|Part\s+\d+)', title):
            return 1
        if re.match(r'^(第[一二三四五六七八九十\d]+章|Chapter\s+\d+)', title):
            return 2
        if re.match(r'^(第[一二三四五六七八九十\d]+[节条]|Section\s+\d+)', title):
            return 3
        if re.match(r'^\d+\.\d+\.\d+', title):
            return 3
        if re.match(r'^\d+\.\d+', title):
            return 2
        if re.match(r'^\d+[.、．]\s*', title):
            return 3
        if re.match(r'^[\(（]\d+[\)）]', title):   #  (1) / （1）
            return 3
        if re.match(r'^(序言|前言|目录|附录|后记|尾声|楔子|卷首|番外|导读)', title):
            return 1
        return 0

    def _find_heading_tags(self, body) -> list[tuple]:
        """多策略检测所有章节标题标签，返回 [(tag, level, title), ...]"""
        # 策略1: h1-h6 标签（最准确，优先使用）
        h_tags = []
        for tag in body.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            title = tag.get_text(strip=True)
            if title:
                level = min(int(tag.name[1]), 3)
                h_tags.append((tag, level, title))
        if h_tags:
            return h_tags

        # 策略2: <p> 中带 <b>/<strong> 且有章节模式
        p_tags = []
        for tag in body.find_all("p"):
            text = tag.get_text(strip=True)
            if not text:
                continue
            if tag.find(["b", "strong", "em"]):
                level = self._detect_level(text)
                if level > 0:
                    p_tags.append((tag, level, text))
        if p_tags:
            return p_tags

        # 策略3: <p> 直接匹配章节模式
        for tag in body.find_all("p"):
            text = tag.get_text(strip=True)
            if not text:
                continue
            level = self._detect_level(text)
            if level > 0:
                p_tags.append((tag, level, text))
        if p_tags:
            return p_tags

        # 策略4: 任意标签包含章节模式
        chapter_pattern = re.compile(
            r'(第[一二三四五六七八九十\d]+[章节部卷篇集]|Chapter\s+\d+|Part\s+\d+)'
        )
        for tag in body.find_all(["p", "div", "span", "a", "td"]):
            text = tag.get_text(strip=True)
            if not text:
                continue
            if chapter_pattern.match(text):
                level = self._detect_level(text)
                if level > 0:
                    p_tags.append((tag, level, text))
        return p_tags

    @staticmethod
    def _make_chapter(title: str, content: str, idx: int) -> dict:
        cleaned = _MobiBackend._clean_text(content)
        return {
            "title": title,
            "content": cleaned,
            "index": idx,
            "file_name": f"ch{idx}",
            "char_count": len(cleaned),
            "item_id": f"ch{idx}",
        }

    @staticmethod
    def _is_content(text: str) -> bool:
        """检查是否为有效内容（至少 10 个中文字符）"""
        text = text.strip() if text else ""
        return len(text) >= 10

    @staticmethod
    def _clean_text(text: str) -> str:
        text = re.sub(r"\s*\n\s*", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()
        return text


# ============================================================
# 兼容旧接口：EpubParser = BookParser
# ============================================================

EpubParser = BookParser

@staticmethod
def is_valid_epub(file_path: str) -> bool:
    return file_path.lower().endswith(".epub")

EpubParser.is_valid_epub = is_valid_epub
