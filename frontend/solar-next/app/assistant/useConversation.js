"use client";
import {useEffect,useRef,useState} from "react";
import {entryId,errorText} from "./messages";
import {streamReply,demoReply} from "./replies";

const blank = () => ({id:entryId(),entries:[]});
const validEntry = m => m?.type==="message" && ["user","assistant"].includes(m.role) && typeof m.content==="string";
function restore(key) {
  const history=JSON.parse(localStorage.getItem(key+".threads") || "null");
  if(Array.isArray(history?.threads)) {
    const threads=history.threads.filter(c=>typeof c?.id==="string" && Array.isArray(c.entries))
      .slice(0,12).map(c=>({...c,entries:c.entries.filter(validEntry).slice(-40)}));
    if(threads.length) return {threads,active:threads.some(c=>c.id===history.active)?history.active:threads[0].id};
  }
  const old=JSON.parse(localStorage.getItem(key) || "[]");
  const thread=blank();
  if(Array.isArray(old)) thread.entries=old.filter(validEntry).slice(-40);
  return {active:thread.id,threads:[thread]};
}

export function useConversation(demo,lang,t) {
  const key=demo?"solar.demo.chat.v1":"chat.v1";
  const [library,setLibrary]=useState(null);
  const [stream,setStream]=useState(null);
  const activeRequest=useRef(null);
  useEffect(()=>{
    try {setLibrary(restore(key));}
    catch {const thread=blank();setLibrary({active:thread.id,threads:[thread]});}
    return ()=>{activeRequest.current?.abort();activeRequest.current=null;};
  },[key]);
  useEffect(()=>{
    if(library) try {
      localStorage.setItem(key+".threads",JSON.stringify(library));
      localStorage.removeItem(key);
    } catch {}
  },[key,library]);

  const thread=library?.threads.find(c=>c.id===library.active);
  function store(entries) {
    setLibrary(old=>({...old,threads:old.threads.map(c=>c.id===thread.id?{...c,entries:entries.slice(-40)}:c)}));
  }
  function select(id) {
    if(!activeRequest.current) setLibrary(old=>({...old,active:id}));
  }
  function create() {
    if(!thread?.entries.length || activeRequest.current) return;
    const next=blank();
    setLibrary(old=>({active:next.id,threads:[next,...old.threads.filter(c=>c.entries.length)].slice(0,12)}));
  }
  function removeActive() {
    if(!thread?.entries.length || activeRequest.current) return;
    const replacement=blank();
    setLibrary(old=>{
      const index=old.threads.findIndex(c=>c.id===thread.id);
      const threads=old.threads.filter(c=>c.id!==thread.id);
      if(!threads.length) return {active:replacement.id,threads:[replacement]};
      return {active:threads[Math.min(index,threads.length-1)].id,threads};
    });
  }
  async function run(history) {
    if(!thread || activeRequest.current) return;
    const controller=new AbortController();
    activeRequest.current=controller;
    store(history);
    setStream({text:"",status:"Thinking…"});
    let frame=0, partial="", tool="", timedOut=false;
    const timer=setTimeout(()=>{timedOut=true;controller.abort();},120000);
    function update(text,status) {
      partial=text;tool=status;
      if(!frame) frame=requestAnimationFrame(()=>{
        frame=0;
        if(activeRequest.current===controller) setStream({text:partial,status:tool});
      });
    }
    const answer={id:entryId(),role:"assistant",type:"message",content:""};
    try {
      answer.content=demo?t(demoReply(history.at(-1).content,t)):await streamReply(history,update,lang,controller.signal);
    } catch(err) {
      answer.content=partial;
      if(controller.signal.aborted && !timedOut) answer.stopped=true;
      else {
        answer.error=true;
        answer.note=t(timedOut || err instanceof TypeError ? errorText("network") : err.message);
      }
    } finally {
      clearTimeout(timer);cancelAnimationFrame(frame);
      if(activeRequest.current===controller){
        store([...history,answer]);activeRequest.current=null;setStream(null);
      }
    }
  }
  function send(raw) {
    const content=raw.trim();
    if(!content || !thread || activeRequest.current) return false;
    void run([...thread.entries,{id:entryId(),role:"user",type:"message",content}]);
    return true;
  }
  function retry(){
    if(!thread || activeRequest.current) return;
    const history=thread.entries.slice();
    if(history.at(-1)?.role==="assistant") history.pop();
    if(history.at(-1)?.role==="user") void run(history);
  }
  return {library,thread,stream,send,retry,create,select,removeActive,stop:()=>activeRequest.current?.abort()};
}
