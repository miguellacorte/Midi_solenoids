# SPDX-FileCopyrightText: 2020 Liz Clark for Adafruit Industries
#
# SPDX-License-Identifier: MIT

import time
import board
import digitalio
import struct
import supervisor
import os  # Import os to handle directory operations
import random  # Import random to select a file randomly

print("Code started running")
boot_time = time.monotonic()

#  pins for the solenoid output signals
noid_pins = [board.D5, board.D6, board.D9, board.D10]

#  array for the solenoids
noids = []

#  setup for the solenoid pins to be outputs
for pin in noid_pins:
    noid = digitalio.DigitalInOut(pin)
    noid.direction = digitalio.Direction.OUTPUT
    noids.append(noid)

#  MIDI note array
notes = [60, 61, 62, 63]


def load_midi_file(filename):
    print(f"Loading {filename}")
    with open(filename, "rb") as f:
        return f.read()


def play_midi_data(midi_data):
    print("Starting playback")
    try:
        if midi_data[:4] != b"MThd" or struct.unpack(">I", midi_data[4:8])[0] != 6:
            print("Not a valid MIDI file")
            return

        format_type, num_tracks, time_division = struct.unpack(">HHH", midi_data[8:14])
        print(f"MIDI format: {format_type}, Tracks: {num_tracks}, Time Division: {time_division}")

        tempo = 500000  # microseconds per quarter note (120 BPM)
        i = 14  # Start after the header

        for track in range(num_tracks):
            print(f"Processing track {track + 1} of {num_tracks}")
            track_start_time = time.monotonic()
            
            if midi_data[i:i+4] != b"MTrk":
                print(f"Track {track + 1} is not valid")
                continue

            track_length = struct.unpack(">I", midi_data[i+4:i+8])[0]
            i += 8
            track_end = i + track_length
            
            while i < track_end:
                delta_time, i = read_variable_length(midi_data, i)
                
                if time_division & 0x8000:
                    frames_per_second = -(time_division >> 8)
                    ticks_per_frame = time_division & 0x00FF
                    d_ms = delta_time * 1000 / (frames_per_second * ticks_per_frame)
                else:
                    d_ms = (delta_time * tempo) / (time_division * 1000)

                time.sleep(d_ms / 1000)  # Convert to seconds
                event_type = midi_data[i]
                i += 1

                if event_type == 0xFF:  # Meta event
                    meta_type = midi_data[i]
                    length, i = read_variable_length(midi_data, i + 1)
                    if meta_type == 0x51:  # Set Tempo
                        tempo = struct.unpack(">I", b'\x00' + midi_data[i:i+3])[0]
                        print(f"Tempo changed to {60000000 / tempo} BPM")
                    i += length
                elif event_type == 0xF0 or event_type == 0xF7:  # SysEx event
                    length, i = read_variable_length(midi_data, i)
                    i += length
                elif event_type & 0x80:  # MIDI event
                    if event_type & 0xF0 in (0x80, 0x90):  # Note Off or Note On
                        note = midi_data[i]
                        velocity = midi_data[i + 1]
                        i += 2

                        if event_type & 0xF0 == 0x90 and velocity > 0:
                            handle_note_on(note)
                        else:
                            handle_note_off(note)
            
            track_end_time = time.monotonic()
            print(f"Track {track + 1} processed in {track_end_time - track_start_time:.2f} seconds")

    except Exception as e:
        print(f"Error playing MIDI file: {e}")


def read_variable_length(data, start):
    value = 0
    i = start
    while True:
        byte = data[i]
        value = (value << 7) | (byte & 0x7F)
        i += 1
        if not byte & 0x80:
            break
    return value, i


def handle_note_on(note):
    for i, note_value in enumerate(notes):
        if note == note_value:
            noids[i].value = True
            print(f"Note On: {note}")


def handle_note_off(note):
    for i, note_value in enumerate(notes):
        if note == note_value:
            noids[i].value = False
            print(f"Note Off: {note}")


# Main execution
print("Starting up... Looking for MIDI files.")
midi_directory = "/midi_files"  # Directory containing subdirectories of MIDI files

while True:
    try:
        # List all subdirectories in the midi_directory
        subdirectories = [d for d in os.listdir(midi_directory) if d.isdigit()]
        subdirectories.sort(key=int)  # Sort numerically
        
        if not subdirectories:
            print("No numbered subdirectories found in the directory.")
        else:
            for subdir in subdirectories:
                subdir_path = midi_directory + "/" + subdir
                # List all MIDI files in the subdirectory, excluding hidden/system files
                midi_files = [f for f in os.listdir(subdir_path) if f.endswith('.mid') and not f.startswith('.')]
                if not midi_files:
                    print(f"No MIDI files found in {subdir_path}.")
                else:
                    # Select a random MIDI file
                    selected_file = random.choice(midi_files)
                    # Manually concatenate the directory and file name
                    midi_file_path = subdir_path + "/" + selected_file
                    print(f"Selected MIDI file: {midi_file_path}")

                    # Load MIDI data
                    midi_data = load_midi_file(midi_file_path)
                    print(f"MIDI file loaded, size: {len(midi_data)} bytes")

                    # Reset boot_time and calculate wait time
                    boot_time = time.monotonic()
                    time_to_next_5s = 5 - ((boot_time - int(boot_time)) % 5)
                    
                    print(f"Waiting {time_to_next_5s:.2f} seconds before starting playback...")
                    time.sleep(time_to_next_5s)

                    print("Starting playback now!")
                    play_midi_data(midi_data)
                    print("Finished playing MIDI file.")

                    print("Playback complete. Entering idle state.")
                    print("Resting for 10 seconds...")
                    time.sleep(10)  # 10 seconds delay between subdirectory playbacks

    except OSError as e:
        print(f"Error accessing MIDI files in {midi_directory}")
        print(f"Error: {e}")

    # Check if the reset button was pressed
    if supervisor.runtime.serial_bytes_available:
        print("Reset detected. Restarting program.")
        supervisor.reload()
