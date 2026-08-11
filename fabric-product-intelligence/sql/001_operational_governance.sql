CREATE TABLE gov_asset (
    asset_id              UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
    workspace_id          NVARCHAR(100)    NULL,
    item_id               NVARCHAR(100)    NULL,
    asset_name            NVARCHAR(300)    NOT NULL,
    asset_type            NVARCHAR(80)     NOT NULL,
    domain_name           NVARCHAR(120)    NULL,
    owner_upn             NVARCHAR(320)    NULL,
    criticality           NVARCHAR(30)     NULL,
    endorsement_status    NVARCHAR(50)     NULL,
    sensitivity_label     NVARCHAR(120)    NULL,
    business_description  NVARCHAR(MAX)    NULL,
    source_system         NVARCHAR(120)    NULL,
    last_seen_at          DATETIME2        NOT NULL,
    is_active             BIT              NOT NULL DEFAULT 1
);

CREATE TABLE gov_quality_rule (
    rule_id             UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
    asset_id            UNIQUEIDENTIFIER NOT NULL,
    rule_name           NVARCHAR(200)    NOT NULL,
    column_name         NVARCHAR(200)    NULL,
    quality_dimension   NVARCHAR(60)     NOT NULL,
    rule_expression     NVARCHAR(MAX)    NULL,
    severity            NVARCHAR(30)     NOT NULL,
    threshold_pct       DECIMAL(5,2)     NULL,
    owner_upn           NVARCHAR(320)    NULL,
    remediation_hint    NVARCHAR(MAX)    NULL,
    is_active           BIT              NOT NULL DEFAULT 1,
    created_at          DATETIME2        NOT NULL DEFAULT SYSUTCDATETIME(),
    FOREIGN KEY (asset_id) REFERENCES gov_asset(asset_id)
);

CREATE TABLE gov_quality_run (
    run_id           UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
    asset_id         UNIQUEIDENTIFIER NOT NULL,
    started_at       DATETIME2        NOT NULL,
    finished_at      DATETIME2        NULL,
    status           NVARCHAR(40)     NOT NULL,
    total_rows       BIGINT           NULL,
    passed_rows      BIGINT           NULL,
    failed_rows      BIGINT           NULL,
    global_score     DECIMAL(5,2)     NULL,
    execution_source NVARCHAR(120)    NULL,
    FOREIGN KEY (asset_id) REFERENCES gov_asset(asset_id)
);

CREATE TABLE gov_quality_result (
    result_id       UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
    run_id          UNIQUEIDENTIFIER NOT NULL,
    rule_id         UNIQUEIDENTIFIER NOT NULL,
    evaluated_rows  BIGINT           NULL,
    passed_rows     BIGINT           NULL,
    failed_rows     BIGINT           NULL,
    ignored_rows    BIGINT           NULL,
    score           DECIMAL(5,2)     NULL,
    sample_query    NVARCHAR(MAX)    NULL,
    sample_json     NVARCHAR(MAX)    NULL,
    status          NVARCHAR(40)     NOT NULL,
    FOREIGN KEY (run_id) REFERENCES gov_quality_run(run_id),
    FOREIGN KEY (rule_id) REFERENCES gov_quality_rule(rule_id)
);

CREATE TABLE gov_lineage_edge (
    edge_id          UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
    source_asset_id  UNIQUEIDENTIFIER NOT NULL,
    target_asset_id  UNIQUEIDENTIFIER NOT NULL,
    relation_type    NVARCHAR(80)     NOT NULL,
    observed_at      DATETIME2        NOT NULL,
    confidence       DECIMAL(5,2)     NULL,
    source_signal    NVARCHAR(120)    NULL,
    FOREIGN KEY (source_asset_id) REFERENCES gov_asset(asset_id),
    FOREIGN KEY (target_asset_id) REFERENCES gov_asset(asset_id)
);

CREATE TABLE gov_policy_signal (
    signal_id       UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
    asset_id        UNIQUEIDENTIFIER NOT NULL,
    signal_type     NVARCHAR(80)     NOT NULL,
    signal_value    NVARCHAR(300)    NULL,
    severity        NVARCHAR(30)     NULL,
    status          NVARCHAR(40)     NULL,
    observed_at     DATETIME2        NOT NULL,
    source_system   NVARCHAR(120)    NULL,
    FOREIGN KEY (asset_id) REFERENCES gov_asset(asset_id)
);

CREATE TABLE gov_action (
    action_id        UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
    asset_id         UNIQUEIDENTIFIER NOT NULL,
    result_id        UNIQUEIDENTIFIER NULL,
    title            NVARCHAR(300)    NOT NULL,
    description      NVARCHAR(MAX)    NULL,
    owner_upn        NVARCHAR(320)    NULL,
    due_date         DATE             NULL,
    status           NVARCHAR(40)     NOT NULL,
    business_impact  NVARCHAR(MAX)    NULL,
    remediation      NVARCHAR(MAX)    NULL,
    created_at       DATETIME2        NOT NULL DEFAULT SYSUTCDATETIME(),
    closed_at        DATETIME2        NULL,
    FOREIGN KEY (asset_id) REFERENCES gov_asset(asset_id),
    FOREIGN KEY (result_id) REFERENCES gov_quality_result(result_id)
);
