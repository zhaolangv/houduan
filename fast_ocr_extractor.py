"""
快速OCR题目提取器：先用传统OCR快速识别，再用规则过滤提取题目内容
如果规则过滤失败，再fallback到AI
"""
import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class FastOCRExtractor:
    """快速OCR题目提取器"""
    
    def __init__(self):
        # 界面元素关键词（需要过滤掉）
        self.ui_keywords = [
            # 时间相关
            r'\d{1,2}:\d{2}',  # 11:30
            r'\d{1,2}:\d{2}:\d{2}',  # 11:30:45
            # 网络状态
            r'[45]G', r'WiFi', r'Wi-Fi',
            # 导航栏
            r'首页', r'朋友', r'消息', r'我', r'经验', r'直播', r'精选',
            # 按钮
            r'点击推荐', r'拍同款', r'关注', r'点赞', r'评论', r'分享',
            # 统计信息
            r'全站正确率', r'正确率', r'正确率为', r'月项', r'第\d+页', r'共\d+页',
            # 账号信息
            r'@\w+', r'用户名', r'用户\d+',
            # 其他界面元素
            r'返回', r'关闭', r'设置', r'更多', r'菜单'
        ]
        
        # 选项模式
        self.option_patterns = [
            r'^[A-Z][\.、。:\s\uFF0E]+',  # A. B. C. D.
            r'^[①②③④⑤⑥]',  # ①②③④
            r'^[（(][A-Z][）)]',  # (A) (B)
            r'^[A-Z]\s+',  # A B C D（空格分隔）
        ]
        
        # 题目结束标记（通常选项之前会有这些标记）
        self.question_end_markers = [
            r'[：:]\s*$',  # 以冒号结尾
            r'[？?]\s*$',  # 以问号结尾
            r'[。]\s*$',  # 以句号结尾
        ]
    
    def extract_question_from_text(self, raw_text: str) -> Dict:
        """
        从OCR识别的原始文字中提取题目内容
        
        Args:
            raw_text: OCR识别的原始文字（可能包含界面元素）
            
        Returns:
            dict: {
                'question_text': str,  # 题干
                'options': List[str],  # 选项列表
                'raw_text': str,  # 清理后的原始文字
                'confidence': float,  # 提取置信度（0-1）
                'is_complete': bool,  # 是否完整提取
                'method': str  # 提取方法：'rule' 或 'partial'
            }
        """
        if not raw_text or not raw_text.strip():
            return self._empty_result()
        
        logger.info(f"[FastOCR] 开始从文字中提取题目，原始文字长度: {len(raw_text)}")
        
        # 第一步：清理文字（移除界面元素）
        cleaned_text = self._clean_text(raw_text)
        logger.info(f"[FastOCR] 清理后文字长度: {len(cleaned_text)}")
        
        # 第二步：提取选项
        options, remaining_text = self._extract_options(cleaned_text)
        logger.info(f"[FastOCR] 提取到 {len(options)} 个选项")
        
        # 第三步：提取题干（选项之前的内容）
        question_text = self._extract_question_text(remaining_text, options)
        logger.info(f"[FastOCR] 提取到题干长度: {len(question_text)}")
        
        # 第四步：评估提取质量
        confidence, is_complete = self._evaluate_extraction(question_text, options)
        
        result = {
            'question_text': question_text,
            'options': options,
            'raw_text': cleaned_text,
            'confidence': confidence,
            'is_complete': is_complete,
            'method': 'rule' if is_complete else 'partial'
        }
        
        logger.info(f"[FastOCR] 提取完成: 置信度={confidence:.2f}, 完整={is_complete}")
        return result
    
    def _clean_text(self, text: str) -> str:
        """清理文字，移除界面元素"""
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检查是否是界面元素
            is_ui_element = False
            for pattern in self.ui_keywords:
                if re.search(pattern, line, re.IGNORECASE):
                    is_ui_element = True
                    logger.debug(f"[FastOCR] 过滤界面元素: {line}")
                    break
            
            # 检查是否是短文本且包含特殊字符（可能是界面元素）
            if not is_ui_element and len(line) < 5:
                # 如果很短且包含特殊字符，可能是界面元素
                if re.search(r'[↑↓←→★☆◆◇]', line):
                    is_ui_element = True
            
            if not is_ui_element:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _extract_options(self, text: str) -> Tuple[List[str], str]:
        """
        提取选项，返回(选项列表, 剩余文字)
        
        Args:
            text: 清理后的文字
            
        Returns:
            tuple: (选项列表, 剩余文字)
        """
        lines = text.split('\n')
        options = []
        remaining_lines = []
        found_options = False
        
        # 从后往前查找选项（选项通常在最后）
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if not line:
                continue
            
            # 检查是否符合选项模式
            is_option = False
            for pattern in self.option_patterns:
                if re.match(pattern, line):
                    is_option = True
                    found_options = True
                    # 规范化选项格式
                    normalized_option = self._normalize_option(line)
                    if normalized_option:
                        options.insert(0, normalized_option)  # 保持顺序
                    break
            
            if is_option:
                continue
            elif found_options:
                # 如果已经找到选项，但当前行不是选项，说明选项区域结束
                break
            else:
                # 还没找到选项，继续查找
                remaining_lines.insert(0, line)
        
        # 如果从后往前没找到，尝试从前往后查找
        if not options:
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                for pattern in self.option_patterns:
                    if re.match(pattern, line):
                        normalized_option = self._normalize_option(line)
                        if normalized_option:
                            options.append(normalized_option)
                            break
                    else:
                        remaining_lines.append(line)
        
        # 如果还是没找到选项，尝试在整个文本中搜索
        if not options:
            # 使用正则表达式在整个文本中搜索选项
            option_matches = re.findall(
                r'([A-Z][\.、。:\s\uFF0E]+[^A-Z\n]{5,})',
                text,
                re.MULTILINE
            )
            if option_matches:
                options = [self._normalize_option(match.strip()) for match in option_matches]
                # 从原文中移除选项
                for option in option_matches:
                    text = text.replace(option, '')
                remaining_lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        return options, '\n'.join(remaining_lines)
    
    def _normalize_option(self, option_text: str) -> str:
        """规范化选项格式为 "A. 内容" """
        # 移除多余的空格和标点
        option_text = option_text.strip()
        
        # 匹配选项字母
        match = re.match(r'([A-Z])[\.、。:\s\uFF0E]+(.+)', option_text)
        if match:
            letter = match.group(1)
            content = match.group(2).strip()
            return f"{letter}. {content}"
        
        # 尝试其他格式
        match = re.match(r'[（(]([A-Z])[）)](.+)', option_text)
        if match:
            letter = match.group(1)
            content = match.group(2).strip()
            return f"{letter}. {content}"
        
        # 如果已经是标准格式，直接返回
        if re.match(r'^[A-Z]\.\s+', option_text):
            return option_text
        
        return option_text
    
    def _extract_question_text(self, text: str, options: List[str]) -> str:
        """
        提取题干（选项之前的内容）
        
        Args:
            text: 剩余文字（已移除选项）
            options: 选项列表
            
        Returns:
            str: 题干文字
        """
        if not text:
            return ""
        
        lines = text.split('\n')
        question_lines = []
        
        # 如果找到了选项，题干就是选项之前的所有内容
        if options:
            # 移除选项相关的文字
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 检查这行是否包含选项内容（可能是选项的一部分）
                is_option_content = False
                for option in options:
                    if option in line or line in option:
                        is_option_content = True
                        break
                
                if not is_option_content:
                    question_lines.append(line)
        else:
            # 没找到选项，假设所有内容都是题干
            question_lines = [line.strip() for line in lines if line.strip()]
        
        # 合并题干，移除多余的空行
        question_text = '\n'.join(question_lines).strip()
        
        # 清理题干：移除可能的标题、页码等
        question_text = self._clean_question_text(question_text)
        
        return question_text
    
    def _clean_question_text(self, text: str) -> str:
        """清理题干文字，移除标题、页码等"""
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 跳过明显的标题行（通常很短且包含特定关键词）
            if len(line) < 20 and any(keyword in line for keyword in ['年', '省', '市', '考试', '题', '卷']):
                # 可能是标题，但如果是题目的一部分（如"第1题"），保留
                if not re.search(r'第\d+题', line):
                    continue
            
            # 跳过页码
            if re.match(r'^\d+/\d+$', line) or re.match(r'^第\d+页', line):
                continue
            
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _evaluate_extraction(self, question_text: str, options: List[str]) -> Tuple[float, bool]:
        """
        评估提取质量
        
        Returns:
            tuple: (置信度, 是否完整)
        """
        confidence = 0.0
        is_complete = False
        
        # 检查题干
        has_question = len(question_text.strip()) > 10
        
        # 检查选项
        has_options = len(options) >= 2  # 至少2个选项
        valid_options = all(
            re.match(r'^[A-Z]\.\s+', opt) for opt in options
        ) if options else False
        
        # 计算置信度
        if has_question and has_options and valid_options:
            # 题干和选项都完整
            confidence = 0.9
            is_complete = True
        elif has_question and has_options:
            # 有题干和选项，但格式可能不标准
            confidence = 0.7
            is_complete = True
        elif has_question:
            # 只有题干，没有选项
            confidence = 0.5
            is_complete = False
        elif has_options:
            # 只有选项，没有题干
            confidence = 0.4
            is_complete = False
        else:
            # 都没有
            confidence = 0.1
            is_complete = False
        
        return confidence, is_complete
    
    def _empty_result(self) -> Dict:
        """返回空结果"""
        return {
            'question_text': '',
            'options': [],
            'raw_text': '',
            'confidence': 0.0,
            'is_complete': False,
            'method': 'rule'
        }


# 全局实例
_fast_extractor = None

def get_fast_extractor():
    """获取快速提取器实例（单例）"""
    global _fast_extractor
    if _fast_extractor is None:
        _fast_extractor = FastOCRExtractor()
    return _fast_extractor

