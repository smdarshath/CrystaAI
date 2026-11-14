from __future__ import annotations

from .base import Agent


class Echo(Agent):
    id, name = "echo", "ECHO"
    description = "Voice and speech: voice studio, speech input/output, language, voice, speed and volume. No wake word."
    system_instruction = ("You are Echo, the voice agent. Explain voice limits honestly: browser speech recognition may send audio to the "
                          "browser vendor, languages depend on installed voices, and there is no wake word.")
    permitted_tools = frozenset({"settings_get", "settings_set", "voice_status", "voice_speak", "voice_stop"})

    def do_voice(self, sub, ctx):
        a = sub.args.get("action")
        if a == "lang":
            self.tool(ctx, "settings_set", key="voice_lang", value=sub.args["value"])
            name = "Tamil" if sub.args["value"] == "ta-IN" else "English"
            return self.ok(f"Voice language set to {name}.", ui_actions=[{"type": "refresh_settings"}],
                           limitations=["Needs a matching speech voice/recogniser in your browser or OS; if it sounds wrong, install that language voice."])
        if a in ("mute", "unmute"):
            self.tool(ctx, "settings_set", key="speak_responses", value=(a == "unmute"))
            return self.ok("Okay, I'll stay quiet and show text only." if a == "mute" else "Voice replies are on.",
                           ui_actions=[{"type": "refresh_settings"}, {"type": "stop_speaking"}] if a == "mute" else [{"type": "refresh_settings"}])
        if a == "wake":
            return self.partial("I don't have a wake word. Press the mic button (or Space) when you want to talk — that way nothing listens in the background.",
                                limitations=["Wake-word detection is not implemented."])
        return self.fail("I didn't understand that voice command.")
