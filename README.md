# Schematic Splitter

Splits large `.schem` (Sponge Schematic) files into smaller chunks based on a configurable block limit.

## Dependencies

- `amulet-nbt`
- `tqdm`
- `schematicutil`, `varintIterator`, `varintWriter` (local modules)

## Usage

```
python schematic-splitter.py <source_file> [options]
```

### Options

| Flag | Description | Default |
|---|---|---|
| `--output_directory DIR` | Output directory | `Output` |
| `--output_file NAME` | Base name for output files | `Out` |
| `--block_limit N` | Max blocks per chunk | `150000` |
| `-a, --skip-air` | Skip chunks that are entirely air | off |
| `-i, --ignore-blocks BLOCK [...]` | Replace specified block types with air | none |
| `-e, --export-entities` | Export entities as separate `.schem` files and strip them from block chunks | off |
| `-s, --max-file-size SIZE` | Re-split files exceeding this size (e.g. `5MB`, `500KB`) | none |

### Examples

Basic split:
```bash
python schematic-splitter.py build.schem
```

Skip air chunks, ignore stone, and cap file size:
```bash
python schematic-splitter.py build.schem -a -i stone dirt -s 5MB --block_limit 100000
```

Export entities separately:
```bash
python schematic-splitter.py build.schem -e -a
```

## Output

- Block chunks: `Out0.schem`, `Out1.schem`, ...
- Entity chunks (with `-e`): `Out_entities0.schem`, `Out_entities1.schem`, ...

File numbering is always sequential with no gaps, even when air-only chunks are skipped.
