from __future__ import annotations

from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types


class LiveSessionService:
    def __init__(self, app_name: str, root_agent, voice_name: str):
        self.app_name = app_name
        self.root_agent = root_agent
        self.voice_name = voice_name
        self.session_service = InMemorySessionService()

    def start_agent_session(self, session_id: str):
        session = self.session_service.create_session(
            app_name=self.app_name,
            user_id=session_id,
            session_id=session_id,
        )

        runner = Runner(
            app_name=self.app_name,
            agent=self.root_agent,
            session_service=self.session_service,
        )

        speech_config = types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice_name)
            )
        )
        run_config = RunConfig(
            response_modalities=["AUDIO"],
            speech_config=speech_config,
            output_audio_transcription={},
        )

        live_request_queue = LiveRequestQueue()
        live_events = runner.run_live(
            session=session,
            live_request_queue=live_request_queue,
            run_config=run_config,
        )
        return live_events, live_request_queue
