import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
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

function SettingsStackScreen() {
  return (
    <SettingsStack.Navigator>
      <SettingsStack.Screen
        name="SettingsMain"
        component={SettingsScreen}
        options={{ title: "Settings" }}
      />
      <SettingsStack.Screen
        name="PetEditor"
        component={PetEditorScreen}
        options={{ title: "Pet GIFs" }}
      />
    </SettingsStack.Navigator>
  );
}

export function RootNavigator() {
  return (
    <NavigationContainer>
      <Tab.Navigator screenOptions={{ headerShown: true }}>
        <Tab.Screen name="Home" component={HomeScreen} />
        <Tab.Screen name="Sessions" component={SessionsScreen} />
        <Tab.Screen
          name="Settings"
          component={SettingsStackScreen}
          options={{ headerShown: false }}
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
