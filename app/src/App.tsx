import React from "react";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import "./i18n";
import { BridgeProvider } from "./bridge/BridgeProvider";
import { useBuddySounds } from "./audio/useBuddySounds";
import { GlobalApproval } from "./components/GlobalApproval";
import { RootNavigator } from "./navigation/RootNavigator";

function AppShell() {
  useBuddySounds();
  return (
    <>
      <RootNavigator />
      <GlobalApproval />
      <StatusBar style="auto" />
    </>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <BridgeProvider>
        <AppShell />
      </BridgeProvider>
    </SafeAreaProvider>
  );
}
