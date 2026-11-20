"use client";
import {memo,useEffect,useRef,useState} from "react";
import {usePreferences} from "../i18n/context";
import {noticeView} from "./messages";
import {examples} from "./replies";
import {useConversation} from "./useConversation";
import Refresh from "../shared/Refresh";
import Composer from "./Composer";

function CopyReply({text}) {
  const {t}=usePreferences();
  const [status,setStatus]=useState("Copy reply");
  async function copy(){
    try{await navigator.clipboard.writeText(text);setStatus("Copied");}
    catch{setStatus("Select the reply to copy it");}
  }
  return <button className="ask-copy" onClick={copy}>{t(status)}</button>;
}

const Transcript=memo(function Transcript({entries}) {
  const {t}=usePreferences();
  return entries.map(e=><article className={"ask-msg "+e.role} key={e.id}>
    <small>{t(e.role==="user"?"You":"Assistant")}</small>
    {e.content && <p>{e.content}</p>}
    {e.note && <p role="alert">{e.note}</p>}
    {e.role==="assistant" && e.content && !e.error && <CopyReply text={e.content}/>}
    {e.stopped && <small>{t("Reply stopped")}</small>}
  </article>);
});
function Notices({demo,notices,ask}) {
  const {lang,t}=usePreferences();
  const [hidden,setHidden]=useState([]),[error,setError]=useState(false);
  const visible=(notices || []).filter(n=>!hidden.includes(n.id));
  async function dismiss(id) {
    setError(false);
    try {
      if(!demo){
        const r=await fetch("/api/notices/"+id+"/dismiss",{method:"POST"});
        if(!r.ok || !(await r.json()).ok) throw new Error();
      }
      setHidden(ids=>[...ids,id]);
    } catch {setError(true);}
  }
  return <details className="ask-notices"><summary>{t("System notices")} <b>{notices?visible.length:"—"}</b></summary>
    {!visible.length && <p>{t(notices?"No active notices.":"Notices unavailable.")}</p>}
    {visible.map(n=>{const v=noticeView(n,lang);return v && <article key={n.id}><b>{v.title}</b><p>{v.detail}</p>
      {ask && <button onClick={e=>{ask(v.ask);e.currentTarget.closest("details").open=false;}}>{t("Ask about this")}</button>}
      <button onClick={()=>dismiss(n.id)}>{t("Dismiss")}</button></article>;})}
    {error && <p role="alert">{t("Could not dismiss the notice. Try again.")}</p>}
  </details>;
}

export default function Conversation({demo,enabled,notices,soc}) {
  const {t,lang}=usePreferences();
  const chat=useConversation(demo,lang,t);
  const {thread,library,stream}=chat;
  const log=useRef(null),follow=useRef(true);
  const entries=thread?.entries;
  const last=entries?.at(-1);
  const empty=!entries?.length;
  function send(text){follow.current=true;return chat.send(text);}
  useEffect(()=>{follow.current=true;},[thread?.id]);
  useEffect(()=>{
    if(log.current && follow.current) log.current.scrollTop=log.current.scrollHeight;
  },[entries,stream]);
  return <div className="ask-workspace">
    {!demo && !stream && <Refresh interval={60000}/>}
    <div className="ask-toolbar"><div><h1>{t("Assistant")}</h1>{soc!=null && <small>{t("Battery charge · ")}{soc}%</small>}</div>
      <div className="ask-tools">
        {library?.threads.length>1 && <select aria-label={t("Chat history")} value={thread.id} disabled={!!stream} onChange={e=>chat.select(e.target.value)}>
          {library.threads.map(c=><option value={c.id} key={c.id}>{c.entries.find(e=>e.role==="user")?.content.slice(0,50) || t("New chat")}</option>)}</select>}
        {enabled && <button onClick={chat.create} disabled={empty || !!stream}><span aria-hidden="true">＋</span> {t("New chat")}</button>}
        {!empty && <button type="button" className="ask-delete" disabled={!!stream} onClick={()=>{
          if(window.confirm(t("Delete this conversation from this browser?"))) chat.removeActive();
        }}>{t("Delete chat")}</button>}
      </div>
    </div>
    <Notices demo={demo} notices={notices} ask={enabled && thread && !stream ? send : null}/>
    {enabled ? <section className="ask-room" aria-label={t("Solar chat")}>
      <div className="ask-log" ref={log} onScroll={e=>{const el=e.currentTarget;follow.current=el.scrollHeight-el.scrollTop-el.clientHeight<48;}}>
        {empty && <div className="ask-welcome"><div className="ask-orbit" aria-hidden="true">☀</div>
          <h2>{t("What would you like to know?")}</h2>
          <div className="ask-starters">{examples.map(([q],i)=><button key={q} disabled={!thread} onClick={()=>send(t(q))}>
            <span aria-hidden="true">{i===0?"◷":"ϟ"}</span>{t(q)}<i aria-hidden="true">↗</i></button>)}</div></div>}
        {entries && <Transcript entries={entries}/>}
        {stream && <article className="ask-msg assistant"><small>{t("Assistant")}</small>
          {stream.text && <p>{stream.text}</p>}{stream.status && <div className="ask-status" role="status">{t(stream.status)}</div>}</article>}
        {last && !stream && <button className="ask-retry" onClick={()=>{follow.current=true;chat.retry();}}>↻ {t(last.error || last.stopped || last.role==="user"?"Retry":"Regenerate reply")}</button>}
      </div>
      <span className="ask-sr" role="status">{stream?t("Replying…"):last?.role==="assistant"?t("Reply finished"):""}</span>
      <Composer key={thread?.id ?? "loading"} busy={!!stream} ready={!!thread} send={send} stop={chat.stop}/>
    </section> : <section className="panel empty"><p>{t(enabled===false?"Chat is off. Enable the AI provider in the backend to start a conversation.":"Assistant status unavailable.")}</p>
      <a href="/assistant">{t("Refresh")}</a> · <a href="?demo=1">{t("Preview demo")}</a></section>}
  </div>;
}
