#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
from openai import OpenAI

# --- Configuration ---
# Make sure you have set the OPENAI_API_KEY environment variable
# You can also uncomment and set it here directly for testing
# os.environ["OPENAI_API_KEY"] = "sk-your-key-here"

API_CLIENT = None
INPUT_FILE = '/home/ubuntu/Yibao/医保规则_txt/第一批-1.药品区分性别使用.txt'
OUTPUT_FILE = '/home/ubuntu/Yibao/第一批-1.药品区分性别使用_llm_parsed.json'
CHUNK_SIZE = 4000  # Number of characters per chunk to send to the LLM

# --- LLM Prompt ---
SYSTEM_PROMPT = """
You are a highly intelligent data extraction assistant. Your task is to analyze a given text from a Chinese medical insurance rulebook and convert it into a structured JSON format.

The text contains rules about drugs that are restricted by gender. Each rule has four components that may be spread across multiple lines:
1.  `序号`: An index number.
2.  `药品通用名`: The name of the drug.
3.  `是否为2024年医保目录内药品`: A flag, which is always '是'.
4.  `限定性别`: The gender restriction, which is either '男' or '女'.

Please process the entire text provided and extract every rule you can find. Return the data as a single JSON array. Each object in the array should represent one rule and have the following keys: "序号", "药品通用名", "是否为2024年医保目录内药品", "限定性别".

Example Input Text:
'''
1
阿帕他胺片
是
男
2
艾附暖宫丸
是
女
'''

Example JSON Output:
'''json
[
  {
    "序号": 1,
    "药品通用名": "阿帕他胺片",
    "是否为2024年医保目录内药品": "是",
    "限定性别": "男"
  },
  {
    "序号": 2,
    "药品通用名": "艾附暖宫丸",
    "是否为2024年医保目录内药品": "是",
    "限定性别": "女"
  }
]
'''

Now, please process the following text:
"""

def get_api_client():
    """Initializes and returns the OpenAI client."""
    global API_CLIENT
    if API_CLIENT is None:
        try:
            API_CLIENT = OpenAI()
        except Exception as e:
            print(f"Error initializing OpenAI client: {e}")
            print("Please ensure the OPENAI_API_KEY environment variable is set correctly.")
            return None
    return API_CLIENT

def parse_chunk(text_chunk):
    """Sends a chunk of text to the LLM and returns the parsed JSON."""
    client = get_api_client()
    if not client:
        return None

    print(f"Sending chunk of {len(text_chunk)} characters to the LLM for parsing...")
    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text_chunk}
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        
        response_content = response.choices[0].message.content
        # The response is a JSON string, which might contain a key for the array.
        # We need to parse it and find the array.
        json_data = json.loads(response_content)
        
        # Check if the data is a list or a dict containing a list
        if isinstance(json_data, list):
            return json_data
        elif isinstance(json_data, dict):
             # Look for a list within the dictionary
            for key, value in json_data.items():
                if isinstance(value, list):
                    print(f"Extracted list of {len(value)} items from key '{key}'.")
                    return value
        
        print("Warning: LLM response was not a JSON list or a dict containing a list.")
        return None

    except Exception as e:
        print(f"An error occurred while calling the LLM API: {e}")
        return None

def main():
    """Main function to read, chunk, parse, and save the data."""
    if not get_api_client():
        return

    print(f"Reading source file: {INPUT_FILE}")
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: Could not find the input file at {INPUT_FILE}")
        return

    text_chunks = [content[i:i + CHUNK_SIZE] for i in range(0, len(content), CHUNK_SIZE)]
    print(f"Split content into {len(text_chunks)} chunks.")

    all_rules = []
    for i, chunk in enumerate(text_chunks):
        print(f"\n--- Processing Chunk {i+1}/{len(text_chunks)} ---")
        parsed_rules = parse_chunk(chunk)
        if parsed_rules:
            all_rules.extend(parsed_rules)
            print(f"Successfully parsed {len(parsed_rules)} rules from this chunk.")
        else:
            print("Failed to parse this chunk.")

    print(f"\n--- Parsing Complete ---")
    print(f"Total rules extracted: {len(all_rules)}")

    print(f"Saving final data to: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_rules, f, ensure_ascii=False, indent=4)
        
    print("Done.")

if __name__ == '__main__':
    main()
