

VoicePipeline:
    Running STT stream 1 for users speech
        Use openai Realtime transcription api
            Emits input_audio_transcription.completed/failed, speech_started and speech_stopped events
            if speech_stopped
                nothing for now

            if input_audio_transcription.completed
                appends the transcribtion to history under role: user
                Run workflow or agent. That returns a text and send it to be TTS

            if speech_started
                cancels workflow run
                sends the event to TTS stream
    
    Running TTS stream
        Use openai TTS: client.audio.speech.with_streaming_response.create
            gets text and TTS it then streams audio to the person and to internal STT stream
            listens to speech_started event
                stops any audio playing
                cancels the current text's TTS


    Running STT stream for internal speech
        Use openai Realtime transcription api
            listens to audio played by TTS stream
            appends the transcribtion to history under role: agent.

Workflow or agent:
    it should just say "Hello World", so just return that in a stream version everytime it is run

Use the computers microphone and audio player so i can test it
