# TOON Format Integration

This project now supports **TOON (Token-Oriented Object Notation)** format as an alternative to JSON/JSONL for data storage and exchange.

## What is TOON?

TOON is a compact, human-readable data format that is more efficient than JSON while maintaining readability. It's particularly useful for:

- **Smaller file sizes**: 20-40% reduction compared to formatted JSON
- **Better readability**: Cleaner syntax, less noise
- **Structured arrays**: Compact table-like representation

### Example

**JSON format:**
```json
{
  "context": {
    "task": "Our favorite hikes together",
    "location": "Boulder"
  },
  "friends": ["ana", "luis", "sam"],
  "hikes": [
    {"id": 1, "name": "Blue Lake Trail", "distanceKm": 7.5},
    {"id": 2, "name": "Ridge Overlook", "distanceKm": 9.2},
    {"id": 3, "name": "Wildflower Loop", "distanceKm": 5.1}
  ]
}
```

**TOON format:**
```
context:
  task: Our favorite hikes together
  location: Boulder
friends[3]: ana,luis,sam
hikes[3]{id,name,distanceKm}:
  1,Blue Lake Trail,7.5
  2,Ridge Overlook,9.2
  3,Wildflower Loop,5.1
```

## Installation

No additional dependencies required! The TOON implementation is included in the project.

## Usage

### 1. Convert Existing Data

Convert your existing JSONL files to TOON format:

```bash
cd services/ingestion-service
python scripts/convert_to_toon.py
```

This will convert:
- `data/db/chunks.jsonl` → `data/db/chunks.toon`
- `data/db/records.jsonl` → `data/db/records.toon`

### 2. Use TOON with Ingestion Service

Run ingestion with TOON output:

```bash
cd services/ingestion-service
python -m app.main --input ../../data/raw_files --use-toon
```

This will create `.toon` files instead of `.jsonl` files.

### 3. Convert Between Formats

#### JSONL to TOON:
```bash
python -m app.toon_converter --mode jsonl2toon --input data/db/chunks.jsonl --output data/db/chunks.toon
```

#### TOON to JSONL:
```bash
python -m app.toon_converter --mode toon2jsonl --input data/db/chunks.toon --output data/db/chunks.jsonl
```

#### JSON to TOON:
```bash
python -m app.toon_converter --mode json2toon --input config.json --output config.toon
```

#### TOON to JSON:
```bash
python -m app.toon_converter --mode toon2json --input config.toon --output config.json
```

### 4. Use TOON in Python Code

```python
from app.toon_format import dumps, loads

# Convert Python dict to TOON
data = {"name": "CPE CHAT", "version": "0.0.3", "tags": ["ai", "rag", "chat"]}
toon_str = dumps(data)
print(toon_str)

# Parse TOON string to Python dict
parsed_data = loads(toon_str)
print(parsed_data)

# Read/write TOON files
from app.toon_format import dump, load

# Write
with open('data.toon', 'w') as f:
    dump(data, f)

# Read
with open('data.toon', 'r') as f:
    data = load(f)
```

### 5. Use TOON Converter Utilities

```python
from app.toon_converter import jsonl_to_toon, toon_to_jsonl, write_toon, read_toon

# Convert JSONL file to TOON
jsonl_to_toon('data/chunks.jsonl', 'data/chunks.toon', max_records=100)

# Convert TOON file back to JSONL
toon_to_jsonl('data/chunks.toon', 'data/chunks.jsonl')

# Write Python data to TOON file
data = {"items": [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]}
write_toon(data, 'output.toon')

# Read TOON file to Python data
data = read_toon('output.toon')
```

## Examples

Run the examples script to see TOON in action:

```bash
cd services/ingestion-service
python scripts/toon_examples.py
```

This demonstrates:
- Structured array formatting
- Document chunk representation
- Round-trip conversion
- Space efficiency comparison

## File Structure

```
services/ingestion-service/
├── app/
│   ├── toon_format.py       # Core TOON encoder/decoder
│   ├── toon_converter.py    # Conversion utilities
│   └── main.py              # Updated with --use-toon flag
└── scripts/
    ├── convert_to_toon.py   # Batch conversion script
    └── toon_examples.py     # Usage examples
```

## API

### TOONEncoder

```python
from app.toon_format import TOONEncoder

encoder = TOONEncoder(indent="  ")
toon_str = encoder.encode(data)
```

### TOONDecoder

```python
from app.toon_format import TOONDecoder

decoder = TOONDecoder()
data = decoder.decode(toon_str)
```

### Convenience Functions

- `dumps(data, indent="  ")` - Convert Python data to TOON string
- `loads(toon_str)` - Parse TOON string to Python data
- `dump(data, file, indent="  ")` - Write Python data to file
- `load(file)` - Read TOON file to Python data

## Benefits

1. **More Compact**: 20-40% smaller than formatted JSON
2. **Human-Readable**: Cleaner syntax, easier to read
3. **Structured Arrays**: Efficient table representation
4. **Type Preservation**: Maintains data types (int, float, bool, null)
5. **Unicode Support**: Full Thai language support

## Compatibility

TOON format is fully compatible with:
- Python 3.7+
- All data types supported by JSON
- Nested structures
- Arrays and objects

## Reference

Based on: https://github.com/toon-format/toon-python

## Notes

- TOON files use `.toon` extension
- The system still supports JSON/JSONL for backward compatibility
- You can mix both formats in your workflow
- Conversion is lossless in both directions
