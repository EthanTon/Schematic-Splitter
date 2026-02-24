# schematic_splitter.py
from math import ceil
import os
import json
import tempfile
import argparse
from typing import Dict, List, Tuple, Optional, Set

import amulet_nbt
from amulet_nbt import (
    ShortTag,
    IntTag,
    DoubleTag,
    ByteArrayTag,
    IntArrayTag,
    CompoundTag,
    ListTag,
)

import schematicutil
import varintIterator
import varintWriter

AIR_BLOCK = "minecraft:air"
CAVE_AIR_BLOCK = "minecraft:cave_air"
VOID_AIR_BLOCK = "minecraft:void_air"
ALL_AIR_BLOCKS = {AIR_BLOCK, CAVE_AIR_BLOCK, VOID_AIR_BLOCK}


def normalize_block_name(name: str) -> str:
    """Ensure block name has minecraft: prefix and strip any block state."""
    base = name.split("[")[0].strip()
    if ":" not in base:
        base = f"minecraft:{base}"
    return base


def is_air_block(block_type: str) -> bool:
    """Check if a block type string is any form of air."""
    base = block_type.split("[")[0]
    return base in ALL_AIR_BLOCKS


def calculate_chunk_dimensions(
    width: int, height: int, length: int, block_limit: int
) -> Tuple[int, int, int]:
    """Calculate optimal chunk dimensions based on block limit."""
    size = width * height * length

    if size <= block_limit:
        return width, height, length

    ratio = (block_limit / size) ** (1 / 3)
    chunk_width = max(1, ceil(width * ratio))
    chunk_height = max(1, ceil(height * ratio))
    chunk_length = max(1, ceil(length * ratio))

    while chunk_width * chunk_height * chunk_length > block_limit:
        max_dim = max(chunk_width, chunk_height, chunk_length)
        if chunk_width == max_dim:
            chunk_width = max(1, chunk_width - 1)
        elif chunk_height == max_dim:
            chunk_height = max(1, chunk_height - 1)
        else:
            chunk_length = max(1, chunk_length - 1)

    return chunk_width, chunk_height, chunk_length


def process_entities(
    source_entities: ListTag,
    max_chunk_dims: Tuple[int, int, int],
    chunk_width: int,
    chunk_length: int,
) -> Dict[int, List]:
    """Process entities and distribute them into chunks."""
    chunk_entities: Dict[int, List] = {}
    max_cw, max_ch, max_cl = max_chunk_dims

    for item in source_entities:
        pos = item["Pos"]
        sx, sy, sz = float(pos[0]), float(pos[1]), float(pos[2])

        cx = int(sx // max_cw)
        cy = int(sy // max_ch)
        cz = int(sz // max_cl)

        file_number = schematicutil.get_index(cx, cy, cz, chunk_width, chunk_length)

        local_pos = ListTag(
            [
                DoubleTag(sx - cx * max_cw),
                DoubleTag(sy - cy * max_ch),
                DoubleTag(sz - cz * max_cl),
            ]
        )

        item["Pos"] = local_pos
        chunk_entities.setdefault(file_number, []).append(CompoundTag(item))

    return chunk_entities


def process_block_entities(
    source_block_entities: ListTag,
    max_chunk_dims: Tuple[int, int, int],
    chunk_width: int,
    chunk_length: int,
) -> Dict[int, List]:
    """Process block entities and distribute them into chunks."""
    chunk_block_entities: Dict[int, List] = {}
    max_cw, max_ch, max_cl = max_chunk_dims

    for item in source_block_entities:
        pos = item["Pos"]
        sx, sy, sz = int(pos[0]), int(pos[1]), int(pos[2])

        cx = sx // max_cw
        cy = sy // max_ch
        cz = sz // max_cl

        file_number = schematicutil.get_index(cx, cy, cz, chunk_width, chunk_length)

        item["Pos"] = IntArrayTag([sx % max_cw, sy % max_ch, sz % max_cl])
        chunk_block_entities.setdefault(file_number, []).append(CompoundTag(item))

    return chunk_block_entities


def process_chunk_data(
    source_blocks: CompoundTag,
    source_biomes: Optional[CompoundTag],
    max_chunk_dims: Tuple[int, int, int],
    source_dims: Tuple[int, int, int],
    source_offset: Tuple[int, int, int],
    chunk_width: int,
    chunk_length: int,
    ignore_blocks: Optional[Set[str]] = None,
) -> Tuple[Dict, ...]:
    source_width, _, source_length = source_dims
    src_ox, src_oy, src_oz = source_offset
    max_cw, max_ch, max_cl = max_chunk_dims

    chunk: Dict[int, List[int]] = {0: []}
    chunk_palette: Dict[int, Dict[str, IntTag]] = {0: {}}
    chunk_offset: Dict[int, List[int]] = {0: [src_ox, src_oy, src_oz]}
    chunk_dimensions: Dict[int, List[int]] = {0: [max_cw, max_ch, max_cl]}

    has_biomes = source_biomes is not None
    chunk_biomes: Optional[Dict[int, List[int]]] = None
    chunk_biomes_palette: Optional[Dict[int, Dict[str, IntTag]]] = None

    if has_biomes:
        chunk_biomes = {0: []}
        chunk_biomes_palette = {0: {}}
        biome_data = bytes(b & 0xFF for b in source_biomes["Data"])
        source_biome_palette = schematicutil.swap_palette(source_biomes["Palette"])
        biome_iter = varintIterator.VarIntIterator(biome_data)

    block_data = bytes(b & 0xFF for b in source_blocks["Data"])
    source_palette = schematicutil.swap_palette(source_blocks["Palette"])
    block_iter = varintIterator.VarIntIterator(block_data)

    # Pre-compute which source palette IDs should be replaced with air
    ignored_source_ids: Set[int] = set()
    if ignore_blocks:
        for src_id, block_type in source_palette.items():
            base_name = block_type.split("[")[0]
            if base_name in ignore_blocks:
                ignored_source_ids.add(src_id)

    source_index = 0
    while block_iter.has_next():
        sx, sy, sz = schematicutil.get_local_coordinate(
            source_index, source_width, source_length
        )

        cx = sx // max_cw
        cy = sy // max_ch
        cz = sz // max_cl

        file_number = schematicutil.get_index(cx, cy, cz, chunk_width, chunk_length)

        x_width = (sx % max_cw) + 1
        y_height = (sy % max_ch) + 1
        z_length = (sz % max_cl) + 1

        # Initialize new chunk data if needed
        if file_number not in chunk:
            chunk[file_number] = []
            chunk_palette[file_number] = {}
            chunk_offset[file_number] = [
                sx + src_ox,
                sy + src_oy,
                sz + src_oz,
            ]
            chunk_dimensions[file_number] = [x_width, y_height, z_length]

            if has_biomes:
                chunk_biomes[file_number] = []
                chunk_biomes_palette[file_number] = {}

        # Update chunk dimensions to track maximums
        dims = chunk_dimensions[file_number]
        if x_width > dims[0]:
            dims[0] = x_width
        if y_height > dims[1]:
            dims[1] = y_height
        if z_length > dims[2]:
            dims[2] = z_length

        # Process block data
        new_block_id = next(block_iter)

        # Replace ignored blocks with air
        if ignored_source_ids and new_block_id in ignored_source_ids:
            block_type = AIR_BLOCK
        else:
            block_type = source_palette[new_block_id]

        palette = chunk_palette[file_number]
        if block_type not in palette:
            block_number = len(palette)
            palette[block_type] = IntTag(block_number)
        else:
            block_number = int(palette[block_type])

        chunk[file_number].append(block_number)

        # Process biome data if present
        if has_biomes:
            new_biome_id = next(biome_iter)
            biome_type = source_biome_palette[new_biome_id]
            b_palette = chunk_biomes_palette[file_number]
            if biome_type not in b_palette:
                biome_number = len(b_palette)
                b_palette[biome_type] = IntTag(biome_number)
            else:
                biome_number = int(b_palette[biome_type])
            chunk_biomes[file_number].append(biome_number)
            biome_iter.has_next()

        source_index += 1

    return (
        chunk,
        chunk_palette,
        chunk_offset,
        chunk_dimensions,
        chunk_biomes,
        chunk_biomes_palette,
    )


def chunk_is_all_air(palette: Dict[str, IntTag]) -> bool:
    """Return True if every block type in the chunk palette is a form of air."""
    if not palette:
        return True
    return all(is_air_block(block_type) for block_type in palette)


def export_entities_file(
    chunk_entities: Dict[int, List],
    chunk_block_entities: Dict[int, List],
    chunk_offsets: Dict[int, List[int]],
    output_directory: str,
    output_name: str,
):
    """Export all entities and block entities to a JSON file."""
    os.makedirs(output_directory, exist_ok=True)

    all_entities = []

    for file_num, ents in chunk_entities.items():
        offset = chunk_offsets.get(file_num, [0, 0, 0])
        for ent in ents:
            entry = {
                "type": "entity",
                "chunk": file_num,
                "chunk_offset": offset,
                "data": str(ent),
            }
            all_entities.append(entry)

    for file_num, bents in chunk_block_entities.items():
        offset = chunk_offsets.get(file_num, [0, 0, 0])
        for bent in bents:
            entry = {
                "type": "block_entity",
                "chunk": file_num,
                "chunk_offset": offset,
                "data": str(bent),
            }
            all_entities.append(entry)

    output_path = os.path.join(output_directory, f"{output_name}_entities.json")
    with open(output_path, "w") as f:
        json.dump(all_entities, f, indent=2)

    print(f"Exported {len(all_entities)} entities to {output_path}")


def write_chunks(
    source_file: amulet_nbt.NamedTag,
    chunk_data: Tuple[Dict, ...],
    chunk_entities: Dict[int, List],
    chunk_block_entities: Dict[int, List],
    output_directory: str,
    output_name: str,
    skip_air: bool = False,
    export_entities: bool = False,
) -> List[str]:
    (
        chunk,
        chunk_palette,
        chunk_offset,
        chunk_dimensions,
        chunk_biomes,
        chunk_biomes_palette,
    ) = chunk_data
    has_biomes = chunk_biomes is not None

    os.makedirs(output_directory, exist_ok=True)

    root = source_file.compound
    schematic = root["Schematic"]
    blocks = schematic["Blocks"]

    written_files: List[str] = []
    skipped_air = 0

    for file_num in chunk:
        # -a: skip chunks that are entirely air
        if skip_air and chunk_is_all_air(chunk_palette[file_num]):
            skipped_air += 1
            continue

        dims = chunk_dimensions[file_num]
        w, h, l = dims[0], dims[1], dims[2]

        schematic["Width"] = ShortTag(w)
        schematic["Height"] = ShortTag(h)
        schematic["Length"] = ShortTag(l)

        # Block entities (omit from schematic if -e is used)
        if export_entities:
            blocks["BlockEntities"] = ListTag()
            schematic["Entities"] = ListTag()
        else:
            be_list = chunk_block_entities.get(file_num)
            blocks["BlockEntities"] = ListTag(be_list) if be_list else ListTag()

            e_list = chunk_entities.get(file_num)
            schematic["Entities"] = ListTag(e_list) if e_list else ListTag()

        # Block data
        blocks["Data"] = ByteArrayTag(varintWriter.write(chunk[file_num], w, h, l))
        blocks["Palette"] = CompoundTag(chunk_palette[file_num])

        # Biomes
        if has_biomes:
            biomes = schematic["Biomes"]
            biomes["Data"] = ByteArrayTag(
                varintWriter.write(chunk_biomes[file_num], w, h, l)
            )
            biomes["Palette"] = CompoundTag(chunk_biomes_palette[file_num])

        schematic["Offset"] = IntArrayTag(chunk_offset[file_num])

        output_location = os.path.join(
            output_directory, f"{output_name}{file_num}.schem"
        )
        source_file.save_to(output_location, compressed=True)
        written_files.append(output_location)

    if skipped_air > 0:
        print(f"Skipped {skipped_air} air-only chunk(s).")

    return written_files


def resplit_oversized(
    written_files: List[str],
    max_file_size: int,
    output_directory: str,
    output_name: str,
    block_limit: int,
    skip_air: bool = False,
    ignore_blocks: Optional[Set[str]] = None,
    export_entities: bool = False,
):
    iteration = 0
    max_iterations = 10  # safety cap to prevent infinite recursion

    while iteration < max_iterations:
        oversized = [f for f in written_files if os.path.getsize(f) > max_file_size]
        if not oversized:
            break

        iteration += 1
        new_block_limit = max(1, block_limit // 2)
        print(
            f"Re-split pass {iteration}: {len(oversized)} file(s) exceed "
            f"{max_file_size} bytes. Halving block limit to {new_block_limit}."
        )

        new_written: List[str] = []
        for filepath in written_files:
            if filepath not in oversized:
                new_written.append(filepath)
                continue

            # Re-split the oversized file into a temp sub-directory
            base = os.path.splitext(os.path.basename(filepath))[0]
            sub_dir = os.path.join(output_directory, f"_resplit_{base}")

            try:
                sub_files = split_schematic(
                    filename=filepath,
                    output_directory=sub_dir,
                    output_name=base + "_",
                    block_limit=new_block_limit,
                    skip_air=skip_air,
                    ignore_blocks=ignore_blocks,
                    export_entities=export_entities,
                    max_file_size=None,  # don't recurse here, we loop externally
                )
            except Exception as e:
                print(f"Warning: could not re-split {filepath}: {e}")
                new_written.append(filepath)
                continue

            # Move the sub-files back into the main output directory and
            # remove the original oversized file
            for sf in sub_files:
                dest = os.path.join(output_directory, os.path.basename(sf))
                # Avoid name collisions
                counter = 0
                while os.path.exists(dest):
                    counter += 1
                    name, ext = os.path.splitext(os.path.basename(sf))
                    dest = os.path.join(output_directory, f"{name}_{counter}{ext}")
                os.rename(sf, dest)
                new_written.append(dest)

            # Clean up
            os.remove(filepath)
            try:
                os.rmdir(sub_dir)
            except OSError:
                pass  # directory not empty (e.g. entity exports), that's fine

        written_files = new_written
        block_limit = new_block_limit

    if iteration >= max_iterations:
        remaining = [f for f in written_files if os.path.getsize(f) > max_file_size]
        if remaining:
            print(
                f"Warning: {len(remaining)} file(s) still exceed the size limit "
                f"after {max_iterations} re-split passes."
            )


def split_schematic(
    filename: str,
    output_directory: str = "Output",
    output_name: str = "Out",
    block_limit: int = 150000,
    skip_air: bool = False,
    ignore_blocks: Optional[Set[str]] = None,
    export_entities: bool = False,
    max_file_size: Optional[int] = None,
) -> List[str]:
    print(f"Loading schematic file: {filename}")
    try:
        source_file = schematicutil.load_schematic(filename)
    except Exception as e:
        raise ValueError(f"Failed to load schematic file: {e}")

    if source_file is None:
        raise ValueError("Invalid file extension. Please provide a .schem file.")

    print("Schematic file loaded successfully.")

    source_dims = schematicutil.get_dimension(source_file)
    source_offset = schematicutil.get_offset(source_file)

    # Calculate chunk dimensions
    max_chunk_dims = calculate_chunk_dimensions(*source_dims, block_limit)
    chunk_width = ceil(source_dims[0] / max_chunk_dims[0])
    chunk_length = ceil(source_dims[2] / max_chunk_dims[2])

    # Process entities
    print("Processing entities...")
    source_entities = schematicutil.get_entities(source_file)
    chunk_entities = process_entities(
        source_entities, max_chunk_dims, chunk_width, chunk_length
    )

    # Process block entities
    print("Processing block entities...")
    source_block_entities = schematicutil.get_block_data(source_file)["BlockEntities"]
    chunk_block_entities = process_block_entities(
        source_block_entities, max_chunk_dims, chunk_width, chunk_length
    )

    # Process chunk data
    print("Processing chunk data...")
    source_blocks = schematicutil.get_block_data(source_file)
    source_biomes = schematicutil.get_biome_data(source_file)
    chunk_data = process_chunk_data(
        source_blocks,
        source_biomes,
        max_chunk_dims,
        source_dims,
        source_offset,
        chunk_width,
        chunk_length,
        ignore_blocks=ignore_blocks,
    )

    # Export entities to separate file if requested
    if export_entities:
        print("Exporting entities to separate file...")
        _, _, chunk_offset, *_ = chunk_data
        export_entities_file(
            chunk_entities,
            chunk_block_entities,
            chunk_offset,
            output_directory,
            output_name,
        )

    # Write chunks to files
    print("Writing chunks to output files...")
    written_files = write_chunks(
        source_file,
        chunk_data,
        chunk_entities,
        chunk_block_entities,
        output_directory,
        output_name,
        skip_air=skip_air,
        export_entities=export_entities,
    )

    # Re-split any chunks that exceed the file-size limit
    if max_file_size is not None and max_file_size > 0:
        resplit_oversized(
            written_files,
            max_file_size,
            output_directory,
            output_name,
            block_limit,
            skip_air=skip_air,
            ignore_blocks=ignore_blocks,
            export_entities=export_entities,
        )

    print("Schematic splitting completed.")
    return written_files


def parse_size(value: str) -> int:
    value = value.strip().upper()
    multipliers = {
        "B": 1,
        "KB": 1024,
        "MB": 1024**2,
        "GB": 1024**3,
    }
    for suffix, mult in sorted(multipliers.items(), key=lambda x: -len(x[0])):
        if value.endswith(suffix):
            num = value[: -len(suffix)].strip()
            return int(float(num) * mult)
    return int(value)


def main():
    parser = argparse.ArgumentParser(
        description="Split a schematic file into smaller chunks."
    )
    parser.add_argument(
        "source_file", type=str, help="Path to the .schem file to split."
    )
    parser.add_argument(
        "--output_directory",
        type=str,
        default="Output",
        help="Directory to save output chunks.",
    )
    parser.add_argument(
        "--output_file",
        type=str,
        default="Out",
        help="Base name for output chunk files.",
    )
    parser.add_argument(
        "--block_limit",
        type=int,
        default=150000,
        help="Maximum number of blocks per chunk.",
    )
    parser.add_argument(
        "-a",
        "--skip-air",
        action="store_true",
        default=False,
        help="Skip output chunks that contain only air blocks.",
    )
    parser.add_argument(
        "-i",
        "--ignore-blocks",
        nargs="+",
        metavar="BLOCK",
        default=None,
        help=(
            "Block type(s) to replace with air (e.g. minecraft:stone stone "
            "minecraft:dirt). The minecraft: prefix is added automatically if "
            "omitted. Block states are stripped before matching."
        ),
    )
    parser.add_argument(
        "-e",
        "--export-entities",
        action="store_true",
        default=False,
        help=(
            "Export all entities and block entities to a separate JSON file "
            "and strip them from the .schem output chunks."
        ),
    )
    parser.add_argument(
        "-s",
        "--max-file-size",
        type=str,
        default=None,
        metavar="SIZE",
        help=(
            "Maximum output file size. Files exceeding this will be re-split "
            "with a halved block limit. Supports suffixes: B, KB, MB, GB "
            "(e.g. 5MB, 500KB, 1048576)."
        ),
    )

    args = parser.parse_args()

    # Normalise ignore-blocks list into a set of full block names
    ignore_set: Optional[Set[str]] = None
    if args.ignore_blocks:
        ignore_set = {normalize_block_name(b) for b in args.ignore_blocks}
        print(f"Ignoring blocks: {', '.join(sorted(ignore_set))}")

    max_file_size: Optional[int] = None
    if args.max_file_size:
        max_file_size = parse_size(args.max_file_size)
        print(f"Max output file size: {max_file_size} bytes")

    try:
        split_schematic(
            filename=args.source_file,
            output_directory=args.output_directory,
            output_name=args.output_file,
            block_limit=args.block_limit,
            skip_air=args.skip_air,
            ignore_blocks=ignore_set,
            export_entities=args.export_entities,
            max_file_size=max_file_size,
        )
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
