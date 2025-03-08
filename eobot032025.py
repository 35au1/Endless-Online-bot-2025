import time
import pymem
import psutil
import ctypes
import math
import os
import pathlib
import random

def read_address_from_file(filename):
    """Read hex address from file."""
    try:
        script_dir = pathlib.Path(__file__).parent.absolute()
        file_path = os.path.join(script_dir, filename)
        
        with open(file_path, 'r') as f:
            content = f.read().strip()
            if content.lower().startswith('0x'):
                return int(content, 16)
            else:
                return int(f"0x{content}", 16)
    except Exception as e:
        print(f"Error reading from {filename}: {e}")
        return None

# Read addresses
MOB_BASE_ADDR = read_address_from_file('mobxy.txt')
CHAR_X_ADDR = read_address_from_file('playerxy.txt')

# Calculate offsets
if MOB_BASE_ADDR is not None:
    # Movement addresses
    FACE_ADDR = MOB_BASE_ADDR
    Y_ADDR = MOB_BASE_ADDR + 0x4
    X_ADDR = MOB_BASE_ADDR + 0x8
    
    # Spawn addresses - CORRECTED using 0x0019B4EC as the face reference
    SPAWN_FACE_ADDR = MOB_BASE_ADDR - 0x14  
    SPAWN_Y_ADDR = MOB_BASE_ADDR - 0x10     
    SPAWN_X_ADDR = MOB_BASE_ADDR - 0xC      
    
    # Mob ID addresses (for hit detection)
    MOB_ID_ADDR1 = MOB_BASE_ADDR + 0x98
    MOB_ID_ADDR2 = MOB_BASE_ADDR + 0xA0
    
    # Kill detection addresses
    KILL_ADDR1 = MOB_BASE_ADDR + 0x9C
    KILL_ADDR2 = MOB_BASE_ADDR + 0xA4
else:
    print("Error: Failed to read mob address")
    FACE_ADDR = Y_ADDR = X_ADDR = None
    SPAWN_FACE_ADDR = SPAWN_Y_ADDR = SPAWN_X_ADDR = None
    MOB_ID_ADDR1 = MOB_ID_ADDR2 = None

if CHAR_X_ADDR is not None:
    CHAR_Y_ADDR = CHAR_X_ADDR + 0x4
else:
    print("Error: Failed to read player address")
    CHAR_Y_ADDR = None

# Direction mapping
FACE_OFFSETS = {0: (0, 1), 1: (-1, 0), 2: (0, -1), 3: (1, 0)}  # down, left, up, right
FACE_NAMES = {0: 'down', 1: 'left', 2: 'up', 3: 'right'}

# Virtual key codes
VK_CODE = {'up': 0x68, 'left': 0x64, 'down': 0x62, 'right': 0x66, 'ctrl': 0x11}

# Adaptive key press durations
INITIAL_MOVEMENT_DURATION = 0.03  # 50ms
MAX_MOVEMENT_DURATION = 0.05
INITIAL_CTRL_DURATION = 0.05
MAX_CTRL_DURATION = 0.3
FACING_DURATION = 0.5
DURATION_INCREMENT = 0.05

# Movement tracking
movement_durations = {key: INITIAL_MOVEMENT_DURATION for key in ['up', 'down', 'left', 'right']}
ctrl_duration = INITIAL_CTRL_DURATION
movement_success_rate = {key: {'attempts': 0, 'successes': 0} for key in ['up', 'down', 'left', 'right', 'ctrl']}

def select_endless_pid():
    """Find endless.exe process."""
    endless_pids = []
    for proc in psutil.process_iter():
        if proc.name().lower() == 'endless.exe':
            endless_pids.append(proc.pid)

    if not endless_pids:
        print("No 'endless.exe' found.")
        return None

    if len(endless_pids) == 1:
        pid = endless_pids[0]
        print(f"Found process (PID {pid}).")
        return pid

    print("Multiple processes found:")
    for i, pid in enumerate(endless_pids, start=1):
        print(f"{i}. PID = {pid}")

    while True:
        choice = input("Select process #: ").strip()
        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(endless_pids):
                return endless_pids[index - 1]
        print("Invalid choice.")

def press_key(key, duration=None, with_feedback=False, pm=None, char_x=None, char_y=None):
    """Press key with adaptive duration based on success rate."""
    vk_code = VK_CODE.get(key.lower())
    if not vk_code:
        print(f"Error: Unknown key '{key}'")
        return False, (None, None) if with_feedback else None
    
    # Use adaptive duration
    if duration is None:
        if key == 'ctrl':
            duration = ctrl_duration
        else:
            duration = movement_durations.get(key, INITIAL_MOVEMENT_DURATION)
    
    # Press key
    ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)  # Down
    time.sleep(duration)
    ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0)  # Up
    
    if not with_feedback or pm is None:
        return True
    
    # Check if movement succeeded
    time.sleep(0.02)
    new_char_x = pm.read_int(CHAR_X_ADDR)
    new_char_y = pm.read_int(CHAR_Y_ADDR)
    
    movement_success_rate[key]['attempts'] += 1
    
    # Check movement success
    success = False
    if key == 'right' and new_char_x > char_x:
        success = True
    elif key == 'left' and new_char_x < char_x:
        success = True
    elif key == 'down' and new_char_y > char_y:
        success = True
    elif key == 'up' and new_char_y < char_y:
        success = True
    
    # Adjust duration based on success
    if success:
        movement_success_rate[key]['successes'] += 1
        success_rate = movement_success_rate[key]['successes'] / movement_success_rate[key]['attempts']
        if success_rate > 0.8 and movement_durations[key] > INITIAL_MOVEMENT_DURATION:
            movement_durations[key] = max(INITIAL_MOVEMENT_DURATION, movement_durations[key] - DURATION_INCREMENT)
            print(f"Success rate: {success_rate:.2f} - Reducing {key} to {movement_durations[key]*1000:.0f}ms")
    else:
        movement_durations[key] = min(MAX_MOVEMENT_DURATION, movement_durations[key] + DURATION_INCREMENT)
    
    return success, (new_char_x, new_char_y)

def press_ctrl_for_interaction(pm):
    """Press Ctrl with adaptive duration and check for hit/kill."""
    global ctrl_duration
    
    # Read kill indicators before hitting
    try:
        before_kill_val1 = pm.read_bytes(KILL_ADDR1, 1)[0]
        before_kill_val2 = pm.read_bytes(KILL_ADDR2, 1)[0]
    except Exception as e:
        print(f"Error reading kill indicators: {e}")
        before_kill_val1 = before_kill_val2 = 0
    
    # Press Ctrl
    ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)  # Ctrl down
    time.sleep(ctrl_duration)
    ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)  # Ctrl up
    
    # Give more time for kill registration
    time.sleep(0.2)  # Increased to 200ms
    
    # Count this attempt BEFORE any potential division operation
    movement_success_rate['ctrl']['attempts'] += 1
    
    hit_detected = False
    kill_detected = False
    
    # Check kill indicators - looking for new non-zero values
    try:
        after_kill_val1 = pm.read_bytes(KILL_ADDR1, 1)[0]
        after_kill_val2 = pm.read_bytes(KILL_ADDR2, 1)[0]
        
        # Looking for new non-zero values to indicate a kill
        if ((before_kill_val1 == 0 and after_kill_val1 != 0) or 
            (before_kill_val2 == 0 and after_kill_val2 != 0)):
            print(f"Kill detected! New values appeared: {after_kill_val1}, {after_kill_val2}")
            kill_detected = True
            hit_detected = True
        # Alternate detection for changing non-zero values
        elif ((before_kill_val1 != after_kill_val1 and after_kill_val1 != 0) or 
              (before_kill_val2 != after_kill_val2 and after_kill_val2 != 0)):
            print(f"Kill detected! Values changed: {before_kill_val1}->{after_kill_val1}, {before_kill_val2}->{after_kill_val2}")
            kill_detected = True
            hit_detected = True
    except Exception as e:
        print(f"Error checking kill: {e}")
    
    # Skip the hit check if we already detected a kill
    if not hit_detected:
        try:
            mob_id1 = pm.read_bytes(MOB_ID_ADDR1, 1)[0]
            mob_id2 = pm.read_bytes(MOB_ID_ADDR2, 1)[0]
            
            if mob_id1 != 0 or mob_id2 != 0:
                hit_detected = True
            else:
                print(f"No hit detected")
        except Exception as e:
            print(f"Error checking hit: {e}")
    
    # Update ctrl duration
    if hit_detected:
        movement_success_rate['ctrl']['successes'] += 1
        
        # Prevent division by zero
        if movement_success_rate['ctrl']['attempts'] > 0:
            success_rate = movement_success_rate['ctrl']['successes'] / movement_success_rate['ctrl']['attempts']
            if success_rate > 0.8 and ctrl_duration > INITIAL_CTRL_DURATION:
                ctrl_duration = max(INITIAL_CTRL_DURATION, ctrl_duration - DURATION_INCREMENT)
                print(f"Ctrl success: {success_rate:.2f} - Reducing to {ctrl_duration*1000:.0f}ms")
    else:
        # Prevent division by zero here too
        if movement_success_rate['ctrl']['attempts'] > 0:
            ctrl_duration = min(MAX_CTRL_DURATION, ctrl_duration + DURATION_INCREMENT)
            print(f"Ctrl failed - Increasing to {ctrl_duration*1000:.0f}ms")
    
    return kill_detected

def calculate_distance(x1, y1, x2, y2):
    """Calculate Manhattan distance."""
    return abs(x1 - x2) + abs(y1 - y2)

def get_closest_mob(tracked_mobs, char_x, char_y, current_target_id=None, targeting_locked=False):
    """Find closest mob with hysteresis for current target."""
    if targeting_locked and current_target_id in tracked_mobs:
        return current_target_id
    
    closest_mobs = []
    min_distance = float('inf')
    
    for mob_id, coords in tracked_mobs.items():
        if coords.get('inactive', False):
            continue
            
        distance = calculate_distance(char_x, char_y, coords['x'], coords['y'])
        
        if distance < min_distance:
            min_distance = distance
            closest_mobs = [(mob_id, coords['x'], coords['y'], distance)]
        elif distance == min_distance:
            closest_mobs.append((mob_id, coords['x'], coords['y'], distance))
    
    if not closest_mobs:
        return None
    
    if len(closest_mobs) > 1:
        closest_mobs.sort(key=lambda mob: (mob[1], mob[2]))
    
    closest_mob_id = closest_mobs[0][0]
    closest_distance = closest_mobs[0][3]
    
    # Keep current target if it's within 2 blocks
    if current_target_id in tracked_mobs:
        current_dist = calculate_distance(
            char_x, char_y, 
            tracked_mobs[current_target_id]['x'], 
            tracked_mobs[current_target_id]['y']
        )
        if current_dist <= closest_distance + 2:
            return current_target_id
    
    return closest_mob_id

def move_toward_mob(pm, mob_coords, char_x, char_y, mob_id=None, tracked_mobs=None, targeting_locked=False):
    """Move toward mob or interact if close."""
    mob_x, mob_y = mob_coords['x'], mob_coords['y']
    
    # If close, interact
    x_diff = abs(mob_x - char_x)
    y_diff = abs(mob_y - char_y)
    
    if x_diff <= 1 and y_diff <= 1:
        
        # Face mob - use FACING_DURATION (500ms)
        direction_key = None
        if mob_x > char_x:
            direction_key = 'right'
        elif mob_x < char_x:
            direction_key = 'left'
        elif mob_y > char_y:
            direction_key = 'down'
        elif mob_y < char_y:
            direction_key = 'up'
            
        if direction_key:
            vk_code = VK_CODE.get(direction_key.lower())
            if vk_code:
                ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
                time.sleep(FACING_DURATION)
                ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0)
        
        time.sleep(0.02)
        
        # Attack and check for kill
        mob_killed = press_ctrl_for_interaction(pm)
        
        if mob_killed and mob_id is not None and tracked_mobs is not None and mob_id in tracked_mobs:
            print(f"Removing killed mob {mob_id}")
            del tracked_mobs[mob_id]
            return True, False
        
        return True, not mob_killed
    
    # Determine movement direction
    primary_moves = []
    if x_diff > y_diff:
        # Horizontal first
        if mob_x > char_x: primary_moves.append('right')
        elif mob_x < char_x: primary_moves.append('left')
        
        # Then vertical
        if mob_y > char_y: primary_moves.append('down')
        elif mob_y < char_y: primary_moves.append('up')
    else:
        # Vertical first
        if mob_y > char_y: primary_moves.append('down')
        elif mob_y < char_y: primary_moves.append('up')
            
        # Then horizontal
        if mob_x > char_x: primary_moves.append('right')
        elif mob_x < char_x: primary_moves.append('left')
    
    # Try primary movement
    for move in primary_moves:
        success, _ = press_key(move, with_feedback=True, pm=pm, char_x=char_x, char_y=char_y)
        
        if success:
            return True, targeting_locked
        else:
            pass
    
    # Try alternative movement
    alternative_moves = []
    if primary_moves[0] in ['right', 'left']:
        # If horizontal failed, try vertical
        if mob_y > char_y:
            alternative_moves.append('down')
        elif mob_y < char_y:
            alternative_moves.append('up')
    else:
        # If vertical failed, try horizontal
        if mob_x > char_x:
            alternative_moves.append('right')
        elif mob_x < char_x:
            alternative_moves.append('left')
    
    for move in alternative_moves:
        success, _ = press_key(move, with_feedback=True, pm=pm, char_x=char_x, char_y=char_y)
        
        if success:
            return True, targeting_locked
    
    return False, targeting_locked

def make_random_move(pm, char_x, char_y):
    """Make random move when stuck."""
    direction = random.choice(['up', 'down', 'left', 'right'])
    success, _ = press_key(direction, with_feedback=True, pm=pm, char_x=char_x, char_y=char_y)
    return success

def main():
    # Verify addresses
    if None in (FACE_ADDR, Y_ADDR, X_ADDR, SPAWN_FACE_ADDR, SPAWN_Y_ADDR, SPAWN_X_ADDR, 
                MOB_ID_ADDR1, MOB_ID_ADDR2, KILL_ADDR1, KILL_ADDR2, 
                CHAR_X_ADDR, CHAR_Y_ADDR):
        print("ERROR: Missing addresses.")
        return

    pid = select_endless_pid()
    if pid is None:
        return

    pm = pymem.Pymem(pid)

    # Initialize tracking
    tracked_mobs = {}
    spawn_locations = {}
    next_mob_id = 1

    # Last memory values
    last_face_val = last_x_val = last_y_val = None
    last_spawn_face_val = last_spawn_y_val = last_spawn_x_val = None
    
    # Movement state
    last_movement_time = 0
    movement_cooldown = 0.02
    current_target_mob_id = None
    targeting_locked = False
    last_successful_movement_time = time.time()
    stuck_timeout = 1.0
    just_made_random_move = False
    last_char_x = last_char_y = None

    print(f"Starting with movement: {INITIAL_MOVEMENT_DURATION*1000:.0f}ms, Ctrl: {INITIAL_CTRL_DURATION*1000:.0f}ms")
    print(f"Facing duration: {FACING_DURATION*1000:.0f}ms")

    try:
        while True:
            try:
                # Read memory
                face_val = pm.read_int(FACE_ADDR)
                y_val = pm.read_int(Y_ADDR)
                x_val = pm.read_int(X_ADDR)
                
                spawn_face_val = pm.read_int(SPAWN_FACE_ADDR)
                spawn_y_val = pm.read_int(SPAWN_Y_ADDR)
                spawn_x_val = pm.read_int(SPAWN_X_ADDR)
                
                char_x = pm.read_int(CHAR_X_ADDR)
                char_y = pm.read_int(CHAR_Y_ADDR)
                
                # Check character movement
                if last_char_x is not None and last_char_y is not None:
                    if char_x != last_char_x or char_y != last_char_y:
                        last_successful_movement_time = time.time()
                        just_made_random_move = False
                
                last_char_x, last_char_y = char_x, char_y
                current_time = time.time()
            except Exception as e:
                print(f"Memory error: {e}")
                time.sleep(0.5)
                continue
                
            # Detect spawns
            if (spawn_face_val != last_spawn_face_val or
                spawn_y_val != last_spawn_y_val or
                spawn_x_val != last_spawn_x_val):
                
                last_spawn_face_val = spawn_face_val
                last_spawn_y_val = spawn_y_val
                last_spawn_x_val = spawn_x_val
                
                # Skip zero values
                if spawn_x_val == 0 or spawn_y_val == 0:
                    continue
                
                spawn_key = f"{spawn_x_val}_{spawn_y_val}"
                facing = FACE_NAMES.get(spawn_face_val, '?')
                print(f"New spawn at ({spawn_x_val}, {spawn_y_val}) facing {facing}")
                
                spawn_locations[spawn_key] = {
                    'face': spawn_face_val,
                    'x': spawn_x_val,
                    'y': spawn_y_val,
                    'time': current_time
                }
                
                tracked_mobs[next_mob_id] = {
                    'x': spawn_x_val,
                    'y': spawn_y_val,
                    'last_x': spawn_x_val,
                    'last_y': spawn_y_val,
                    'last_activity_time': current_time,
                    'from_spawn': True
                }
                print(f"Added spawn as mob #{next_mob_id}")
                next_mob_id += 1

            # Update inactive mobs
            for mob_id in list(tracked_mobs.keys()):
                mob = tracked_mobs[mob_id]
                
                if mob['x'] == mob.get('last_x') and mob['y'] == mob.get('last_y'):
                    if 'last_activity_time' not in mob:
                        mob['last_activity_time'] = current_time
                    elif current_time - mob['last_activity_time'] >= 7:
                        print(f"Mob {mob_id} inactive for 4s, removing")
                        del tracked_mobs[mob_id]
                        if current_target_mob_id == mob_id:
                            current_target_mob_id = None
                            targeting_locked = False
                        continue
                else:
                    mob['last_activity_time'] = current_time
                
                mob['last_x'], mob['last_y'] = mob['x'], mob['y']

            # Target and move toward mobs
            if tracked_mobs:
                new_closest_mob_id = get_closest_mob(tracked_mobs, char_x, char_y, 
                                                   current_target_mob_id, targeting_locked)
                
                if (new_closest_mob_id != current_target_mob_id or 
                    (current_target_mob_id is not None and current_time - last_movement_time >= movement_cooldown)):
                    
                    if not targeting_locked or current_target_mob_id is None:
                        current_target_mob_id = new_closest_mob_id
                    
                    if current_target_mob_id is not None:
                        status = "LOCKED" if targeting_locked else "moving toward"
                        
                        move_success, still_targeting = move_toward_mob(
                            pm, tracked_mobs[current_target_mob_id], 
                            char_x, char_y, current_target_mob_id, tracked_mobs, targeting_locked)
                        
                        last_movement_time = current_time
                        targeting_locked = still_targeting
                        
                        if not still_targeting and current_target_mob_id not in tracked_mobs:
                            current_target_mob_id = None
                        
                        # Handle stuck state
                        if not move_success and current_time - last_successful_movement_time > stuck_timeout and not just_made_random_move:
                            make_random_move(pm, char_x, char_y)
                            just_made_random_move = True
                            last_movement_time = current_time

            # Track mob movement
            if (face_val == last_face_val and
                x_val == last_x_val and
                y_val == last_y_val):
                time.sleep(0.04)
                continue

            last_face_val = face_val
            last_x_val = x_val
            last_y_val = y_val

            # Skip (0,0)
            if x_val == 0 and y_val == 0:
                continue

            # Calculate previous position
            dx, dy = FACE_OFFSETS.get(face_val, (0, 0))
            old_x = x_val - dx
            old_y = y_val - dy

            # Check if from spawn
            spawn_key = f"{x_val}_{y_val}"
            is_from_spawn = spawn_key in spawn_locations
            
            found_mob_id = None
            
            # Check if existing mob
            for mob_id, coords in tracked_mobs.items():
                if coords['x'] == old_x and coords['y'] == old_y:
                    found_mob_id = mob_id
                    break
            
            if found_mob_id is not None:
                # Update existing mob
                tracked_mobs[found_mob_id]['x'] = x_val
                tracked_mobs[found_mob_id]['y'] = y_val
                tracked_mobs[found_mob_id]['last_activity_time'] = current_time
                facing = FACE_NAMES.get(face_val, '?')
                print(f"[Mob {found_mob_id}] => ({x_val}, {y_val}) facing {facing}")
            else:
                # New mob detected
                tracked_mobs[next_mob_id] = {
                    'x': x_val, 
                    'y': y_val, 
                    'last_x': x_val, 
                    'last_y': y_val,
                    'last_activity_time': current_time,
                    'from_spawn': is_from_spawn
                }
                facing = FACE_NAMES.get(face_val, '?')
                print(f"New mob #{next_mob_id} => ({x_val}, {y_val}) facing {facing}")
                next_mob_id += 1

            time.sleep(0.03)
            
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()