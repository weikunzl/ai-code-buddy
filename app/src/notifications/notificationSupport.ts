import Constants from "expo-constants";
import { Platform } from "react-native";

type NotificationsModule = typeof import("expo-notifications");

let notificationsModule: NotificationsModule | null | undefined;

async function loadNotificationsModule(): Promise<NotificationsModule | null> {
  if (notificationsModule !== undefined) {
    return notificationsModule;
  }
  if (Platform.OS === "web") {
    notificationsModule = null;
    return null;
  }
  // Expo Go on Android blocks expo-notifications entirely (SDK 53+).
  if (Platform.OS === "android" && Constants.appOwnership === "expo") {
    notificationsModule = null;
    return null;
  }
  try {
    notificationsModule = await import("expo-notifications");
  } catch {
    notificationsModule = null;
  }
  return notificationsModule;
}

/** True when expo-notifications is installed and allowed on this runtime. */
export async function canUseBuddyNotifications(): Promise<boolean> {
  return (await loadNotificationsModule()) !== null;
}

/** Custom WAV assets need a dev/release build with the notifications plugin. */
export function canUseCustomNotificationSounds(): boolean {
  return Constants.appOwnership !== "expo";
}

export { loadNotificationsModule };
