import { FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

export function FreshRSSSettings() {
  const client = useQueryClient(); const connections = useQuery({ queryKey:["freshrss-status"], queryFn:api.getFreshRSSStatus });
  const [base_url,setUrl]=useState("");const [username,setUsername]=useState("");const [api_password,setPassword]=useState("");const [sync_interval,setInterval]=useState(900);const [message,setMessage]=useState("");
  const payload=()=>({base_url,username,api_password,sync_interval});
  async function submit(event:FormEvent){event.preventDefault();try{await api.createFreshRSS(payload());setMessage("连接已保存");client.invalidateQueries({queryKey:["freshrss-status"]})}catch(error){setMessage(error instanceof Error?error.message:"保存失败")}}
  const items = Array.isArray(connections.data) ? connections.data : [];
  return <section className="settings"><h2>FreshRSS 设置</h2><form onSubmit={submit}><input aria-label="FreshRSS URL" placeholder="https://freshrss.example" value={base_url} onChange={e=>setUrl(e.target.value)} required/><input aria-label="FreshRSS 用户名" placeholder="用户名" value={username} onChange={e=>setUsername(e.target.value)} required/><input aria-label="FreshRSS API 密码" type="password" placeholder="API 密码" value={api_password} onChange={e=>setPassword(e.target.value)} required/><input aria-label="同步间隔" type="number" min="60" value={sync_interval} onChange={e=>setInterval(Number(e.target.value))}/><button type="button" onClick={()=>void api.testFreshRSS(payload()).then(()=>setMessage("连接测试成功")).catch(e=>setMessage(e.message))}>测试连接</button><button type="submit">保存连接</button></form>{message&&<p role="status">{message}</p>}<ul>{items.map(connection=><li key={connection.id}>{connection.base_url} · {connection.status} <button onClick={()=>void api.syncFreshRSS(connection.id).then(()=>client.invalidateQueries({queryKey:["freshrss-status"]}))}>立即同步</button></li>)}</ul></section>
}
