#!/usr/bin/env python3
"""
Curved Wall Platform Builder
Comprehensive tool for building curved wall display platforms with:
- Camera generation from wall specs
- Camera splitting and joining
- Node allocation and viewport management
- Over-render region insertion
- Complete platform JSON output
"""

import json
import math
import copy
from typing import Dict, List, Tuple, Optional

# ============================================================================
# WALL PARAMETERS (can be overridden)
# ============================================================================

PPMM = 0.64              # Pixels per millimeter
PANEL_HEIGHT_MM = 3375   # Wall height
PANEL_Y_MM = 0.0         # Y position of panels
DIST_MM = 3500           # Viewing distance
OUTER_FLAT_MM = 3675     # 3m outer flat section
CURVE_RADIUS_MM = 2865   # Curve radius
CURVE_ANGLE_DEG = 90     # Total curve angle
INNER_FLAT_MM = 7575     # 7.5m inner flat section
CURVE_SEGMENTS = 3       # Number of curve segments
NODE_WIDTH_PX = 7680     # Dual 4K outputs per node
OUTPUT_WIDTH_PX = 3840   # Single 4K output

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def pt(x, y, z):
    """Round point coordinates."""
    return [round(x, 3), round(y, 3), round(z, 3)]


# ============================================================================
# 1. CREATE CAMERAS FROM WALL SPEC
# ============================================================================

def create_wall_cameras() -> Dict:
    """
    Generate all camera displays for the curved wall.
    
    Returns:
        Dictionary of camera displays with geometry and pixel widths
    """
    displays = {}
    
    # Curve parameters
    # screen curve of 90 degrees is made up of 30 sections, 96 pixels each, at PPMM.
    curve90_px = 30 * 96
    curve90_mm = curve90_px / PPMM
    #print(f"curve90_px = {curve90_px}, length = {curve90_mm}")

    angle_per_segment = CURVE_ANGLE_DEG / CURVE_SEGMENTS
    delta_yaw = math.radians(angle_per_segment)

    # the exact number of pixels taken to turn 90 degrees must be shared amongst n_segments
    arc_per_segment_mm = curve90_mm / CURVE_SEGMENTS
    chord_per_segment_mm = curve90_mm / CURVE_SEGMENTS
    #arc_per_segment_mm = CURVE_RADIUS_MM * math.radians(angle_per_segment)
    #chord_per_segment_mm = 2 * CURVE_RADIUS_MM * math.sin(delta_yaw / 2)
    
    # Build segments (right side, centre to outer)
    segments_right = []
    for i in range(CURVE_SEGMENTS):
        yaw_deg = angle_per_segment * (i + 0.5)
        #print(f"yaw_deg = {yaw_deg}")
        segments_right.append(('curve', chord_per_segment_mm, yaw_deg, arc_per_segment_mm))
    segments_right.append(('flat', OUTER_FLAT_MM, CURVE_ANGLE_DEG, None))
    
    # Position right side cameras
    prev_x, prev_z, current_yaw = INNER_FLAT_MM, 0.0, 0.0
    
    for idx, (seg_type, width_mm, yaw_deg, arc_mm) in enumerate(segments_right):
        if seg_type == 'flat':
            cx = prev_x + (width_mm / 2) * math.cos(current_yaw)
            cz = prev_z + (width_mm / 2) * math.sin(current_yaw)
            prev_x += width_mm * math.cos(current_yaw)
            prev_z += width_mm * math.sin(current_yaw)
        else:
            panel_yaw = current_yaw + delta_yaw / 2
            cx = prev_x + (width_mm / 2) * math.cos(panel_yaw)
            cz = prev_z + (width_mm / 2) * math.sin(panel_yaw)
            prev_x = cx + (width_mm / 2) * math.cos(panel_yaw)
            prev_z = cz + (width_mm / 2) * math.sin(panel_yaw)
            current_yaw += delta_yaw
            yaw_deg = math.degrees(panel_yaw)
        
        # Create right camera
        W = width_mm / 1000.0
        H = PANEL_HEIGHT_MM / 1000.0
        cx_m, cz_m = cx / 1000.0, cz / 1000.0
        cy_m = PANEL_Y_MM / 1000.0
        yaw_rad = math.radians(yaw_deg)
        
        local_ul = (-W/2, H/2, 0)
        local_ll = (-W/2, -H/2, 0)
        local_lr = (W/2, -H/2, 0)
        
        def transform(lx, ly, lz):
            rx = lx * math.cos(yaw_rad) - lz * math.sin(yaw_rad)
            rz = lx * math.sin(yaw_rad) + lz * math.cos(yaw_rad)
            return (cx_m + rx, cy_m + ly, cz_m + rz)
        
        ul, ll, lr = transform(*local_ul), transform(*local_ll), transform(*local_lr)
        measurement_mm = arc_mm if arc_mm else width_mm
        
        name = f"disp_R_{idx+1:03d}"
        displays[name] = {
            "type": "offaxis",
            "ul": pt(ul[0], ul[1], ul[2] - DIST_MM/1000.0),
            "ll": pt(ll[0], ll[1], ll[2] - DIST_MM/1000.0),
            "lr": pt(lr[0], lr[1], lr[2] - DIST_MM/1000.0),
            "width_px": round(measurement_mm * PPMM)
        }
    
    # Mirror for left side
    for idx in range(len(segments_right)):
        right_name = f"disp_R_{idx+1:03d}"
        left_name = f"disp_L_{idx+1:03d}"
        r = displays[right_name]
        
        # When mirroring, the right camera's right edge becomes the left camera's left edge
        # Left camera ul should have same x as ll (left edge)
        # ul is at same x,z as lr but at upper y
        displays[left_name] = {
            "type": "offaxis",
            "ul": [-r['lr'][0], r['ul'][1], r['lr'][2]],  # Upper corner at same x,z as right's lr
            "ll": [-r['lr'][0], r['lr'][1], r['lr'][2]],  # Mirror of right's lr
            "lr": [-r['ll'][0], r['ll'][1], r['ll'][2]],  # Mirror of right's ll
            "width_px": r['width_px']
        }
    
    # Centre camera
    centre_width_mm = INNER_FLAT_MM * 2
    W = centre_width_mm / 1000.0
    H = PANEL_HEIGHT_MM / 1000.0
    cz = 0.0 - DIST_MM / 1000.0
    
    displays["disp_centre"] = {
        "type": "offaxis",
        "ul": [-W/2, H/2, cz],
        "ll": [-W/2, -H/2, cz],
        "lr": [W/2, -H/2, cz],
        "width_px": round(centre_width_mm * PPMM)
    }

    tw = 0
    for key, value in displays.items():
        w = value["width_px"]
        tw += w
        print(f"display {key} width_px = {w}")

    print(f"Total display width = {tw} pixels")
    
    return displays


# ============================================================================
# 2. SPLIT CAMERA AT PERCENTAGE
# ============================================================================

def split_camera(displays: Dict, camera_name: str, split_percent: float) -> Tuple[str, str]:
    """
    Split a camera at a percentage of its width.
    
    Args:
        displays: Dictionary of cameras (modified in place)
        camera_name: Name of camera to split
        split_percent: Split position (0-100)
    
    Returns:
        Tuple of (split1_name, split2_name)
    """
    if camera_name not in displays:
        raise ValueError(f"Camera '{camera_name}' not found")
    if not 0 < split_percent < 100:
        raise ValueError("split_percent must be between 0 and 100")
    
    cam = displays[camera_name]
    ul, ll, lr = cam['ul'], cam['ll'], cam['lr']
    total_px = cam['width_px']
    ratio = split_percent / 100.0
    
    # Interpolate split point
    split_ll = [ll[0] + (lr[0]-ll[0])*ratio, ll[1] + (lr[1]-ll[1])*ratio, ll[2] + (lr[2]-ll[2])*ratio]
    split_ul = [ul[0] + (lr[0]-ll[0])*ratio, ul[1], ul[2] + (lr[2]-ll[2])*ratio]
    
    split1_name = f"{camera_name}_split1"
    split2_name = f"{camera_name}_split2"
    split1_px = round(total_px * ratio)
    split2_px = total_px - split1_px
    
    del displays[camera_name]
    
    displays[split1_name] = {
        "type": "offaxis",
        "ul": pt(*ul),
        "ll": pt(*ll),
        "lr": pt(*split_ll),
        "width_px": split1_px
    }
    
    displays[split2_name] = {
        "type": "offaxis",
        "ul": pt(*split_ul),
        "ll": pt(*split_ll),
        "lr": pt(*lr),
        "width_px": split2_px
    }
    
    return split1_name, split2_name


# ============================================================================
# 3. JOIN ADJACENT COPLANAR CAMERAS
# ============================================================================

def join_cameras(displays: Dict, cam1_name: str, cam2_name: str, 
                 tolerance_mm: float = 1.0, new_name: Optional[str] = None) -> str:
    """
    Join two adjacent coplanar cameras if they abut within tolerance.
    
    Args:
        displays: Dictionary of cameras (modified in place)
        cam1_name: First camera (left)
        cam2_name: Second camera (right)
        tolerance_mm: Maximum gap/overlap allowed (mm)
        new_name: Optional name for joined camera
    
    Returns:
        Name of joined camera
    """
    if cam1_name not in displays or cam2_name not in displays:
        raise ValueError("Both cameras must exist")
    
    cam1, cam2 = displays[cam1_name], displays[cam2_name]
    
    # Check if cam1.lr ≈ cam2.ll (within tolerance)
    gap = sum((cam1['lr'][i] - cam2['ll'][i])**2 for i in range(3))**0.5 * 1000  # to mm
    if gap > tolerance_mm:
        raise ValueError(f"Cameras not abutting (gap: {gap:.2f}mm > {tolerance_mm}mm)")
    
    # Check coplanar (normals should be similar)
    # For simplicity, check if ul.y and ll.y match
    if abs(cam1['ul'][1] - cam2['ul'][1]) > 0.001 or abs(cam1['ll'][1] - cam2['ll'][1]) > 0.001:
        raise ValueError("Cameras not coplanar")
    
    joined_name = new_name or f"{cam1_name}_joined"
    total_px = cam1['width_px'] + cam2['width_px']
    
    del displays[cam1_name]
    del displays[cam2_name]
    
    displays[joined_name] = {
        "type": "offaxis",
        "ul": cam1['ul'],
        "ll": cam1['ll'],
        "lr": cam2['lr'],
        "width_px": total_px
    }
    
    return joined_name


# ============================================================================
# 4. ALLOCATE CAMERAS TO NODES/OUTPUTS
# ============================================================================

class NodeAllocator:
    """Manages camera allocation to render nodes and outputs."""
    
    def __init__(self):
        self.nodes = {}  # node_name -> {cameras: [], viewports: {}}
        self.displays = {}  # All camera displays
    
    def allocate_to_node(self, camera_names: List[str], node_name: str, 
                        output_num: Optional[int] = None, fill_from_left: bool = True):
        """
        Allocate cameras to a node (or specific output).
        
        Args:
            camera_names: List of camera names to allocate
            node_name: Target node
            output_num: Optional output number (1 or 2), None for spanning both outputs
            fill_from_left: Start from left edge (x=0) or pack from right
        """
        if node_name not in self.nodes:
            self.nodes[node_name] = {'cameras': [], 'viewports': {}}
        
        # Calculate total width needed
        total_width_px = sum(self.displays[name]['width_px'] for name in camera_names)
        
        # Determine starting position and max width
        if output_num is None:
            # Can span both outputs - no width check (user responsibility to fit)
            start_x = 0 if fill_from_left else max(0, NODE_WIDTH_PX - total_width_px)
        else:
            # Restricted to single output
            max_width = OUTPUT_WIDTH_PX
            base_offset = (output_num - 1) * OUTPUT_WIDTH_PX
            
            if total_width_px > OUTPUT_WIDTH_PX:
                raise ValueError(f"Cameras too wide for single output ({total_width_px}px > {OUTPUT_WIDTH_PX}px)")
            
            start_x = base_offset if fill_from_left else (base_offset + OUTPUT_WIDTH_PX - total_width_px)
        
        # Create viewports
        current_x = start_x
        for name in camera_names:
            width_px = self.displays[name]['width_px']
            
            self.nodes[node_name]['cameras'].append(name)
            self.nodes[node_name]['viewports'][f"vp_{name}"] = {
                "x": current_x / NODE_WIDTH_PX,
                "y": 0.0,
                "width": width_px / NODE_WIDTH_PX,
                "height": 1.0
            }
            
            current_x += width_px
    
    def set_displays(self, displays: Dict):
        """Set the displays dictionary."""
        self.displays = displays


# ============================================================================
# 5. MOVE CAMERAS ON NODE
# ============================================================================

def move_cameras(node_allocator: NodeAllocator, node_name: str, 
                camera_names: List[str], offset_px: Optional[int] = None,
                offset_mm: Optional[float] = None):
    """
    Move cameras left (-) or right (+) on a node.
    
    Args:
        node_allocator: NodeAllocator instance
        node_name: Target node
        camera_names: Cameras to move
        offset_px: Offset in pixels (or None)
        offset_mm: Offset in millimeters (or None)
    """
    if node_name not in node_allocator.nodes:
        raise ValueError(f"Node '{node_name}' not found")
    
    if offset_px is None and offset_mm is None:
        raise ValueError("Must specify offset_px or offset_mm")
    
    offset = offset_px if offset_px is not None else round(offset_mm * PPMM)
    
    for name in camera_names:
        vp_name = f"vp_{name}"
        if vp_name not in node_allocator.nodes[node_name]['viewports']:
            raise ValueError(f"Camera '{name}' not in node '{node_name}'")
        
        vp = node_allocator.nodes[node_name]['viewports'][vp_name]
        current_x_px = vp['x'] * NODE_WIDTH_PX
        new_x_px = current_x_px + offset
        
        if new_x_px < 0 or new_x_px + vp['width'] * NODE_WIDTH_PX > NODE_WIDTH_PX:
            raise ValueError(f"Move would place camera outside node bounds")
        
        vp['x'] = new_x_px / NODE_WIDTH_PX


# ============================================================================
# 6. INSERT OVER-RENDER
# ============================================================================

def insert_overrender(displays: Dict, camera_name: str, side: str, 
                     overrender_mm: float):
    """
    Insert over-render region to left or right of a camera.
    Extends the camera geometry to include over-render.
    
    Args:
        displays: Dictionary of cameras (modified in place)
        camera_name: Target camera
        side: 'left' or 'right'
        overrender_mm: Over-render width in mm
    """
    if camera_name not in displays:
        raise ValueError(f"Camera '{camera_name}' not found")
    if side not in ['left', 'right']:
        raise ValueError("side must be 'left' or 'right'")
    
    cam = displays[camera_name]
    ul, ll, lr = cam['ul'], cam['ll'], cam['lr']
    
    # Calculate camera width vector and extend
    width_vec = [lr[i] - ll[i] for i in range(3)]
    width_m = sum(v**2 for v in width_vec)**0.5
    unit_vec = [v / width_m for v in width_vec]
    extend_m = overrender_mm / 1000.0
    
    if side == 'left':
        # Extend ll and ul to the left
        new_ll = [ll[i] - unit_vec[i] * extend_m for i in range(3)]
        new_ul = [ul[i] - unit_vec[i] * extend_m for i in range(3)]
        cam['ll'] = pt(*new_ll)
        cam['ul'] = pt(*new_ul)
    else:
        # Extend lr to the right
        new_lr = [lr[i] + unit_vec[i] * extend_m for i in range(3)]
        cam['lr'] = pt(*new_lr)
    
    # Update pixel width
    cam['width_px'] += round(overrender_mm * PPMM)


# ============================================================================
# 7. GENERATE PLATFORM JSON
# ============================================================================

def generate_platform_json(displays: Dict, node_allocator: NodeAllocator,
                           head_node: str = "head", head_ip: str = "192.168.0.131",
                           platform_name: str = "CurvedWall") -> Dict:
    """
    Generate complete platform JSON configuration.
    
    Args:
        displays: Camera displays dictionary
        node_allocator: NodeAllocator with camera assignments
        head_node: Head node name
        head_ip: Head node IP
        platform_name: Platform name
    
    Returns:
        Complete platform configuration dictionary
    """
    # Build node configurations
    nodes_config = {}
    all_viewports = {}
    
    for node_name, node_data in node_allocator.nodes.items():
        nodes_config[node_name] = {
            "display": node_data['cameras']
        }
        all_viewports.update(node_data['viewports'])
    
    # Build machines list
    machines = [{"name": head_node, "host": head_ip}]
    for node_name in node_allocator.nodes.keys():
        # Assume IPs are sequential (can be parameterized)
        node_num = len(machines)
        ip = f"192.168.0.{131 + node_num}"
        machines.append({"name": node_name, "host": ip})
    
    # Complete platform JSON
    platform_json = {
        "platforms": {
            platform_name: {
                "displays": displays,
                "viewports": all_viewports,
                "nodes": nodes_config,
                "head": head_node
            }
        },
        "machines": machines
    }
    
    return platform_json


# ============================================================================
# 9. DEDUCE OUTPUT RECTANGLES TO WALL MAPPING
# ============================================================================

def get_output_to_wall_mapping(displays: Dict, node_allocator: NodeAllocator, 
                                wall_camera_order: List[str]) -> Dict:
    """
    Deduce which rectangle(s) on each display output map to pixels on the wall.
    
    Args:
        displays: Camera displays dictionary
        node_allocator: NodeAllocator with camera assignments
        wall_camera_order: Ordered list of camera names (left to right on wall)
    
    Returns:
        Dictionary mapping each node to its output rectangles and wall positions
        Format:
        {
            "nodeL": {
                "output1": [
                    {
                        "output_rect": (x, y, width, height),  # In output pixels (3840x2160)
                        "wall_rect": (x, y, width, height),     # In wall pixels (19200 wide)
                        "camera": "disp_L_004"
                    },
                    ...
                ],
                "output2": [...]
            },
            ...
        }
    """
    # Calculate wall positions for each camera
    wall_positions = {}
    wall_x = 0
    
    for cam_name in wall_camera_order:
        if cam_name not in displays:
            continue
        width_px = displays[cam_name]['width_px']
        wall_positions[cam_name] = {
            'wall_x': wall_x,
            'wall_width': width_px
        }
        wall_x += width_px
    
    # Build output mapping for each node
    output_mapping = {}
    
    for node_name, node_data in node_allocator.nodes.items():
        output_mapping[node_name] = {
            'output1': [],
            'output2': []
        }
        
        # Process each camera on this node
        for cam_name in node_data['cameras']:
            if cam_name not in displays or cam_name not in wall_positions:
                continue
            
            # Get viewport on node (normalized 0-1)
            vp_name = f'vp_{cam_name}'
            if vp_name not in node_data['viewports']:
                continue
                
            vp = node_data['viewports'][vp_name]
            
            # Convert to node pixels (0-7680)
            node_x = vp['x'] * NODE_WIDTH_PX
            node_width = vp['width'] * NODE_WIDTH_PX
            node_end = node_x + node_width
            
            # Wall position
            wall_x = wall_positions[cam_name]['wall_x']
            wall_width = wall_positions[cam_name]['wall_width']
            
            # Determine which output(s) this camera spans
            output1_end = OUTPUT_WIDTH_PX  # 3840
            
            # Check if camera is on output 1
            if node_x < output1_end:
                # Calculate rectangle on output 1
                out1_x = int(node_x)
                out1_end_x = min(int(node_end), output1_end)
                out1_width = out1_end_x - out1_x
                
                if out1_width > 0:
                    # Calculate corresponding wall portion
                    # What fraction of the camera is on output 1?
                    fraction_on_out1 = out1_width / node_width
                    wall_width_on_out1 = int(wall_width * fraction_on_out1)
                    
                    output_mapping[node_name]['output1'].append({
                        'output_rect': (out1_x, 0, out1_width, 2160),
                        'wall_rect': (wall_x, 0, wall_width_on_out1, 2160),
                        'camera': cam_name
                    })
            
            # Check if camera is on output 2
            if node_end > output1_end:
                # Calculate rectangle on output 2
                out2_x = max(0, int(node_x - output1_end))
                out2_end_x = int(node_end - output1_end)
                out2_width = out2_end_x - out2_x
                
                if out2_width > 0:
                    # Calculate corresponding wall portion
                    # How much of the camera is on output 2?
                    if node_x >= output1_end:
                        # Entire camera is on output 2
                        wall_x_offset = 0
                        wall_width_on_out2 = wall_width
                    else:
                        # Camera spans both outputs
                        fraction_on_out2 = out2_width / node_width
                        wall_width_on_out2 = int(wall_width * fraction_on_out2)
                        wall_x_offset = wall_width - wall_width_on_out2
                    
                    output_mapping[node_name]['output2'].append({
                        'output_rect': (out2_x, 0, out2_width, 2160),
                        'wall_rect': (wall_x + wall_x_offset, 0, wall_width_on_out2, 2160),
                        'camera': cam_name
                    })
    
    return output_mapping


# ============================================================================
# 8. LINEAR TRANSFORM Z COORDINATES
# ============================================================================

def transform_z_linear(displays: Dict, a: float, b: float):
    """
    Apply linear transform to z coordinates of all cameras.
    
    Transform: z_new = a * z_old + b
    
    Args:
        displays: Dictionary of cameras (modified in place)
        a: Scale factor
        b: Offset
    
    Examples:
        transform_z_linear(displays, 1.0, 0.5)  # Shift all z by +0.5m
        transform_z_linear(displays, -1.0, 0.0)  # Flip z axis
        transform_z_linear(displays, 2.0, 0.0)   # Double z distances
    """
    for cam_name, cam_data in displays.items():
        # Transform each corner's z coordinate
        for corner in ['ul', 'll', 'lr']:
            x, y, z = cam_data[corner]
            z_new = a * z + b
            cam_data[corner] = [x, y, round(z_new, 3)]


# ============================================================================
# TESTING
# ============================================================================

def run_tests():
    """Run comprehensive tests of all functions."""
    
    print("="*80)
    print("WALL PLATFORM BUILDER - COMPREHENSIVE TESTS")
    print("="*80)
    
    # Test 1: Create cameras
    print("\n[TEST 1] Creating wall cameras...")
    displays = create_wall_cameras()
    print(f"✓ Created {len(displays)} cameras")
    assert len(displays) == 9, "Should have 9 cameras"
    assert 'disp_centre' in displays
    assert 'disp_L_001' in displays
    assert 'disp_R_004' in displays
    
    # Test 2: Split camera
    print("\n[TEST 2] Splitting disp_centre at 60%...")
    s1, s2 = split_camera(displays, "disp_centre", 60)
    print(f"✓ Split into {s1} ({displays[s1]['width_px']}px) and {s2} ({displays[s2]['width_px']}px)")
    assert s1 == "disp_centre_split1"
    assert s2 == "disp_centre_split2"
    assert displays[s1]['width_px'] + displays[s2]['width_px'] == 9600
    assert 'disp_centre' not in displays
    
    # Test 3: Join cameras back
    print("\n[TEST 3] Joining split cameras back together...")
    joined = join_cameras(displays, s1, s2, tolerance_mm=1.0, new_name="disp_centre_rejoined")
    print(f"✓ Joined into {joined} ({displays[joined]['width_px']}px)")
    assert displays[joined]['width_px'] == 9600
    assert s1 not in displays
    assert s2 not in displays
    
    # Test 4: Node allocation
    print("\n[TEST 4] Allocating cameras to nodes...")
    allocator = NodeAllocator()
    allocator.set_displays(displays)
    
    # Allocate left cameras to nodeL (in wall order: L_004 to L_001, left to right)
    left_cams = [f"disp_L_{i:03d}" for i in range(4, 0, -1)]  # L_004, L_003, L_002, L_001
    allocator.allocate_to_node(left_cams, "nodeL", fill_from_left=True)
    print(f"✓ Allocated {len(left_cams)} cameras to nodeL (L_004->L_001, 4800px total)")
    
    # Allocate centre to nodeC (spanning - 9600px, exceeds node but tests spanning logic)
    allocator.allocate_to_node([joined], "nodeC")
    print(f"✓ Allocated {joined} ({displays[joined]['width_px']}px) to nodeC (spanning)")
    
    # Allocate right cameras to nodeR (in wall order: R_001 to R_004, left to right)
    right_cams = [f"disp_R_{i:03d}" for i in range(1, 5)]  # R_001, R_002, R_003, R_004
    allocator.allocate_to_node(right_cams, "nodeR", fill_from_left=True)
    print(f"✓ Allocated {len(right_cams)} cameras to nodeR (R_001->R_004, 4800px total)")
    
    # Test 5: Move cameras
    print("\n[TEST 5] Moving cameras on node...")
    # Use L_004 which is now first (leftmost) on nodeL
    test_cam = "disp_L_004"
    original_x = allocator.nodes["nodeL"]['viewports'][f'vp_{test_cam}']['x']
    move_cameras(allocator, "nodeL", [test_cam], offset_px=50)
    new_x = allocator.nodes["nodeL"]['viewports'][f'vp_{test_cam}']['x']
    print(f"✓ Moved {test_cam} from {original_x:.4f} to {new_x:.4f}")
    assert new_x > original_x
    
    # Move back
    move_cameras(allocator, "nodeL", [test_cam], offset_mm=-50/PPMM)
    reset_x = allocator.nodes["nodeL"]['viewports'][f'vp_{test_cam}']['x']
    print(f"✓ Moved back to {reset_x:.4f}")
    assert abs(reset_x - original_x) < 0.001
    
    # Test 6: Insert over-render
    print("\n[TEST 6] Inserting over-render...")
    original_width = displays["disp_L_004"]['width_px']
    insert_overrender(displays, "disp_L_004", "left", 312.5)  # 200px
    new_width = displays["disp_L_004"]['width_px']
    print(f"✓ Extended disp_L_004 from {original_width}px to {new_width}px")
    assert new_width == original_width + 200
    
    # Test 7: Generate platform JSON
    print("\n[TEST 7] Generating platform JSON...")
    platform = generate_platform_json(displays, allocator)
    print(f"✓ Generated platform with {len(platform['platforms']['CurvedWall']['displays'])} displays")
    print(f"✓ Platform has {len(platform['machines'])} machines")
    assert 'platforms' in platform
    assert 'CurvedWall' in platform['platforms']
    assert 'machines' in platform
    
    # Test 8: Transform z coordinates
    print("\n[TEST 8] Transforming z coordinates...")
    # Get original z values from a sample camera
    sample_cam = "disp_R_001"
    original_z = displays[sample_cam]['ll'][2]
    print(f"  Original {sample_cam} ll.z: {original_z:.3f}")
    
    # Apply transform: z_new = 1.0 * z_old + 0.5 (shift by +0.5m)
    transform_z_linear(displays, 1.0, 0.5)
    new_z = displays[sample_cam]['ll'][2]
    print(f"  After z_new = 1.0*z + 0.5: {new_z:.3f}")
    expected_z = original_z + 0.5
    assert abs(new_z - expected_z) < 0.001, f"Expected {expected_z:.3f}, got {new_z:.3f}"
    print(f"✓ Transform applied correctly (shift by +0.5m)")
    
    # Test scale transform: z_new = 2.0 * z_old + 0.0 (double distances)
    transform_z_linear(displays, 2.0, 0.0)
    doubled_z = displays[sample_cam]['ll'][2]
    expected_doubled = new_z * 2.0
    print(f"  After z_new = 2.0*z + 0.0: {doubled_z:.3f}")
    assert abs(doubled_z - expected_doubled) < 0.001
    print(f"✓ Scale transform applied correctly (doubled)")
    
    # Transform back to original for consistency with rest of output
    # Reverse operations: first undo scale (z/2), then undo shift (z-0.5)
    # Combined: z_new = 0.5 * z_old - 0.5
    transform_z_linear(displays, 0.5, -0.5)
    final_z = displays[sample_cam]['ll'][2]
    print(f"  After reversing: {final_z:.3f}")
    assert abs(final_z - original_z) < 0.001
    print(f"✓ Reversed back to original")
    
    # Test 9: Deduce output to wall mapping
    print("\n[TEST 9] Deducing output to wall mapping...")
    
    # Define wall camera order (left to right)
    wall_order = [
        'disp_L_004', 'disp_L_003', 'disp_L_002', 'disp_L_001',  # Left side
        'disp_centre_rejoined',  # Centre (this is from join test)
        'disp_R_001', 'disp_R_002', 'disp_R_003', 'disp_R_004'   # Right side
    ]
    
    mapping = get_output_to_wall_mapping(displays, allocator, wall_order)
    
    print(f"✓ Generated output mapping for {len(mapping)} nodes")
    
    # Verify each node has mapping
    for node_name in ['nodeL', 'nodeC', 'nodeR']:
        assert node_name in mapping
        out1_rects = len(mapping[node_name]['output1'])
        out2_rects = len(mapping[node_name]['output2'])
        total_rects = out1_rects + out2_rects
        print(f"  {node_name}: {total_rects} rectangles ({out1_rects} on Out1, {out2_rects} on Out2)")
    
    # Verify nodeL has cameras on output 1
    assert len(mapping['nodeL']['output1']) > 0, "nodeL should have cameras on output 1"
    
    # Show sample mapping
    if len(mapping['nodeL']['output1']) > 0:
        sample = mapping['nodeL']['output1'][0]
        print(f"\n  Sample: {sample['camera']}")
        print(f"    Output rect: {sample['output_rect']}")
        print(f"    Wall rect:   {sample['wall_rect']}")
    
    print(f"✓ Output to wall mapping validated")
    
    print("\n" + "="*80)
    print("ALL TESTS PASSED ✓")
    print("="*80)
    
    return platform, displays, allocator


def create_config():
    """Create production platform configuration."""

    # novastar boundaries: 2976, 6048, 9120, 11808, 14880, 17856

    # without overlap:
    # nodeL output1: L_004 w=1920, L_003 w=960, L_002 w=960 (3840) (864 into bin 2)
    # nodeL output2: L_001 w=960, CL_001 w=1248 (at 6048 end of bin 2).
    # nodeC output1: C_001 w=3840 (at 9888 ... 768 into bin 4)
    # nodeC output2: C_002 w=3840 (at 13728 ... 1920 into bin 5)
    # nodeR output1: CR_001 w = 672, R_001 w=960,  (at 15360 ... 480 into bin 6)
    # nodeR output2: R_002 w=960, R_003 w=960, R_004 w=1920 (19200)
    # 
    
    print("="*80)
    print("WALL PLATFORM CONFIGURATION GENERATOR")
    print("="*80)
    
    # Step 1: Create base cameras
    print("\n[1] Creating wall cameras...")
    displays = create_wall_cameras()
    print(f"    Created {len(displays)} cameras")

    # Step 2: Split cameras
    print("\n[2] Splitting cameras...")
    cl001, ca = split_camera(displays, "disp_centre", 10.396)
    assert cl001 == "disp_centre_split1"
    assert ca == "disp_centre_split2"

    c001, cb = split_camera(displays, ca, 44.199)
    assert c001 == "disp_centre_split2_split1"
    assert cb == "disp_centre_split2_split2"

    c002, cr001 = split_camera(displays, cb, 79.208)
    assert c002 == "disp_centre_split2_split2_split1"
    assert cr001 == "disp_centre_split2_split2_split2"
    print(f"    Now there are {len(displays)} cameras")

    tw = 0
    for key, value in displays.items():
        w = value["width_px"]
        tw += w
        print(f"display {key} width_px = {w}")

    print(f"Total display width = {tw} pixels")
    
    # Step 2.5: Setup node allocator
    #print("\n[3] Setting up node allocator...")
    allocator = NodeAllocator()
    allocator.set_displays(displays)
    
    # Step 3: Allocate cameras to nodes
    print("\n[3] Allocating cameras to nodes...")
    
    # Left side: L_004, L_003, L_002, L_001 (wall order)
    left_cams = [f"disp_L_{i:03d}" for i in range(4, 0, -1)]
    left_cams.append(cl001)
    allocator.allocate_to_node(left_cams, "nodeL", fill_from_left=True)
    
    # Centre
    centre_cams = [c001, c002]
    allocator.allocate_to_node(centre_cams, "nodeC", fill_from_left=True)
 
    # Right side: R_001, R_002, R_003, R_004 (wall order)
    right_cams = [f"disp_R_{i:03d}" for i in range(1, 5)]
    right_cams.insert(0, cr001)
    allocator.allocate_to_node(right_cams, "nodeR", fill_from_left=False)
    
    # Step 4: Add over-render to edge cameras
    #print("\n[4] Adding over-render to edge cameras...")
    #insert_overrender(displays, "disp_L_004", "left", 312.5)  # 200px
    #insert_overrender(displays, "disp_R_004", "right", 312.5)  # 200px
    #print(f"    Added 200px over-render to L_004 (left) and R_004 (right)")

    transform_z_linear(displays, -1, -3.5)
    
    # Step 5: Generate platform JSON
    print("\n[5] Generating platform JSON...")
    platform = generate_platform_json(displays, allocator, 
                                     head_node="head", 
                                     head_ip="192.168.0.131",
                                     platform_name="CurvedWall")
    print(f"    Generated complete platform configuration")
    
    # Step 6: Generate output to wall mapping
    print("\n[6] Generating output to wall mapping...")
    wall_order = [
        'disp_L_004', 'disp_L_003', 'disp_L_002', 'disp_L_001', 'disp_centre_split1',
        'disp_centre_split2_split1', 'disp_centre_split2_split2_split1',
        'disp_centre_split2_split2_split2', 'disp_R_001', 'disp_R_002', 'disp_R_003', 'disp_R_004'
    ]
    mapping = get_output_to_wall_mapping(displays, allocator, wall_order)
    print(f"    Generated output mapping for {len(mapping)} nodes")
    
    # Step 7: Save outputs
    print("\n[7] Saving configuration files...")
    
    # Save platform JSON
    with open('platform_config.json', 'w') as f:
        json.dump(platform, f, indent=2)
    print(f"    ✓ platform_config.json")
    
    # Save output mapping
    with open('output_mapping.json', 'w') as f:
        json.dump(mapping, f, indent=2)
    print(f"    ✓ output_mapping.json")
    
    # Save summary
    summary = {
        "wall_width_px": 19200,
        "wall_height_px": 2160,
        "total_cameras": len(displays),
        "nodes": list(allocator.nodes.keys()),
        "node_details": {
            node_name: {
                "cameras": len(node_data['cameras']),
                "output1_rectangles": len(mapping[node_name]['output1']),
                "output2_rectangles": len(mapping[node_name]['output2'])
            }
            for node_name, node_data in allocator.nodes.items()
        }
    }
    
    with open('config_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"    ✓ config_summary.json")
    
    print("\n" + "="*80)
    print("CONFIGURATION COMPLETE ✓")
    print("="*80)
    print("\nGenerated files:")
    print("  - platform_config.json      (Complete platform configuration)")
    print("  - output_mapping.json       (Output to wall pixel mapping)")
    print("  - config_summary.json       (Configuration summary)")
    print("\n" + "="*80)
    
    return platform, displays, allocator, mapping


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point."""
    import sys
    
    if '--test' in sys.argv:
        platform, displays, allocator = run_tests()
        
        # Save test output
        with open('platform_test_output.json', 'w') as f:
            json.dump(platform, f, indent=2)
        print("\n✓ Test output saved to platform_test_output.json")
        
    elif '--config' in sys.argv:
        platform, displays, allocator, mapping = create_config()
        
    else:
        print("Usage: python wall_platform_builder.py [--test | --config]")
        print("\nOptions:")
        print("  --test    Run comprehensive tests of all functions")
        print("  --config  Generate production platform configuration")
        print("\nThis script provides tested functions for:")
        print("  1. create_wall_cameras() - Generate cameras from wall spec")
        print("  2. split_camera() - Split camera at percentage")
        print("  3. join_cameras() - Join adjacent coplanar cameras")
        print("  4. NodeAllocator.allocate_to_node() - Allocate to nodes/outputs")
        print("  5. move_cameras() - Move cameras left/right")
        print("  6. insert_overrender() - Add over-render regions")
        print("  7. generate_platform_json() - Output complete platform JSON")
        print("  8. transform_z_linear() - Apply linear transform to z coordinates")
        print("  9. get_output_to_wall_mapping() - Deduce output rectangles to wall mapping")


if __name__ == "__main__":
    main()
