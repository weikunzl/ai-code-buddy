import { createNavigationContainerRef } from "@react-navigation/native";
import type { NavigatorScreenParams } from "@react-navigation/native";
import type { SettingsStackParamList } from "./types";

export type RootParamList = {
  Home: undefined;
  Sessions: undefined;
  Settings: NavigatorScreenParams<SettingsStackParamList>;
};

export const navigationRef = createNavigationContainerRef<RootParamList>();
