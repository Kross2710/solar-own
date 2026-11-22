"use client";

import {ViewTransition} from "react";

export default function Template({children}) {
  return <ViewTransition
    name="dashboard-page"
    default="none"
    enter="page-crossfade"
    update="page-crossfade"
    exit="page-crossfade"
    share="page-crossfade"
  >{children}</ViewTransition>;
}
