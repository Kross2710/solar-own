"use client";
import {createContext,useContext} from "react";
import {translator} from "./translate";
const Preferences = createContext({lang:"en",advanced:false});
export function PreferenceProvider({value,children}) {
  return <Preferences.Provider value={value}>{children}</Preferences.Provider>;
}
export function usePreferences() {
  const prefs=useContext(Preferences);
  return {...prefs,t:translator(prefs.lang)};
}
