"""
TOON Format Converter - Convert between JSON/JSONL and TOON formats
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from .toon_format import dumps, loads


def jsonl_to_toon(jsonl_path: str, toon_path: str, max_records: Optional[int] = None):
    """
    Convert JSONL file to TOON format
    
    Args:
        jsonl_path: Path to input JSONL file
        toon_path: Path to output TOON file
        max_records: Maximum number of records to convert (None = all)
    """
    jsonl_file = Path(jsonl_path)
    toon_file = Path(toon_path)
    
    if not jsonl_file.exists():
        raise FileNotFoundError(f"JSONL file not found: {jsonl_path}")
    
    # Read JSONL records
    records = []
    with jsonl_file.open('r', encoding='utf-8') as f:
        for idx, line in enumerate(f):
            if max_records and idx >= max_records:
                break
            line = line.strip()
            if line:
                records.append(json.loads(line))
    
    # Create TOON structure
    toon_data = {
        'metadata': {
            'source_file': jsonl_file.name,
            'total_records': len(records),
            'format': 'TOON v1.0'
        },
        'records': records
    }
    
    # Write TOON file
    toon_file.parent.mkdir(parents=True, exist_ok=True)
    with toon_file.open('w', encoding='utf-8') as f:
        toon_str = dumps(toon_data)
        f.write(toon_str)
    
    print(f"Converted {len(records)} records from {jsonl_path} to {toon_path}")
    return len(records)


def toon_to_jsonl(toon_path: str, jsonl_path: str):
    """
    Convert TOON file back to JSONL format
    
    Args:
        toon_path: Path to input TOON file
        jsonl_path: Path to output JSONL file
    """
    toon_file = Path(toon_path)
    jsonl_file = Path(jsonl_path)
    
    if not toon_file.exists():
        raise FileNotFoundError(f"TOON file not found: {toon_path}")
    
    # Read TOON file
    with toon_file.open('r', encoding='utf-8') as f:
        toon_data = loads(f.read())
    
    # Extract records
    if isinstance(toon_data, dict):
        records = toon_data.get('records', [])
    else:
        records = toon_data if isinstance(toon_data, list) else []
    
    # Write JSONL file
    jsonl_file.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_file.open('w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    print(f"Converted {len(records)} records from {toon_path} to {jsonl_path}")
    return len(records)


def json_to_toon(json_path: str, toon_path: str):
    """
    Convert JSON file to TOON format
    
    Args:
        json_path: Path to input JSON file
        toon_path: Path to output TOON file
    """
    json_file = Path(json_path)
    toon_file = Path(toon_path)
    
    if not json_file.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")
    
    # Read JSON file
    with json_file.open('r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Write TOON file
    toon_file.parent.mkdir(parents=True, exist_ok=True)
    with toon_file.open('w', encoding='utf-8') as f:
        toon_str = dumps(data)
        f.write(toon_str)
    
    print(f"Converted {json_path} to {toon_path}")


def toon_to_json(toon_path: str, json_path: str):
    """
    Convert TOON file to JSON format
    
    Args:
        toon_path: Path to input TOON file
        json_path: Path to output JSON file
    """
    toon_file = Path(toon_path)
    json_file = Path(json_path)
    
    if not toon_file.exists():
        raise FileNotFoundError(f"TOON file not found: {toon_path}")
    
    # Read TOON file
    with toon_file.open('r', encoding='utf-8') as f:
        data = loads(f.read())
    
    # Write JSON file
    json_file.parent.mkdir(parents=True, exist_ok=True)
    with json_file.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Converted {toon_path} to {json_path}")


def write_toon(data: Any, file_path: str):
    """
    Write Python data structure to TOON file
    
    Args:
        data: Python dict or list
        file_path: Path to output TOON file
    """
    toon_file = Path(file_path)
    toon_file.parent.mkdir(parents=True, exist_ok=True)
    
    with toon_file.open('w', encoding='utf-8') as f:
        toon_str = dumps(data)
        f.write(toon_str)


def read_toon(file_path: str) -> Any:
    """
    Read TOON file and return Python data structure
    
    Args:
        file_path: Path to TOON file
    
    Returns:
        Python dict or list
    """
    toon_file = Path(file_path)
    
    if not toon_file.exists():
        raise FileNotFoundError(f"TOON file not found: {file_path}")
    
    with toon_file.open('r', encoding='utf-8') as f:
        return loads(f.read())


# CLI interface
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert between JSON/JSONL and TOON formats')
    parser.add_argument('--mode', choices=['jsonl2toon', 'toon2jsonl', 'json2toon', 'toon2json'], 
                       required=True, help='Conversion mode')
    parser.add_argument('--input', required=True, help='Input file path')
    parser.add_argument('--output', required=True, help='Output file path')
    parser.add_argument('--max-records', type=int, help='Max records to convert (JSONL only)')
    
    args = parser.parse_args()
    
    if args.mode == 'jsonl2toon':
        jsonl_to_toon(args.input, args.output, args.max_records)
    elif args.mode == 'toon2jsonl':
        toon_to_jsonl(args.input, args.output)
    elif args.mode == 'json2toon':
        json_to_toon(args.input, args.output)
    elif args.mode == 'toon2json':
        toon_to_json(args.input, args.output)
