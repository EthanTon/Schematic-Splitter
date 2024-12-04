from math import floor
import os
import nbtlib
import schematicutil


class SchematicSplitter:
    def __init__(self, block_limit: int):
        self.block_limit = block_limit

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
        chunk = []
        for y in range(chunkHeight):
            for z in range(chunkLength):
                for x in range(chunkWidth):
                    # From minecraft wiki on NBT format: https://minecraft.wiki/w/Schematic_file_format
                    index = (
                        ((y + offsetHeight) * (length)) + (z + offsetLength)
                    ) * width + (x + offsetWidth)
                    chunk.append(data[index])
        return chunk

    def split_schematic(
        self, inputFile: str, outputFile: str = "Out", outputDirectory: str = "Output"
    ):
        file = schematicutil.load_schematic(inputFile)
        schematic = file["Schematic"]

        # Get data and amount of blocks(size)
        data = schematic["Blocks"]["Data"]
        size = len(data)

        if size <= self.block_limit:
            print("File does not need to be split")
            return

        # Determine the amount of split each dimension by
        numberOfFiles = size / self.block_limit
        splitFactor = 1 / (numberOfFiles ** (1 / 3))

        # Get dimensions from schematic
        width = schematic["Width"]
        height = schematic["Height"]
        length = schematic["Length"]

        # Determine new dimension for each chunk
        chunkWidth = floor(width * splitFactor)
        chunkHeight = floor(height * splitFactor)
        chunkLength = floor(length * splitFactor)

        chunkSize = chunkWidth * chunkHeight * chunkLength

        numberOfChunkWidth = width // chunkWidth
        numberOfChunkHeight = height // chunkHeight
        numberOfChunkLength = length // chunkLength

        # Get offset fom schematic
        offset = schematic["Offset"]

        offsetX = int(offset[0])
        offsetY = int(offset[1])
        offsetZ = int(offset[2])

        if not os.path.isdir(outputDirectory):
            os.mkdir(outputDirectory)

        fileNumber = 0

        # Standard Chunks
        for j in range(numberOfChunkHeight):
            for k in range(numberOfChunkLength):
                for i in range(numberOfChunkWidth):
                    # Get chunk

                    chunk = self.copy_chunk(
                        data,
                        width,
                        length,
                        chunkWidth,
                        chunkHeight,
                        chunkLength,
                        (i * chunkWidth),
                        (j * chunkHeight),
                        (k * chunkLength),
                    )
                    # Get offset
                    chunkOffset = [
                        int(offsetX + (i * chunkWidth)),
                        int(offsetY + (j * chunkHeight)),
                        int(offsetZ + (k * chunkLength)),
                    ]

                    output = file

                    output["Schematic"]["Width"] = nbtlib.Short(chunkWidth)
                    output["Schematic"]["Height"] = nbtlib.Short(chunkHeight)
                    output["Schematic"]["Length"] = nbtlib.Short(chunkLength)

                    output["Schematic"]["Blocks"]["Data"] = nbtlib.ByteArray(chunk)

                    output["Schematic"]["Offset"] = nbtlib.IntArray(chunkOffset)

                    outputLocation = (
                        outputDirectory + "/" + outputFile + str(fileNumber) + ".schem"
                    )

                    fileNumber += 1

                    output.save(outputLocation)

                    chunk = []
                    chunkOffset = []

        # # Get origin from schematic
        # origin = schematic["Metadata"]["WorldEdit"]["Origin"]  # World Edit only

        # originX = int(origin[0])
        # originY = int(origin[1])
        # originZ = int(origin[2])


def main():
    # Set block limit
    block_limit = int(input("Set block limit: "))  # Adjust this value as needed
    splitter = SchematicSplitter(block_limit)
    splitter.split_schematic(input("Input filename(.schem): "))


if __name__ == "__main__":
    main()
