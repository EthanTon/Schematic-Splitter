import nbtlib
from typing import List, Tuple, Optional


def load_schematic(filename: str) -> Optional[nbtlib.File]:
    """
    Load a schematic file and return its NBT data structure.

    Args:
        filename (str): Path to the .schem file

    Returns:
        nbtlib.File: Loaded NBT file object, or None if file extension is incorrect
    """
    if filename.split(".")[-1] != "schem":
        return None
    return nbtlib.load(filename, gzipped=True)


def get_block_data(file: nbtlib.tag.Compound) -> nbtlib.tag.Compound:
    return file["Schematic"]["Blocks"]


def get_dimension(
    file: nbtlib.tag.Compound,
) -> Tuple[nbtlib.tag.Short, nbtlib.tag.Short, nbtlib.tag.Short]:
    width = file["Schematic"]["Width"]
    height = file["Schematic"]["Height"]
    length = file["Schematic"]["Length"]

    return (width, height, length)


def get_offset(
    file: nbtlib.tag.Compound,
) -> Tuple[nbtlib.tag.Int, nbtlib.tag.Int, nbtlib.tag.Int]:
    offsetX = file["Schematic"]["Offset"][0]
    offsetY = file["Schematic"]["Offset"][1]
    offsetZ = file["Schematic"]["Offset"][2]

    return (offsetX, offsetY, offsetZ)


def get_local_coordinate(index: int, width: int, length: int) -> Tuple[int, int, int]:
    """
    Convert linear index to local coordinates.

    Args:
        index (int): Linear index in the schematic data
        width (int): Width of the schematic
        length (int): Length of the schematic

    Returns:
        Tuple[int, int, int]: (x, y, z) local coordinates
    """
    localY = int(index / (width * length))
    localZ = int((index % (width * length)) / width)
    localX = int((index % (width * length)) % width)
    return (localX, localY, localZ)


def get_relative_coordinates(
    index: int,
    width: int,
    length: int,
    offsetX: int = 0,
    offsetY: int = 0,
    offsetZ: int = 0,
) -> Tuple[int, int, int]:
    """
    Get coordinates relative to offset.

    Args:
        index (int): Linear index in the schematic data
        width (int): Width of the schematic
        length (int): Length of the schematic
        offsetX (int): X-axis offset
        offsetY (int): Y-axis offset
        offsetZ (int): Z-axis offset

    Returns:
        Tuple[int, int, int]: (x, y, z) relative coordinates
    """
    localCoordinates = get_local_coordinate(index, width, length)
    return (
        localCoordinates[0] + offsetX,
        localCoordinates[1] + offsetY,
        localCoordinates[2] + offsetZ,
    )


def get_global_coordinates(
    index: int,
    width: int,
    length: int,
    offsetX: int = 0,
    offsetY: int = 0,
    offsetZ: int = 0,
    originX: int = 0,
    originY: int = 0,
    originZ: int = 0,
) -> Tuple[int, int, int]:
    """
    Get global coordinates including offset and origin.

    Args:
        index (int): Linear index in the schematic data
        width (int): Width of the schematic
        length (int): Length of the schematic
        offsetX (int): X-axis offset
        offsetY (int): Y-axis offset
        offsetZ (int): Z-axis offset
        originX (int): X-axis origin
        originY (int): Y-axis origin
        originZ (int): Z-axis origin

    Returns:
        Tuple[int, int, int]: (x, y, z) global coordinates
    """
    relativeCoordinates = get_relative_coordinates(
        index, width, length, offsetX, offsetY, offsetZ
    )
    return (
        relativeCoordinates[0] + originX,
        relativeCoordinates[1] + originY,
        relativeCoordinates[2] + originZ,
    )
