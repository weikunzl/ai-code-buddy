export type SoundRole =
  | "input_required"
  | "answer_sent"
  | "deny"
  | "complete"
  | "ui_click";

const SOUND_ASSETS: Record<SoundRole, number> = {
  input_required: require("../../assets/sounds/input_required.wav"),
  answer_sent: require("../../assets/sounds/answer_sent.wav"),
  deny: require("../../assets/sounds/deny.wav"),
  complete: require("../../assets/sounds/complete.wav"),
  ui_click: require("../../assets/sounds/ui_click.wav"),
};

let configured = false;
let audioModule: typeof import("expo-audio") | null = null;

async function getAudioModule(): Promise<typeof import("expo-audio")> {
  if (!audioModule) {
    audioModule = await import("expo-audio");
  }
  return audioModule;
}

async function ensureAudioMode(): Promise<void> {
  if (configured) return;
  const { setAudioModeAsync } = await getAudioModule();
  await setAudioModeAsync({
    playsInSilentMode: true,
    interruptionMode: "mixWithOthers",
  });
  configured = true;
}

/** Play a bundled buddy sound (no-op when muted). Lazy-loads expo-audio for Expo Go compatibility. */
export async function playBuddySound(role: SoundRole, muted: boolean): Promise<void> {
  if (muted) return;
  try {
    const { createAudioPlayer } = await getAudioModule();
    await ensureAudioMode();
    const player = createAudioPlayer(SOUND_ASSETS[role]);
    const sub = player.addListener("playbackStatusUpdate", (status) => {
      if (status.didJustFinish) {
        sub.remove();
        player.release();
      }
    });
    player.play();
  } catch {
    // Ignore playback errors (simulator, missing native module, etc.)
  }
}
