import React from "react";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { BridgeProvider } from "./bridge/BridgeProvider";
import { RootNavigator } from "./navigation/RootNavigator";

export default function App() {
  return (
    <SafeAreaProvider>
      <BridgeProvider>
        <RootNavigator />
        <StatusBar style="auto" />
      </BridgeProvider>
    </SafeAreaProvider>
  );
}
