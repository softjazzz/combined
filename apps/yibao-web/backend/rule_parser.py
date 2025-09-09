"""
医保规则解析器
解析Markdown格式的规则文档，转换为结构化的JSON格式
"""

import re
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from rule_schema import MedicalRule, RuleCondition, RuleAction, DrugInfo, RuleType, SeverityLevel, TriggerEvent, OperatorType, RULE_TEMPLATES

class RuleParser:
    """医保规则解析器"""
    
    def __init__(self):
        self.rule_type_mapping = {
            "药品区分性别使用": RuleType.DRUG_GENDER,
            "医疗服务项目区分性别使用": RuleType.SERVICE_GENDER,
            "药品儿童专用": RuleType.DRUG_CHILDREN_ONLY,
            "药品限儿童使用": RuleType.DRUG_CHILDREN_LIMIT,
            "药品限工伤保险": RuleType.DRUG_INSURANCE_TYPE,
            "药品限生育保险": RuleType.DRUG_INSURANCE_TYPE,
            "药品限医疗机构级别": RuleType.DRUG_HOSPITAL_LEVEL,
            "药品限支付疗程": RuleType.DRUG_PAYMENT_COURSE,
            "药品限就医方式": RuleType.DRUG_VISIT_TYPE,
            "手术项目未按规定折价收费": RuleType.SURGERY_PRICING
        }
    
    def parse_markdown_file(self, file_path: str) -> List[MedicalRule]:
        """解析单个Markdown文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取文件标题和规则类型
        title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        if not title_match:
            raise ValueError(f"无法从文件 {file_path} 中提取标题")
        
        title = title_match.group(1).strip()
        rule_type = self._extract_rule_type(title)
        
        # 解析表格数据
        table_data = self._parse_table(content)
        
        # 转换为规则对象
        rules = []
        for idx, row in enumerate(table_data):
            try:
                rule = self._convert_row_to_rule(row, rule_type, title, idx + 1)
                if rule:
                    rules.append(rule)
            except Exception as e:
                print(f"解析第 {idx + 1} 行时出错: {e}")
                continue
        
        return rules
    
    def _extract_rule_type(self, title: str) -> RuleType:
        """从标题中提取规则类型"""
        for key, rule_type in self.rule_type_mapping.items():
            if key in title:
                return rule_type
        
        # 默认返回药品年龄限制
        return RuleType.DRUG_AGE
    
    def _parse_table(self, content: str) -> List[Dict[str, str]]:
        """解析Markdown表格"""
        # 查找表格开始位置
        table_start = content.find('| 序号 | 药品通用名')
        if table_start == -1:
            raise ValueError("未找到规则表格")
        
        # 提取表格内容
        lines = content[table_start:].split('\n')
        
        # 解析表头
        header_line = lines[0].strip()
        headers = [h.strip() for h in header_line.split('|')[1:-1]]  # 去掉首尾空元素
        
        # 解析数据行
        data_rows = []
        for line in lines[2:]:  # 跳过表头和分隔线
            line = line.strip()
            if not line or not line.startswith('|'):
                continue
            
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            if len(cells) >= len(headers):
                row_data = dict(zip(headers, cells))
                data_rows.append(row_data)
        
        return data_rows
    
    def _convert_row_to_rule(self, row: Dict[str, str], rule_type: RuleType, batch_name: str, sequence: int) -> Optional[MedicalRule]:
        """将表格行转换为规则对象"""
        drug_name = row.get('药品通用名', '').strip()
        logic_desc = row.get('检出逻辑', '').strip()
        logic_basis = row.get('逻辑依据（2024版国家药品目录备注）', '').strip()
        
        # 跳过无效行
        if not drug_name or drug_name in ['是', '否'] or not logic_desc:
            return None
        
        # 生成规则编码
        rule_code = f"{rule_type.value.upper()}_{sequence:03d}"
        
        # 根据规则类型生成条件和动作
        conditions, actions = self._generate_conditions_and_actions(rule_type, logic_desc, logic_basis, drug_name)
        
        # 创建药品信息
        drug_info = DrugInfo(
            drug_names=[drug_name],
            drug_codes=[],  # 需要从其他数据源补充
            categories=[]
        )
        
        # 创建规则对象
        rule = MedicalRule(
            code=rule_code,
            name=f"{drug_name} - {self._get_rule_type_name(rule_type)}",
            description=f"检查{drug_name}的{self._get_rule_type_name(rule_type)}限制",
            rule_type=rule_type,
            severity=self._determine_severity(logic_desc),
            conditions=conditions,
            actions=actions,
            triggers=self._get_default_triggers(rule_type),
            drug_info=drug_info,
            applicable_scenarios=["处方开立", "医嘱录入"],
            source="2024版国家药品目录",
            version="1.0",
            enabled=True
        )
        
        return rule
    
    def _generate_conditions_and_actions(self, rule_type: RuleType, logic_desc: str, logic_basis: str, drug_name: str) -> tuple:
        """根据规则类型生成条件和动作"""
        conditions = []
        actions = []
        
        if rule_type == RuleType.DRUG_GENDER:
            # 性别限制规则
            required_gender = self._extract_gender_requirement(logic_basis)
            conditions = [
                RuleCondition(
                    fact="patient.gender",
                    operator=OperatorType.NOT_EQUALS,
                    value=required_gender,
                    description=f"患者性别不符合{drug_name}的使用要求"
                ),
                RuleCondition(
                    fact="drug.name",
                    operator=OperatorType.EQUALS,
                    value=drug_name,
                    description=f"药品为{drug_name}"
                )
            ]
            actions = [
                RuleAction(
                    action_type="intercept",
                    message_template=f"患者性别为{{patient.gender}}，不能使用{drug_name}（该药品限{required_gender}性使用）",
                    parameters={"required_gender": required_gender}
                )
            ]
        
        elif rule_type == RuleType.DRUG_CHILDREN_ONLY:
            # 儿童专用药品
            conditions = [
                RuleCondition(
                    fact="patient.age",
                    operator=OperatorType.GREATER_EQUAL,
                    value=18,
                    description="患者年龄超出儿童范围"
                ),
                RuleCondition(
                    fact="drug.name",
                    operator=OperatorType.EQUALS,
                    value=drug_name,
                    description=f"药品为{drug_name}"
                )
            ]
            actions = [
                RuleAction(
                    action_type="intercept",
                    message_template=f"患者年龄{{patient.age}}岁，不能使用{drug_name}（该药品限儿童使用）",
                    parameters={}
                )
            ]
        
        elif rule_type == RuleType.DRUG_PAYMENT_COURSE:
            # 支付疗程限制
            max_days = self._extract_payment_days(logic_basis)
            conditions = [
                RuleCondition(
                    fact="prescription.duration_days",
                    operator=OperatorType.GREATER_THAN,
                    value=max_days,
                    description=f"处方天数超过{max_days}天限制"
                ),
                RuleCondition(
                    fact="drug.name",
                    operator=OperatorType.EQUALS,
                    value=drug_name,
                    description=f"药品为{drug_name}"
                )
            ]
            actions = [
                RuleAction(
                    action_type="warn",
                    message_template=f"{drug_name}支付天数不能超过{max_days}天，当前处方{{prescription.duration_days}}天",
                    parameters={"max_days": max_days}
                )
            ]
        
        else:
            # 默认规则
            conditions = [
                RuleCondition(
                    fact="drug.name",
                    operator=OperatorType.EQUALS,
                    value=drug_name,
                    description=f"药品为{drug_name}"
                )
            ]
            actions = [
                RuleAction(
                    action_type="warn",
                    message_template=f"使用{drug_name}时请注意相关限制条件",
                    parameters={}
                )
            ]
        
        return conditions, actions
    
    def _extract_gender_requirement(self, logic_basis: str) -> str:
        """从逻辑依据中提取性别要求"""
        if "男" in logic_basis or "前列腺" in logic_basis or "阳痿" in logic_basis:
            return "男"
        elif "女" in logic_basis or "妇" in logic_basis or "月经" in logic_basis or "妊娠" in logic_basis:
            return "女"
        return "未知"
    
    def _extract_payment_days(self, logic_basis: str) -> int:
        """从逻辑依据中提取支付天数限制"""
        # 查找数字+天的模式
        match = re.search(r'(\d+)天', logic_basis)
        if match:
            return int(match.group(1))
        return 14  # 默认14天
    
    def _determine_severity(self, logic_desc: str) -> SeverityLevel:
        """根据逻辑描述确定严重级别"""
        if "拦截" in logic_desc or "禁止" in logic_desc:
            return SeverityLevel.BLOCK
        elif "警告" in logic_desc or "提醒" in logic_desc:
            return SeverityLevel.WARN
        return SeverityLevel.INFO
    
    def _get_rule_type_name(self, rule_type: RuleType) -> str:
        """获取规则类型的中文名称"""
        type_names = {
            RuleType.DRUG_GENDER: "性别限制",
            RuleType.DRUG_AGE: "年龄限制", 
            RuleType.DRUG_CHILDREN_ONLY: "儿童专用",
            RuleType.DRUG_CHILDREN_LIMIT: "儿童限制",
            RuleType.DRUG_INSURANCE_TYPE: "保险类型限制",
            RuleType.DRUG_HOSPITAL_LEVEL: "医疗机构级别限制",
            RuleType.DRUG_PAYMENT_COURSE: "支付疗程限制",
            RuleType.DRUG_VISIT_TYPE: "就医方式限制",
            RuleType.SERVICE_GENDER: "服务性别限制",
            RuleType.SURGERY_PRICING: "手术定价规则"
        }
        return type_names.get(rule_type, "未知规则")
    
    def _get_default_triggers(self, rule_type: RuleType) -> List[TriggerEvent]:
        """获取规则类型的默认触发事件"""
        if rule_type in [RuleType.DRUG_PAYMENT_COURSE]:
            return [TriggerEvent.PRESCRIPTION_CREATE, TriggerEvent.PAYMENT_CALCULATE]
        else:
            return [TriggerEvent.PRESCRIPTION_CREATE, TriggerEvent.PRESCRIPTION_UPDATE]
    
    def parse_directory(self, directory_path: str) -> Dict[str, List[MedicalRule]]:
        """解析整个目录中的所有规则文件"""
        directory = Path(directory_path)
        results = {}
        
        for md_file in directory.glob("*.md"):
            try:
                print(f"正在解析文件: {md_file.name}")
                rules = self.parse_markdown_file(str(md_file))
                results[md_file.name] = rules
                print(f"成功解析 {len(rules)} 条规则")
            except Exception as e:
                print(f"解析文件 {md_file.name} 时出错: {e}")
                results[md_file.name] = []
        
        return results
    
    def export_to_json(self, rules: List[MedicalRule], output_file: str):
        """导出规则到JSON文件"""
        rules_data = [rule.dict() for rule in rules]
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2)
        print(f"已导出 {len(rules)} 条规则到 {output_file}")

# 使用示例
if __name__ == "__main__":
    parser = RuleParser()
    
    # 解析单个文件
    # rules = parser.parse_markdown_file("Yibao/医保规则_precise/第一批-1.药品区分性别使用_precise.md")
    
    # 解析整个目录
    all_rules = parser.parse_directory("../../../Yibao/医保规则_precise")
    
    # 合并所有规则
    combined_rules = []
    for file_name, rules in all_rules.items():
        combined_rules.extend(rules)
    
    # 导出到JSON
    parser.export_to_json(combined_rules, "medical_rules.json")
    
    print(f"总共解析了 {len(combined_rules)} 条规则")
