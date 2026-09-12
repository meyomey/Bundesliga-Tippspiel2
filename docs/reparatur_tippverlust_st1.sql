-- ============================================================
-- Diagnose + Wiederherstellung: verlorene Tipps in der Tippübersicht (Vorfall 06.09.2026)
-- Ausführen in Plesk → Datenbanken → SQL-Console (bzw. phpMyAdmin). Nur SELECTs
-- gefahrlos; INSERT erst nach Rückfrage/Backup. Der zugehörige Code-Fix
-- (sync_shared.py) verhindert weitere Verluste, stellt alte Tipps aber nicht wieder her.
-- ============================================================

-- 1) Spieltag 1: jedes Spiel mit Tipp-Anzahl. 0 Tipps bei finished = verwaistes
--    Ersatz-Spiel (genau das Symptom „—" in der Übersicht):
SELECT m.id, m.external_id, m.status, m.home_score, m.away_score,
       (SELECT COUNT(*) FROM predictions p WHERE p.match_id = m.id) AS tipps,
       h.short_name AS heim, a.short_name AS auswaerts
FROM matches m
JOIN teams h ON h.id = m.home_team_id
JOIN teams a ON a.id = m.away_team_id
WHERE m.matchday = 1
  AND m.competition_id = (SELECT id FROM competitions WHERE is_active ORDER BY id LIMIT 1)
ORDER BY m.id;

-- 2) Zwillingsspiele (gleiches Duell, gleicher Spieltag) über alle Runden:
SELECT home_team_id, away_team_id, matchday, COUNT(*) AS anzahl
FROM matches GROUP BY home_team_id, away_team_id, matchday HAVING COUNT(*) > 1;

-- 3) Falls ein DB-Backup existiert (Netcup-Backupplan / Plesk-Backups): im
--    Backup-Exemplar nach den Tipps der GELÖSCHTEN Alnzeile suchen, z. B.:
--    SELECT * FROM matches WHERE matchday = 1;          -- Backup-Seite
--    SELECT * FROM predictions WHERE match_id = <alte_id>;
--    Die gefundenen Zeilen mit neuer match_id auf die Ersatz-Zeile zurückschreiben:
-- INSERT INTO predictions (user_id, match_id, home_tip, away_tip, joker, points, created_at, updated_at)
-- SELECT user_id, <neue_match_id>, home_tip, away_tip, joker, 0, created_at, updated_at
-- FROM predictions WHERE match_id = <alte_id>;   -- (im Backup als SELECT, manuell übernehmen)

-- 4) Einzelnen Tipp manuell nachtragen (Werte einsetzen):
-- INSERT INTO predictions (user_id, match_id, home_tip, away_tip, joker, points, created_at, updated_at)
-- VALUES (<user_id>, <match_id_vom_angezeigten_Spiel>, 2, 1, false, 0, now(), now());

-- Danach zwingend: Admin → Wartung → Aufgabe „Punkte neu berechnen"
-- (sonst bleiben points=0 und Rangliste/Live-Punkte stimmen nicht).
