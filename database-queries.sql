-- ============================================================
-- QUERIES PARA AVALIACAO DO ORQESTRA
-- Execute dentro do container: docker compose exec db psql -U orqestra
-- ============================================================


-- ************************************************************
-- 1. AUTH SERVICE
-- ************************************************************
\c auth_service

-- Usuarios cadastrados e seus papeis
SELECT id, email, full_name, role, is_active, created_at
FROM users
ORDER BY created_at;

-- Historico de tentativas de login (auditoria de seguranca)
SELECT email, success, failure_reason, ip_address, created_at
FROM login_audits
ORDER BY created_at DESC
LIMIT 20;

-- Tokens de refresh ativos
SELECT id, user_id, is_revoked, expires_at, created_at
FROM refresh_tokens
ORDER BY created_at DESC
LIMIT 10;


-- ************************************************************
-- 2. CAMPAIGNS SERVICE
-- ************************************************************
\c campaigns_service

-- Campanhas e seus status atuais
SELECT id, name, status, category, priority,
       communication_channels, commercial_spaces,
       created_date
FROM campaigns
ORDER BY created_date DESC;

-- Pecas criativas com veredito da IA
SELECT cp.id, c.name AS campanha, cp.piece_type, cp.ia_verdict, 
       LEFT(cp.ia_analysis_text, 80) AS analise,
       cp.created_at
FROM creative_pieces cp
JOIN campaigns c ON c.id = cp.campaign_id
ORDER BY cp.created_at DESC;

-- Reviews: veredito da IA vs veredito humano
SELECT pr.channel, pr.ia_verdict, pr.human_verdict,
       pr.rejection_reason, pr.reviewed_by, pr.reviewed_at,
       c.name AS campanha
FROM piece_review pr
JOIN campaigns c ON c.id = pr.campaign_id
ORDER BY pr.reviewed_at DESC NULLS LAST;

-- Historico imutavel de eventos de revisao
SELECT c.name AS campanha, pre.channel, pre.event_type,
       pre.ia_verdict, pre.rejection_reason, pre.created_at
FROM piece_review_event pre
JOIN campaigns c ON c.id = pre.campaign_id
ORDER BY pre.created_at DESC;

-- Historico imutavel de transicoes de status
SELECT c.name AS campanha, cse.from_status, cse.to_status,
       cse.actor_id, cse.created_at
FROM campaign_status_event cse
JOIN campaigns c ON c.id = cse.campaign_id
ORDER BY cse.created_at;

-- Especificacoes tecnicas por canal e espaco comercial
SELECT channel, commercial_space, field_name,
       min_chars, max_chars, max_weight_kb,
       expected_width, expected_height, tolerance_pct
FROM channel_specs
WHERE active = true
ORDER BY channel, commercial_space NULLS FIRST;

-- Comentarios nas campanhas
SELECT c.name AS campanha, cm.role, cm.text, cm.timestamp
FROM comments cm
JOIN campaigns c ON c.id = cm.campaign_id
ORDER BY cm.timestamp DESC;


-- ************************************************************
-- 3. BRIEFING ENHANCER SERVICE
-- ************************************************************
\c briefing_enhancer

-- Interacoes com a IA: texto original, sugestao e decisao do usuario
SELECT ai.field_name,
       LEFT(ai.input_text, 60) AS entrada,
       LEFT(ai.output_text, 60) AS sugestao,
       ai.user_decision, ai.decision_at,
       ai.llm_model, ai.created_at
FROM audit_interactions ai
ORDER BY ai.created_at DESC
LIMIT 20;

-- Estatisticas de aceitacao/rejeicao por campo
SELECT field_name,
       COUNT(*) AS total,
       COUNT(*) FILTER (WHERE user_decision = 'approved') AS aceitas,
       COUNT(*) FILTER (WHERE user_decision = 'rejected') AS rejeitadas,
       COUNT(*) FILTER (WHERE user_decision IS NULL) AS sem_decisao
FROM audit_interactions
GROUP BY field_name
ORDER BY total DESC;

-- Campos enriqueciveis configurados
SELECT field_name, expectations, improvement_guidelines
FROM enhanceable_fields
ORDER BY field_name;


-- ************************************************************
-- 4. CONTENT VALIDATION SERVICE
-- ************************************************************
\c content_validation

-- Auditoria de validacoes de pecas
SELECT campaign_id, channel, content_hash, llm_model,
       response_json->'final_verdict'->>'decision' AS decisao,
       response_json->'final_verdict'->>'summary' AS resumo,
       response_json->'final_verdict'->>'failure_stage' AS falha_em,
       created_at
FROM piece_validation_audit
ORDER BY created_at DESC
LIMIT 20;

-- Distribuicao de decisoes por canal
SELECT channel,
       response_json->'final_verdict'->>'decision' AS decisao,
       COUNT(*) AS total
FROM piece_validation_audit
GROUP BY channel, response_json->'final_verdict'->>'decision'
ORDER BY channel, decisao;


-- ************************************************************
-- 5. LEGAL SERVICE
-- ************************************************************
\c legal_service

-- Auditoria de validacoes juridicas
SELECT channel, decision, requires_human_review,
       LEFT(summary, 80) AS resumo,
       sources, llm_model, created_at
FROM legal_validation_audits
ORDER BY created_at DESC
LIMIT 20;

-- Distribuicao de decisoes por canal
SELECT channel, decision, COUNT(*) AS total
FROM legal_validation_audits
GROUP BY channel, decision
ORDER BY channel, decision;

-- Validacoes que exigem revisao humana
SELECT channel, LEFT(content_preview, 60) AS conteudo,
       LEFT(summary, 100) AS resumo,
       sources, created_at
FROM legal_validation_audits
WHERE requires_human_review = true
ORDER BY created_at DESC
LIMIT 10;
