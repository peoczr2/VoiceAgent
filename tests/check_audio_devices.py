import pyaudio

p = pyaudio.PyAudio()

print("Available audio input devices:")
for i in range(p.get_device_count()):
    dev_info = p.get_device_info_by_index(i)
    if dev_info['maxInputChannels'] > 0:
        print(f"  Device Index: {dev_info['index']} - Name: {dev_info['name']}")

print("\n" + "="*40 + "\n")

print("Available audio output devices:")
for i in range(p.get_device_count()):
    dev_info = p.get_device_info_by_index(i)
    if dev_info['maxOutputChannels'] > 0:
        print(f"  Device Index: {dev_info['index']} - Name: {dev_info['name']}")
        try:
            if p.is_format_supported(16000, output_device=i, output_channels=1, output_format=pyaudio.paInt16):
                print("    [+] Supports 16000 Hz, 1 channel, 16-bit PCM")
            else:
                print("    [-] Does NOT support 16000 Hz, 1 channel, 16-bit PCM")
        except ValueError:
            print(f"    [!] Could not check format support for this device.")

p.terminate()
