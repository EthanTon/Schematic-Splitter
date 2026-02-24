import amulet_nbt
from amulet_nbt import CompoundTag, ListTag, IntArrayTag
from typing import Tuple, Optional, Dict


def load_schematic(filename: str) -> Optional[amulet_nbt.NamedTag]:
    """
    Load a schematic file and return its NBT data structure.

    Args:
        filename: Path to the .schem file

    Returns:
        NamedTag or None if file extension is incorrect
    """
    if not filename.endswith(".schem"):
        return None

    named_tag = amulet_nbt.load(filename, compressed=True)

    if "Schematic" not in named_tag.compound:
        raise ValueError("The provided file does not contain a 'Schematic' root tag.")

    return named_tag


def get_block_data(file: amulet_nbt.NamedTag) -> CompoundTag:
    return file.compound["Schematic"]["Blocks"]


def get_biome_data(file: amulet_nbt.NamedTag) -> Optional[CompoundTag]:
    schematic = file.compound["Schematic"]
    return schematic["Biomes"] if "Biomes" in schematic else None


def get_entities(file: amulet_nbt.NamedTag) -> ListTag:
    schematic = file.compound["Schematic"]
    return schematic["Entities"] if "Entities" in schematic else ListTag()


def get_dimension(file: amulet_nbt.NamedTag) -> Tuple[int, int, int]:
    schematic = file.compound["Schematic"]
    return int(schematic["Width"]), int(schematic["Height"]), int(schematic["Length"])


def get_offset(file: amulet_nbt.NamedTag) -> Tuple[int, int, int]:
    offset = file.compound["Schematic"]["Offset"]
    return int(offset[0]), int(offset[1]), int(offset[2])


def get_index(x: int, y: int, z: int, width: int, length: int) -> int:
    """Calculate the linear index from chunk grid coordinates."""
    return x + z * width + y * width * length


def get_local_coordinate(index: int, width: int, length: int) -> Tuple[int, int, int]:
    """
    Convert linear index to local coordinates.

    Args:
        index: Linear index in the schematic data
        width: Width of the schematic
        length: Length of the schematic

    Returns:
        (x, y, z) local coordinates
    """
    wl = width * length
    y, remainder = divmod(index, wl)
    z, x = divmod(remainder, width)
    return x, y, z


def get_relative_coordinates(
    index: int,
    width: int,
    length: int,
    offsetX: int = 0,
    offsetY: int = 0,
    offsetZ: int = 0,
) -> Tuple[int, int, int]:
    """Get coordinates relative to offset."""
    x, y, z = get_local_coordinate(index, width, length)
    return x + offsetX, y + offsetY, z + offsetZ


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
    """Get global coordinates including offset and origin."""
    x, y, z = get_relative_coordinates(index, width, length, offsetX, offsetY, offsetZ)
    return x + originX, y + originY, z + originZ


def swap_palette(source_palette) -> Dict[int, str]:
    """Swap palette from {name: IntTag(id)} to {id: name}."""
    return {int(tag): name for name, tag in source_palette.items()}
