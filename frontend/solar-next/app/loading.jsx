"use client";

import {usePathname} from "next/navigation";
import PageSkeleton from "./shared/PageSkeleton";

export default function Loading() {
  const path = usePathname();
  return path === "/" ? <PageSkeleton title="Overview" type="overview"/> : <PageSkeleton/>;
}
