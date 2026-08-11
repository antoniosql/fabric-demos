# Semantic Model

`model.tmdl` defines the minimum semantic surface for the two sessions:

- Net revenue and movement counts over `curated_fact_transactions`.
- Customer feature fields for scoring explanation.
- Current customer score and average score.

Deploy this model after the Lakehouse tables exist. In tenants where REST creation of semantic models is restricted, import the TMDL from Fabric or keep it as the contract for the session.
