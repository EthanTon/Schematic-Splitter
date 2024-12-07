from math import ceil
import os
import nbtlib
import schematicutil
import varintIterator


class SchematicSplitter:
    def __init__(self, block_limit: int):
        self.block_limit = block_limit

    def get_index(self, x, y, z, width, length):
        """Calculate the correct index in the block array using full dimensions"""
        return int(x + z * width + y * width * length)

    def split_schematic(self, filename, output_directory="Output", output_name="Out"):
        file = schematicutil.load_schematic(filename)

        print(file.gzipped)

        # Get dimensions
        width, height, length = schematicutil.get_dimension(file)
        width, height, length = int(width), int(height), int(length)

        # Get offset
        offset_x, offset_y, offset_z = schematicutil.get_offset(file)
        offset_x, offset_y, offset_z = int(offset_x), int(offset_y), int(offset_z)

        size = width * height * length
        if size <= self.block_limit:
            # If original size is within limits, keep original dimensions
            chunk_width = width
            chunk_height = height
            chunk_length = length
        else:
            # Calculate dimensions to get close to block_limit
            ratio = (self.block_limit / size) ** (1/3)
    
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


        chunk_x = int(ceil(width / chunk_width))
        # chunk_y = int(ceil(height / chunk_height))
        chunk_z = int(ceil(length / chunk_length))

        blocks = schematicutil.get_block_data(file)

        block_entities = blocks["BlockEntities"]
        source_data = blocks["Data"]
        source_palette = blocks["Palette"]

        chunk = {0: []}
        chunk_offset = {0: [offset_x, offset_y, offset_z]}
        chunk_dimensions = {0: [chunk_width, chunk_height, chunk_length]}

        source_index = 0
        block_data = bytes(block & 0xFF for block in source_data)
        iter = varintIterator.VarIntIterator(block_data)

        has_next = iter.has_next()


        while(has_next):
            new_block_id = iter.__next__()

            x, y, z = schematicutil.get_local_coordinate(source_index, width, length)

            new_x = x // chunk_width
            new_y = y // chunk_height
            new_z = z // chunk_length

            file_number = self.get_index(
                new_x,
                new_y,
                new_z,
                chunk_x,
                chunk_z,
            )

            x_width = (x % chunk_width) + 1
            y_height = (y % chunk_height) + 1
            z_length = (z % chunk_length) + 1

            if not file_number in chunk:
                chunk[file_number] = []
                chunk_offset[file_number] = [
                    (x + offset_x),
                    (y + offset_y),
                    (z + offset_z),
                ]
                chunk_dimensions[file_number] = [
                    x_width,
                    y_height,
                    z_length,
                ]

            # Update maximum dimensions for the current file's chunk
            chunk_dimensions[file_number] = [
                int(max(x_width, chunk_dimensions[file_number][0])),
                int(max(y_height, chunk_dimensions[file_number][1])),
                int(max(z_length, chunk_dimensions[file_number][2])),
            ]

            chunk[file_number].append(source_data[source_index])

            has_next = iter.has_next()
            source_index += 1

        # Make new files

        for file_num in chunk.keys():

            output = file

            output["Schematic"]["Width"] = nbtlib.Short(chunk_dimensions[file_num][0])
            output["Schematic"]["Height"] = nbtlib.Short(chunk_dimensions[file_num][1])
            output["Schematic"]["Length"] = nbtlib.Short(chunk_dimensions[file_num][2])

            print(file_num,output["Schematic"]["Width"],output["Schematic"]["Height"],output["Schematic"]["Length"])

            output["Schematic"]["Blocks"]["Data"] = nbtlib.ByteArray(chunk[file_num])

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
