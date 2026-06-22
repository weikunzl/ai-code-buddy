import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";
import { PRODUCT_NAME } from "../constants/product";
import { HomeScreen } from "../screens/HomeScreen";
import { SessionsScreen } from "../screens/SessionsScreen";
import { SettingsScreen } from "../screens/SettingsScreen";
import { PetEditorScreen } from "../screens/PetEditorScreen";

export type SettingsStackParamList = {
  SettingsMain: undefined;
  PetEditor: undefined;
};

const Tab = createBottomTabNavigator();
const SettingsStack = createNativeStackNavigator<SettingsStackParamList>();

type TabIconName = React.ComponentProps<typeof Ionicons>["name"];

function tabIcon(name: TabIconName) {
  return ({ color, size }: { color: string; size: number }) => (
    <Ionicons name={name} size={size} color={color} />
  );
}

function SettingsStackScreen() {
  const { t } = useTranslation();
  return (
    <SettingsStack.Navigator>
      <SettingsStack.Screen
        name="SettingsMain"
        component={SettingsScreen}
        options={{ title: t("nav.settings") }}
      />
      <SettingsStack.Screen
        name="PetEditor"
        component={PetEditorScreen}
        options={{ title: t("nav.petGifs", { product: PRODUCT_NAME }) }}
      />
    </SettingsStack.Navigator>
  );
}

export function RootNavigator() {
  const { t } = useTranslation();

  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={{
          headerShown: true,
          tabBarActiveTintColor: "#2563eb",
          tabBarInactiveTintColor: "#6b7280",
        }}
      >
        <Tab.Screen
          name="Home"
          component={HomeScreen}
          options={{
            title: PRODUCT_NAME,
            tabBarIcon: tabIcon("paw"),
          }}
        />
        <Tab.Screen
          name="Sessions"
          component={SessionsScreen}
          options={{
            title: t("nav.sessions"),
            tabBarIcon: tabIcon("list"),
          }}
        />
        <Tab.Screen
          name="Settings"
          component={SettingsStackScreen}
          options={{
            headerShown: false,
            title: t("nav.settings"),
            tabBarIcon: tabIcon("settings-outline"),
          }}
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
