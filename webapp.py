import os
import time

from flask import Flask, request, redirect, session, jsonify, Response

from db import (
    init_db,
    verify_reg_token,
    get_or_create_user,
    get_mine_state,
    start_mining,
    get_inventory,
    get_username,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SITE_SECRET", os.urandom(24))

init_db()


HOME_PAGE = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NODE</title>
<style>
  body{background:#000;color:#fff;font-family:sans-serif;display:flex;align-items:center;
       justify-content:center;height:100vh;margin:0;text-align:center;padding:24px}
</style></head>
<body><div>
  <p>Аккаунт не привязан.</p>
  <p>Напиши боту команду /link и открой присланную ссылку в течение минуты.</p>
</div></body></html>"""


ERROR_PAGE = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NODE</title>
<style>
  body{background:#000;color:#fff;font-family:sans-serif;display:flex;align-items:center;
       justify-content:center;height:100vh;margin:0;text-align:center;padding:24px}
</style></head>
<body><div>
  <p>Ссылка недействительна или истекла.</p>
  <p>Получи новую командой /link у бота — она живёт минуту.</p>
</div></body></html>"""


APP_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>NODE</title>
<style>
  :root{ --bg:#000; --fg:#fff; --line:rgba(255,255,255,.08); --line-strong:rgba(255,255,255,.22); --dim:rgba(255,255,255,.55) }
  *{box-sizing:border-box}
  html,body{margin:0;height:100%;background:var(--bg);color:var(--fg);font-family:-apple-system,sans-serif}
  .app{position:relative;max-width:440px;margin:0 auto;height:100%;display:flex;flex-direction:column;
       border-left:1px solid var(--line);border-right:1px solid var(--line);overflow:hidden}
  .grid-bg{position:absolute;inset:0;z-index:0;pointer-events:none;
    background-image:
      repeating-linear-gradient(to right, var(--line) 0 1px, transparent 1px 40px),
      repeating-linear-gradient(to bottom, var(--line) 0 1px, transparent 1px 40px);
    mask-image: radial-gradient(ellipse 90% 70% at 50% 30%, rgba(0,0,0,.9), transparent 85%);
  }
  .screen{position:relative;z-index:1;flex:1;overflow-y:auto;display:none;flex-direction:column}
  .screen.active{display:flex}
  .stage{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:20px;padding:24px;text-align:center}
  .btn{width:200px;height:200px;border-radius:50%;border:1px solid var(--fg);background:none;color:var(--fg);
       display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;cursor:pointer}
  .btn[disabled]{opacity:.4;cursor:default}
  .label{font-weight:700;font-size:18px;letter-spacing:.06em}
  .timer{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:26px;min-height:32px}
  .status{font-size:13px;color:var(--dim);max-width:260px}
  .balance{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:14px;color:var(--dim)}
  .profile{padding:40px 24px;display:flex;flex-direction:column;align-items:center;gap:6px;text-align:center}
  .avatar{width:64px;height:64px;border-radius:50%;border:1px solid var(--fg);display:flex;align-items:center;
          justify-content:center;font-weight:700;font-size:22px;margin-bottom:14px}
  .pname{font-size:19px;font-weight:600;margin:0}
  .pnote{font-size:13px;color:var(--dim);margin:6px 0 28px}
  .stat-row{display:flex;width:100%;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
  .stat{flex:1;padding:20px 8px;display:flex;flex-direction:column;gap:4px}
  .stat:first-child{border-right:1px solid var(--line)}
  .stat-value{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:24px;font-weight:500}
  .stat-label{font-size:12px;color:var(--dim)}
  .inv{width:100%;margin-top:24px;text-align:left}
  .inv-item{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--line);font-size:14px}
  .tabbar{position:relative;z-index:1;display:flex;border-top:1px solid var(--line);
          padding-bottom:env(safe-area-inset-bottom,0px);background:var(--bg)}
  .tab-btn{flex:1;background:none;border:none;padding:16px 0 14px;font-size:13px;font-weight:500;
           color:var(--dim);cursor:pointer}
  .tab-btn.active{color:var(--fg)}
  .logout{position:fixed;top:16px;right:16px;font-size:12px;color:var(--dim);text-decoration:none;z-index:2}
</style>
</head>
<body>
<a class="logout" href="/logout">выйти</a>
<div class="app">
  <div class="grid-bg"></div>

  <main class="screen active" id="screen-home">
    <div class="stage">
      <div class="balance" id="balance">Баланс: —</div>
      <button class="btn" id="btn">
        <span class="label">NODE</span>
        <span class="timer" id="timer"></span>
      </button>
      <p class="status" id="status">Загрузка…</p>
    </div>
  </main>

  <main class="screen" id="screen-profile">
    <div class="profile">
      <div class="avatar" id="avatar">?</div>
      <h1 class="pname" id="pname">Гость</h1>
      <p class="pnote">Аккаунт привязан через бота.</p>
      <div class="stat-row">
        <div class="stat"><span class="stat-value" id="p-balance">0</span><span class="stat-label">Баланс</span></div>
        <div class="stat"><span class="stat-value" id="p-since">—</span><span class="stat-label">На сайте с</span></div>
      </div>
      <div class="inv" id="inv"></div>
    </div>
  </main>

  <nav class="tabbar">
    <button class="tab-btn active" data-tab="home">Главная</button>
    <button class="tab-btn" data-tab="profile">Профиль</button>
  </nav>
</div>

<script>
const btn = document.getElementById('btn');
const timerEl = document.getElementById('timer');
const statusEl = document.getElementById('status');
const balanceEl = document.getElementById('balance');

function fmt(s){
  s = Math.max(0, Math.ceil(s));
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return m + ':' + (sec < 10 ? '0' + sec : sec);
}

async function refreshState(){
  const r = await fetch('/api/state');
  if (r.status === 401){ window.location.href = '/'; return; }
  const d = await r.json();
  balanceEl.textContent = 'Баланс: ' + d.balance;
  if (d.state === 'idle'){
    btn.disabled = false;
    timerEl.textContent = '';
    statusEl.textContent = 'Нажми, чтобы начать майнить';
  }
  if (d.state === 'mining'){
    btn.disabled = true;
    timerEl.textContent = fmt(d.remaining);
    statusEl.textContent = 'Идёт добыча';
  }
  if (d.state === 'cooldown'){
    btn.disabled = true;
    timerEl.textContent = fmt(d.remaining);
    statusEl.textContent = 'Перезарядка';
  }
}

async function refreshProfile(){
  const r = await fetch('/api/profile');
  if (r.status === 401){ window.location.href = '/'; return; }
  const d = await r.json();
  document.getElementById('p-balance').textContent = d.balance;
  document.getElementById('p-since').textContent = d.since;
  document.getElementById('pname').textContent = d.username ? '@' + d.username : 'Гость';
  document.getElementById('avatar').textContent = d.username ? d.username[0].toUpperCase() : '?';
  const inv = document.getElementById('inv');
  inv.innerHTML = '';
  if (d.inventory.length === 0){
    inv.innerHTML = '<div class="inv-item"><span>Пусто</span><span></span></div>';
  } else {
    d.inventory.forEach(it => {
      const row = document.createElement('div');
      row.className = 'inv-item';
      row.innerHTML = '<span>' + it.name + '</span><span>x' + it.count + '</span>';
      inv.appendChild(row);
    });
  }
}

btn.addEventListener('click', async () => {
  btn.disabled = true;
  await fetch('/api/mine/start', { method: 'POST' });
  refreshState();
});

document.querySelectorAll('.tab-btn').forEach(tabBtn => {
  tabBtn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(t => t.classList.toggle('active', t === tabBtn));
    const target = tabBtn.getAttribute('data-tab');
    document.getElementById('screen-home').classList.toggle('active', target === 'home');
    document.getElementById('screen-profile').classList.toggle('active', target === 'profile');
    if (target === 'profile') refreshProfile();
  });
});

refreshState();
setInterval(refreshState, 1000);
</script>
</body>
</html>"""


@app.route("/")
def index():
    if "user_id" in session:
        return redirect("/app")
    return HOME_PAGE


@app.route("/register")
def register():
    token = request.args.get("token", "")
    user_id = verify_reg_token(token)
    if user_id is None:
        return Response(ERROR_PAGE, status=400, mimetype="text/html")
    get_or_create_user(user_id, None)
    session["user_id"] = user_id
    return redirect("/app")


@app.route("/app")
def app_page():
    if "user_id" not in session:
        return redirect("/")
    return APP_PAGE


@app.route("/api/state")
def api_state():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(get_mine_state(user_id))


@app.route("/api/mine/start", methods=["POST"])
def api_mine_start():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    ok = start_mining(user_id)
    return jsonify({"ok": ok})


@app.route("/api/profile")
def api_profile():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    state = get_mine_state(user_id)
    username, created_at = get_username(user_id)
    since = time.strftime("%d.%m.%Y", time.localtime(created_at)) if created_at else "—"
    return jsonify({
        "balance": state["balance"],
        "username": username,
        "since": since,
        "inventory": get_inventory(user_id),
    })


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
