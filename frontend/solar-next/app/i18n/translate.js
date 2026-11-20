import vietnamese from "./vi.json";

export function translator(lang) {
  if (lang!=="vi") return text=>text;
  return text=>{
    if(typeof text!=="string") return text;
    const key=text.trim();
    return Object.hasOwn(vietnamese,key) ? text.replace(key,()=>vietnamese[key]) : text;
  };
}
