import {preferences} from "./preferences";
import {translator} from "./translate";

export async function pageMetadata(name) {
  const {lang}=await preferences();
  return {title:translator(lang)(name)+" · Home Solar"};
}
