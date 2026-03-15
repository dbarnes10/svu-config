# Configuration Generator Mode

## Overview

The `--config` option generates a production-ready platform configuration without running tests.

## Usage

```bash
python3 wall_platform_builder.py --config
```

## What It Does

The configuration generator:

1. **Creates wall cameras** (9 cameras matching the wall geometry)
2. **Allocates cameras to nodes:**
   - nodeL: 4 cameras (L_004, L_003, L_002, L_001)
   - nodeC: 1 camera (disp_centre, spanning both outputs)
   - nodeR: 4 cameras (R_001, R_002, R_003, R_004)
3. **Adds over-render** (200px to edge cameras L_004 and R_004)
4. **Generates platform JSON** (complete configuration)
5. **Generates output mapping** (output rectangle to wall pixel mapping)
6. **Saves configuration files**

## Generated Files

### 1. `platform_config.json` (5.1 KB)
Complete platform configuration including:
- All camera displays (geometry and pixel widths)
- Viewports for each node
- Node assignments
- Machine list

**Format:**
```json
{
  "platforms": {
    "CurvedWall": {
      "displays": {...},
      "viewports": {...},
      "nodes": {...},
      "head": "head"
    }
  },
  "machines": [...]
}
```

### 2. `output_mapping.json` (2.8 KB)
Maps each node's output rectangles to wall pixels.

**Format:**
```json
{
  "nodeL": {
    "output1": [
      {
        "output_rect": [0, 0, 1920, 2160],
        "wall_rect": [0, 0, 2120, 2160],
        "camera": "disp_L_004"
      },
      ...
    ],
    "output2": [...]
  },
  ...
}
```

### 3. `config_summary.json` (465 bytes)
High-level summary of the configuration.

**Format:**
```json
{
  "wall_width_px": 19200,
  "wall_height_px": 2160,
  "total_cameras": 9,
  "nodes": ["nodeL", "nodeC", "nodeR"],
  "node_details": {
    "nodeL": {
      "cameras": 4,
      "output1_rectangles": 3,
      "output2_rectangles": 1
    },
    ...
  }
}
```

## Configuration Details

### Wall Geometry
- **Total width:** 19,200 pixels (30.0m at 0.64 ppmm)
- **Height:** 2,160 pixels (3.375m)
- **Cameras:** 9 total

### Node Configuration
- **nodeL:** 4,800 pixels (4 cameras)
  - Output 1: 3 cameras (L_004, L_003, L_002)
  - Output 2: 1 camera (L_001)
  
- **nodeC:** 9,600 pixels (1 camera, spanning)
  - Output 1: disp_centre left portion (3,840px)
  - Output 2: disp_centre right portion (5,760px)
  
- **nodeR:** 4,800 pixels (4 cameras)
  - Output 1: 4 cameras (R_001, R_002, R_003, R_004 partial)
  - Output 2: R_004 remainder

### Over-Render
- **L_004 left edge:** +200 pixels (312.5mm)
- **R_004 right edge:** +200 pixels (312.5mm)

## Comparison with Test Mode

| Mode | Command | Purpose | Output |
|------|---------|---------|--------|
| **Test** | `--test` | Run comprehensive tests | `platform_test_output.json` |
| **Config** | `--config` | Generate production config | `platform_config.json`, `output_mapping.json`, `config_summary.json` |

## Example Output

```
================================================================================
WALL PLATFORM CONFIGURATION GENERATOR
================================================================================

[1] Creating wall cameras...
    Created 9 cameras

[2] Setting up node allocator...

[3] Allocating cameras to nodes...
    nodeL: 4 cameras (4800px)
    nodeC: 1 camera (9600px, spanning)
    nodeR: 4 cameras (4800px)

[4] Adding over-render to edge cameras...
    Added 200px over-render to L_004 (left) and R_004 (right)

[5] Generating platform JSON...
    Generated complete platform configuration

[6] Generating output to wall mapping...
    Generated output mapping for 3 nodes

[7] Saving configuration files...
    ✓ platform_config.json
    ✓ output_mapping.json
    ✓ config_summary.json

================================================================================
CONFIGURATION COMPLETE ✓
================================================================================

Generated files:
  - platform_config.json      (Complete platform configuration)
  - output_mapping.json       (Output to wall pixel mapping)
  - config_summary.json       (Configuration summary)

================================================================================
```

## Next Steps

After generating the configuration:

1. **Review** `config_summary.json` for an overview
2. **Integrate** `platform_config.json` into your rendering system
3. **Use** `output_mapping.json` to map output rectangles to wall pixels
4. **Customize** if needed using the provided functions (split, join, move, etc.)

## Customization

To create a custom configuration, use the script as a library:

```python
from wall_platform_builder import *

# Create and customize
displays = create_wall_cameras()
split_camera(displays, "disp_centre", 50)  # Custom split
# ... more customization ...

# Then generate
allocator = NodeAllocator()
allocator.set_displays(displays)
# ... allocate cameras ...

platform = generate_platform_json(displays, allocator)
```
