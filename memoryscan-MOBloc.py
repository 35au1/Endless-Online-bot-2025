import time
import pymem
import psutil
import os
import struct
from datetime import datetime
from collections import defaultdict

# Pattern description with dynamic values:
# [00-03] 00 00 00 [01-FF] 00 00 00 [01-FF] 00 00 00 [00-03] 00 00 00 [00-03] 00 00 00 00 00 00 00 00 00 00 00
# The first, fifth, ninth, thirteenth, and seventeenth bytes should change over time
# The thirteenth and seventeenth bytes should always be the same value

# Memory range to scan
START_ADDR = 0x0019A000
END_ADDR = 0x0019D000

# Minimum number of scans required
MIN_SCANS = 4

# Minimum number of different values required for dynamic fields
MIN_DIFFERENT_VALUES = 4

def select_endless_pid():
    """Find all processes named 'endless.exe' and let user pick one if there's more than one."""
    endless_pids = []
    for proc in psutil.process_iter():
        if proc.name().lower() == 'endless.exe':
            endless_pids.append(proc.pid)

    if not endless_pids:
        print("No 'endless.exe' process found.")
        return None

    if len(endless_pids) == 1:
        pid = endless_pids[0]
        print(f"Found one 'endless.exe' process (PID {pid}).")
        return pid

    print("Multiple 'endless.exe' processes found:")
    for i, pid in enumerate(endless_pids, start=1):
        print(f"{i}. PID = {pid}")

    while True:
        choice = input("Select the process # to attach: ").strip()
        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(endless_pids):
                return endless_pids[index - 1]
        print("Invalid selection. Try again.")

def is_pattern_match(buffer, offset):
    """
    Check if the bytes at the current offset match our pattern.
    
    Pattern:
    [00-03] 00 00 00 [01-FF] 00 00 00 [01-FF] 00 00 00 [00-03] 00 00 00 [00-03] 00 00 00 00 00 00 00 00 00 00 00
    
    The 13th and 17th bytes (indexes 12 and 16) should be the same value.
    """
    try:
        # First byte should be between 0-3
        if not (0 <= buffer[offset] <= 3):
            return False
        
        # Next 3 bytes should be zeros
        if buffer[offset+1] != 0 or buffer[offset+2] != 0 or buffer[offset+3] != 0:
            return False
        
        # Fifth byte should be between 1-255
        if not (1 <= buffer[offset+4] <= 255):
            return False
        
        # Next 3 bytes should be zeros
        if buffer[offset+5] != 0 or buffer[offset+6] != 0 or buffer[offset+7] != 0:
            return False
        
        # Ninth byte should be between 1-255
        if not (1 <= buffer[offset+8] <= 255):
            return False
        
        # Next 3 bytes should be zeros
        if buffer[offset+9] != 0 or buffer[offset+10] != 0 or buffer[offset+11] != 0:
            return False
        
        # 13th byte should be between 0-3
        if not (0 <= buffer[offset+12] <= 3):
            return False
        
        # Next 3 bytes should be zeros
        if buffer[offset+13] != 0 or buffer[offset+14] != 0 or buffer[offset+15] != 0:
            return False
        
        # 17th byte should be between 0-3 and EQUAL to 13th byte
        if not (0 <= buffer[offset+16] <= 3) or buffer[offset+16] != buffer[offset+12]:
            return False
        
        # Next 3 bytes should be zeros
        if buffer[offset+17] != 0 or buffer[offset+18] != 0 or buffer[offset+19] != 0:
            return False
        
        # Last 12 bytes should be zeros
        for i in range(20, 32):
            if buffer[offset+i] != 0:
                return False
        
        return True
        
    except IndexError:
        # If we're near the end of the buffer, we might get an index error
        return False

def extract_dynamic_values(buffer, offset):
    """Extract the dynamic values from the matched pattern."""
    return {
        'first_byte': buffer[offset],
        'fifth_byte': buffer[offset+4],
        'ninth_byte': buffer[offset+8],
        'control_bytes': buffer[offset+12]  # 13th and 17th bytes should be the same
    }

def format_pattern(buffer, offset):
    """Format the matched pattern for display."""
    pattern_bytes = buffer[offset:offset+32]
    hex_values = ' '.join(f"{b:02X}" for b in pattern_bytes)
    return hex_values

def scan_memory(pm, scan_number):
    """Scan memory for the pattern."""
    print(f"\nScan #{scan_number}: Scanning memory range 0x{START_ADDR:08X} to 0x{END_ADDR:08X}...")
    
    # Calculate the size of memory to read
    memory_size = END_ADDR - START_ADDR
    
    try:
        # Read the memory block
        buffer = pm.read_bytes(START_ADDR, memory_size)
        
        # Found matches list: (addr, pattern_string, dynamic_values)
        matches = []
        
        # Scan the buffer
        for offset in range(0, len(buffer) - 32):
            if is_pattern_match(buffer, offset):
                addr = START_ADDR + offset
                pattern = format_pattern(buffer, offset)
                dynamic_values = extract_dynamic_values(buffer, offset)
                matches.append((addr, pattern, dynamic_values))
        
        return matches
    
    except Exception as e:
        print(f"Error scanning memory: {e}")
        return []

def check_pattern_changes(address_scans):
    """
    Check if the dynamic fields have enough variation across scans.
    
    According to requirements, we need at least 4 different values across the scans
    for the first three dynamic fields: first byte (00-03), fifth byte (01-FF), and ninth byte (01-FF).
    """
    # Extract all values from the dynamic fields across all scans
    first_bytes = []   # First byte (index 0)
    fifth_bytes = []   # Fifth byte (index 4)
    ninth_bytes = []   # Ninth byte (index 8)
    
    for _, _, dynamic_values in address_scans:
        first_bytes.append(dynamic_values['first_byte'])
        fifth_bytes.append(dynamic_values['fifth_byte'])
        ninth_bytes.append(dynamic_values['ninth_byte'])
    
    # Get unique values for each dynamic field
    unique_first = set(first_bytes)
    unique_fifth = set(fifth_bytes)
    unique_ninth = set(ninth_bytes)
    
    # Count total number of different values across the three fields
    total_different_values = len(unique_first) + len(unique_fifth) + len(unique_ninth)
    
    # Log the analysis
    print(f"  Different values: first byte={len(unique_first)}, fifth byte={len(unique_fifth)}, " +
          f"ninth byte={len(unique_ninth)}, total={total_different_values}")
    print(f"  First byte values: {', '.join(f'{v:02X}' for v in sorted(unique_first))}")
    print(f"  Fifth byte values: {', '.join(f'{v:02X}' for v in sorted(unique_fifth))}")
    print(f"  Ninth byte values: {', '.join(f'{v:02X}' for v in sorted(unique_ninth))}")
    
    # We must have at least 4 different values across ALL these fields combined
    return total_different_values >= 4

def write_address_to_file(valid_addresses):
    """Write only the memory address to mobxy.txt file."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(script_dir, "mobxy.txt")
    
    with open(filename, "w") as f:
        if valid_addresses:
            # Write only the first valid address (hex format with 0x prefix)
            f.write(f"0x{valid_addresses[0]:08X}")
    
    print(f"\nAddress written to: {filename}")
    return filename

def main():
    pid = select_endless_pid()
    if pid is None:
        return

    try:
        pm = pymem.Pymem(pid)
        print(f"Successfully attached to process ID {pid}")
        
        # Track all addresses across scans
        address_scans = defaultdict(list)
        total_scan_count = 0
        valid_addresses = []
        
        # Keep scanning until we find at least one valid address or hit a limit
        scan_limit = 100  # Limit to prevent infinite scanning
        
        print(f"Beginning memory scans. Looking for patterns with at least {MIN_DIFFERENT_VALUES} different values.")
        print(f"Will perform at least {MIN_SCANS} scans, and continue if needed.")
        
        while total_scan_count < scan_limit and (total_scan_count < MIN_SCANS or not valid_addresses):
            total_scan_count += 1
            
            # Perform scan
            scan_results = scan_memory(pm, total_scan_count)
            
            # Process results
            if scan_results:
                print(f"Scan #{total_scan_count}: Found {len(scan_results)} matching patterns.")
                
                # Add results to address tracking
                for addr, pattern, dynamic_values in scan_results:
                    address_scans[addr].append((total_scan_count, pattern, dynamic_values))
                
                # After minimum scans, check for valid addresses
                if total_scan_count >= MIN_SCANS:
                    # Find addresses with proper variance
                    valid_addresses = []
                    print("\nEvaluating pattern changes for each address:")
                    for addr, scans in address_scans.items():
                        if len(scans) >= MIN_SCANS:
                            print(f"Address 0x{addr:08X}:")
                            if check_pattern_changes(scans):
                                valid_addresses.append(addr)
                                print(f"  ✓ VALID - Has at least 4 changes across dynamic fields")
                            else:
                                print(f"  ✗ INVALID - Not enough changes in dynamic fields")
                    
                    if valid_addresses:
                        print(f"\nFound {len(valid_addresses)} valid addresses with sufficient value changes.")
                        print("Addresses found:")
                        for addr in valid_addresses:
                            print(f"  0x{addr:08X}")
            else:
                print(f"Scan #{total_scan_count}: No matching patterns found.")
            
            # Wait for next scan
            if not valid_addresses or total_scan_count < MIN_SCANS:
                print(f"Waiting for next scan (1 second)...")
                time.sleep(1)
        
        # Final report and output address to file
        if valid_addresses:
            result_file = write_address_to_file(valid_addresses)
            print(f"\nScan complete! {len(valid_addresses)} valid patterns found.")
            print(f"Address has been saved to {result_file}")
        else:
            print(f"\nAfter {total_scan_count} scans, no valid patterns were found matching the criteria.")
            print("Try adjusting the memory range or pattern requirements.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Clean up
        try:
            pm.close_process()
            print("Process handle closed.")
        except:
            pass

if __name__ == "__main__":
    main()