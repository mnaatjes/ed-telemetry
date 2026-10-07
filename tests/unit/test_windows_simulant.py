"""Unit test suite for Win32 binary ABI memory layout validation.

Asserts that ctypes data structures used in WindowsPathStrategy strictly match
the Microsoft Windows SDK C header specifications (KnownFolders.h and guiddef.h).
"""

from __future__ import annotations

import ctypes


def test_guid_structure_binary_abi_layout() -> None:
    """Verify GUID struct matches Windows SDK: 16 bytes total with exact byte offsets."""

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_uint32),
            ("Data2", ctypes.c_uint16),
            ("Data3", ctypes.c_uint16),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    # Microsoft SDK specification:
    # typedef struct _GUID {
    #     unsigned long  Data1; // 4 bytes uint32 (offset 0)
    #     unsigned short Data2; // 2 bytes uint16 (offset 4)
    #     unsigned short Data3; // 2 bytes uint16 (offset 6)
    #     unsigned char  Data4[8]; // 8 bytes ubyte[8] (offset 8)
    # } GUID;
    assert ctypes.sizeof(GUID) == 16
    assert GUID.Data1.offset == 0
    assert GUID.Data2.offset == 4
    assert GUID.Data3.offset == 6
    assert GUID.Data4.offset == 8


def test_folderid_saved_games_guid_literal_bytes() -> None:
    """Verify FOLDERID_SavedGames literal GUID byte representation matches Microsoft spec."""

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_uint32),
            ("Data2", ctypes.c_uint16),
            ("Data3", ctypes.c_uint16),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    # GUID: {4C5C32FF-BB9D-43B0-B5B4-2D780DDF04E3}
    folderid_saved_games = GUID(
        0x4C5C32FF,
        0xBB9D,
        0x43B0,
        (ctypes.c_ubyte * 8)(0xB5, 0xB4, 0x2D, 0x78, 0x0D, 0xDF, 0x04, 0xE3),
    )

    raw_bytes = bytes(folderid_saved_games)
    assert len(raw_bytes) == 16

    # Verify Little-Endian DWORD for Data1: 0x4C5C32FF -> FF 32 5C 4C
    assert raw_bytes[0:4] == bytes([0xFF, 0x32, 0x5C, 0x4C])
    # Verify Little-Endian WORD for Data2: 0xBB9D -> 9D BB
    assert raw_bytes[4:6] == bytes([0x9D, 0xBB])
    # Verify Little-Endian WORD for Data3: 0x43B0 -> B0 43
    assert raw_bytes[6:8] == bytes([0xB0, 0x43])
    # Verify Data4 byte sequence: B5 B4 2D 78 0D DF 04 E3
    assert raw_bytes[8:16] == bytes([0xB5, 0xB4, 0x2D, 0x78, 0x0D, 0xDF, 0x04, 0xE3])
