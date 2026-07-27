const MAX_MESSAGE_LENGTH = 1200;

function clean(value, limit) {
  return String(value || "").replace(/[\u0000-\u001F\u007F]/g, " ").trim().slice(0, limit);
}

async function support(request, env) {
  if (request.method !== "POST") return Response.json({ error: "仅支持 POST" }, { status: 405 });
  const type = request.headers.get("content-type") || "";
  if (!type.includes("application/json")) return Response.json({ error: "请求格式错误" }, { status: 415 });
  let payload;
  try { payload = await request.json(); } catch { return Response.json({ error: "请求内容无效" }, { status: 400 }); }
  const message = clean(payload.message, MAX_MESSAGE_LENGTH);
  const name = clean(payload.name, 50) || "未填写称呼";
  const page = clean(payload.page, 300);
  if (message.length < 2) return Response.json({ error: "消息过短" }, { status: 400 });
  if (!env.TG_BOT_TOKEN || !env.TG_CHAT_ID) return Response.json({ error: "客服暂未配置" }, { status: 503 });
  const text = `【ATELIER 网站客服】\n称呼：${name}\n消息：${message}\n页面：${page || "未知"}\n时间：${new Date().toISOString()}`;
  const telegram = await fetch(`https://api.telegram.org/bot${env.TG_BOT_TOKEN}/sendMessage`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ chat_id: env.TG_CHAT_ID, text, disable_web_page_preview: true }) });
  if (!telegram.ok) return Response.json({ error: "客服转发暂不可用" }, { status: 502 });
  return Response.json({ ok: true });
}

export default { fetch(request, env) { return new URL(request.url).pathname === "/api/support" ? support(request, env) : env.ASSETS.fetch(request); } };
