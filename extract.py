#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
客服对话信息提取工具
使用规则匹配（Mock 模式）从对话中提取结构化信息
"""

import json
import os
import sys
from typing import Dict, List


# ==================== 规则匹配函数 ====================

def extract_by_rules(conv: Dict) -> Dict:
    """基于规则匹配提取对话信息"""
    
    conv_id = conv.get("id", "")
    channel = conv.get("channel", "在线")
    agent = conv.get("agent", "unknown")
    turns = conv.get("turns", [])
    turn_count = len(turns)
    
    # 将所有用户消息合并为一个字符串
    user_messages = []
    agent_messages = []
    for turn in turns:
        if turn["role"] == "user":
            user_messages.append(turn["content"])
        else:
            agent_messages.append(turn["content"])
    
    user_text = " ".join(user_messages)
    agent_text = " ".join(agent_messages)
    all_text = user_text + " " + agent_text
    
    # === 1. 判断问题类别 ===
    categories = []
    
    # 退款/退货相关
    if any(kw in all_text for kw in ["退款", "退货", "退钱", "退回"]):
        categories.append("退货退款")
    
    # 质量问题
    if any(kw in all_text for kw in ["坏", "碎", "破", "裂", "损坏", "质量", "不工作", "不能用", "坏的"]):
        categories.append("商品质量问题")
    
    # 物流问题
    if any(kw in all_text for kw in ["快递", "物流", "派送", "签收", "配送", "送货", "收货", "没收到"]):
        categories.append("物流问题")
    
    # 换货
    if any(kw in all_text for kw in ["换货", "换码", "换新", "更换"]):
        categories.append("换货")
    
    # 取消订单
    if any(kw in all_text for kw in ["取消订单", "取消", "不想要了"]):
        categories.append("取消订单")
    
    # 优惠券/价格
    if any(kw in all_text for kw in ["优惠券", "满减", "价格", "折扣", "优惠"]):
        categories.append("优惠券/价格")
    
    # 商品咨询
    if any(kw in all_text for kw in ["咨询", "请问", "了解", "介绍", "成分", "功能", "参数", "型号", "颜色"]):
        categories.append("商品咨询")
    
    # 投诉态度
    if any(kw in all_text for kw in ["投诉", "破服务", "智障", "垃圾", "差评", "态度", "等太久", "没人理", "浪费时间"]):
        categories.append("投诉态度")
    
    # 账号安全
    if any(kw in all_text for kw in ["账号", "登录", "密码", "盗号", "安全", "异地登录"]):
        categories.append("账号安全")
    
    # 库存
    if any(kw in all_text for kw in ["库存", "补货", "有货", "缺货"]):
        categories.append("库存")
    
    # 建议/反馈
    if any(kw in all_text for kw in ["建议", "反馈", "能不能", "功能"]):
        categories.append("建议/反馈")
    
    # 如果没有任何类别匹配，尝试根据关键词补一个最可能的
    if not categories:
        if "退" in all_text:
            categories.append("退货退款")
        elif "问" in user_text:
            categories.append("商品咨询")
        else:
            categories = []
    
    # 去重
    categories = list(dict.fromkeys(categories))
    
    # === 2. 生成问题摘要 ===
    summary = ""
    if not user_messages:
        summary = "无用户消息"
    elif len(user_messages) == 1:
        summary = user_messages[0][:50] + ("..." if len(user_messages[0]) > 50 else "")
    else:
        # 取第一条和最后一条用户消息
        summary = user_messages[0][:30] + "..." + user_messages[-1][:30]
    
    # === 3. 判断是否解决 ===
    resolved_keywords = ["帮您", "已帮您", "已为您", "我帮您", "可以了", "好的谢谢", "完成了", "已处理", "安排", "申请", "发起"]
    unresolved_keywords = ["转人工", "还没收到", "还没到", "放弃", "算了", "不用了"]
    
    is_resolved = False
    if any(kw in agent_text for kw in resolved_keywords):
        is_resolved = True
    if any(kw in user_text for kw in unresolved_keywords):
        is_resolved = False
    # 如果客服说了解决方案且用户没有明确反对，视为解决
    if any(kw in agent_text for kw in ["退款申请", "补发", "换新", "已取消", "已发起"]) and not any(kw in user_text for kw in ["还没", "没收到"]):
        is_resolved = True
    
    # === 4. 判断用户情绪 ===
    negative_words = ["破", "烂", "差", "投诉", "智障", "垃圾", "气", "烦", "浪费", "怎么还没", "多长时间了", "破服务"]
    positive_words = ["谢谢", "感谢", "好的", "可以", "满意", "太好了", "不错"]
    
    negative_score = sum(1 for kw in negative_words if kw in user_text)
    positive_score = sum(1 for kw in positive_words if kw in user_text)
    
    if negative_score > positive_score:
        sentiment = "negative"
    elif positive_score > negative_score:
        sentiment = "positive"
    else:
        sentiment = "neutral"
    
    # === 5. 判断是否多诉求 ===
    # 简单判断：用户消息中包含多个不同关键词
    topic_keywords = ["退货", "快递", "优惠券", "补货", "成分", "换货", "取消"]
    topic_count = sum(1 for kw in topic_keywords if kw in user_text)
    has_multiple_issues = topic_count >= 2
    
    # === 6. 判断是否有特殊处理 ===
    special_handling = None
    if "转人工" in all_text or "转接" in all_text:
        special_handling = "转人工"
    elif "优惠券" in agent_text and "补偿" in agent_text:
        special_handling = "补偿优惠券"
    elif "补发" in agent_text and "优惠券" in agent_text:
        special_handling = "补偿优惠券"
    
    # === 7. 判断是否缺少信息 ===
    missing_info = any(kw in agent_text for kw in ["请问您的订单号", "方便提供", "手机号", "具体型号", "截图"])
    
    # === 8. 提取解决方案 ===
    resolution = None
    if "退款" in agent_text and "申请" in agent_text:
        resolution = "已发起退款申请"
    elif "补发" in agent_text:
        resolution = "补发商品"
    elif "换新" in agent_text:
        resolution = "换新处理"
    elif "取消" in agent_text and "订单" in agent_text:
        resolution = "已取消订单"
    elif "解释" in agent_text or "说明" in agent_text:
        resolution = "已解释说明"
    elif "反馈" in agent_text:
        resolution = "已记录反馈"
    else:
        # 尝试提取客服最后一条消息作为解决方案
        for turn in reversed(turns):
            if turn["role"] == "agent":
                resolution = turn["content"][:80]
                break
    
    return {
        "conversation_id": conv_id,
        "channel": channel,
        "agent": agent,
        "turn_count": turn_count,
        "user_issue_summary": summary,
        "issue_categories": categories,
        "resolution": resolution,
        "is_resolved": is_resolved,
        "user_sentiment": sentiment,
        "has_multiple_issues": has_multiple_issues,
        "special_handling": special_handling,
        "missing_info": missing_info
    }


def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else "conversations.json"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "extracted_results.json"
    
    if not os.path.exists(input_file):
        print(f"❌ 错误：输入文件 '{input_file}' 不存在")
        print(f"💡 使用方法: python extract.py [输入文件] [输出文件]")
        sys.exit(1)
    
    with open(input_file, "r", encoding="utf-8") as f:
        conversations = json.load(f)
    
    print(f"📂 读取到 {len(conversations)} 条对话")
    print("=" * 50)
    
    results = []
    for i, conv in enumerate(conversations):
        conv_id = conv.get("id", f"unknown_{i}")
        print(f"🔄 处理第 {i+1}/{len(conversations)} 条对话: {conv_id}")
        result = extract_by_rules(conv)
        results.append(result)
        print(f"   ✅ 完成 -> 类别: {result['issue_categories']}, 情绪: {result['user_sentiment']}")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("=" * 50)
    print(f"✅ 完成！结果已保存至 {output_file}")
    
    resolved_count = sum(1 for r in results if r.get("is_resolved") is True)
    negative_count = sum(1 for r in results if r.get("user_sentiment") == "negative")
    total = len(results)
    print(f"📊 统计：解决率 {resolved_count}/{total} ({resolved_count/total*100:.1f}%)，负面情绪 {negative_count} 条")


if __name__ == "__main__":
    main()