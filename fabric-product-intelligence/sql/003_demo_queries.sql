SELECT
    r.quality_dimension,
    r.rule_name,
    r.severity,
    qr.score,
    qr.failed_rows,
    act.status AS action_status
FROM gov_quality_result qr
JOIN gov_quality_rule r ON qr.rule_id = r.rule_id
LEFT JOIN gov_action act ON act.result_id = qr.result_id
WHERE qr.score < 95
ORDER BY qr.failed_rows DESC;

SELECT TOP 20
    customer_id,
    score_date,
    model_version,
    score,
    score_band,
    recommended_action
FROM ml_customer_score_current
ORDER BY score DESC;

SELECT
    status,
    COUNT(*) AS open_actions
FROM gov_action
GROUP BY status;
