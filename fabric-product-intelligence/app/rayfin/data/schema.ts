import { decimal, entity, int, text, uuid } from "@microsoft/rayfin-core/decorators";

@entity("GovernanceRule")
export class GovernanceRule {
  @uuid()
  resultId!: string;

  @text()
  ruleName!: string;

  @text()
  qualityDimension!: string;

  @text()
  severity!: string;

  @decimal({ precision: 5, scale: 2 })
  score!: number;

  @int()
  failedRows!: number;

  @text()
  status!: string;
}

@entity("GovernanceAction")
export class GovernanceAction {
  @uuid()
  actionId!: string;

  @text()
  title!: string;

  @text()
  ownerUpn!: string;

  @text()
  status!: string;

  @text()
  businessImpact!: string;
}

@entity("CustomerScore")
export class CustomerScore {
  @uuid()
  customerId!: string;

  @text()
  scoreDate!: string;

  @text()
  modelVersion!: string;

  @decimal({ precision: 5, scale: 2 })
  score!: number;

  @text()
  scoreBand!: string;

  @text()
  recommendedAction!: string;
}
