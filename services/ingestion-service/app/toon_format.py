"""
TOON (Token-Oriented Object Notation) Format Handler
Based on: https://github.com/toon-format/toon-python

TOON is a compact, human-readable data format designed for efficiency.
Example:
  context:
    task: Our favorite hikes together
    location: Boulder
  friends[3]: ana,luis,sam
  hikes[3]{id,name,distanceKm}:
    1,Blue Lake Trail,7.5
    2,Ridge Overlook,9.2
    3,Wildflower Loop,5.1
"""

from typing import Any, Dict, List, Union
import re
from io import StringIO


class TOONEncoder:
    """Convert Python dict/list to TOON format"""
    
    def __init__(self, indent: str = "  "):
        self.indent = indent
    
    def encode(self, data: Union[Dict, List], level: int = 0) -> str:
        """Encode data to TOON format string"""
        if isinstance(data, dict):
            return self._encode_dict(data, level)
        elif isinstance(data, list):
            return self._encode_list(data, level)
        else:
            return str(data)
    
    def _encode_dict(self, data: Dict[str, Any], level: int) -> str:
        """Encode dictionary to TOON format"""
        lines = []
        prefix = self.indent * level
        
        for key, value in data.items():
            if isinstance(value, dict):
                # Nested object
                lines.append(f"{prefix}{key}:")
                lines.append(self._encode_dict(value, level + 1))
            elif isinstance(value, list):
                # Array
                lines.append(self._encode_array(key, value, level))
            else:
                # Simple value
                lines.append(f"{prefix}{key}: {self._format_value(value)}")
        
        return "\n".join(lines)
    
    def _encode_array(self, key: str, value: List, level: int) -> str:
        """Encode array to TOON format"""
        prefix = self.indent * level
        
        if not value:
            return f"{prefix}{key}[0]:"
        
        # Check if all items are dicts with same keys
        if all(isinstance(item, dict) for item in value):
            # Get common keys
            if value:
                keys = list(value[0].keys())
                # Check if all items have same keys
                if all(set(item.keys()) == set(keys) for item in value):
                    # Structured array
                    header = f"{prefix}{key}[{len(value)}]{{{','.join(keys)}}}:"
                    lines = [header]
                    for item in value:
                        row = self.indent * (level + 1) + ','.join(
                            self._format_value(item.get(k)) for k in keys
                        )
                        lines.append(row)
                    return "\n".join(lines)
        
        # Simple array
        if all(not isinstance(item, (dict, list)) for item in value):
            values_str = ','.join(self._format_value(v) for v in value)
            return f"{prefix}{key}[{len(value)}]: {values_str}"
        
        # Complex array - fall back to line-by-line
        lines = [f"{prefix}{key}[{len(value)}]:"]
        for item in value:
            if isinstance(item, dict):
                lines.append(self._encode_dict(item, level + 1))
            elif isinstance(item, list):
                lines.append(self._encode_list(item, level + 1))
            else:
                lines.append(f"{self.indent * (level + 1)}{self._format_value(item)}")
        return "\n".join(lines)
    
    def _encode_list(self, data: List, level: int) -> str:
        """Encode list to TOON format"""
        prefix = self.indent * level
        lines = []
        for item in data:
            if isinstance(item, dict):
                lines.append(self._encode_dict(item, level))
            elif isinstance(item, list):
                lines.append(self._encode_list(item, level))
            else:
                lines.append(f"{prefix}{self._format_value(item)}")
        return "\n".join(lines)
    
    def _format_value(self, value: Any) -> str:
        """Format a single value for TOON output"""
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            # Escape if contains special characters
            if any(c in value for c in [',', '\n', ':']):
                return f'"{value}"'
            return value
        return str(value)


class TOONDecoder:
    """Parse TOON format to Python dict/list"""
    
    def decode(self, toon_str: str) -> Union[Dict, List]:
        """Decode TOON format string to Python data"""
        lines = toon_str.strip().split('\n')
        return self._parse_lines(lines, 0)[0]
    
    def _parse_lines(self, lines: List[str], start_idx: int) -> tuple:
        """Parse lines starting from start_idx, return (data, next_idx)"""
        result = {}
        idx = start_idx
        current_indent = self._get_indent(lines[idx]) if idx < len(lines) else 0
        
        while idx < len(lines):
            line = lines[idx]
            if not line.strip():
                idx += 1
                continue
            
            indent = self._get_indent(line)
            if indent < current_indent:
                # Back to parent level
                break
            
            # Parse key-value or array
            if ':' in line:
                key, rest = line.split(':', 1)
                key = key.strip()
                rest = rest.strip()
                
                # Check for array notation
                array_match = re.match(r'(\w+)\[(\d+)\](?:\{([^}]+)\})?', key)
                if array_match:
                    arr_name, arr_len, arr_keys = array_match.groups()
                    arr_size = int(arr_len)
                    
                    if arr_keys:
                        # Structured array
                        keys = [k.strip() for k in arr_keys.split(',')]
                        arr_data = []
                        idx += 1
                        for _ in range(arr_size):
                            if idx >= len(lines):
                                break
                            row = lines[idx].strip()
                            values = [v.strip() for v in row.split(',')]
                            row_dict = {k: self._parse_value(v) for k, v in zip(keys, values)}
                            arr_data.append(row_dict)
                            idx += 1
                        result[arr_name] = arr_data
                        continue
                    elif rest:
                        # Simple array inline
                        values = [v.strip() for v in rest.split(',')]
                        result[arr_name] = [self._parse_value(v) for v in values]
                        idx += 1
                        continue
                
                if rest:
                    # Simple key-value
                    result[key] = self._parse_value(rest)
                    idx += 1
                else:
                    # Nested object or array
                    idx += 1
                    if idx < len(lines) and self._get_indent(lines[idx]) > indent:
                        nested_data, idx = self._parse_lines(lines, idx)
                        result[key] = nested_data
            else:
                idx += 1
        
        return result, idx
    
    def _get_indent(self, line: str) -> int:
        """Get indentation level of line"""
        return len(line) - len(line.lstrip())
    
    def _parse_value(self, value_str: str) -> Any:
        """Parse a value string to appropriate Python type"""
        value_str = value_str.strip()
        
        if value_str == 'null':
            return None
        elif value_str == 'true':
            return True
        elif value_str == 'false':
            return False
        elif value_str.startswith('"') and value_str.endswith('"'):
            return value_str[1:-1]
        else:
            # Try to parse as number
            try:
                if '.' in value_str:
                    return float(value_str)
                else:
                    return int(value_str)
            except ValueError:
                return value_str


# Convenience functions
def dumps(data: Union[Dict, List], indent: str = "  ") -> str:
    """Convert Python data to TOON format string"""
    encoder = TOONEncoder(indent=indent)
    return encoder.encode(data)


def loads(toon_str: str) -> Union[Dict, List]:
    """Parse TOON format string to Python data"""
    decoder = TOONDecoder()
    return decoder.decode(toon_str)


def dump(data: Union[Dict, List], file, indent: str = "  "):
    """Write Python data to file in TOON format"""
    toon_str = dumps(data, indent)
    file.write(toon_str)


def load(file) -> Union[Dict, List]:
    """Read TOON format from file and parse to Python data"""
    toon_str = file.read()
    return loads(toon_str)
