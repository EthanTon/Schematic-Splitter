from math import ceil, floor
import os
import nbtlib
import schematicutil


class SchematicSplitter:
    def __init__(self, block_limit: int):
        self.block_limit = block_limit

    def get_source_index(self, x, y, z, width, length):
        """Calculate the correct index in the block array using full dimensions"""
        return x + z * width + y * width * length

    def get_blockentities_in_region(
        self,
        blockEntities,
        startX,
        startY,
        startZ,
        width,
        height,
        length,
        offsetX,
        offsetY,
        offsetZ
    ):
        """
        Extract BlockEntities that fall within the specified chunk region
        and adjust their positions relative to the new chunk.
        """
        chunk_blockentities = []
        
        for blockEntity in blockEntities:
            pos = blockEntity.get('Pos', [0, 0, 0])
            x, y, z = pos
            
            # Check if BlockEntity is within chunk bounds
            if (startX <= x < startX + width and
                startY <= y < startY + height and
                startZ <= z < startZ + length):
                
                # Create a copy of the BlockEntity
                new_blockentity = blockEntity.copy()
                
                # Adjust position relative to chunk
                new_pos = [
                    x - startX,
                    y - startY,
                    z - startZ
                ]
                new_blockentity['Pos'] = nbtlib.IntArray(new_pos)
                
                chunk_blockentities.append(new_blockentity)
        
        return chunk_blockentities

    def copy_chunk(
        self,
        data,
        width,
        length,
        chunkWidth,
        chunkHeight,
        chunkLength,
        offsetWidth,
        offsetHeight,
        offsetLength,
    ):
        chunk = [0] * (chunkWidth * chunkLength * chunkHeight)

        # Iterate in Y,Z,X order to match schematic format
        for y in range(chunkHeight):
            absolute_y = y + offsetHeight
            for z in range(chunkLength):
                absolute_z = z + offsetLength
                for x in range(chunkWidth):
                    absolute_x = x + offsetWidth

                    source_index = self.get_source_index(
                        absolute_x, absolute_y, absolute_z, width, length
                    )

                    index = self.get_source_index(x, y, z, chunkWidth, chunkLength)

                    chunk[index] = data[source_index]

        return chunk

    def split_schematic(
        self, inputFile: str, outputFile: str = "Out", outputDirectory: str = "Output"
    ):
        file = schematicutil.load_schematic(inputFile)

        schematic = file["Schematic"]

        # Get data and amount of blocks(size)
        data = schematic["Blocks"]["Data"]
        size = len(data)

        print(type(data))

        if size <= self.block_limit:
            print("File does not need to be split")
            return

        # Get dimensions from schematic
        width = schematic["Width"]
        height = schematic["Height"]
        length = schematic["Length"]

        # Calculate dimensions that won't exceed block limit
        targetVolume = min(self.block_limit, width * height * length)
        splitFactor = (targetVolume / (width * height * length)) ** (1 / 3)

        # Determine new dimension for each chunk
        chunkWidth = max(1, floor(width * splitFactor))
        chunkHeight = max(1, floor(height * splitFactor))
        chunkLength = max(1, floor(length * splitFactor))

        numberOfChunkWidth = ceil(width / chunkWidth)
        numberOfChunkHeight = ceil(height / chunkHeight)
        numberOfChunkLength = ceil(length / chunkLength)

        print(f"Splitting into chunks of {chunkWidth}x{chunkHeight}x{chunkLength}")
        print(
            f"Number of chunks: {numberOfChunkWidth}x{numberOfChunkHeight}x{numberOfChunkLength}"
        )

        # Get palette and block entities
        palette = schematic["Blocks"]["Palette"]
        blockEntities = schematic["Blocks"].get("BlockEntities", [])

        # Get offset from schematic
        offset = schematic["Offset"]

        offsetX = int(offset[0])
        offsetY = int(offset[1])
        offsetZ = int(offset[2])

        if not os.path.isdir(outputDirectory):
            os.mkdir(outputDirectory)

        fileNumber = 0

        # Standard Chunks
        for j in range(numberOfChunkHeight):
            startY = j * chunkHeight
            actual_height = min(chunkHeight, height - startY)

            for k in range(numberOfChunkLength):
                startZ = k * chunkLength
                actual_length = min(chunkLength, length - startZ)

                for i in range(numberOfChunkWidth):
                    startX = i * chunkWidth
                    actual_width = min(chunkWidth, width - startX)

                    if actual_width <= 0 or actual_height <= 0 or actual_length <= 0:
                        continue

                    chunk = self.copy_chunk(
                        data,
                        width,
                        length,
                        actual_width,
                        actual_height,
                        actual_length,
                        startX,
                        startY,
                        startZ,
                    )

                    # Calculate offset for this chunk
                    chunkOffset = [
                        offsetX + (i * chunkWidth),
                        offsetY + (j * chunkHeight),
                        offsetZ + (k * chunkLength),
                    ]

                    # Handle BlockEntities for this chunk
                    chunk_blockentities = self.get_blockentities_in_region(
                        blockEntities,
                        startX,
                        startY,
                        startZ,
                        actual_width,
                        actual_height,
                        actual_length,
                        chunkOffset[0],
                        chunkOffset[1],
                        chunkOffset[2]
                    )
                    # Create output schematic
                    output = file
                    output["Schematic"]["Width"] = nbtlib.Short(actual_width)
                    output["Schematic"]["Height"] = nbtlib.Short(actual_height)
                    output["Schematic"]["Length"] = nbtlib.Short(actual_length)
                    output["Schematic"]["Blocks"]["Data"] = nbtlib.ByteArray(chunk)
                    output["Schematic"]["Blocks"]["BlockEntities"] = nbtlib.List[nbtlib.Compound](chunk_blockentities)
                    output["Schematic"]["Blocks"]["Palette"] = palette
                    output["Schematic"]["Offset"] = nbtlib.IntArray(chunkOffset)

                    # Save chunk
                    outputLocation = os.path.join(
                        outputDirectory, f"{outputFile}{fileNumber}.schem"
                    )

                    output.save(outputLocation, gzipped=True)
                    fileNumber += 1


def main():
    # Set block limit
    block_limit = int(input("Set block limit: "))
    splitter = SchematicSplitter(block_limit)
    splitter.split_schematic(input("Input filename(.schem): "))


if __name__ == "__main__":
    main()
