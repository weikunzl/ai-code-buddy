import React from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useConnectionStore } from "../store/connection";
import { useBridge } from "../bridge/BridgeProvider";
import type { SettingsStackParamList } from "../navigation/RootNavigator";

type Props = NativeStackScreenProps<SettingsStackParamList, "SettingsMain">;

export function SettingsScreen({ navigation }: Props) {
  const bridgeUrl = useConnectionStore((s) => s.bridgeUrl);
  const status = useConnectionStore((s) => s.status);
  const setBridgeUrl = useConnectionStore((s) => s.setBridgeUrl);
  const { connect, disconnect } = useBridge();

  const connected = status === "connected";

  return (
    <View style={styles.container}>
      <Text style={styles.label}>Bridge WebSocket URL</Text>
      <Text style={styles.hint}>Manual LAN IP for MVP (mDNS discovery deferred).</Text>
      <TextInput
        style={styles.input}
        value={bridgeUrl}
        onChangeText={setBridgeUrl}
        autoCapitalize="none"
        autoCorrect={false}
        placeholder="ws://192.168.1.10:9877"
      />

      <Pressable
        style={[styles.btn, connected ? styles.disconnect : styles.connect]}
        onPress={() => (connected ? disconnect() : connect())}
      >
        <Text style={styles.btnText}>{connected ? "Disconnect" : "Connect"}</Text>
      </Pressable>

      <Text style={styles.status}>Status: {status}</Text>

      <Pressable style={styles.link} onPress={() => navigation.navigate("PetEditor")}>
        <Text style={styles.linkText}>Edit pet GIFs →</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20, backgroundColor: "#fff" },
  label: { fontSize: 16, fontWeight: "600", marginBottom: 4 },
  hint: { fontSize: 12, color: "#6b7280", marginBottom: 8 },
  input: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    marginBottom: 16,
  },
  btn: {
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: "center",
    marginBottom: 12,
  },
  connect: { backgroundColor: "#2563eb" },
  disconnect: { backgroundColor: "#6b7280" },
  btnText: { color: "#fff", fontWeight: "600" },
  status: { fontSize: 14, color: "#374151", marginBottom: 24 },
  link: { paddingVertical: 8 },
  linkText: { fontSize: 16, color: "#2563eb" },
});
