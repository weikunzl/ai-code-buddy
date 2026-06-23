import { AppState, Platform } from "react-native";
import type { PendingItem } from "@protocol/index";
import {
  canUseCustomNotificationSounds,
  loadNotificationsModule,
} from "./notificationSupport";

export const APPROVAL_CHANNEL = "devpet-approvals";
export const COMPLETE_CHANNEL = "devpet-complete";
const APPROVAL_SOUND = "input_required.wav";
const COMPLETE_SOUND = "complete.wav";

let initialized = false;

function approvalSound(): string | undefined {
  return canUseCustomNotificationSounds() ? APPROVAL_SOUND : "default";
}

function completeSound(): string | undefined {
  return canUseCustomNotificationSounds() ? COMPLETE_SOUND : "default";
}

function pendingNotificationId(pendingId: string): string {
  return `pending-${pendingId}`;
}

async function ensureAndroidChannels(
  Notifications: NonNullable<Awaited<ReturnType<typeof loadNotificationsModule>>>,
): Promise<void> {
  if (Platform.OS !== "android") return;
  await Notifications.setNotificationChannelAsync(APPROVAL_CHANNEL, {
    name: "Approvals",
    importance: Notifications.AndroidImportance.HIGH,
    sound: approvalSound(),
    enableVibrate: true,
    vibrationPattern: [0, 200, 120, 200],
    lockscreenVisibility: Notifications.AndroidNotificationVisibility.PUBLIC,
    bypassDnd: false,
  });
  await Notifications.setNotificationChannelAsync(COMPLETE_CHANNEL, {
    name: "Session updates",
    importance: Notifications.AndroidImportance.DEFAULT,
    sound: completeSound(),
    lockscreenVisibility: Notifications.AndroidNotificationVisibility.PUBLIC,
  });
}

/** Request permissions and configure channels. Safe to call multiple times. */
export async function initBuddyNotifications(): Promise<boolean> {
  const Notifications = await loadNotificationsModule();
  if (!Notifications) return false;
  if (initialized) return true;
  try {
    Notifications.setNotificationHandler({
      handleNotification: async () => {
        const foreground = AppState.currentState === "active";
        return {
          shouldShowBanner: true,
          shouldShowList: true,
          shouldPlaySound: !foreground,
          shouldSetBadge: true,
        };
      },
    });

    await ensureAndroidChannels(Notifications);

    const current = await Notifications.getPermissionsAsync();
    let granted =
      current.granted ||
      current.ios?.status === Notifications.IosAuthorizationStatus.PROVISIONAL;
    if (!granted) {
      const requested = await Notifications.requestPermissionsAsync({
        ios: {
          allowAlert: true,
          allowBadge: true,
          allowSound: true,
        },
      });
      granted =
        requested.granted ||
        requested.ios?.status === Notifications.IosAuthorizationStatus.PROVISIONAL;
    }

    initialized = granted;
    return granted;
  } catch {
    return false;
  }
}

export async function presentApprovalNotification(
  pending: PendingItem,
  title: string,
  body: string,
  muted: boolean,
): Promise<void> {
  if (muted) return;
  const Notifications = await loadNotificationsModule();
  if (!Notifications) return;
  const granted = await initBuddyNotifications();
  if (!granted) return;

  try {
    const foreground = AppState.currentState === "active";
    await Notifications.scheduleNotificationAsync({
      identifier: pendingNotificationId(pending.id),
      content: {
        title,
        body: body || pending.title,
        sound: foreground ? undefined : approvalSound(),
        data: { type: "approval", pendingId: pending.id },
        priority: Notifications.AndroidNotificationPriority.HIGH,
        channelId: APPROVAL_CHANNEL,
        sticky: true,
      },
      trigger: null,
    });
  } catch {
    // Ignore when notifications unavailable.
  }
}

export async function presentCompleteNotification(
  title: string,
  body: string,
  muted: boolean,
): Promise<void> {
  if (muted) return;
  const Notifications = await loadNotificationsModule();
  if (!Notifications) return;
  const granted = await initBuddyNotifications();
  if (!granted) return;

  try {
    await Notifications.scheduleNotificationAsync({
      identifier: `complete-${Date.now()}`,
      content: {
        title,
        body,
        sound: completeSound(),
        data: { type: "complete" },
        channelId: COMPLETE_CHANNEL,
      },
      trigger: null,
    });
  } catch {
    // Ignore notification errors.
  }
}

export async function dismissPendingNotification(pendingId: string): Promise<void> {
  const Notifications = await loadNotificationsModule();
  if (!Notifications) return;
  try {
    await Notifications.dismissNotificationAsync(pendingNotificationId(pendingId));
    const presented = await Notifications.getPresentedNotificationsAsync();
    if (presented.length === 0) {
      await Notifications.setBadgeCountAsync(0);
    }
  } catch {
    // Ignore dismiss errors.
  }
}
