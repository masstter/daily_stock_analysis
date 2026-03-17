# -*- coding: utf-8 -*-
"""
===================================
Markdown 转图片工具模块
===================================

将 Markdown 转为 PNG 图片（用于不支持 Markdown 的通知渠道）。
支持 wkhtmltoimage (imgkit) 与 markdown-to-file (m2f)，后者对 emoji 支持更好 (Issue #455)。

Security note: imgkit passes HTML to wkhtmltoimage via stdin, not argv, so
command injection from content is not applicable. Output is rasterized to PNG
(no script execution). Input is from system-generated reports, not raw user
input. Risk is considered low for the current use case.
"""

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Optional

from src.formatters import markdown_to_html_document

logger = logging.getLogger(__name__)

# Cache runtime status to avoid repeatedly trying a broken m2f/puppeteer stack.
_M2F_RUNTIME_BROKEN = False

# Substrings that indicate Puppeteer/Chromium runtime is broken and retries are pointless.
_M2F_BROKEN_INDICATORS = (
    "Failed to launch the browser process",
    "error while loading shared libraries",
    "cannot open shared object file",
    "libX11",
    "libglib",
    "ENOENT",
    ".local-chromium",
)

def _markdown_to_image_m2f(markdown_text: str) -> Optional[bytes]:
    """Convert Markdown to PNG via markdown-to-file (m2f) CLI. Better emoji support (Issue #455)."""
    m2f_exec = shutil.which("m2f")
    if m2f_exec is None:
        logger.warning(
            "m2f (markdown-to-file) not found in PATH. "
            "Install with: npm i -g markdown-to-file. Fallback to text."
        )
        return None

    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        md_filename = "report.md"
        md_path = os.path.join(temp_dir, md_filename)
        expected_png = os.path.join(temp_dir, "report.png")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_text)

        # Windows: npm installs m2f as m2f.cmd; subprocess needs shell=True to run .cmd scripts.
        use_shell = sys.platform == "win32"
        candidates = [
            ([m2f_exec, md_path, "png", f"outputDirectory={temp_dir}"], None),
            ([m2f_exec, md_path, "png"], None),
            ([m2f_exec, md_filename, "png"], temp_dir),
            ([m2f_exec, md_path, "png", f"--outputDirectory={temp_dir}"], None),
        ]

        # m2f versions differ in CLI contract. Try compatible forms in order.

        def _find_generated_png(root_dir: str) -> Optional[str]:
            """Find the newest png under root_dir (recursive)."""
            found = []
            for root, _, files in os.walk(root_dir):
                for name in files:
                    if name.lower().endswith(".png"):
                        found.append(os.path.join(root, name))
            if not found:
                return None
            found.sort(key=os.path.getmtime, reverse=True)
            return found[0]

        last_stdout = ""
        last_stderr = ""
        last_returncode = None

        # Linux runtime hints: prefer system chromium when available.
        run_env = os.environ.copy()
        if sys.platform.startswith("linux"):
            chromium = (
                shutil.which("chromium")
                or shutil.which("chromium-browser")
                or shutil.which("google-chrome")
                or shutil.which("google-chrome-stable")
            )
            if chromium:
                run_env.setdefault("PUPPETEER_EXECUTABLE_PATH", chromium)
                run_env.setdefault("CHROME_BIN", chromium)

        for cmd, cwd in candidates:
            logger.info("正在执行命令: %s", " ".join(str(part) for part in cmd))
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=False,
                timeout=120,
                shell=use_shell,
                cwd=cwd,
                env=run_env,
            )
            last_returncode = result.returncode
            last_stdout = (result.stdout or b"").decode("utf-8", errors="replace")[:600]
            last_stderr = (result.stderr or b"").decode("utf-8", errors="replace")[:600]

            if result.returncode != 0:
                combined = last_stdout + last_stderr
                if any(ind in combined for ind in _M2F_BROKEN_INDICATORS):
                    break
                continue

            # Some m2f builds finish process before png is fully written.
            # Poll briefly to avoid false negative on returncode=0.
            png_path = None
            deadline = time.time() + 5.0
            while time.time() < deadline:
                if os.path.isfile(expected_png):
                    png_path = expected_png
                    break
                png_path = _find_generated_png(temp_dir)
                if png_path:
                    break
                time.sleep(0.2)

            if png_path and os.path.isfile(png_path):
                with open(png_path, "rb") as f:
                    return f.read()

        combined = last_stdout + last_stderr
        is_broken = any(ind in combined for ind in _M2F_BROKEN_INDICATORS)

        logger.warning(
            "m2f did not produce png. returncode=%s, stdout=%s, stderr=%s",
            last_returncode,
            last_stdout,
            last_stderr,
        )
        if is_broken:
            global _M2F_RUNTIME_BROKEN
            _M2F_RUNTIME_BROKEN = True
            logger.warning(
                "m2f/puppeteer 运行时不可用（捆绑 Chromium 缺失或系统库不足），"
                "已标记为不可用，本进程内后续将直接回退 wkhtmltoimage。"
            )
        return None
    except subprocess.TimeoutExpired:
        logger.warning("m2f conversion timed out (60s)")
        return None
    except Exception as e:
        logger.warning("markdown_to_image (m2f) failed: %s", e)
        return None
    finally:
        if temp_dir and os.path.isdir(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except OSError as e:
                logger.debug("Failed to remove temp dir %s: %s", temp_dir, e)


_LINUX_FONT_WARNING_SHOWN = False


def _check_linux_fonts() -> None:
    """在 Linux 下检查 CJK / Emoji 字体是否安装，缺失时打一次警告并给出安装建议。"""
    global _LINUX_FONT_WARNING_SHOWN
    if _LINUX_FONT_WARNING_SHOWN or not sys.platform.startswith("linux"):
        return
    _LINUX_FONT_WARNING_SHOWN = True

    fc_list = shutil.which("fc-list")
    if not fc_list:
        return  # fontconfig 未安装，无法检测

    try:
        result = subprocess.run(
            [fc_list],
            capture_output=True,
            timeout=5,
            check=False,
        )
        fonts_output = (result.stdout or b"").decode("utf-8", errors="replace").lower()
    except Exception:
        return

    missing = []
    if not any(k in fonts_output for k in ("wenquanyi", "noto sans cjk", "source han", "wqy")):
        missing.append("CJK（中文）字体")
    if not any(k in fonts_output for k in ("noto color emoji", "noto emoji", "symbola")):
        missing.append("Emoji 字体")

    if missing:
        logger.warning(
            "wkhtmltoimage 渲染图片时检测到以下字体缺失：%s\n"
            "中文和 emoji 可能显示为方块或乱码。\n"
            "CentOS 7 安装方法（需 EPEL）：\n"
            "  yum install -y epel-release\n"
            "  yum install -y wqy-zenhei-fonts wqy-microhei-fonts \\\n"
            "    google-noto-emoji-fonts google-noto-sans-cjk-fonts\n"
            "Debian/Ubuntu 安装方法：\n"
            "  apt-get install -y fonts-wqy-zenhei fonts-wqy-microhei \\\n"
            "    fonts-noto-color-emoji fonts-noto-cjk",
            "、".join(missing),
        )


def _markdown_to_image_wkhtml(markdown_text: str) -> Optional[bytes]:
    """Convert Markdown to PNG via imgkit/wkhtmltoimage."""
    _check_linux_fonts()
    try:
        import imgkit
    except ImportError:
        logger.debug("imgkit not installed, markdown_to_image unavailable")
        return None

    html = markdown_to_html_document(markdown_text)
    try:
        options = {
            "format": "png",
            "encoding": "UTF-8",
            "quiet": "",
        }
        out = imgkit.from_string(html, False, options=options)
        if out and isinstance(out, bytes) and len(out) > 0:
            return out
        logger.warning("imgkit.from_string returned empty or invalid result")
        return None
    except OSError as e:
        if "wkhtmltoimage" in str(e).lower() or "wkhtmltopdf" in str(e).lower():
            logger.debug("wkhtmltopdf/wkhtmltoimage not found: %s", e)
        else:
            logger.warning("imgkit/wkhtmltoimage error: %s", e)
        return None
    except Exception as e:
        logger.warning("markdown_to_image conversion failed: %s", e)
        return None


def markdown_to_image(markdown_text: str, max_chars: int = 15000) -> Optional[bytes]:
    """
    Convert Markdown to PNG image bytes.

    Engine is read from config.md2img_engine: wkhtmltoimage (default) or
    markdown-to-file (better emoji support, Issue #455).

    When conversion fails or dependencies unavailable, returns None so caller
    can fall back to text sending.

    Args:
        markdown_text: Raw Markdown content.
        max_chars: Skip conversion and return None if content exceeds this length
            (avoids huge images). Default 15000.

    Returns:
        PNG bytes, or None if conversion fails or dependencies unavailable.
    """
    if len(markdown_text) > max_chars:
        logger.warning(
            "Markdown content (%d chars) exceeds max_chars (%d), skipping image conversion",
            len(markdown_text),
            max_chars,
        )
        return None

    try:
        from src.config import get_config

        engine = getattr(get_config(), "md2img_engine", "wkhtmltoimage")
    except Exception:
        engine = "wkhtmltoimage"

    if engine == "markdown-to-file":
        global _M2F_RUNTIME_BROKEN
        if _M2F_RUNTIME_BROKEN:
            logger.debug("m2f 已被标记不可用，直接回退到 wkhtmltoimage")
            return _markdown_to_image_wkhtml(markdown_text)

        png = _markdown_to_image_m2f(markdown_text)
        if png:
            return png
        # Runtime fallback: m2f may fail on Linux when Chromium cannot start.
        logger.info("m2f 转图失败，自动回退到 wkhtmltoimage")
        return _markdown_to_image_wkhtml(markdown_text)
    return _markdown_to_image_wkhtml(markdown_text)
