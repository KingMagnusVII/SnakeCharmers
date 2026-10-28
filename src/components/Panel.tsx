import type {ReactNode} from "react";
export default function Panel({title,eyebrow,children,action,className=""}:{title:string;eyebrow?:string;children:ReactNode;action?:ReactNode;className?:string}){
  return <section className={`panel ${className}`}><header className="panel-head"><div>{eyebrow&&<div className="panel-eyebrow">{eyebrow}</div>}<h3>{title}</h3></div>{action&&<div>{action}</div>}</header><div className="panel-body">{children}</div></section>
}
