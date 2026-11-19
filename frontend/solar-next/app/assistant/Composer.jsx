"use client";
import {useRef,useState} from "react";
import {usePreferences} from "../i18n/context";

export default function Composer({busy,ready,send,stop}) {
  const {t}=usePreferences();
  const [draft,setDraft]=useState("");
  const field=useRef(null);
  function submit(e) {
    e.preventDefault();
    if(!busy && send(draft)) {setDraft("");field.current.focus();}
  }
  return <form className="ask-composer" onSubmit={submit}>
    <textarea ref={field} aria-label={t("Your question")} placeholder={t("Ask about your solar system…")}
      rows={2} maxLength={2000} value={draft} onChange={e=>setDraft(e.target.value)}
      onKeyDown={e=>{
        if(e.key==="Enter" && !e.shiftKey && !e.nativeEvent.isComposing && e.nativeEvent.keyCode!==229) {
          e.preventDefault();if(!e.repeat && !busy) e.currentTarget.form.requestSubmit();
        }
      }}/>
    <div><small>{draft.length>1800 ? draft.length+" / 2000" : t("Shift + Enter for a new line")}</small>
    {busy ? <button type="button" className="ask-send" onClick={stop} aria-label={t("Stop reply")} title={t("Stop reply")}>■</button> :
    <button className="ask-send" type="submit" disabled={!ready || !draft.trim()} aria-label={t("Send question")} title={t("Send question")}>↑</button>}</div>
  </form>;
}
