import React, { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

type Props = {
  question: string;
  answer: string;
  defaultExpanded?: boolean;
};

export function CollapsibleFaq({ question, answer, defaultExpanded = false }: Props) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <View style={styles.wrap}>
      <Pressable
        style={styles.header}
        onPress={() => setExpanded((v) => !v)}
        accessibilityRole="button"
        accessibilityState={{ expanded }}
      >
        <Text style={styles.question}>{question}</Text>
        <Ionicons
          name={expanded ? "chevron-up" : "chevron-down"}
          size={18}
          color="#6b7280"
        />
      </Pressable>
      {expanded ? <Text style={styles.answer}>{answer}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "#e5e7eb",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    paddingVertical: 12,
  },
  question: {
    flex: 1,
    fontSize: 14,
    fontWeight: "600",
    color: "#374151",
    lineHeight: 20,
  },
  answer: {
    fontSize: 13,
    color: "#6b7280",
    lineHeight: 20,
    paddingBottom: 12,
  },
});
