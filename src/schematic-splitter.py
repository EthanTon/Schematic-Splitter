# schematic_splitter.py
from math import ceil
import os
from numpy import double
from typing import Dict, List, Tuple, Optional
import nbtlib
import schematicutil
import varintIterator
import varintWriter


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

    while (chunk_width * chunk_height * chunk_length) > block_limit:
        max_dim = max(chunk_width, chunk_height, chunk_length)
        if chunk_width == max_dim:
            chunk_width = max(1, chunk_width - 1)
        elif chunk_height == max_dim:
            chunk_height = max(1, chunk_height - 1)
        else:
            chunk_length = max(1, chunk_length - 1)

    return chunk_width, chunk_height, chunk_length


def process_entities(
    source_entities: List,
    max_chunk_dims: Tuple[int, int, int],
    chunk_width: int,
    chunk_length: int,
) -> Dict[int, List]:
    """Process entities and distribute them into chunks."""
    chunk_entities = {}
    max_chunk_width, max_chunk_height, max_chunk_length = max_chunk_dims

    for item in source_entities:
        pos = item["Pos"]
        source_x, source_y, source_z = double(pos[0]), double(pos[1]), double(pos[2])

        chunk_x = int(source_x // max_chunk_width)
        chunk_y = int(source_y // max_chunk_height)
        chunk_z = int(source_z // max_chunk_length)

        file_number = schematicutil.get_index(
            chunk_x, chunk_y, chunk_z, chunk_width, chunk_length
        )

        x = nbtlib.Double(source_x - (chunk_x * max_chunk_width))
        y = nbtlib.Double(source_y - (chunk_y * max_chunk_height))
        z = nbtlib.Double(source_z - (chunk_z * max_chunk_length))

        if file_number not in chunk_entities:
            chunk_entities[file_number] = []

        item["Pos"] = nbtlib.List([x, y, z])
        chunk_entities[file_number].append(nbtlib.Compound(item))

    return chunk_entities


def process_block_entities(
    source_block_entities: List,
    max_chunk_dims: Tuple[int, int, int],
    chunk_width: int,
    chunk_length: int,
) -> Dict[int, List]:
    """Process block entities and distribute them into chunks."""
    chunk_block_entities = {}
    max_chunk_width, max_chunk_height, max_chunk_length = max_chunk_dims

    for item in source_block_entities:
        pos = item["Pos"]
        source_x, source_y, source_z = int(pos[0]), int(pos[1]), int(pos[2])

        chunk_x = source_x // max_chunk_width
        chunk_y = source_y // max_chunk_height
        chunk_z = source_z // max_chunk_length

        file_number = schematicutil.get_index(
            chunk_x, chunk_y, chunk_z, chunk_width, chunk_length
        )

        x = source_x % max_chunk_width
        y = source_y % max_chunk_height
        z = source_z % max_chunk_length

        if file_number not in chunk_block_entities:
            chunk_block_entities[file_number] = []

        item["Pos"] = nbtlib.tag.IntArray([x, y, z])
        chunk_block_entities[file_number].append(nbtlib.Compound(item))

    return chunk_block_entities


def process_chunk_data(
    source_blocks: Dict,
    source_biomes: Optional[Dict],
    max_chunk_dims: Tuple[int, int, int],
    source_dims: Tuple[int, int, int],
    source_offset: Tuple[int, int, int],
    chunk_width: int,
    chunk_length: int,
) -> Tuple[Dict, ...]:
    """Process blocks, palette, and biome data into chunks."""
    source_width, _, source_length = source_dims
    source_offset_x, source_offset_y, source_offset_z = source_offset
    max_chunk_width, max_chunk_height, max_chunk_length = max_chunk_dims

    chunk = {0: []}
    chunk_palette = {0: {}}
    chunk_offset = {0: [source_offset_x, source_offset_y, source_offset_z]}
    chunk_dimensions = {0: [max_chunk_width, max_chunk_height, max_chunk_length]}

    has_biomes = source_biomes is not None
    if has_biomes:
        chunk_biomes = {0: []}
        chunk_biomes_palette = {0: {}}
        source_biome_data = source_biomes["Data"]
        biome_data = bytes(biome & 0xFF for biome in source_biome_data)
        source_biome_palette = schematicutil.swap_palette(
            dict(source_biomes["Palette"])
        )
        biome_iter = varintIterator.VarIntIterator(biome_data)

    source_data = source_blocks["Data"]
    block_data = bytes(block & 0xFF for block in source_data)
    source_palette = schematicutil.swap_palette(dict(source_blocks["Palette"]))
    block_iter = varintIterator.VarIntIterator(block_data)

    source_index = 0
    while block_iter.has_next():
        source_x, source_y, source_z = schematicutil.get_local_coordinate(
            source_index, source_width, source_length
        )

        chunk_x = source_x // max_chunk_width
        chunk_y = source_y // max_chunk_height
        chunk_z = source_z // max_chunk_length

        file_number = schematicutil.get_index(
            chunk_x, chunk_y, chunk_z, chunk_width, chunk_length
        )

        x_width = (source_x % max_chunk_width) + 1
        y_height = (source_y % max_chunk_height) + 1
        z_length = (source_z % max_chunk_length) + 1

        # Initialize new chunk data if needed
        if file_number not in chunk:
            chunk[file_number] = []
            chunk_palette[file_number] = {}
            chunk_offset[file_number] = [
                (source_x + source_offset_x),
                (source_y + source_offset_y),
                (source_z + source_offset_z),
            ]
            chunk_dimensions[file_number] = [x_width, y_height, z_length]

            if has_biomes:
                chunk_biomes[file_number] = []
                chunk_biomes_palette[file_number] = {}

        # Update chunk dimensions
        chunk_dimensions[file_number] = [
            int(max(x_width, chunk_dimensions[file_number][0])),
            int(max(y_height, chunk_dimensions[file_number][1])),
            int(max(z_length, chunk_dimensions[file_number][2])),
        ]

        # Process block data
        new_block_id = block_iter.__next__()
        block_type = source_palette[new_block_id]
        if block_type not in chunk_palette[file_number]:
            block_number = len(chunk_palette[file_number])
            chunk_palette[file_number][block_type] = nbtlib.Int(block_number)
        else:
            block_number = int(chunk_palette[file_number][block_type])

        chunk[file_number].append(block_number)

        # Process biome data if present
        if has_biomes:
            new_biome_id = biome_iter.__next__()
            biome_type = source_biome_palette[new_biome_id]
            if biome_type not in chunk_biomes_palette[file_number]:
                biome_number = len(chunk_biomes_palette[file_number])
                chunk_biomes_palette[file_number][biome_type] = nbtlib.Int(biome_number)
            else:
                biome_number = int(chunk_biomes_palette[file_number][biome_type])
            chunk_biomes[file_number].append(biome_number)
            biome_iter.has_next()

        source_index += 1

    if has_biomes:
        return (
            chunk,
            chunk_palette,
            chunk_offset,
            chunk_dimensions,
            chunk_biomes,
            chunk_biomes_palette,
        )
    return chunk, chunk_palette, chunk_offset, chunk_dimensions, None, None


def write_chunks(
    source_file: nbtlib.File,
    chunk_data: Tuple[Dict, ...],
    chunk_entities: Dict[int, List],
    chunk_block_entities: Dict[int, List],
    output_directory: str,
    output_name: str,
):
    """Write processed chunks to output files."""
    (
        chunk,
        chunk_palette,
        chunk_offset,
        chunk_dimensions,
        chunk_biomes,
        chunk_biomes_palette,
    ) = chunk_data
    has_biomes = chunk_biomes is not None

    if not os.path.isdir(output_directory):
        os.mkdir(output_directory)

    for file_num in chunk.keys():
        output = source_file

        output["Schematic"]["Width"] = nbtlib.Short(chunk_dimensions[file_num][0])
        output["Schematic"]["Height"] = nbtlib.Short(chunk_dimensions[file_num][1])
        output["Schematic"]["Length"] = nbtlib.Short(chunk_dimensions[file_num][2])

        # Set block entities
        output["Schematic"]["Blocks"]["BlockEntities"] = (
            nbtlib.List(chunk_block_entities.get(file_num, []))
            if file_num in chunk_block_entities
            else nbtlib.List[nbtlib.tag.Compound]([])
        )

        # Set entities
        output["Schematic"]["Entities"] = (
            nbtlib.List(chunk_entities.get(file_num, []))
            if file_num in chunk_entities
            else nbtlib.List({})
        )

        # Set blocks data
        output["Schematic"]["Blocks"]["Data"] = nbtlib.ByteArray(
            varintWriter.write(
                chunk[file_num],
                chunk_dimensions[file_num][0],
                chunk_dimensions[file_num][1],
                chunk_dimensions[file_num][2],
            )
        )
        output["Schematic"]["Blocks"]["Palette"] = nbtlib.Compound(
            chunk_palette[file_num]
        )

        # Set biomes if present
        if has_biomes:
            output["Schematic"]["Biomes"]["Data"] = nbtlib.ByteArray(
                varintWriter.write(
                    chunk_biomes[file_num],
                    chunk_dimensions[file_num][0],
                    chunk_dimensions[file_num][1],
                    chunk_dimensions[file_num][2],
                )
            )
            output["Schematic"]["Biomes"]["Palette"] = nbtlib.Compound(
                chunk_biomes_palette[file_num]
            )

        output["Schematic"]["Offset"] = nbtlib.IntArray(chunk_offset[file_num])

        output_location = f"{output_directory}/{output_name}{file_num}.schem"
        output.save(output_location)


class SchematicSplitter:
    def __init__(self, block_limit: int):
        self.block_limit = block_limit

    def split_schematic(
        self, filename: str, output_directory: str = "Output", output_name: str = "Out"
    ):
        """Split a schematic file into smaller chunks based on block limit."""
        # Load source file and get dimensions
        source_file = schematicutil.load_schematic(filename)
        source_dims = tuple(map(int, schematicutil.get_dimension(source_file)))
        source_offset = tuple(map(int, schematicutil.get_offset(source_file)))

        # Calculate chunk dimensions
        max_chunk_dims = calculate_chunk_dimensions(*source_dims, self.block_limit)
        chunk_width = int(ceil(source_dims[0] / max_chunk_dims[0]))
        chunk_length = int(ceil(source_dims[2] / max_chunk_dims[2]))

        # Process entities
        source_entities = schematicutil.get_entities(source_file)
        chunk_entities = process_entities(
            source_entities, max_chunk_dims, chunk_width, chunk_length
        )

        # Process block entities
        source_block_entities = schematicutil.get_block_data(source_file)[
            "BlockEntities"
        ]
        chunk_block_entities = process_block_entities(
            source_block_entities, max_chunk_dims, chunk_width, chunk_length
        )

        # Process chunk data
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
        )

        # Write chunks to files
        write_chunks(
            source_file,
            chunk_data,
            chunk_entities,
            chunk_block_entities,
            output_directory,
            output_name,
        )


def main():
    block_limit = int(input("Set block limit: "))
    splitter = SchematicSplitter(block_limit)
    splitter.split_schematic(input("Input filename(.schem): "))


if __name__ == "__main__":
    main()
