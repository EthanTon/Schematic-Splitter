from math import ceil
import os
import nbtlib
from numpy import double
import schematicutil
import varintIterator
import varintWriter


class SchematicSplitter:
    def __init__(self, block_limit: int):
        self.block_limit = block_limit

    def get_chunk_dimensions(
        self, width: int, height: int, length: int
    ) -> tuple[int, int, int]:
        size = width * height * length

        if size <= self.block_limit:
            # If original size is within limits, keep original dimensions
            chunk_width = width
            chunk_height = height
            chunk_length = length
        else:
            # Calculate dimensions to get close to block_limit
            ratio = (self.block_limit / size) ** (1 / 3)
            # Initial chunk sizes
            chunk_width = max(1, ceil(width * ratio))
            chunk_height = max(1, ceil(height * ratio))
            chunk_length = max(1, ceil(length * ratio))
            # Iteratively reduce dimensions if still over block limit
            while (chunk_width * chunk_height * chunk_length) > self.block_limit:
                max_dim = max(chunk_width, chunk_height, chunk_length)
                if chunk_width == max_dim:
                    chunk_width = max(1, chunk_width - 1)
                elif chunk_height == max_dim:
                    chunk_height = max(1, chunk_height - 1)
                else:
                    chunk_length = max(1, chunk_length - 1)

        return chunk_width, chunk_height, chunk_length

    def split_schematic(self, filename, output_directory="Output", output_name="Out"):
        source_file = schematicutil.load_schematic(filename)

        # Get dimensions
        source_width, source_height, source_length = schematicutil.get_dimension(
            source_file
        )
        source_width, source_height, source_length = (
            int(source_width),
            int(source_height),
            int(source_length),
        )

        # Get offset
        source_offset_x, source_offset_y, source_offset_z = schematicutil.get_offset(
            source_file
        )
        source_offset_x, source_offset_y, source_offset_z = (
            int(source_offset_x),
            int(source_offset_y),
            int(source_offset_z),
        )

        max_chunk_width, max_chunk_height, max_chunk_length = self.get_chunk_dimensions(
            source_width, source_height, source_length
        )

        chunk_width = int(ceil(source_width / max_chunk_width))
        # chunk_height = int(ceil(source_height / max_chunk_height))
        chunk_length = int(ceil(source_length / max_chunk_length))

        source_blocks = schematicutil.get_block_data(source_file)
        source_entities = schematicutil.get_entities(source_file)

        source_data = source_blocks["Data"]
        block_data = bytes(block & 0xFF for block in source_data)
        source_palette = schematicutil.swap_palette(dict(source_blocks["Palette"]))
        source_block_entities = source_blocks["BlockEntities"]

        chunk = {0: []}
        chunk_offset = {0: [source_offset_x, source_offset_y, source_offset_z]}
        chunk_dimensions = {0: [max_chunk_width, max_chunk_height, max_chunk_length]}
        chunk_palette = {0: {}}
        chunk_block_entities = {}
        chunk_entities = {}

        # Entity Handler
        for item in source_entities:
            pos = item["Pos"]

            source_x, source_y, source_z = (
                double(pos[0]),
                double(pos[1]),
                double(pos[2]),
            )

            chunk_x = int(source_x // max_chunk_width)
            chunk_y = int(source_y // max_chunk_height)
            chunk_z = int(source_z // max_chunk_length)

            file_number = schematicutil.get_index(
                chunk_x,
                chunk_y,
                chunk_z,
                chunk_width,
                chunk_length,
            )

            x = nbtlib.Double(source_x - (chunk_x * max_chunk_width))
            y = nbtlib.Double(source_y - (chunk_y * max_chunk_height))
            z = nbtlib.Double(source_z - (chunk_z * max_chunk_length))

            if not file_number in chunk_entities:
                chunk_entities[file_number] = []

            item["Pos"] = nbtlib.List([x, y, z])
            print(file_number)
            chunk_entities[file_number].append(nbtlib.Compound(item))

        # Block Entity Handler
        for item in source_block_entities:
            pos = item["Pos"]

            source_x, source_y, source_z = int(pos[0]), int(pos[1]), int(pos[2])

            chunk_x = source_x // max_chunk_width
            chunk_y = source_y // max_chunk_height
            chunk_z = source_z // max_chunk_length

            file_number = schematicutil.get_index(
                chunk_x,
                chunk_y,
                chunk_z,
                chunk_width,
                chunk_length,
            )

            x = source_x % max_chunk_width
            y = source_y % max_chunk_height
            z = source_z % max_chunk_length

            if not file_number in chunk_block_entities:
                chunk_block_entities[file_number] = []

            item["Pos"] = nbtlib.tag.IntArray([x, y, z])
            chunk_block_entities[file_number].append(nbtlib.Compound(item))

        # Block and Palette Handler
        source_index = 0

        iter = varintIterator.VarIntIterator(block_data)

        has_next = iter.has_next()
        while has_next:

            source_x, source_y, source_z = schematicutil.get_local_coordinate(
                source_index, source_width, source_length
            )

            chunk_x = source_x // max_chunk_width
            chunk_y = source_y // max_chunk_height
            chunk_z = source_z // max_chunk_length

            file_number = schematicutil.get_index(
                chunk_x,
                chunk_y,
                chunk_z,
                chunk_width,
                chunk_length,
            )

            x_width = (source_x % max_chunk_width) + 1
            y_height = (source_y % max_chunk_height) + 1
            z_length = (source_z % max_chunk_length) + 1

            if not file_number in chunk:
                chunk[file_number] = []
                chunk_palette[file_number] = {}
                chunk_offset[file_number] = [
                    (source_x + source_offset_x),
                    (source_y + source_offset_y),
                    (source_z + source_offset_z),
                ]
                chunk_dimensions[file_number] = [
                    x_width,
                    y_height,
                    z_length,
                ]

            # Update maximum dimensions for the current chunk
            chunk_dimensions[file_number] = [
                int(max(x_width, chunk_dimensions[file_number][0])),
                int(max(y_height, chunk_dimensions[file_number][1])),
                int(max(z_length, chunk_dimensions[file_number][2])),
            ]

            # Update block palette for the current chunk
            new_block_id = iter.__next__()
            block_type = source_palette[new_block_id]
            if not block_type in chunk_palette[file_number]:
                block_number = len(chunk_palette[file_number])
                chunk_palette[file_number][block_type] = nbtlib.Int(block_number)
            else:
                block_number = int(chunk_palette[file_number][block_type])

            chunk[file_number].append(block_number)

            has_next = iter.has_next()
            source_index += 1

        # Make new files

        for file_num in chunk.keys():

            output = source_file

            output["Schematic"]["Width"] = nbtlib.Short(chunk_dimensions[file_num][0])
            output["Schematic"]["Height"] = nbtlib.Short(chunk_dimensions[file_num][1])
            output["Schematic"]["Length"] = nbtlib.Short(chunk_dimensions[file_num][2])

            # print(
            #     file_num,
            #     output["Schematic"]["Width"],
            #     output["Schematic"]["Height"],
            #     output["Schematic"]["Length"],
            # )
            if file_num in chunk_block_entities:
                output["Schematic"]["Blocks"]["BlockEntities"] = nbtlib.List(
                    chunk_block_entities[file_num]
                )
            else:
                output["Schematic"]["Blocks"]["BlockEntities"] = nbtlib.List([])

            if file_num in chunk_entities:
                output["Schematic"]["Entities"] = nbtlib.List(chunk_entities[file_num])
            else:
                output["Schematic"]["Entities"] = nbtlib.List([])

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

            output["Schematic"]["Offset"] = nbtlib.IntArray(chunk_offset[file_num])

            output_location = (
                output_directory + "/" + output_name + str(file_num) + ".schem"
            )

            if not os.path.isdir(output_directory):
                os.mkdir(output_directory)

            output.save(output_location)


def main():
    # Set block limit
    block_limit = int(input("Set block limit: "))
    splitter = SchematicSplitter(block_limit)
    splitter.split_schematic(input("Input filename(.schem): "))


if __name__ == "__main__":
    main()
