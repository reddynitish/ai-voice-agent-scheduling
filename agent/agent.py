from dotenv import load_dotenv

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, TurnHandlingOptions, inference

load_dotenv(".env.local")


class Scheduler(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a friendly voice receptionist who helps callers book appointments.
Keep replies short and conversational. Never use markdown, lists, emojis, or symbols.""",
        )


server = AgentServer()


@server.rtc_session(agent_name="scheduler")
async def entrypoint(ctx: agents.JobContext):
    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3", language="en"),
        llm=inference.LLM(model="openai/gpt-4.1-mini"),
        tts=inference.TTS(model="cartesia/sonic-3", voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"),
        vad=inference.VAD(),
        turn_handling=TurnHandlingOptions(turn_detection=inference.TurnDetector()),
    )
    await session.start(room=ctx.room, agent=Scheduler())
    await session.generate_reply(instructions="Greet the caller and ask how you can help.")


if __name__ == "__main__":
    agents.cli.run_app(server)
