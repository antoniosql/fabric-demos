CREATE TABLE ml_customer_score_current (
    customer_id        NVARCHAR(100) NOT NULL PRIMARY KEY,
    score_date         DATE          NOT NULL,
    model_name         NVARCHAR(200) NOT NULL,
    model_version      NVARCHAR(80)  NOT NULL,
    score              DECIMAL(8,6)  NOT NULL,
    score_band         NVARCHAR(40)  NOT NULL,
    recommended_action NVARCHAR(200) NULL,
    explanation_json   NVARCHAR(MAX) NULL
);

CREATE TABLE ml_customer_score_history (
    score_event_id     UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
    customer_id        NVARCHAR(100)    NOT NULL,
    score_date         DATE             NOT NULL,
    model_name         NVARCHAR(200)    NOT NULL,
    model_version      NVARCHAR(80)     NOT NULL,
    score              DECIMAL(8,6)     NOT NULL,
    score_band         NVARCHAR(40)     NOT NULL,
    feature_snapshot   NVARCHAR(MAX)    NULL,
    created_at         DATETIME2        NOT NULL DEFAULT SYSUTCDATETIME()
);
