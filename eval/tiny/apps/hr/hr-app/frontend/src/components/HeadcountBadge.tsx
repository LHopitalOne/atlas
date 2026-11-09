import { useEffect, useState } from "react";
import { getHeadcount } from "../api/hr";
import type { Headcount } from "../api/types";

export default function HeadcountBadge() {
  const [data, setData] = useState<Headcount | null>(null);
  useEffect(() => {
    getHeadcount().then(setData).catch(() => setData(null));
  }, []);
  if (!data) return null;
  return <span title={data.by_department.map((d) => `${d.department}: ${d.count}`).join("\n")}>{data.total} people</span>;
}
