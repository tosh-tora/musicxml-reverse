# Direction Element Multiplication Analysis: 威風堂々 Viola Part

## Summary

The reversal process is creating **12 extra direction elements** (24 → 36), representing a **50% increase**.

## Key Findings

### 1. Empty Word Direction Elements Created

The primary issue is the creation of **14 new empty word direction elements** `(('words', ''),)`:
- These did not exist in the input file (0 instances)
- They appear in the output file as placeholder directions
- They are always paired with sound attributes (tempo settings)

### 2. Pattern of Multiplication

When a tempo/expression marking exists in the input, the output shows:
1. **3 new empty word directions** with the tempo sound attribute
2. **The original word directions** preserved but with sound attributes removed

**Example - Measure 13 (originally Measure 41):**

Input (Measure 41):
```
M41: 6 directions total
- Empty direction (above)
- "Tempo primo." with sound:[tempo=120] (above)
- "Tempo primo." with sound:[tempo=120] (below)
- "Tempo primo." with sound:[tempo=120] (below)
- Empty direction (below)
- "div." (above)
```

Output (Measure 13):
```
M13: 9 directions total (+3 extra)
- Empty word with sound:[tempo=120] (above)
- Empty word with sound:[tempo=120] (below)
- Empty word with sound:[tempo=120] (below)
- Empty direction (above)
- "Tempo primo." without sound (above)
- "Tempo primo." without sound (below)
- "Tempo primo." without sound (below)
- Empty direction (below)
- "div." (above)
```

### 3. Affected Measures

| Output Measure | Original Measure | Expression | Extra Directions | Pattern |
|----------------|------------------|------------|------------------|---------|
| 9 | 45 | "Più mosso." | +3 | Empty words with tempo=126 + original words |
| 13 | 41 | "Tempo primo." | +3 | Empty words with tempo=120 + original words |
| 20 | 34 | "rit." | +3 | Empty words with tempo=92 + original words |
| 25 | 29 | "(allargando)" | +1 | Empty words with tempo=92 + original words (wedge:stop missing) |
| 53 | 1 | "Molto Maestoso." | +3 | Empty words with tempo=92 + original words |

### 4. Lost Elements

Two wedge elements were lost:
- `wedge:crescendo` from Measure 28 (not found in output)
- `wedge:stop` from Measure 29 (not found in output)

## Root Cause Analysis

The reversal process is **splitting direction elements** during music21's MusicXML serialization (in `score.write('musicxml')` and `score.write('mxl')` calls in `reverse_score.py`).

**The bug is NOT in the reversal code itself**, but in how **music21 library serializes direction elements back to MusicXML**:

1. **For each original direction with words + sound**:
   - music21 creates a **new direction** with empty `<words />` + the `<sound>` element
   - Preserves the **original direction** with the word text but **removes** the `<sound>` element

2. **Wedge elements are lost**: Crescendo/diminuendo wedge elements are not being properly preserved through the music21 read/write cycle

3. **System attributes are removed**: `system="also-top"` and `system="only-top"` attributes are stripped during music21 processing

### Why This Happens

The `reverse_score.py` script:
1. Reads MusicXML with `converter.parse()` (music21 API)
2. Manipulates the music21 stream objects (notes, measures, etc.)
3. Writes back with `score.write('musicxml')` or `score.write('mxl')` (music21 API)

At step 3, **music21's XML serializer is incorrectly splitting direction elements** that have both word content and sound attributes. This is a known limitation/bug in music21's MusicXML export functionality.

## Technical Details - Confirmed from XML

### Original Direction Structure (Input - Measure 41, Direction 2)
```xml
<direction placement="above" system="also-top">
  <direction-type>
    <words default-x="5.5" default-y="25.4" relative-y="20"
           font-weight="bold" font-size="12">Tempo primo.</words>
  </direction-type>
  <sound tempo="120" />
</direction>
```

### Multiplied Structure (Output - Measure 13)

**NEW Direction 1 (empty words + sound):**
```xml
<direction placement="above">
  <direction-type>
    <words />
  </direction-type>
  <sound tempo="120" />
</direction>
```

**PRESERVED Direction 5 (words without sound):**
```xml
<direction placement="above">
  <direction-type>
    <words default-x="5.5" default-y="25.4" font-size="12"
           font-weight="bold" relative-y="20">Tempo primo.</words>
  </direction-type>
</direction>
```

### Same Pattern in Measure 1 → 53

**Input (Measure 1):**
```xml
<direction placement="above" system="also-top">
  <direction-type>
    <words default-x="-37.68" default-y="13.42" relative-y="20"
           font-weight="bold" font-size="12">(Molto Maestoso.)</words>
  </direction-type>
  <sound tempo="92" />
</direction>
```

**Output (Measure 53) - splits into:**

1. Empty words direction with sound:
```xml
<direction placement="above">
  <direction-type>
    <words />
  </direction-type>
  <sound tempo="92" />
</direction>
```

2. Full words direction without sound:
```xml
<direction placement="above">
  <direction-type>
    <words default-x="-37.68" default-y="13.42" font-size="12"
           font-weight="bold" relative-y="20">(Molto Maestoso.)</words>
  </direction-type>
</direction>
```

## Statistics

- **Input file**: 24 direction elements across 7 measures
- **Output file**: 36 direction elements across 7 measures
- **Net increase**: +12 elements (+50%)
- **Empty word directions created**: 14
- **Wedge elements lost**: 2

## Recommendations

### Short-term Fix (Post-processing XML)

Since the bug is in music21's MusicXML serialization, the best fix is to **post-process the XML after music21 writes it**:

1. **After `score.write()` completes**, read the output MXL/XML file
2. **Identify empty word directions** that have sound attributes
3. **Merge them back** with their corresponding word directions:
   - Find direction with `<words />` + `<sound>`
   - Find matching direction with full `<words>` but no `<sound>` (same measure, placement)
   - Merge: keep the full `<words>` and add the `<sound>` element to it
   - Delete the empty word direction

4. **Restore system attributes** from the original XML (already available in `layout_preservation.py`)

### Implementation Location

Add new function in `layout_preservation.py`:
```python
def fix_direction_multiplication(output_path: Path) -> None:
    """
    Post-process output MXL to fix music21's direction element splitting bug.

    Merges empty <words /> + <sound> directions back with their
    corresponding full word directions.
    """
```

Call this function in `reverse_score.py` after line 590 (`reversed_score.write(...)`):
```python
reversed_score.write(output_format, fp=str(output_path))
print(f"  出力: {output_path.name}")

# FIX: Post-process to merge split direction elements
fix_direction_multiplication(output_path)
```

### Long-term Fix

Consider contributing a patch to the music21 library to fix the MusicXML direction serialization bug, or switch to a lower-level XML manipulation approach that bypasses music21's serializer for direction elements.

### Additional Fixes Needed

1. **Preserve wedge elements**: Investigate why crescendo/diminuendo wedges are lost
2. **Maintain system attributes**: Store and restore `system="also-top"` and `system="only-top"` attributes from original XML
