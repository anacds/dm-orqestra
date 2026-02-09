import os
import sys
import time
import requests

BASE = os.getenv("METABASE_URL", "http://metabase:3000")
ADMIN_EMAIL = os.getenv("METABASE_ADMIN_EMAIL", "admin@orqestra.com")
ADMIN_PASS = os.getenv("METABASE_ADMIN_PASS", "Orqestra2026!")
PG_HOST = os.getenv("PG_HOST", "db")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("PG_USER", "orqestra")
PG_PASS = os.getenv("PG_PASS", "orqestra_password")


# ═════════════════════════════════════════════════════════════════════════
# Wait for Metabase
# ═════════════════════════════════════════════════════════════════════════

def wait_for_metabase(timeout=300):
    print("Waiting for Metabase to be ready...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{BASE}/api/health", timeout=5)
            if r.ok and r.json().get("status") == "ok":
                print("  Metabase is ready.")
                return True
        except Exception:
            pass
        time.sleep(5)
    print("ERROR: Metabase did not become ready.")
    return False


# ═════════════════════════════════════════════════════════════════════════
# Setup wizard
# ═════════════════════════════════════════════════════════════════════════

def is_setup_done() -> bool:
    r = requests.get(f"{BASE}/api/session/properties", timeout=10)
    if r.ok:
        return r.json().get("has-user-setup", False)
    return False


def run_setup() -> str:
    """Complete the Metabase setup wizard. Returns session token."""
    # Get setup token
    r = requests.get(f"{BASE}/api/session/properties", timeout=10)
    r.raise_for_status()
    setup_token = r.json().get("setup-token")
    if not setup_token:
        print("  No setup-token found, setup may already be done.")
        return login()

    payload = {
        "token": setup_token,
        "user": {
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASS,
            "first_name": "Admin",
            "last_name": "Orqestra",
            "site_name": "Orqestra Analytics",
        },
        "prefs": {
            "site_name": "Orqestra Analytics",
            "site_locale": "pt",
            "allow_tracking": False,
        },
    }
    r = requests.post(f"{BASE}/api/setup", json=payload, timeout=30)
    r.raise_for_status()
    token = r.json().get("id")
    print(f"  Setup completed. Session: {token[:8]}...")
    return token


def login() -> str:
    r = requests.post(f"{BASE}/api/session", json={
        "username": ADMIN_EMAIL,
        "password": ADMIN_PASS,
    }, timeout=10)
    r.raise_for_status()
    token = r.json()["id"]
    print(f"  Logged in. Session: {token[:8]}...")
    return token


def headers(token: str) -> dict:
    return {"X-Metabase-Session": token, "Content-Type": "application/json"}


# ═════════════════════════════════════════════════════════════════════════
# Databases
# ═════════════════════════════════════════════════════════════════════════

DATABASES = [
    {"name": "Campanhas", "db": "campaigns_service"},
    {"name": "Autenticação", "db": "auth_service"},
    {"name": "Briefing Enhancer", "db": "briefing_enhancer"},
    {"name": "Legal Service", "db": "legal_service"},
]


def get_existing_databases(token: str) -> dict[str, int]:
    r = requests.get(f"{BASE}/api/database", headers=headers(token), timeout=10)
    r.raise_for_status()
    return {d["name"]: d["id"] for d in r.json().get("data", []) if d["name"] != "Sample Database"}


def create_databases(token: str) -> dict[str, int]:
    existing = get_existing_databases(token)
    db_ids: dict[str, int] = {}

    for db_def in DATABASES:
        name = db_def["name"]
        if name in existing:
            db_ids[name] = existing[name]
            print(f"  [db] '{name}' already exists (id={existing[name]})")
            continue

        r = requests.post(f"{BASE}/api/database", headers=headers(token), json={
            "name": name,
            "engine": "postgres",
            "details": {
                "host": PG_HOST,
                "port": PG_PORT,
                "dbname": db_def["db"],
                "user": PG_USER,
                "password": PG_PASS,
                "ssl": False,
                "ssl-mode": "disable",
            },
            "auto_run_queries": True,
            "is_full_sync": True,
        }, timeout=30)
        if r.status_code in (200, 201):
            db_id = r.json()["id"]
            db_ids[name] = db_id
            print(f"  [db] '{name}' created (id={db_id})")
        else:
            print(f"  [db] WARNING: '{name}' → {r.status_code}: {r.text[:200]}")

    return db_ids


# ═════════════════════════════════════════════════════════════════════════
# Wait for database sync
# ═════════════════════════════════════════════════════════════════════════

def wait_for_sync(token: str, db_ids: dict[str, int], timeout=120):
    """Wait for Metabase to finish syncing all databases."""
    print("  Waiting for database sync to complete...")
    start = time.time()
    while time.time() - start < timeout:
        all_done = True
        for name, db_id in db_ids.items():
            try:
                r = requests.get(f"{BASE}/api/database/{db_id}", headers=headers(token), timeout=10)
                if r.ok:
                    status = r.json().get("initial_sync_status", "incomplete")
                    if status != "complete":
                        all_done = False
            except Exception:
                all_done = False
        if all_done:
            print("  All databases synced.")
            return
        time.sleep(5)
    print("  WARNING: Sync timeout, proceeding anyway.")


# ═════════════════════════════════════════════════════════════════════════
# Collections (folders for organizing)
# ═════════════════════════════════════════════════════════════════════════

COLLECTIONS = [
    "[Orqestra] Funil de Campanhas",
    "[Orqestra] Qualidade & Compliance",
    "[Orqestra] Adoção & Eficácia da IA",
]


def create_collections(token: str) -> dict[str, int]:
    existing_r = requests.get(f"{BASE}/api/collection", headers=headers(token), timeout=10)
    existing_r.raise_for_status()
    existing = {c["name"]: c["id"] for c in existing_r.json()}

    coll_ids: dict[str, int] = {}
    for name in COLLECTIONS:
        if name in existing:
            coll_ids[name] = existing[name]
            continue

        r = requests.post(f"{BASE}/api/collection", headers=headers(token), json={
            "name": name,
            "color": "#509EE3",
        }, timeout=10)
        if r.status_code in (200, 201):
            coll_ids[name] = r.json()["id"]
            print(f"  [coll] '{name}' created")
        else:
            print(f"  [coll] WARNING: '{name}' → {r.status_code}")

    return coll_ids


# ═════════════════════════════════════════════════════════════════════════
# Questions (native SQL cards)
# ═════════════════════════════════════════════════════════════════════════

def _q(name: str, db_name: str, collection: str, sql: str, display: str = "table", full_width: bool = False):
    return {
        "name": name,
        "db_name": db_name,
        "collection": collection,
        "sql": sql,
        "display": display,
        "full_width": full_width,
    }


C1 = "[Orqestra] Funil de Campanhas"
C2 = "[Orqestra] Qualidade & Compliance"
C3 = "[Orqestra] Adoção & Eficácia da IA"

QUESTIONS = [
    # ── Dashboard 1: Funil ─────────────────────────────────────────
    _q("Campanhas por Status (Funil)", "Campanhas", C1, """
SELECT
  CASE status
    WHEN 'DRAFT' THEN '1. Rascunho'
    WHEN 'CREATIVE_STAGE' THEN '2. Criação'
    WHEN 'CONTENT_REVIEW' THEN '3. Revisão'
    WHEN 'CONTENT_ADJUSTMENT' THEN '4. Ajustes'
    WHEN 'CAMPAIGN_BUILDING' THEN '5. Construção'
    WHEN 'CAMPAIGN_PUBLISHED' THEN '6. Publicada'
  END AS "Status",
  count(*) AS "Campanhas"
FROM campaigns
GROUP BY status
ORDER BY "Status"
""", "bar"),

    _q("Volume de Impacto (BRL) por Status", "Campanhas", C1, """
SELECT
  CASE status
    WHEN 'DRAFT' THEN '1. Rascunho'
    WHEN 'CREATIVE_STAGE' THEN '2. Criação'
    WHEN 'CONTENT_REVIEW' THEN '3. Revisão'
    WHEN 'CONTENT_ADJUSTMENT' THEN '4. Ajustes'
    WHEN 'CAMPAIGN_BUILDING' THEN '5. Construção'
    WHEN 'CAMPAIGN_PUBLISHED' THEN '6. Publicada'
  END AS "Status",
  COALESCE(sum(estimated_impact_volume), 0) AS "Volume BRL"
FROM campaigns
GROUP BY status
ORDER BY "Status"
""", "bar"),

    _q("Campanhas por Categoria", "Campanhas", C1, """
SELECT category AS "Categoria", count(*) AS "Total"
FROM campaigns GROUP BY category ORDER BY "Total" DESC
""", "pie"),

    _q("Campanhas por Canal", "Campanhas", C1, """
SELECT unnest(communication_channels) AS "Canal", count(*) AS "Total"
FROM campaigns GROUP BY "Canal" ORDER BY "Total" DESC
""", "pie"),

    _q("Campanhas por Prioridade", "Campanhas", C1, """
SELECT priority AS "Prioridade", count(*) AS "Total"
FROM campaigns GROUP BY priority
""", "pie"),

    _q("Tempo Médio por Transição (horas)", "Campanhas", C1, """
SELECT
  e.from_status AS "De",
  e.to_status AS "Para",
  ROUND(AVG(EXTRACT(EPOCH FROM (nxt.lead_ts - e.created_at)) / 3600)::numeric, 1) AS "Horas (média)",
  count(*) AS "Transições"
FROM campaign_status_event e
LEFT JOIN LATERAL (
  SELECT min(e2.created_at) AS lead_ts
  FROM campaign_status_event e2
  WHERE e2.campaign_id = e.campaign_id AND e2.created_at > e.created_at
) nxt ON true
WHERE e.from_status IS NOT NULL AND nxt.lead_ts IS NOT NULL
GROUP BY e.from_status, e.to_status
ORDER BY e.from_status
""", "table", full_width=True),

    _q("Campanhas Publicadas por Semana", "Campanhas", C1, """
SELECT
  date_trunc('week', e.created_at)::date AS "Semana",
  count(DISTINCT e.campaign_id) AS "Publicadas"
FROM campaign_status_event e
WHERE e.to_status = 'CAMPAIGN_PUBLISHED'
GROUP BY "Semana" ORDER BY "Semana"
""", "line", full_width=True),

    # ── Dashboard 2: Qualidade ─────────────────────────────────────
    _q("Taxa de Aprovação IA por Canal", "Campanhas", C2, """
SELECT
  channel AS "Canal",
  count(*) FILTER (WHERE ia_verdict = 'approved') AS "IA Aprovadas",
  count(*) FILTER (WHERE ia_verdict = 'rejected') AS "IA Reprovadas",
  count(*) FILTER (WHERE ia_verdict IS NULL) AS "Sem IA"
FROM piece_review GROUP BY channel ORDER BY channel
""", "bar"),

    _q("Taxa de Aprovação Humana por Canal", "Campanhas", C2, """
SELECT
  channel AS "Canal",
  count(*) FILTER (WHERE human_verdict = 'approved') AS "Aprovadas",
  count(*) FILTER (WHERE human_verdict IN ('rejected','manually_rejected')) AS "Reprovadas",
  count(*) FILTER (WHERE human_verdict = 'pending') AS "Pendentes"
FROM piece_review GROUP BY channel ORDER BY channel
""", "bar"),

    _q("Concordância IA vs. Humano", "Campanhas", C2, """
SELECT
  channel AS "Canal",
  CASE
    WHEN ia_verdict = 'approved' AND human_verdict = 'approved' THEN 'Ambos aprovam'
    WHEN ia_verdict = 'rejected' AND human_verdict IN ('rejected','manually_rejected') THEN 'Ambos reprovam'
    WHEN ia_verdict = 'approved' AND human_verdict IN ('rejected','manually_rejected') THEN 'IA aprovou, Humano reprovou'
    WHEN ia_verdict = 'rejected' AND human_verdict = 'approved' THEN 'IA reprovou, Humano aprovou'
    WHEN ia_verdict IS NULL THEN 'Sem IA'
    ELSE 'Pendente'
  END AS "Classificação",
  count(*) AS "Total"
FROM piece_review WHERE human_verdict != 'pending'
GROUP BY "Canal", "Classificação" ORDER BY "Canal"
""", "bar"),

    _q("Decisões do Agente Legal por Canal", "Legal Service", C2, """
SELECT
  channel AS "Canal",
  decision AS "Decisão",
  count(*) AS "Total"
FROM legal_validation_audits
GROUP BY channel, decision ORDER BY channel
""", "bar"),

    _q("Últimas Reprovações Legais", "Legal Service", C2, """
SELECT
  created_at AS "Data",
  channel AS "Canal",
  decision AS "Decisão",
  LEFT(summary, 200) AS "Resumo",
  llm_model AS "Modelo"
FROM legal_validation_audits
WHERE decision != 'APROVADO'
ORDER BY created_at DESC LIMIT 20
""", "table", full_width=True),

    # ── Dashboard 3: Adoção IA ─────────────────────────────────────
    _q("Interações Briefing por Dia", "Briefing Enhancer", C3, """
SELECT
  date_trunc('day', created_at)::date AS "Dia",
  count(*) AS "Interações",
  count(DISTINCT user_id) AS "Usuários"
FROM audit_interactions GROUP BY "Dia" ORDER BY "Dia"
""", "line"),

    _q("Taxa de Aceitação por Campo", "Briefing Enhancer", C3, """
SELECT
  field_name AS "Campo",
  count(*) FILTER (WHERE user_decision = 'approved') AS "Aceitas",
  count(*) FILTER (WHERE user_decision = 'rejected') AS "Rejeitadas",
  count(*) FILTER (WHERE user_decision IS NULL) AS "Sem decisão"
FROM audit_interactions GROUP BY field_name ORDER BY "Aceitas" DESC
""", "bar"),

    _q("Peças Com vs. Sem Validação IA", "Campanhas", C3, """
SELECT
  channel AS "Canal",
  CASE WHEN ia_verdict IS NOT NULL THEN 'Com IA' ELSE 'Sem IA' END AS "Validação",
  count(*) FILTER (WHERE human_verdict = 'approved') AS "Humano Aprovou",
  count(*) FILTER (WHERE human_verdict IN ('rejected','manually_rejected')) AS "Humano Reprovou"
FROM piece_review WHERE human_verdict != 'pending'
GROUP BY "Canal", "Validação" ORDER BY "Canal"
""", "bar"),

    _q("Validações por Modelo LLM", "Legal Service", C3, """
SELECT
  COALESCE(llm_model, 'N/A') AS "Modelo",
  channel AS "Canal",
  decision AS "Decisão",
  count(*) AS "Total"
FROM legal_validation_audits
GROUP BY llm_model, channel, decision ORDER BY "Total" DESC
""", "bar"),
]


def get_existing_cards(token: str) -> set[str]:
    r = requests.get(f"{BASE}/api/card", headers=headers(token), timeout=10)
    if r.ok:
        return {c["name"] for c in r.json()}
    return set()


def create_questions(token: str, db_ids: dict[str, int], coll_ids: dict[str, int]) -> dict[str, int]:
    existing = get_existing_cards(token)
    card_ids: dict[str, int] = {}

    for q in QUESTIONS:
        name = q["name"]
        if name in existing:
            print(f"  [q] '{name}' already exists")
            continue

        db_id = db_ids.get(q["db_name"])
        coll_id = coll_ids.get(q["collection"])
        if not db_id:
            print(f"  [q] WARNING: db '{q['db_name']}' not found, skipping '{name}'")
            continue

        payload = {
            "name": name,
            "dataset_query": {
                "type": "native",
                "native": {"query": q["sql"].strip()},
                "database": db_id,
            },
            "display": q["display"],
            "visualization_settings": {},
        }
        if coll_id:
            payload["collection_id"] = coll_id

        r = requests.post(f"{BASE}/api/card", headers=headers(token), json=payload, timeout=30)
        if r.status_code in (200, 201, 202):
            card_id = r.json()["id"]
            card_ids[name] = card_id
            print(f"  [q] '{name}' created (id={card_id})")
        else:
            print(f"  [q] WARNING: '{name}' → {r.status_code}: {r.text[:200]}")

    return card_ids


# ═════════════════════════════════════════════════════════════════════════
# Dashboards
# ═════════════════════════════════════════════════════════════════════════

DASHBOARD_DEFS = [
    {
        "name": "[Orqestra] Funil de Campanhas",
        "description": "Pipeline de campanhas: volume por status, throughput, distribuição por categoria/canal/prioridade, tempo médio por estágio.",
        "collection": C1,
        "questions": [
            "Campanhas por Status (Funil)",
            "Volume de Impacto (BRL) por Status",
            "Campanhas por Categoria",
            "Campanhas por Canal",
            "Campanhas por Prioridade",
            "Tempo Médio por Transição (horas)",
            "Campanhas Publicadas por Semana",
        ],
    },
    {
        "name": "[Orqestra] Qualidade & Compliance",
        "description": "Taxas de aprovação IA e humana, concordância IA vs. humano, decisões do agente legal, motivos de reprovação.",
        "collection": C2,
        "questions": [
            "Taxa de Aprovação IA por Canal",
            "Taxa de Aprovação Humana por Canal",
            "Concordância IA vs. Humano",
            "Decisões do Agente Legal por Canal",
            "Últimas Reprovações Legais",
        ],
    },
    {
        "name": "[Orqestra] Adoção & Eficácia da IA",
        "description": "Volume de uso do briefing enhancer, aceitação de sugestões, correlação validação IA vs. aprovação humana, modelos LLM.",
        "collection": C3,
        "questions": [
            "Interações Briefing por Dia",
            "Taxa de Aceitação por Campo",
            "Peças Com vs. Sem Validação IA",
            "Validações por Modelo LLM",
        ],
    },
]


def get_existing_dashboards(token: str) -> dict[str, int]:
    r = requests.get(f"{BASE}/api/dashboard", headers=headers(token), timeout=10)
    if r.ok:
        return {d["name"]: d["id"] for d in r.json()}
    return {}


def get_all_cards(token: str) -> dict[str, int]:
    r = requests.get(f"{BASE}/api/card", headers=headers(token), timeout=10)
    if r.ok:
        return {c["name"]: c["id"] for c in r.json()}
    return {}


def create_dashboards(token: str, coll_ids: dict[str, int]):
    existing = get_existing_dashboards(token)
    all_cards = get_all_cards(token)

    for dash_def in DASHBOARD_DEFS:
        name = dash_def["name"]
        dash_id = existing.get(name)

        if dash_id:
            print(f"  [dash] '{name}' already exists (id={dash_id}), updating layout...")
        else:
            coll_id = coll_ids.get(dash_def["collection"])
            payload = {
                "name": name,
                "description": dash_def["description"],
            }
            if coll_id:
                payload["collection_id"] = coll_id

            r = requests.post(f"{BASE}/api/dashboard", headers=headers(token), json=payload, timeout=10)
            if r.status_code not in (200, 201):
                print(f"  [dash] WARNING: '{name}' → {r.status_code}")
                continue

            dash_id = r.json()["id"]
            print(f"  [dash] '{name}' created (id={dash_id})")

        # Add cards to dashboard (2-column grid, 24 cols total)
        # Charts (bar/pie/line) → 12 cols each, 2 per row
        # Tables / full_width → 24 cols, own row
        cards_to_add = []
        row = 0
        col = 0  # 0 = left, 12 = right

        # Build a lookup for question metadata (display type, full_width)
        q_meta = {q["name"]: q for q in QUESTIONS}

        for q_name in dash_def["questions"]:
            card_id = all_cards.get(q_name)
            if not card_id:
                print(f"    [card] WARNING: question '{q_name}' not found")
                continue

            meta = q_meta.get(q_name, {})
            is_full = meta.get("full_width", False) or meta.get("display") == "table"

            if is_full:
                # Full-width: flush pending half-row first
                if col == 12:
                    row += 6
                    col = 0
                cards_to_add.append({
                    "id": -len(cards_to_add) - 1,
                    "card_id": card_id,
                    "row": row,
                    "col": 0,
                    "size_x": 24,
                    "size_y": 8,
                })
                row += 8
                col = 0
            else:
                # Half-width: pair side by side
                cards_to_add.append({
                    "id": -len(cards_to_add) - 1,
                    "card_id": card_id,
                    "row": row,
                    "col": col,
                    "size_x": 12,
                    "size_y": 6,
                })
                if col == 0:
                    col = 12  # next card goes right
                else:
                    col = 0   # row full, move down
                    row += 6

        # If last card was on the left (col=12), close the row
        if col == 12:
            row += 6

        if cards_to_add:
            r2 = requests.put(
                f"{BASE}/api/dashboard/{dash_id}",
                headers=headers(token),
                json={"dashcards": cards_to_add},
                timeout=30,
            )
            if r2.ok:
                print(f"    Added {len(cards_to_add)} cards to dashboard")
            else:
                print(f"    WARNING: failed to add cards: {r2.status_code}: {r2.text[:200]}")


# ═════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════

def main():
    print("\n╔══════════════════════════════════════════╗")
    print("║  Orqestra — Metabase Auto-Provisioning   ║")
    print("╚══════════════════════════════════════════╝\n")

    if not wait_for_metabase():
        sys.exit(1)

    # Setup or login
    print("── Setup / Login ──")
    if is_setup_done():
        print("  Setup already completed.")
        token = login()
    else:
        token = run_setup()

    # Databases
    print("\n── Databases ──")
    db_ids = create_databases(token)

    print("\n── Sync ──")
    wait_for_sync(token, db_ids, timeout=90)

    # Collections
    print("\n── Collections ──")
    coll_ids = create_collections(token)

    # Questions
    print("\n── Questions (SQL) ──")
    create_questions(token, db_ids, coll_ids)

    # Dashboards
    print("\n── Dashboards ──")
    create_dashboards(token, coll_ids)

    print("\n╔══════════════════════════════════════════╗")
    print("║  Setup complete!                         ║")
    print("║  http://localhost:3002                    ║")
    print(f"║  Login: {ADMIN_EMAIL:<31}║")
    print(f"║  Senha: {ADMIN_PASS:<31}║")
    print("╚══════════════════════════════════════════╝\n")


if __name__ == "__main__":
    main()
