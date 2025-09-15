#!/usr/bin/env python3
"""
Test script to verify the rule filtering functionality works correctly
"""

import json
import sys
from collections import Counter

def load_rules():
    """Load rules from the medical_rules.json file"""
    try:
        with open('medical_rules.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: medical_rules.json not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        sys.exit(1)

def test_filtering():
    """Test the filtering functionality"""
    rules = load_rules()
    
    print(f"Total rules loaded: {len(rules)}")
    print()
    
    # Count rule types
    rule_types = Counter(rule.get('rule_type', 'unknown') for rule in rules)
    print("Rule types in data:")
    for rule_type, count in rule_types.most_common():
        print(f"  {rule_type}: {count}")
    print()
    
    # Test filtering by each rule type
    print("Testing filtering by rule type:")
    for rule_type in rule_types.keys():
        filtered = [r for r in rules if r.get('rule_type') == rule_type]
        print(f"  {rule_type}: {len(filtered)} rules")
        
        # Show a sample rule
        if filtered:
            sample = filtered[0]
            print(f"    Sample: {sample.get('name', 'No name')}")
    print()
    
    # Test the problematic rule types that were in the frontend
    problematic_types = ['drug_diagnosis', 'drug_dosage_form']
    print("Testing problematic rule types from frontend:")
    for rule_type in problematic_types:
        filtered = [r for r in rules if r.get('rule_type') == rule_type]
        print(f"  {rule_type}: {len(filtered)} rules (should be 0)")
    print()
    
    # Test the new rule types we added to frontend
    new_types = ['drug_gender', 'drug_age', 'visit_type', 'drug_hospital_level', 'drug_insurance_type']
    print("Testing new rule types in frontend:")
    for rule_type in new_types:
        filtered = [r for r in rules if r.get('rule_type') == rule_type]
        print(f"  {rule_type}: {len(filtered)} rules")
        if filtered:
            print(f"    Sample: {filtered[0].get('name', 'No name')}")
    print()

if __name__ == "__main__":
    test_filtering()
