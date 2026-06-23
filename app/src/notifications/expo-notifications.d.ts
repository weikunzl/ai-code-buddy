/** Optional at install time — required only for dev/release builds with lock-screen notifications. */
declare module "expo-notifications" {
  export const AndroidImportance: {
    HIGH: number;
    DEFAULT: number;
  };
  export const AndroidNotificationPriority: {
    HIGH: string;
  };
  export const AndroidNotificationVisibility: {
    PUBLIC: number;
  };
  export const IosAuthorizationStatus: {
    PROVISIONAL: number;
  };

  export function setNotificationHandler(handler: {
    handleNotification: () => Promise<{
      shouldShowBanner: boolean;
      shouldShowList: boolean;
      shouldPlaySound: boolean;
      shouldSetBadge: boolean;
    }>;
  }): void;

  export function setNotificationChannelAsync(
    id: string,
    channel: Record<string, unknown>,
  ): Promise<void>;

  export function getPermissionsAsync(): Promise<{
    granted: boolean;
    ios?: { status: number };
  }>;

  export function requestPermissionsAsync(
    options?: Record<string, unknown>,
  ): Promise<{ granted: boolean; ios?: { status: number } }>;

  export function scheduleNotificationAsync(
    request: Record<string, unknown>,
  ): Promise<string>;

  export function dismissNotificationAsync(id: string): Promise<void>;
  export function getPresentedNotificationsAsync(): Promise<unknown[]>;
  export function setBadgeCountAsync(count: number): Promise<void>;
}
