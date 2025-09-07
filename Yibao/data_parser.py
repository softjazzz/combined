#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
import os

def is_number(s):
    """Check if a string is a number."""
    return s.strip().isdigit()

def parse_drug_gender_rules(text_content):
    """
    Parses the text content using a state machine approach to handle
    rules spanning multiple lines.
    """
    lines = text_content.split('\n')
    rules = []
    
    current_rule = {}
    state = "find_index"  # Possible states: find_index, find_name, find_catalog, find_gender

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if is_number(line) and state != "find_index":
             # This is a new index, so the previous rule was malformed.
             # Start fresh with the new index.
             current_rule = {"序号": int(line)}
             state = "find_name"
             continue

        if state == "find_index":
            if is_number(line):
                current_rule = {"序号": int(line)}
                state = "find_name"
        
        elif state == "find_name":
            # Any non-numeric, non-empty line is assumed to be the name.
            # This is a simplification.
            current_rule["药品通用名"] = line
            state = "find_catalog"
            
        elif state == "find_catalog":
            if line == "是":
                current_rule["是否为2024年医保目录内药品"] = "是"
                state = "find_gender"
            # else: ignore the line and keep looking for '是'

        elif state == "find_gender":
            if line in ["男", "女"]:
                current_rule["限定性别"] = line
                rules.append(current_rule)
                # Reset for the next rule
                current_rule = {}
                state = "find_index"
            # else: ignore the line and keep looking for the gender
                
    return rules, [] # Return empty list for unmatched, as the logic is now different

def main():
    """
    Main function to read the source file, parse it, and write to JSON.
    """
    input_file = '/home/ubuntu/Yibao/医保规则_txt/第一批-1.药品区分性别使用.txt'
    output_file = '/home/ubuntu/Yibao/第一批-1.药品区分性别使用.json'
    
    print(f"Reading from {input_file}...")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: Input file not found at {input_file}")
        return

    print("Parsing file content...")
    structured_rules, unmatched = parse_drug_gender_rules(content)
    
    print(f"Found {len(structured_rules)} rules.")
    
    if unmatched:
        print(f"--- Found {len(unmatched)} UNMATCHED lines (showing first 20): ---")
        for i, line in enumerate(unmatched[:20]):
            print(f"  {i+1}: {line}")
        print("-" * 20)

    # Save to JSON file
    print(f"Saving structured data to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(structured_rules, f, ensure_ascii=False, indent=4)
        
    print("Done.")

if __name__ == '__main__':
    main()
