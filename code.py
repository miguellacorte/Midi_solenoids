# SPDX-FileCopyrightText: 2020 Liz Clark for Adafruit Industries
#
# SPDX-License-Identifier: MIT

import time
import board
import digitalio
import struct
import supervisor

print("Code started running")

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


def play_midi_file(filename):
    print(f"Starting to play {filename}")
    start_time = time.monotonic()
    try:
        with open(filename, "rb") as f:
            print("Reading MIDI header...")
            header = f.read(14)
            if header[:4] != b"MThd" or struct.unpack(">I", header[4:8])[0] != 6:
                print("Not a valid MIDI file")
                return

            format_type, num_tracks, time_division = struct.unpack(">HHH", header[8:14])
            print("MIDI format: " + str(format_type) + 
                  ", Tracks: " + str(num_tracks) + 
                  ", Time Division: " + str(time_division))

            tempo = 500000  # microseconds per quarter note (120 BPM)

            # Calculate the time remaining until playback should start
            elapsed_time = time.monotonic() - start_time
            remaining_delay = max(0, 3 - elapsed_time)
            print(f"Waiting {remaining_delay:.2f} seconds before starting playback...")
            time.sleep(remaining_delay)

            print("Starting playback now!")

            for track in range(num_tracks):
                print(f"Processing track {track + 1} of {num_tracks}")
                track_start_time = time.monotonic()
                
                track_header = f.read(8)
                if track_header[:4] != b"MTrk":
                    print(f"Track {track + 1} is not valid")
                    continue

                track_length = struct.unpack(">I", track_header[4:])[0]
                track_data = f.read(track_length)
                print(f"Track {track + 1} length: {track_length} bytes")
                
                i = 0
                while i < len(track_data):
                    delta_time, i = read_variable_length(track_data, i)
                    
                    if time_division & 0x8000:
                        frames_per_second = -(time_division >> 8)
                        ticks_per_frame = time_division & 0x00FF
                        d_ms = delta_time * 1000 / (frames_per_second * ticks_per_frame)
                    else:
                        d_ms = (delta_time * tempo) / (time_division * 1000)

                    time.sleep(d_ms / 1000)  # Convert to seconds
                    event_type = track_data[i]
                    i += 1

                    if event_type == 0xFF:  # Meta event
                        meta_type = track_data[i]
                        length, i = read_variable_length(track_data, i + 1)
                        if meta_type == 0x51:  # Set Tempo
                            tempo = struct.unpack(">I", b'\x00' + track_data[i:i+3])[0]
                            print(f"Tempo changed to {60000000 / tempo} BPM")
                        i += length
                    elif event_type == 0xF0 or event_type == 0xF7:  # SysEx event
                        length, i = read_variable_length(track_data, i)
                        i += length
                    elif event_type & 0x80:  # MIDI event
                        if event_type & 0xF0 in (0x80, 0x90):  # Note Off or Note On
                            note = track_data[i]
                            velocity = track_data[i + 1]
                            i += 2

                            if event_type & 0xF0 == 0x90 and velocity > 0:
                                handle_note_on(note)
                            else:
                                handle_note_off(note)
                
                track_end_time = time.monotonic()
                print("Track " + str(track + 1) + " processed in " +
                      f"{track_end_time - track_start_time:.2f} seconds")

        end_time = time.monotonic()
        print(f"Total MIDI processing time: {end_time - start_time:.2f} seconds")
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
print("Starting up... Looking for MIDI file.")
midi_file_path = "/song.mid"  # Make sure this matches your MIDI file

# Add a startup sound to indicate the board is ready
# def play_startup_sound():
#     for noid in noids:
#         noid.value = True
#         time.sleep(0.1)
#         noid.value = False
#         time.sleep(0.1)

# print("Playing startup sound...")
# play_startup_sound()

try:
    print(f"Attempting to open MIDI file: {midi_file_path}")
    with open(midi_file_path, "rb") as f:
        print(f"Found MIDI file: {midi_file_path}")
        file_size = f.seek(0, 2)
        f.seek(0)
        print(f"MIDI file size: {file_size} bytes")
    print("Starting playback process...")
    start_time = time.monotonic()
    print(f"Playback will begin in 3 seconds (at {start_time + 3:.2f})")
    play_midi_file(midi_file_path)
    print("Finished playing MIDI file.")
except OSError as e:
    print(f"MIDI file not found at {midi_file_path}")
    print(f"Error: {e}")

print("Playback complete. Entering idle state.")
print("Press the reset button to replay the MIDI file.")

while True:
    # Check if the reset button was pressed
    if supervisor.runtime.serial_bytes_available:
        print("Reset detected. Restarting program.")
        supervisor.reload()
    
    time.sleep(0.1)  # Small delay to prevent busy-waiting
