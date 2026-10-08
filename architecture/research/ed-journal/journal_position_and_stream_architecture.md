---
title: "Repository Research: ed-journal Position Tracking & 64-bit Integer Safety"
tags: ["research", "reference", "ed-journal", "offset-tracking", "bigint", "stream"]
created_at: "2026-10-08"
last_updated_at: "2026-10-08"
---

# Repository Research: ed-journal Position Tracking & 64-bit Integer Safety

## 1. Diagnostic: Core Mechanics

`kayahr/ed-journal` addresses two of the most technically difficult aspects of Elite Dangerous journal ingestion:
1. **Accurate Stream Resumption:** Tracking precise offsets without relying on fragile relative seek operations.
2. **64-bit Integer Overflow:** Protecting large astronomical and game IDs from standard IEEE-754 floating-point truncation.

## 2. Theory: Monotonic Position Tracking (`JournalPosition.ts`)

Instead of treating offset tracking as an afterthought or storing only file size, `ed-journal` models state as a first-class composite record:

```typescript
export interface JournalPosition {
    file: string;    // Filename of the active journal file
    offset: number;  // Absolute byte offset in the file
    line: number;    // 1-indexed line number
}
```

### Stream Startup & Fast Forward
The `Journal.open()` factory method supports declarative stream positioning:
* `position: "start"`: Seeks to offset 0 of the oldest journal file in the directory.
* `position: "end"`: Discovers the newest journal file and seeks directly to `file_size`, reading only future events as they occur.
* `position: "FSDJump"`: Traverses backward through journal history to locate the most recent occurrence of a specific event (e.g. finding current star system location without replaying historical megabytes of exploration scans).

### Monotonic Line Reading (`LineReader.ts`)
Rather than reading the entire file or using negative seek relative to `SEEK_END`, `LineReader` maintains an internal byte buffer:
1. Reads chunks sequentially from disk starting at `lastPosition.offset`.
2. Identifies `\n` line delimiters within the buffer.
3. Yields exact line slices, advancing `offset` by `slice.byteLength` and incrementing `line` count monotonically.
4. Survives partial line writes: if a buffer ends without a trailing newline, the incomplete slice is held in memory until the next read cycle completes the line.

## 3. Analysis: 64-bit Integer Precision Safety (`jsonReviver`)

Standard JSON parsers (e.g., standard JavaScript `JSON.parse()` or untyped Python float loaders) parse numbers into 64-bit IEEE-754 floats.

### The Inherent Problem with Elite Dangerous IDs
* JavaScript's `Number.MAX_SAFE_INTEGER` is $2^{53} - 1 = 9,007,199,254,740,991$.
* Frontier's internal Stellar Forge `SystemAddress` values and market transaction IDs frequently exceed this limit (e.g., `9470537180601`, `18446744073709551615` for unassigned mission IDs, or high 64-bit market addresses).
* If parsed into standard floating-point representations, the lowest bits are truncated, corrupting system addresses and breaking coordinate lookup keys!

### ed-journal's Solution
In `src/main/Journal.ts`:
```typescript
function jsonReviver(key: string, value: unknown, context?: { source: string }): unknown {
    if (context != null && typeof value === "number" &&
       (value > Number.MAX_SAFE_INTEGER || value < Number.MIN_SAFE_INTEGER)) {
        const source = context.source;
        if (key.endsWith("ID") || key.endsWith("Address")) {
            return BigInt(source);
        } else if (/^[-+]?\d+$/.test(source)) {
            throw new JournalError(
                `Value of property '${key}' looks like a bigint (${source}) ` +
                `but was parsed as an imprecise number (${value})`
            );
        }
    }
    return value;
}
```

## 4. Remediation: Architectural Guidance for ed-telemetry

1. **Python Integer Safety:**
   Unlike JavaScript, Python natively supports arbitrary precision integers (`int`). However, deserialization libraries that bridge into C/C++ or fast JSON parsers (e.g. `orjson` or `ujson`) must ensure integers are parsed as signed/unsigned 64-bit integers without float conversion.
2. **`FileIngestionEvent` State Schema:**
   The composite `JournalPosition` (`file`, `offset`, `line`) maps directly to `ed-telemetry`'s `FileIngestionEvent` metadata, ensuring downstream consumers know the exact byte range and line number that produced each event.
