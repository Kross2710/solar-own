"use client";
import {useEffect} from "react";
import {useRouter} from "next/navigation";

export default function Refresh({interval}) {
  const router = useRouter();
  useEffect(() => {
    const refresh = () => { if (!document.hidden) router.refresh(); };
    const timer = setInterval(refresh, interval);
    document.addEventListener("visibilitychange",refresh);
    return () => {clearInterval(timer); document.removeEventListener("visibilitychange",refresh);};
  }, [router, interval]);
  return null;
}
