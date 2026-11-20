export default function Readings({title,rows}) {
  return <section className="panel adv-readings"><h2>{title}</h2><dl>
    {rows.map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value ?? "—"}</dd></div>)}
  </dl></section>;
}
