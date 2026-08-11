export type GovernanceRule = {
  result_id: string;
  rule_name: string;
  quality_dimension: string;
  severity: string;
  score: number;
  failed_rows: number;
  status: string;
};

export type GovernanceAction = {
  action_id: string;
  title: string;
  owner_upn: string;
  status: string;
  business_impact: string;
  remediation: string;
};

export type CustomerScore = {
  customer_id: string;
  score_date: string;
  model_version: string;
  score: number;
  score_band: string;
  recommended_action: string;
};

export const fallbackData = {
  governance: {
    summary: {
      global_score: 91.7,
      failed_rules: 4,
      open_actions: 3
    },
    rules: [
      {
        result_id: "r1",
        rule_name: "Customer master referenced",
        quality_dimension: "Integrity",
        severity: "Critical",
        score: 58.68,
        failed_rows: 2055,
        status: "Failed"
      },
      {
        result_id: "r2",
        rule_name: "Product master referenced",
        quality_dimension: "Integrity",
        severity: "Critical",
        score: 95.84,
        failed_rows: 207,
        status: "Passed"
      },
      {
        result_id: "r3",
        rule_name: "Movement date parsed",
        quality_dimension: "Validity",
        severity: "High",
        score: 99.62,
        failed_rows: 19,
        status: "Passed"
      }
    ] as GovernanceRule[],
    actions: [
      {
        action_id: "a1",
        title: "Remediate: Customer master referenced",
        owner_upn: "data.steward@contoso.com",
        status: "Open",
        business_impact: "Impacts trusted BI, scoring and data agent answers.",
        remediation: "Normalize customer identifiers and reconcile unknown customer records with CRM."
      }
    ] as GovernanceAction[]
  },
  intelligence: {
    metrics: {
      model_name: "customer_engagement_baseline",
      model_version: "local-001",
      roc_auc: 0.71,
      pr_auc: 0.62
    },
    top_customers: [
      {
        customer_id: "C0030",
        score_date: "2025-11-01",
        model_version: "local-001",
        score: 0.91,
        score_band: "High",
        recommended_action: "Prioritize premium cross-sell."
      },
      {
        customer_id: "C0014",
        score_date: "2025-11-01",
        model_version: "local-001",
        score: 0.78,
        score_band: "Risk",
        recommended_action: "Trigger retention review for high-potential customer."
      }
    ] as CustomerScore[]
  }
};
