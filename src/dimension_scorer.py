# -*- coding: utf-8 -*-
"""
===================================
多维度评分计算器
===================================

职责：
1. 基于分析结果计算各维度的评分（0-100分）
2. 支持自定义权重的加权平均计算
3. 提供评分解释和建议
"""

import logging
import re
from typing import Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ScoringWeights:
    """评分权重配置"""
    # 技术面权重分布
    technical_weight: float = 0.35  # 技术面总权重
    ma_ratio: float = 0.4  # 均线在技术面中的占比
    volume_ratio: float = 0.35  # 量能在技术面中的占比
    pattern_ratio: float = 0.25  # 形态在技术面中的占比

    # 基本面权重分布
    fundamental_weight: float = 0.25  # 基本面总权重
    valuation_ratio: float = 0.4  # 估值在基本面中的占比
    growth_ratio: float = 0.6  # 成长性在基本面中的占比

    # 消息面权重分布
    sentiment_weight: float = 0.40  # 消息面总权重
    news_ratio: float = 0.5  # 新闻在消息面中的占比
    catalyst_ratio: float = 0.5  # 催化剂在消息面中的占比


class DimensionScorer:
    """多维度评分计算器"""

    def __init__(self, weights: Optional[ScoringWeights] = None):
        """初始化评分计算器"""
        self.weights = weights or ScoringWeights()

    def _extract_flat_data(self, analysis_data: Any) -> Dict[str, Any]:
        """
        从分析数据中提取扁平化字段，支持多种输入格式：
        1. 原始 LLM JSON dict（包含顶层字段及可能的嵌套 dashboard）
        2. AnalysisResult 对象（直接读取属性）
        3. 已扁平化的 dict

        Returns:
            扁平化后包含所有评分所需字段的 dict
        """
        flat: Dict[str, Any] = {}

        # 支持 AnalysisResult 对象（避免循环导入，用 duck typing）
        if hasattr(analysis_data, '__dataclass_fields__'):
            for field in (
                'ma_analysis', 'volume_analysis', 'pattern_analysis',
                'technical_analysis', 'fundamental_analysis',
                'sector_position', 'company_highlights',
                'news_summary', 'market_sentiment', 'hot_topics',
                'trend_prediction', 'operation_advice', 'analysis_summary',
            ):
                flat[field] = getattr(analysis_data, field, '') or ''
            # 尝试从 dashboard 补充缺失字段
            dashboard = getattr(analysis_data, 'dashboard', None) or {}
            flat = self._merge_dashboard_fields(flat, dashboard)
            return flat

        # dict 输入
        if not isinstance(analysis_data, dict):
            return flat

        # 复制顶层字段
        flat.update({k: v for k, v in analysis_data.items() if isinstance(v, str)})

        # 尝试从嵌套的 dashboard 补充缺失或空字段
        dashboard = analysis_data.get('dashboard') or {}
        flat = self._merge_dashboard_fields(flat, dashboard)

        return flat

    def _merge_dashboard_fields(self, flat: Dict[str, Any], dashboard: Dict[str, Any]) -> Dict[str, Any]:
        """
        从 dashboard 嵌套结构中提取并补充/合并评分所需字段。
        只有当 flat 中对应字段缺失或为空时才补充。
        """
        if not dashboard:
            return flat

        def _get_or_empty(d: Dict, *keys: str) -> str:
            for k in keys:
                v = d.get(k, '')
                if v:
                    return str(v)
            return ''

        # data_perspective → 技术分析字段
        data_persp = dashboard.get('data_perspective', {}) or {}
        if data_persp:
            trend_data = data_persp.get('trend_status', {}) or {}
            vol_data = data_persp.get('volume_analysis', {}) or {}
            price_data = data_persp.get('price_position', {}) or {}

            if not flat.get('ma_analysis'):
                ma_parts = []
                if trend_data.get('ma_alignment'):
                    ma_parts.append(str(trend_data['ma_alignment']))
                if trend_data.get('is_bullish'):
                    ma_parts.append('多头排列')
                if trend_data.get('trend_score'):
                    ma_parts.append(f"趋势强度{trend_data['trend_score']}")
                flat['ma_analysis'] = ' '.join(ma_parts)

            if not flat.get('volume_analysis'):
                vol_parts = []
                if vol_data.get('description'):
                    vol_parts.append(str(vol_data['description']))
                if vol_data.get('trend'):
                    vol_parts.append(str(vol_data['trend']))
                flat['volume_analysis'] = ' '.join(vol_parts)

            if not flat.get('pattern_analysis'):
                pat_parts = []
                if price_data.get('bias_status'):
                    pat_parts.append(str(price_data['bias_status']))
                flat['pattern_analysis'] = ' '.join(pat_parts)

        # intelligence → 消息面字段
        intel = dashboard.get('intelligence', {}) or {}
        if intel:
            if not flat.get('news_summary'):
                news_parts = []
                if intel.get('latest_news'):
                    news_parts.append(str(intel['latest_news']))
                if intel.get('sentiment_summary'):
                    news_parts.append(str(intel['sentiment_summary']))
                risk_alerts = intel.get('risk_alerts', []) or []
                if risk_alerts:
                    news_parts.append(' '.join(str(r) for r in risk_alerts[:3]))
                flat['news_summary'] = ' '.join(news_parts)

            if not flat.get('hot_topics'):
                catalysts = intel.get('positive_catalysts', []) or []
                if catalysts:
                    flat['hot_topics'] = ' '.join(str(c) for c in catalysts[:3])

            if not flat.get('market_sentiment'):
                flat['market_sentiment'] = str(intel.get('earnings_outlook', ''))

        # core_conclusion → 趋势/操作建议
        core = dashboard.get('core_conclusion', {}) or {}
        if core:
            if not flat.get('trend_prediction'):
                flat['trend_prediction'] = str(core.get('signal', ''))
            if not flat.get('analysis_summary'):
                flat['analysis_summary'] = str(core.get('one_sentence', ''))

        # 基本面 (fundamental_analysis 合并)
        if not flat.get('fundamental_analysis'):
            fa_parts = []
            if flat.get('sector_position'):
                fa_parts.append(flat['sector_position'])
            if flat.get('company_highlights'):
                fa_parts.append(flat['company_highlights'])
            flat['fundamental_analysis'] = ' '.join(fa_parts)

        return flat

    def calculate_scores(self, analysis_data: Union[Dict[str, Any], Any]) -> Dict[str, int]:
        """
        计算多维度评分

        Args:
            analysis_data: 分析结果数据（支持原始 LLM JSON dict 或 AnalysisResult 对象）

        Returns:
            包含各维度评分的字典
        """
        # 提取扁平化数据，兼容各种输入格式
        data = self._extract_flat_data(analysis_data)

        scores = {
            # 技术面评分
            'technical_score': self._calculate_technical_score(data),
            'ma_score': self._calculate_ma_score(data),
            'volume_score': self._calculate_volume_score(data),
            'pattern_score': self._calculate_pattern_score(data),

            # 基本面评分
            'fundamental_score': self._calculate_fundamental_score(data),
            'valuation_score': self._calculate_valuation_score(data),
            'growth_score': self._calculate_growth_score(data),

            # 消息面评分
            'sentiment_score': self._calculate_sentiment_score(data),
            'news_score': self._calculate_news_score(data),
            'catalyst_score': self._calculate_catalyst_score(data),
        }

        # 计算技术面综合评分（加权平均）
        scores['technical_score'] = int(
            scores['ma_score'] * self.weights.ma_ratio +
            scores['volume_score'] * self.weights.volume_ratio +
            scores['pattern_score'] * self.weights.pattern_ratio
        )

        # 计算基本面综合评分（加权平均）
        scores['fundamental_score'] = int(
            scores['valuation_score'] * self.weights.valuation_ratio +
            scores['growth_score'] * self.weights.growth_ratio
        )

        # 计算消息面综合评分（加权平均）
        scores['sentiment_score'] = int(
            scores['news_score'] * self.weights.news_ratio +
            scores['catalyst_score'] * self.weights.catalyst_ratio
        )

        # 计算综合评分（加权平均）
        scores['overall_score'] = int(
            scores['technical_score'] * self.weights.technical_weight +
            scores['fundamental_score'] * self.weights.fundamental_weight +
            scores['sentiment_score'] * self.weights.sentiment_weight
        )

        return scores

    def _calculate_ma_score(self, data: Dict[str, Any]) -> int:
        """计算均线评分（0-100）"""
        ma_analysis = data.get('ma_analysis', '') or ''
        score = 50  # 基础分

        # 关键词评分
        positive_keywords = {
            '多头排列': 25,
            '强势多头': 25,
            '金叉': 15,
            '上升': 10,
            '突破': 15,
            '支撑': 10,
            '均线粘合': 10,
        }

        negative_keywords = {
            '空头排列': -25,
            '死叉': -15,
            '下跌': -10,
            '跌破': -15,
            '压力': -10,
            '走弱': -10,
        }

        for keyword, points in positive_keywords.items():
            if keyword in ma_analysis:
                score += points

        for keyword, points in negative_keywords.items():
            if keyword in ma_analysis:
                score += points

        return max(0, min(100, score))

    def _calculate_volume_score(self, data: Dict[str, Any]) -> int:
        """计算量能评分（0-100）"""
        volume_analysis = data.get('volume_analysis', '') or ''
        score = 50  # 基础分

        positive_keywords = {
            '缩量': 15,
            '放量上涨': 20,
            '成交额': 10,
            '活跃': 10,
            '主力': 10,
        }

        negative_keywords = {
            '放量下跌': -20,
            '萎缩': -15,
            '无量': -10,
            '清仓': -15,
        }

        for keyword, points in positive_keywords.items():
            if keyword in volume_analysis:
                score += points

        for keyword, points in negative_keywords.items():
            if keyword in volume_analysis:
                score += points

        return max(0, min(100, score))

    def _calculate_pattern_score(self, data: Dict[str, Any]) -> int:
        """计算形态评分（0-100）"""
        pattern_analysis = data.get('pattern_analysis', '') or ''
        score = 50  # 基础分

        positive_keywords = {
            '突破': 15,
            '底部': 15,
            '黄金': 10,
            '上升': 10,
            '看多': 10,
        }

        negative_keywords = {
            '顶部': -15,
            '跌破': -15,
            '看空': -10,
            '下降': -10,
        }

        for keyword, points in positive_keywords.items():
            if keyword in pattern_analysis:
                score += points

        for keyword, points in negative_keywords.items():
            if keyword in pattern_analysis:
                score += points

        return max(0, min(100, score))

    def _calculate_technical_score(self, data: Dict[str, Any]) -> int:
        """计算技术面综合评分（占位，实际由加权计算覆盖）"""
        technical_analysis = data.get('technical_analysis', '') or ''
        trend_prediction = data.get('trend_prediction', '') or ''
        operation_advice = data.get('operation_advice', '') or ''

        score = 50  # 基础分

        text = f"{technical_analysis} {trend_prediction} {operation_advice}"

        positive_patterns = [
            r'(强|很).*?(上升|突破|多头)',
            r'(看多|看好)',
            r'(短期|近期).*(机会|机遇)',
        ]

        negative_patterns = [
            r'(弱|风险)',
            r'(看空)',
            r'(下跌|破|风险)',
        ]

        for pattern in positive_patterns:
            if re.search(pattern, text):
                score += 10

        for pattern in negative_patterns:
            if re.search(pattern, text):
                score -= 10

        return max(0, min(100, score))

    def _calculate_valuation_score(self, data: Dict[str, Any]) -> int:
        """计算估值评分（0-100）"""
        fundamental_analysis = data.get('fundamental_analysis', '') or ''
        score = 50  # 基础分

        positive_keywords = {
            '低估': 20,
            '便宜': 15,
            '合理': 10,
            'PE': 5,
        }

        negative_keywords = {
            '高估': -20,
            '昂贵': -15,
            '泡沫': -20,
        }

        for keyword, points in positive_keywords.items():
            if keyword in fundamental_analysis:
                score += points

        for keyword, points in negative_keywords.items():
            if keyword in fundamental_analysis:
                score += points

        return max(0, min(100, score))

    def _calculate_growth_score(self, data: Dict[str, Any]) -> int:
        """计算成长性评分（0-100）"""
        fundamental_analysis = data.get('fundamental_analysis', '') or ''
        company_highlights = data.get('company_highlights', '') or ''
        sector_position = data.get('sector_position', '') or ''

        text = f"{fundamental_analysis} {company_highlights} {sector_position}"
        score = 50  # 基础分

        positive_keywords = {
            '成长': 15,
            '增长': 15,
            '龙头': 15,
            '创新': 10,
            '领先': 10,
            '优势': 10,
        }

        negative_keywords = {
            '衰退': -15,
            '下降': -10,
            '竞争': -5,
            '风险': -10,
        }

        for keyword, points in positive_keywords.items():
            if keyword in text:
                score += points

        for keyword, points in negative_keywords.items():
            if keyword in text:
                score += points

        return max(0, min(100, score))

    def _calculate_fundamental_score(self, data: Dict[str, Any]) -> int:
        """计算基本面综合评分（占位，实际由加权计算覆盖）"""
        return 50

    def _calculate_news_score(self, data: Dict[str, Any]) -> int:
        """计算新闻面评分（0-100）"""
        news_summary = data.get('news_summary', '') or ''
        market_sentiment = data.get('market_sentiment', '') or ''

        text = f"{news_summary} {market_sentiment}"
        score = 50  # 基础分

        positive_keywords = {
            '利好': 20,
            '上升': 10,
            '强势': 10,
            '看多': 15,
            '机遇': 10,
            '机会': 10,
        }

        negative_keywords = {
            '利空': -20,
            '下跌': -10,
            '看空': -15,
            '风险': -10,
            '暴雷': -20,
        }

        for keyword, points in positive_keywords.items():
            if keyword in text:
                score += points

        for keyword, points in negative_keywords.items():
            if keyword in text:
                score += points

        return max(0, min(100, score))

    def _calculate_catalyst_score(self, data: Dict[str, Any]) -> int:
        """计算催化剂评分（0-100）"""
        news_summary = data.get('news_summary', '') or ''
        hot_topics = data.get('hot_topics', '') or ''

        text = f"{news_summary} {hot_topics}"
        score = 50  # 基础分

        # 催化剂关键词
        catalyst_keywords = {
            '收购': 20,
            '重组': 20,
            '业绩': 15,
            '新产品': 15,
            '融资': 10,
            '合作': 10,
            '订单': 15,
            '突破': 10,
        }

        risk_keywords = {
            '暴雷': -30,
            '风险': -15,
            '制裁': -20,
        }

        for keyword, points in catalyst_keywords.items():
            if keyword in text:
                score += points

        for keyword, points in risk_keywords.items():
            if keyword in text:
                score += points

        return max(0, min(100, score))

    def _calculate_sentiment_score(self, data: Dict[str, Any]) -> int:
        """计算情绪面综合评分（占位，实际由加权计算覆盖）"""
        return 50

    def get_score_insight(self, scores: Dict[str, int]) -> str:
        """
        生成评分解释

        Args:
            scores: 评分字典

        Returns:
            评分解释文本
        """
        insights = []

        # 技术面解释
        tech_score = scores.get('technical_score', 0)
        if tech_score >= 70:
            insights.append(f"📈 技术面强势（评分{tech_score}），趋势向好")
        elif tech_score >= 50:
            insights.append(f"📊 技术面中等（评分{tech_score}），需观察")
        else:
            insights.append(f"📉 技术面较弱（评分{tech_score}），需谨慎")

        # 基本面解释
        fund_score = scores.get('fundamental_score', 0)
        if fund_score >= 70:
            insights.append(f"🏢 基本面良好（评分{fund_score}），基础扎实")
        elif fund_score >= 50:
            insights.append(f"🏢 基本面一般（评分{fund_score}），值得关注")
        else:
            insights.append(f"🏢 基本面较弱（评分{fund_score}），需要改善")

        # 消息面解释
        sentiment_score = scores.get('sentiment_score', 0)
        if sentiment_score >= 70:
            insights.append(f"📰 消息面积极（评分{sentiment_score}），看好前景")
        elif sentiment_score >= 50:
            insights.append(f"📰 消息面中立（评分{sentiment_score}），需观察")
        else:
            insights.append(f"📰 消息面消极（评分{sentiment_score}），需警惕")

        return "；".join(insights)

