import time
import pymem
import psutil
import os
from datetime import datetime
from collections import defaultdict

# Pattern description:
# (digit 4-180) 00 00 00 (digit 4-180) 00 00 00 ?? ?? 00 00 ?? ?? 00 00 00 00 00 00 00 00 00 00 ?? ?? ?? ?? ?? ?? FF FF
# The first and fifth byte should be between 4-180 and remain constant across scans
# The ?? bytes can be any value and are ignored in the pattern matching

# Memory range to scan
START_ADDR = 0x04000000
END_ADDR = 0x07000000

# Number of scans to perform
NUM_SCANS = 2

# Chunk size for memory reading to handle the larger range
CHUNK_SIZE = 1024 * 1024  # 1 MB chunks

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

def is_pattern_match(buffer, offset, debug=False):
    """
    Check if the bytes at the current offset match our pattern.
    
    Pattern:
    (digit 4-180) 00 00 00 (digit 4-180) 00 00 00 ?? ?? 00 00 ?? ?? 00 00 00 00 00 00 00 00 00 00 ?? ?? ?? ?? ?? ?? FF FF
    
    The first and fifth bytes should be between 4-180.
    ?? bytes can be any value and are ignored in the pattern matching.
    """
    try:
        # If in debug mode and the address looks like it might be interesting,
        # print the full pattern for inspection
        addr = START_ADDR + offset
        if debug and ((0x04F04BB0 <= addr <= 0x04F04BE0) or (addr % 0x100000 == 0)):
            pattern = ' '.join(f"{b:02X}" for b in buffer[offset:offset+32])
            print(f"Debug: Checking address 0x{addr:08X}: {pattern}")
        
        # First byte should be between 4-180
        if not (4 <= buffer[offset] <= 180):
            if debug and (0x04F04BB0 <= addr <= 0x04F04BE0):
                print(f"  Fail at pos 0: Value {buffer[offset]:02X} not in range 4-180")
            return False
        
        # Next 3 bytes should be zeros
        if buffer[offset+1] != 0 or buffer[offset+2] != 0 or buffer[offset+3] != 0:
            if debug and (0x04F04BB0 <= addr <= 0x04F04BE0):
                print(f"  Fail at pos 1-3: Values {buffer[offset+1]:02X} {buffer[offset+2]:02X} {buffer[offset+3]:02X} should be zeros")
            return False
        
        # Fifth byte should be between 4-180
        if not (4 <= buffer[offset+4] <= 180):
            if debug and (0x04F04BB0 <= addr <= 0x04F04BE0):
                print(f"  Fail at pos 4: Value {buffer[offset+4]:02X} not in range 4-180")
            return False
        
        # Next 3 bytes should be zeros
        if buffer[offset+5] != 0 or buffer[offset+6] != 0 or buffer[offset+7] != 0:
            if debug and (0x04F04BB0 <= addr <= 0x04F04BE0):
                print(f"  Fail at pos 5-7: Values {buffer[offset+5]:02X} {buffer[offset+6]:02X} {buffer[offset+7]:02X} should be zeros")
            return False
        
        # Positions 8-9 can be any value (??), skip checking
        
        # Positions 10-11 should be zeros
        if buffer[offset+10] != 0 or buffer[offset+11] != 0:
            if debug and (0x04F04BB0 <= addr <= 0x04F04BE0):
                print(f"  Fail at pos 10-11: Values {buffer[offset+10]:02X} {buffer[offset+11]:02X} should be zeros")
            return False
        
        # Positions 12-13 can be any value (??), skip checking
        
        # Positions 14-15 should be zeros
        if buffer[offset+14] != 0 or buffer[offset+15] != 0:
            if debug and (0x04F04BB0 <= addr <= 0x04F04BE0):
                print(f"  Fail at pos 14-15: Values {buffer[offset+14]:02X} {buffer[offset+15]:02X} should be zeros")
            return False
        
        # Next 8 bytes should be zeros
        for i in range(16, 24):
            if buffer[offset+i] != 0:
                if debug and (0x04F04BB0 <= addr <= 0x04F04BE0):
                    print(f"  Fail at pos {i}: Value {buffer[offset+i]:02X} should be zero")
                return False
        
        # Positions 24-29 can be any value (??), skip checking
        
        # Positions 30-31 should be 0xFF
        if buffer[offset+30] != 0xFF or buffer[offset+31] != 0xFF:
            if debug and (0x04F04BB0 <= addr <= 0x04F04BE0):
                print(f"  Fail at pos 30-31: Values {buffer[offset+30]:02X} {buffer[offset+31]:02X} should be 0xFF")
            return False
        
        if debug and (0x04F04BB0 <= addr <= 0x04F04BE0):
            print(f"  ✓ MATCH at 0x{addr:08X}")
        
        return True
        
    except IndexError:
        # If we're near the end of the buffer, we might get an index error
        if debug and (0x04F04BB0 <= addr <= 0x04F04BE0):
            print(f"  Fail: IndexError at address 0x{addr:08X}")
        return False

def extract_static_values(buffer, offset):
    """Extract the static values from the matched pattern."""
    return {
        'first_byte': buffer[offset],
        'fifth_byte': buffer[offset+4],
    }

def format_pattern(buffer, offset):
    """Format the matched pattern for display."""
    pattern_bytes = buffer[offset:offset+32]
    hex_values = ' '.join(f"{b:02X}" for b in pattern_bytes)
    return hex_values

def scan_memory_chunk(pm, start_addr, chunk_size, scan_number, debug_mode=False):
    """Scan a chunk of memory for the pattern."""
    try:
        # Read the memory chunk
        buffer = pm.read_bytes(start_addr, chunk_size)
        
        # Found matches list: (addr, pattern_string, static_values)
        matches = []
        
        # Special case: If the address range includes our example address, add debug info
        contains_example = (0x04F04BB0 <= start_addr <= 0x04F04BE0) or (start_addr <= 0x04F04BB0 <= start_addr + chunk_size)
        
        if contains_example and debug_mode:
            print(f"\n*** FOUND EXAMPLE REGION: 0x{start_addr:08X} - 0x{start_addr + chunk_size:08X} ***")
            
            # Calculate offset for our example
            example_offset = 0x04F04BBC - start_addr
            if 0 <= example_offset < len(buffer) - 32:
                # Print a dump of the memory around our example
                example_start = max(0, example_offset - 16)
                example_end = min(len(buffer), example_offset + 48)
                
                print("Memory dump around example region:")
                for i in range(example_start, example_end, 16):
                    addr = start_addr + i
                    bytes_str = ' '.join(f"{b:02X}" for b in buffer[i:i+16])
                    ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in buffer[i:i+16])
                    print(f"0x{addr:08X}: {bytes_str} | {ascii_str}")
        
        # Enable debug mode in this specific region
        local_debug = contains_example and debug_mode
        
        # Scan the buffer
        for offset in range(0, len(buffer) - 32):
            if is_pattern_match(buffer, offset, debug=local_debug):
                addr = start_addr + offset
                pattern = format_pattern(buffer, offset)
                static_values = extract_static_values(buffer, offset)
                matches.append((addr, pattern, static_values))
        
        return matches
    
    except Exception as e:
        # Print error but continue with next chunk
        print(f"Error scanning memory at 0x{start_addr:08X}: {e}")
        return []

def scan_memory(pm, scan_number, debug_mode=False):
    """Scan memory for the pattern, chunk by chunk."""
    print(f"\nScan #{scan_number}: Scanning memory range 0x{START_ADDR:08X} to 0x{END_ADDR:08X}...")
    
    all_matches = []
    chunks_scanned = 0
    
    # Process memory in chunks
    current_addr = START_ADDR
    while current_addr < END_ADDR:
        # Calculate chunk size (might be smaller for last chunk)
        size = min(CHUNK_SIZE, END_ADDR - current_addr)
        
        # Progress indicator (every 10 chunks)
        chunks_scanned += 1
        if chunks_scanned % 10 == 0:
            progress = (current_addr - START_ADDR) / (END_ADDR - START_ADDR) * 100
            print(f"  Progress: {progress:.1f}% (Address: 0x{current_addr:08X})")
        
        try:
            # Scan this chunk
            matches = scan_memory_chunk(pm, current_addr, size, scan_number, debug_mode)
            all_matches.extend(matches)
            
        except Exception as e:
            print(f"Error processing chunk at 0x{current_addr:08X}: {e}")
        
        # Move to next chunk
        current_addr += size
    
    print(f"Scan #{scan_number} complete. Total matches found: {len(all_matches)}")
    return all_matches

def verify_consistent_patterns(address_scans):
    """
    Verify that the static values remain consistent across all scans.
    Return addresses that had the same values in all scans.
    """
    consistent_addresses = []
    
    for addr, scans in address_scans.items():
        # Check if we have the right number of scans
        if len(scans) == NUM_SCANS:
            # Check if static values are consistent across all scans
            first_values = set(values['first_byte'] for _, _, values in scans)
            fifth_values = set(values['fifth_byte'] for _, _, values in scans)
            
            # If there's only one unique value for each static field, 
            # then the pattern is consistent
            if len(first_values) == 1 and len(fifth_values) == 1:
                consistent_addresses.append(addr)
    
    return consistent_addresses

def write_results_to_file(consistent_addresses, address_scans):
    """Write scan results to a simple text file."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(script_dir, "playerxy.txt")
    
    with open(filename, "w") as f:
        for addr in consistent_addresses:
            f.write(f"0x{addr:08X}\n")
    
    print(f"\nResults written to: {filename}")
    return filename

def main():
    pid = select_endless_pid()
    if pid is None:
        return
    
    # Set debug mode to False by default
    debug_mode = False
    specific_addr = None
    
    try:
        pm = pymem.Pymem(pid)
        print(f"Successfully attached to process ID {pid}")
        
        # Track all addresses across scans
        address_scans = defaultdict(list)
        
        print(f"\nBeginning {NUM_SCANS} memory scans. Looking for consistent patterns across all scans.")
        print(f"Pattern: (digit 4-180) 00 00 00 (digit 4-180) 00 00 00 ?? ?? 00 00 ?? ?? 00 00 00 00 00 00 00 00 00 00 ?? ?? FF FF ?? ?? FF FF")
        print(f"The ?? bytes can be any value and may change across scans. The digits must remain consistent.")
        
        # Perform all scans
        for scan_num in range(1, NUM_SCANS + 1):
            # Perform scan
            scan_results = scan_memory(pm, scan_num, debug_mode)
            
            # Process results
            if scan_results:
                print(f"Scan #{scan_num}: Found {len(scan_results)} matching patterns.")
                
                # Add results to address tracking
                for addr, pattern, static_values in scan_results:
                    address_scans[addr].append((scan_num, pattern, static_values))
                
                # Progress display
                print(f"Current unique addresses being tracked: {len(address_scans)}")
            else:
                print(f"Scan #{scan_num}: No matching patterns found.")
            
            # Wait between scans (unless it's the last scan)
            if scan_num < NUM_SCANS:
                print(f"Waiting for next scan (1 second)...")
                time.sleep(1)
        
        # Process results after all scans
        print("\nAll scans complete. Analyzing results...")
        
        # Find addresses that maintained consistent values across all scans
        consistent_addresses = verify_consistent_patterns(address_scans)
        
        # Final report
        if consistent_addresses:
            # Print addresses to console
            print("\nFound addresses:")
            for addr in consistent_addresses:
                print(f"0x{addr:08X}")
                
            # Write to file
            result_file = write_results_to_file(consistent_addresses, address_scans)
            print(f"\nScan complete! {len(consistent_addresses)} consistent patterns found.")
            print(f"Results have been saved to {result_file}")
        else:
            print(f"\nAfter {NUM_SCANS} scans, no consistent patterns were found matching the criteria.")
            # Create empty file anyway
            with open("playerxy.txt", "w") as f:
                pass
            print("Created empty playerxy.txt file")
        
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
