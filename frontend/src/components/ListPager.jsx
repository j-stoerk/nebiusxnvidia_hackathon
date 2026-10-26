import { useState } from "react";
import { Button } from "@/components/ui/button";

// Render a small page without limiting the size of the underlying scenario.
export function usePage(items, size = 10) {
  const [requested, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil(items.length / size));
  const page = Math.min(requested, pages - 1);
  return { rows: items.slice(page * size, (page + 1) * size), offset: page * size,
    page, pages, total: items.length, setPage };
}

export default function ListPager({ list, name }) {
  if (list.pages === 1) return null;
  return <div className="flex flex-wrap items-center gap-3">
    <Button type="button" variant="ghost" disabled={!list.page} onClick={() => list.setPage(list.page - 1)}>Previous {name}</Button>
    <span className="text-xs text-muted-foreground">Page {list.page + 1} of {list.pages} · {list.total} {name}</span>
    <Button type="button" variant="ghost" disabled={list.page + 1 === list.pages} onClick={() => list.setPage(list.page + 1)}>Next {name}</Button>
  </div>;
}
