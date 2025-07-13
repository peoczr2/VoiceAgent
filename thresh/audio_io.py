import sounddevice as sd
import queue
import threading

class AudioIO:
    def __init__(self, input_queue, output_queue, sample_rate=16000, channels=1, device=None):
        """
        Initializes the AudioIO class.

        Args:
            input_queue (queue.Queue): Queue to put incoming audio chunks into.
            output_queue (queue.Queue): Queue to get outgoing audio chunks from.
            sample_rate (int): The sample rate for audio recording and playback.
            channels (int): The number of audio channels.
            device (int or None): The device ID for microphone and speakers. None for default.
        """
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self.muted = False
        self._stop_event = threading.Event()
        self._input_thread = None
        self._output_thread = None

    def _input_stream_callback(self, indata, frames, time, status):
        """This is called (from a separate thread) for each audio block."""
        if status:
            print(status)
        self.input_queue.put(bytes(indata))

    def _output_stream_callback(self, outdata, frames, time, status):
        """This is called (from a separate thread) for each audio block."""
        if status:
            print(status)
        
        if self.muted:
            outdata[:] = 0
            return

        try:
            data = self.output_queue.get_nowait()
        except queue.Empty:
            outdata.fill(0)
            return
        
        if len(data) < len(outdata):
            outdata[:len(data)] = data
            outdata[len(data):].fill(0)
        else:
            outdata[:] = data

    def start(self):
        """Starts the audio input and output streams in separate threads."""
        self._stop_event.clear()
        
        self.input_stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            device=self.device,
            callback=self._input_stream_callback,
            dtype='int16' # OpenAI requires 16-bit PCM
        )
        self.output_stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            device=self.device,
            callback=self._output_stream_callback,
            dtype='int16'
        )
        
        self.input_stream.start()
        self.output_stream.start()
        print("Audio streams started.")

    def stop(self):
        """Stops the audio input and output streams."""
        self._stop_event.set()
        self.input_stream.stop()
        self.output_stream.stop()
        self.input_stream.close()
        self.output_stream.close()
        print("Audio streams stopped.")

    def mute(self):
        """Mutes the output stream."""
        self.muted = True
        print("Audio output muted.")

    def unmute(self):
        """Unmutes the output stream."""
        self.muted = False
        print("Audio output unmuted.")
