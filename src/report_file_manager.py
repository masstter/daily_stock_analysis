# -*- coding: utf-8 -*-
"""
===================================
报告文件管理模块
===================================

职责：
1. 从 reports 目录获取动态日期后缀的文件
2. 向企业微信发送报告文件
3. 支持多种文件类型（md、xlsx 等）
"""
import re
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List

logger = logging.getLogger(__name__)


class ReportFileManager:
    """报告文件管理器"""

    # 支持的报告文件前缀
    REPORT_PREFIXES = [
        'report',           # report_20260303.md - 个股分析报告
        'market_review',    # market_review_20260303.md - 大盘复盘
    ]

    def __init__(self, report_dir: str = "./reports"):
        """
        初始化报告文件管理器

        Args:
            report_dir: 报告目录路径
        """
        self.report_dir = Path(report_dir)
        if not self.report_dir.exists():
            self.report_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def get_today_date_suffix() -> str:
        """获取当前日期后缀（yyyymmdd格式）"""
        return datetime.now().strftime("%Y%m%d")

    def find_report_files(self, date_suffix: Optional[str] = None) -> List[Path]:
        """
        查找今日的报告文件

        Args:
            date_suffix: 日期后缀（默认为今日）

        Returns:
            找到的报告文件列表
        """
        if date_suffix is None:
            date_suffix = self.get_today_date_suffix()

        found_files = []

        # 遍历所有支持的前缀
        for prefix in self.REPORT_PREFIXES:
            # 构造文件名模式：prefix_yyyymmdd.*
            pattern = f"{prefix}_{date_suffix}.*"
            matches = list(self.report_dir.glob(pattern))
            found_files.extend(matches)

        if found_files:
            logger.info(f"找到 {len(found_files)} 个报告文件: {[f.name for f in found_files]}")
        else:
            logger.warning(f"未找到日期为 {date_suffix} 的报告文件")

        return sorted(found_files)

    def find_report_file_by_prefix(self, prefix: str, date_suffix: Optional[str] = None) -> Optional[Path]:
        """
        根据前缀查找特定的报告文件

        Args:
            prefix: 文件前缀（如 'report'、'market_review'）
            date_suffix: 日期后缀（默认为今日）

        Returns:
            找到的文件路径，未找到返回 None
        """
        if date_suffix is None:
            date_suffix = self.get_today_date_suffix()

        # 构造文件名模式
        pattern = f"{prefix}_{date_suffix}.*"
        matches = list(self.report_dir.glob(pattern))

        if matches:
            # 优先使用 .md 文件
            md_files = [f for f in matches if f.suffix == '.md']
            if md_files:
                return md_files[0]
            # 否则返回第一个匹配的文件
            return matches[0]

        return None

    def get_report_content(self, prefix: str, date_suffix: Optional[str] = None) -> Optional[str]:
        """
        读取报告文件内容

        Args:
            prefix: 文件前缀
            date_suffix: 日期后缀

        Returns:
            文件内容，文件不存在返回 None
        """
        file_path = self.find_report_file_by_prefix(prefix, date_suffix)

        if not file_path or not file_path.exists():
            logger.warning(f"报告文件不存在: {prefix}_{date_suffix}")
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"成功读取报告文件: {file_path.name}")
            return content
        except Exception as e:
            logger.error(f"读取报告文件失败: {file_path.name}, 错误: {e}")
            return None

    def list_all_reports(self) -> List[Path]:
        """
        列出报告目录中的所有文件

        Returns:
            文件列表（按修改时间倒序）
        """
        if not self.report_dir.exists():
            return []

        files = list(self.report_dir.glob('*'))
        # 按修改时间倒序排列
        return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)

    def _extract_report_date(self, file_name: str, prefix: str) -> Optional[datetime]:
        """从报告文件名中提取日期（如 report_20260316.md -> 2026-03-16）。"""
        pattern = rf"^{re.escape(prefix)}_(\d{{8}})\..+$"
        match = re.match(pattern, file_name)
        if not match:
            return None
        try:
            return datetime.strptime(match.group(1), "%Y%m%d")
        except ValueError:
            return None

    def cleanup_history_files(self, retain_days: int = 7) -> int:
        """
        清理 reports 目录中的历史报告文件。

        保留最近 retain_days 天（含今天）的 report_* 与 market_review_* 文件。

        Args:
            retain_days: 保留天数，默认 7

        Returns:
            删除的文件数量
        """
        if retain_days <= 0:
            logger.warning("REPORT_RETENTION_DAYS=%s 非法，自动回退为 7", retain_days)
            retain_days = 7

        cutoff_date = (datetime.now() - timedelta(days=retain_days - 1)).date()
        deleted_count = 0

        for prefix in self.REPORT_PREFIXES:
            for file_path in self.report_dir.glob(f"{prefix}_*.*"):
                if not file_path.is_file():
                    continue
                file_dt = self._extract_report_date(file_path.name, prefix)
                if file_dt is None:
                    continue
                if file_dt.date() < cutoff_date:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                        logger.info("已清理历史报告文件: %s", file_path.name)
                    except Exception as e:
                        logger.warning("清理历史报告文件失败 %s: %s", file_path.name, e)

        logger.info(
            "报告历史清理完成：保留近 %s 天，删除 %s 个文件",
            retain_days,
            deleted_count,
        )
        return deleted_count
